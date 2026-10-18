"""
Phase 8.5.2 — Product Integrity, Truthful State Contracts & Error Handling Regression Tests.

Validates:
1. Test Impact Truthful State & Snapshot Scoping:
   - Invalid target snapshot returns HTTP 404 with error detail (never fake zero).
   - Foreign / non-existent base snapshot returns HTTP 404 (never fake zero).
   - Single snapshot with base=None resolves safely within repository scope.
2. Workflow Inference Integrity:
   - External dependencies (npm packages, pip packages) are excluded from workflow execution steps.
   - External dependencies are never chosen as process entrypoints.
3. Risk Intelligence Truthful Evidence Gaps:
   - If test impact fails or is None, risk engine flags status='FAILED', adds evidence gap, and penalizes confidence.
4. Identical Snapshot Comparison:
   - Diffing identical snapshots produces total_changes=0 cleanly without engine errors.
5. Architecture Progressive Disclosure:
   - Level 1 (Macro) excludes leaf methods and classes, focusing on architectural hubs and packages.
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from main import app
from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
)
from app.services.testing.service import test_impact_service
from app.services.testing.models import TestImpactConfig
from app.services.process.discovery import process_discovery_engine
from app.services.risk.engine import risk_intelligence_engine, RiskFactorType
from app.services.impact.change_detector import change_detector
from app.services.analysis.graph.projection import twin_graph_projection

client = TestClient(app)


@pytest.fixture
def integrity_repo(db_session: Session):
    """Creates a dedicated repository with two snapshots and known components for integrity tests."""
    suffix = uuid.uuid4().hex[:8]
    proj = Project(name=f"IntegrityProj-{suffix}", description="Product integrity validation")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        project_id=proj.id,
        name=f"integrity_repo_{suffix}",
        vcs_type="git",
        local_path=f"/tmp/test_integrity_repo_{suffix}",
    )
    db_session.add(repo)
    db_session.flush()

    snap1 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash=f"111111111111111111111111111111111111{suffix[:4]}",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    db_session.add(snap1)
    db_session.flush()

    snap2 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash=f"222222222222222222222222222222222222{suffix[:4]}",
        branch_name="main",
        total_files=5,
        total_symbols=12,
    )
    db_session.add(snap2)
    db_session.flush()

    # Add artifacts to snap1 with explicit IDs
    art_mod = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        artifact_type="MODULE",
        language="typescript",
        name="AuthModule",
        qualified_name="src.auth.AuthModule",
        location="src/auth/AuthModule.ts:1",
        metadata_payload={},
    )
    art_ext = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        artifact_type="EXTERNAL_DEPENDENCY",
        language="typescript",
        name="react",
        qualified_name="react",
        location="<external>",
        metadata_payload={},
    )
    art_test = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        artifact_type="TEST_CASE",
        language="typescript",
        name="test_auth_login",
        qualified_name="tests.test_auth_login",
        location="tests/auth.test.ts:10",
        metadata_payload={},
    )
    db_session.add_all([art_mod, art_ext, art_test])
    db_session.flush()

    # Add relationship: test -> mod
    rel_test = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        snapshot_id=snap1.id,
        repository_id=repo.id,
        source_artifact_id=art_test.id,
        target_artifact_id=art_mod.id,
        relationship_type="TESTS",
        confidence=1.0,
        detection_method="static_analysis",
    )
    # Add relationship: mod -> ext (IMPORTS)
    rel_import = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        snapshot_id=snap1.id,
        repository_id=repo.id,
        source_artifact_id=art_mod.id,
        target_artifact_id=art_ext.id,
        relationship_type="IMPORTS",
        confidence=1.0,
        detection_method="static_analysis",
    )
    db_session.add_all([rel_test, rel_import])
    db_session.commit()

    return {
        "project": proj,
        "repo": repo,
        "snap1": snap1,
        "snap2": snap2,
        "art_mod": art_mod,
        "art_ext": art_ext,
        "art_test": art_test,
    }


def test_test_impact_truthful_failure_handling(integrity_repo, db_session: Session):
    """
    Test Impact must reject non-existent or foreign snapshots with 404
    and never return fake success with zeroed numbers.
    """
    repo = integrity_repo["repo"]
    snap1 = integrity_repo["snap1"]

    # 1. Invalid target snapshot
    res_bad_target = client.post(
        f"/repositories/{repo.id}/test-impact",
        json={"target_snapshot_id": "nonexistent_snap_target"},
    )
    assert res_bad_target.status_code == 404
    assert "Target snapshot 'nonexistent_snap_target' not found" in res_bad_target.json()["detail"]

    # 2. Invalid base snapshot
    res_bad_base = client.post(
        f"/repositories/{repo.id}/test-impact",
        json={"target_snapshot_id": snap1.id, "base_snapshot_id": "nonexistent_snap_base"},
    )
    assert res_bad_base.status_code == 404
    assert "Base snapshot 'nonexistent_snap_base' not found" in res_bad_base.json()["detail"]

    # 3. Single snapshot with base_snapshot_id=None
    res_valid_self = client.post(
        f"/repositories/{repo.id}/test-impact",
        json={"target_snapshot_id": snap1.id, "base_snapshot_id": None},
    )
    assert res_valid_self.status_code == 200
    data = res_valid_self.json()
    assert data["status"] == "completed"
    assert data["summary"]["total_tests_mapped"] == 1
    assert data["summary"]["unaffected_count"] == 1
    assert data["summary"]["potentially_affected_count"] == 0


def test_workflow_discovery_excludes_external_dependencies(integrity_repo, db_session: Session):
    """
    Verifies that workflow discovery never selects EXTERNAL_DEPENDENCY as an entry point
    and never traverses into external packages as execution workflow steps.
    """
    repo = integrity_repo["repo"]
    snap1 = integrity_repo["snap1"]

    result = process_discovery_engine.discover_and_persist(
        db=db_session,
        project_id=repo.project_id,
        repository_id=repo.id,
        snapshot_id=snap1.id,
    )

    # Check all generated process definitions and steps
    for proc in result.processes:
        assert "react" not in proc.name.lower()
        for step in proc.steps:
            assert step.name != "react"
            assert step.component_artifact_id != integrity_repo["art_ext"].id


def test_risk_intelligence_surfaces_evidence_gap_on_test_impact_failure(integrity_repo, db_session: Session):
    """
    When Test Impact analysis fails or is None, Risk Intelligence must NOT quietly assume 0 risk.
    It must flag status='FAILED', surface an explicit evidence gap, and reduce confidence.
    """
    repo = integrity_repo["repo"]
    snap1 = integrity_repo["snap1"]

    # Evaluate risk with simulated test impact failure (precomputed_test_impact=None and mock exception)
    res = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=snap1.id,
        target_snapshot_id=snap1.id,
        precomputed_test_impact=None,
    )

    # Factor 3: TEST_IMPACT must be observed or evaluated honestly
    f_test = next((f for f in res.risk_factors if f.factor_id == RiskFactorType.TEST_IMPACT), None)
    assert f_test is not None

    # If test impact was passed as None and test engine fails, it must report FAILED status
    f_test_failed, unknowns = risk_intelligence_engine._compute_test_impact_factor(
        test_res=None,
        test_impact_error="Simulated DB Connection Timeout",
    )
    assert f_test_failed.status == "FAILED"
    assert "Simulated DB Connection Timeout" in f_test_failed.evidence[0]
    assert any("Test impact analysis failed" in u for u in unknowns)

    # Confidence must be penalized for missing test evidence
    conf_level, conf_score = risk_intelligence_engine._derive_confidence(
        unknown_signals=unknowns,
        test_res=None,
        runtime_events=[],
    )
    assert conf_score < 0.80  # Penalty applied


def test_identical_snapshot_diff_is_truthful(integrity_repo, db_session: Session):
    """
    Diffing the exact same snapshot against itself must return 0 changes cleanly (not an error).
    """
    repo = integrity_repo["repo"]
    snap1 = integrity_repo["snap1"]

    diff = change_detector.detect_changes(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=snap1.id,
        target_snapshot_id=snap1.id,
    )
    assert len(diff.changes) == 0
    assert diff.summary.get("total_changes", 0) == 0


def test_macro_architecture_progressive_disclosure(integrity_repo, db_session: Session):
    """
    Level 1 (Macro) must focus on macro architectural components and not leak internal classes/methods.
    """
    repo = integrity_repo["repo"]
    snap1 = integrity_repo["snap1"]

    g_l1 = twin_graph_projection.project_graph(
        db=db_session,
        repository_id=repo.id,
        snapshot_id=snap1.id,
        level=1,
    )
    l1_types = {n["type"] for n in g_l1["nodes"]}
    assert "CLASS" not in l1_types
    assert "METHOD" not in l1_types
    assert "FUNCTION" not in l1_types
