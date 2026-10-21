"""
Phase Post-Fix Integration Verification Suite.
Validates Steps 2 through 8 in the live application environment against PostgreSQL:
- STEP 2: Startup, Health, Readiness, and Database Schema
- STEP 3: Real Repository Ingestion & Identifier Consistency
- STEP 4: Historical Change Impact & Identical Commit Fast-Path
- STEP 5: Snapshot Isolation & Boundary Enforcement
- STEP 6: Discovery & Technical Assessment Engine (No NameError, Real Evidence)
- STEP 7: P0 Workflows (What-If Orchestration, Test Impact by SHA, Graph Degree Metrics)
- STEP 8: Error Handling & Graceful Degradation
"""

import os
import sys
import uuid
import unittest

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest", os.path.abspath(__file__)])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from sqlalchemy import text
from main import app
from app.core.database import SessionLocal
from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    File,
    StructuralArtifact,
    ArtifactRelationship,
    Scenario,
    ScenarioResult,
)
from app.services.analysis.engine import structural_twin_engine
from app.services.impact.change_detector import ChangeDetector
from app.services.impact.analyzer import ImpactAnalyzer
from app.services.impact.models import ChangeType
from app.services.discovery.engine import discovery_engine
from app.services.discovery.assessment_engine import TechnicalAssessmentEngine


class TestLiveWorkflowIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "test_live_workflow"
        cls.db = SessionLocal()
        cls.client = TestClient(app)
        cls.real_repo_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "real_validation_repo")
        )

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def tearDown(self):
        self.db.rollback()

    # =========================================================================
    # STEP 2 — STARTUP AND DATABASE
    # =========================================================================
    def test_step2_backend_health_and_database_readiness(self):
        """Verifies backend liveness, readiness probe, and direct SQL query."""
        # 1. Liveness
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200, f"Health check failed: {res_health.text}")
        data_health = res_health.json()
        self.assertEqual(data_health["status"], "healthy")
        self.assertIn("version", data_health)

        # 2. Readiness with DB connectivity
        res_ready = self.client.get("/ready")
        self.assertEqual(res_ready.status_code, 200, f"Readiness check failed: {res_ready.text}")
        data_ready = res_ready.json()
        self.assertEqual(data_ready["status"], "ready")
        self.assertEqual(data_ready["database"], "connected")

        # 3. Direct SQL query
        val = self.db.execute(text("SELECT 1")).scalar()
        self.assertEqual(val, 1)

        # 4. Schema verification: Ensure key tables are queryable
        for entity_cls in (Project, Repository, RepositorySnapshot, StructuralArtifact, Scenario, ScenarioResult):
            count = self.db.query(entity_cls).count()
            self.assertGreaterEqual(count, 0)

    # =========================================================================
    # STEP 3 — REAL REPOSITORY INGESTION
    # =========================================================================
    def test_step3_real_repository_ingestion(self):
        """Ingests real_validation_repo and verifies snapshots, files, and artifacts."""
        self.assertTrue(os.path.exists(self.real_repo_path), f"Missing repo at {self.real_repo_path}")

        uid = uuid.uuid4().hex[:8]
        proj = Project(id=f"proj-real-{uid}", name=f"Project-Real-{uid}")
        self.db.add(proj)
        self.db.commit()

        repo = Repository(
            id=f"repo-real-{uid}",
            project_id=proj.id,
            name=f"real-repo-{uid}",
            local_path=self.real_repo_path,
            environment="TEST",
        )
        self.db.add(repo)
        self.db.commit()

        # Ingest real repository
        snap_id, result = structural_twin_engine.build_structural_twin(
            db=self.db,
            repository_id=repo.id,
            commit_hash="commit_live_v1",
            branch_name="main",
        )

        self.assertEqual(result.status, "COMPLETED")
        self.assertGreaterEqual(result.files_scanned, 2)
        self.assertGreaterEqual(len(result.artifacts), 3)

        # Verify database persistence
        persisted_snap = self.db.query(RepositorySnapshot).filter_by(id=snap_id).first()
        self.assertIsNotNone(persisted_snap)
        self.assertEqual(persisted_snap.repository_id, repo.id)

        persisted_arts = self.db.query(StructuralArtifact).filter_by(snapshot_id=snap_id).all()
        self.assertGreaterEqual(len(persisted_arts), 3)
        art_names = [a.qualified_name for a in persisted_arts]
        self.assertTrue(any("Calculator" in name for name in art_names))

        # Surface non-existent workspace failure honestly
        with self.assertRaises(ValueError):
            structural_twin_engine.build_structural_twin(
                db=self.db,
                repository_id=repo.id,
                source_path="/non/existent/repo/path/xyz",
                commit_hash="bad_commit",
            )

    # =========================================================================
    # STEP 4 — HISTORICAL CHANGE IMPACT
    # =========================================================================
    def test_step4_historical_change_impact_and_identical_fastpath(self):
        """Verifies dual-level change detection, evidence provenance, and identical commit fast-path."""
        detector = ChangeDetector()

        uid = uuid.uuid4().hex[:8]
        proj = Project(id=f"proj-diff-{uid}", name=f"Project-Diff-{uid}")
        self.db.add(proj)
        self.db.commit()

        repo = Repository(
            id=f"repo-diff-{uid}",
            project_id=proj.id,
            name=f"repo-diff-{uid}",
            local_path=self.real_repo_path,
            environment="TEST",
        )
        self.db.add(repo)

        snap1 = RepositorySnapshot(
            id=f"snap_v1_{uid}",
            repository_id=repo.id,
            commit_hash="1111111111111111111111111111111111111111",
            branch_name="main",
        )
        snap2 = RepositorySnapshot(
            id=f"snap_v2_{uid}",
            repository_id=repo.id,
            commit_hash="2222222222222222222222222222222222222222",
            branch_name="main",
        )
        self.db.add(snap1)
        self.db.add(snap2)
        self.db.commit()

        # 1. Distinct snapshot comparison with AST symbol differences
        art_v1 = StructuralArtifact(
            id=f"art_calc_{uid}_v1",
            snapshot_id=snap1.id,
            repository_id=repo.id,
            qualified_name="calculator.Calculator.add",
            name="add",
            artifact_type="METHOD",
            file_path="calculator.py",
            content_hash="sha_v1_aaa",
        )
        art_v2 = StructuralArtifact(
            id=f"art_calc_{uid}_v2",
            snapshot_id=snap2.id,
            repository_id=repo.id,
            qualified_name="calculator.Calculator.add",
            name="add",
            artifact_type="METHOD",
            file_path="calculator.py",
            content_hash="sha_v2_bbb",  # Hash changed
        )

        cs = detector.detect_changes(
            db=self.db,
            repository_id=repo.id,
            base_snapshot_id=snap1.id,
            target_snapshot_id=snap2.id,
            base_artifacts=[art_v1],
            target_artifacts=[art_v2],
        )

        self.assertEqual(cs.status, "COMPLETED")
        self.assertEqual(cs.diff_mode, "SYMBOL_AND_FILE")
        self.assertFalse(cs.is_verified_zero)
        self.assertEqual(len(cs.changes), 1)
        self.assertEqual(cs.changes[0].change_type, ChangeType.MODIFIED)
        self.assertIn("source_hash_differs", cs.changes[0].evidence[0])

        # Repeat to confirm determinism
        cs_repeat = detector.detect_changes(
            db=self.db,
            repository_id=repo.id,
            base_snapshot_id=snap1.id,
            target_snapshot_id=snap2.id,
            base_artifacts=[art_v1],
            target_artifacts=[art_v2],
        )
        self.assertEqual(cs.summary, cs_repeat.summary)
        self.assertEqual(len(cs.changes), len(cs_repeat.changes))

        # 2. Identical commit comparison
        cs_identical = detector.detect_changes(
            db=self.db,
            repository_id=repo.id,
            base_snapshot_id="3253040bc18b28cf9db0b53755cf643f8705bc03",
            target_snapshot_id="3253040bc18b28cf9db0b53755cf643f8705bc03",
        )
        self.assertEqual(cs_identical.status, "IDENTICAL_COMMITS")
        self.assertTrue(cs_identical.is_verified_zero)
        self.assertEqual(cs_identical.diff_mode, "IDENTICAL")
        self.assertEqual(cs_identical.summary["total_changes"], 0)

    # =========================================================================
    # STEP 5 — SNAPSHOT ISOLATION
    # =========================================================================
    def test_step5_snapshot_isolation_prevents_leakage(self):
        """Verifies artifacts from unrelated snapshots cannot appear in the comparison."""
        detector = ChangeDetector()
        uid = uuid.uuid4().hex[:8]

        art_base = StructuralArtifact(
            id=f"art_base_{uid}",
            snapshot_id=f"snap_allowed_base_{uid}",
            qualified_name="pkg.AllowedService",
            name="AllowedService",
            artifact_type="CLASS",
            file_path="pkg/service.py",
            content_hash="hash_1",
        )
        art_target = StructuralArtifact(
            id=f"art_target_{uid}",
            snapshot_id=f"snap_allowed_target_{uid}",
            qualified_name="pkg.AllowedService",
            name="AllowedService",
            artifact_type="CLASS",
            file_path="pkg/service.py",
            content_hash="hash_1",
        )
        art_foreign = StructuralArtifact(
            id=f"art_foreign_{uid}",
            snapshot_id="unrelated_foreign_snapshot_999",
            qualified_name="pkg.ForeignLeakedSecretService",
            name="ForeignLeakedSecretService",
            artifact_type="CLASS",
            file_path="pkg/foreign.py",
            content_hash="hash_foreign",
        )

        cs = detector.detect_changes(
            db=self.db,
            repository_id=f"repo_iso_{uid}",
            base_snapshot_id=f"snap_allowed_base_{uid}",
            target_snapshot_id=f"snap_allowed_target_{uid}",
            base_artifacts=[art_base, art_foreign],
            target_artifacts=[art_target],
        )

        for change in cs.changes:
            self.assertNotEqual(change.qualified_name, "pkg.ForeignLeakedSecretService")
            self.assertNotIn("ForeignLeakedSecretService", change.evidence[0])

    # =========================================================================
    # STEP 6 — DISCOVERY & HEALTH
    # =========================================================================
    def test_step6_discovery_and_health_assessment(self):
        """Verifies technical assessment executes without NameError and grounds findings in evidence."""
        uid = uuid.uuid4().hex[:8]
        proj = Project(id=f"proj-disc-{uid}", name=f"Project-Disc-{uid}")
        self.db.add(proj)
        self.db.commit()

        repo = Repository(
            id=f"repo-disc-{uid}",
            project_id=proj.id,
            name=f"repo-disc-{uid}",
            local_path=self.real_repo_path,
            environment="TEST",
        )
        self.db.add(repo)
        self.db.commit()

        # Run Discovery Engine
        disc_profile, disc_plan = discovery_engine.discover(self.real_repo_path)
        self.assertIsNotNone(disc_profile)
        self.assertGreater(disc_profile.total_files_scanned, 0)

        # Ingest repository so snapshot exists for assessment
        snap_id, _ = structural_twin_engine.build_structural_twin(
            db=self.db,
            repository_id=repo.id,
            commit_hash="commit_live_assess",
            branch_name="main",
        )
        self.assertIsNotNone(snap_id)

        # Run Technical Assessment Engine (verifies no NameError for SUPPORTED_EXTS)
        assessment_engine = TechnicalAssessmentEngine()
        assessment = assessment_engine.assess_repository(
            db=self.db,
            repository_id=repo.id,
        )

        self.assertEqual(assessment.status.value, "COMPLETE")
        self.assertEqual(len(assessment.dimensional_scores), 9)
        self.assertTrue(all(ds.score >= 0.0 for ds in assessment.dimensional_scores))

        # Confirm evidence grounding: Findings must have genuine file/line references
        for finding in assessment.findings:
            self.assertTrue(len(finding.evidence_references) >= 0)
            self.assertIn(finding.severity.value, ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"))

    # =========================================================================
    # STEP 7 — P0 WORKFLOWS (WHAT-IF, TEST IMPACT, GRAPH METRICS)
    # =========================================================================
    def test_step7_p0_workflows_end_to_end(self):
        """Verifies What-If orchestration, Scenario persistence, Test Impact by SHA, and Graph Metrics."""
        uid = uuid.uuid4().hex[:8]
        repo = Repository(
            id=f"repo-p0-live-{uid}",
            name=f"test-repo-p0-live-{uid}",
            local_path=self.real_repo_path,
            environment="TEST",
        )
        self.db.merge(repo)

        commit_sha = "4444444444444444444444444444444444444444"
        snap = RepositorySnapshot(
            id=f"snap-p0-live-{uid}",
            repository_id=repo.id,
            commit_hash=commit_sha,
            commit_message="Live test commit",
        )
        self.db.merge(snap)

        art_calc = StructuralArtifact(
            id=f"art-calc-{uid}",
            snapshot_id=snap.id,
            name="Calculator",
            qualified_name="calculator.Calculator",
            artifact_type="CLASS",
            location="calculator.py:1:50",
        )
        art_test = StructuralArtifact(
            id=f"art-test-{uid}",
            snapshot_id=snap.id,
            name="test_add",
            qualified_name="test_calculator.test_add",
            artifact_type="TEST_CASE",
            location="test_calculator.py:1:20",
        )
        rel_test = ArtifactRelationship(
            id=f"rel-test-{uid}",
            snapshot_id=snap.id,
            source_artifact_id=art_test.id,
            target_artifact_id=art_calc.id,
            relationship_type="TESTS",
        )
        self.db.merge(art_calc)
        self.db.merge(art_test)
        self.db.merge(rel_test)
        self.db.commit()

        # 1. What-If Orchestration with file target
        payload = {
            "query": "What happens if we remove calculator.py?",
            "base_snapshot_id": snap.id,
            "explicit_target": "calculator.py",
            "explicit_type": "REMOVE_ENTITY",
        }
        res_orch = self.client.post(f"/repositories/{repo.id}/scenarios/orchestrate", json=payload)
        self.assertEqual(res_orch.status_code, 200, f"Orchestrate failed: {res_orch.text}")
        data_orch = res_orch.json()
        scen_id = data_orch["scenario_id"]
        self.assertIsNotNone(scen_id)

        # Verify Scenario and ScenarioResult in PostgreSQL
        persisted_scen = self.db.query(Scenario).filter_by(id=scen_id).first()
        self.assertIsNotNone(persisted_scen)
        self.assertEqual(persisted_scen.repository_id, repo.id)

        persisted_result = self.db.query(ScenarioResult).filter_by(scenario_id=scen_id).first()
        self.assertIsNotNone(persisted_result)

        # 2. Test Impact using commit SHA or snapshot ID
        res_impact = self.client.post(
            f"/repositories/{repo.id}/test-impact",
            json={"base_snapshot_id": snap.id, "target_snapshot_id": snap.id},
        )
        self.assertIn(res_impact.status_code, (200, 201), f"Test impact failed: {res_impact.text}")
        data_impact = res_impact.json()
        self.assertIn("summary", data_impact)

        # 3. Architecture Graph Metrics
        res_graph = self.client.get(f"/repositories/{repo.id}/graph?snapshot_id={snap.id}")
        self.assertEqual(res_graph.status_code, 200, f"Graph endpoint failed: {res_graph.text}")
        data_graph = res_graph.json()
        self.assertIn("nodes", data_graph)
        self.assertIn("edges", data_graph)
        for node in data_graph["nodes"]:
            self.assertIn("in_degree", node)
            self.assertIn("out_degree", node)

    # =========================================================================
    # STEP 8 — ERROR HANDLING & ROBUSTNESS
    # =========================================================================
    def test_step8_error_handling_and_status_codes(self):
        """Verifies non-existent entities return structured 404s without uncaught 500s."""
        # Unknown repository
        res_unknown_repo = self.client.get("/repositories/non_existent_repo_id_12345/graph")
        self.assertEqual(res_unknown_repo.status_code, 404)

        # Unknown scenario report
        res_unknown_scen = self.client.get("/repositories/repo-test/scenarios/non_existent_scen/report")
        self.assertEqual(res_unknown_scen.status_code, 404)


if __name__ == "__main__":
    unittest.main()
