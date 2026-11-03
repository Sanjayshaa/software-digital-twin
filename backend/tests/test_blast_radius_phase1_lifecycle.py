"""
Tests for Phase 1 P0: Snapshot Lifecycle & Blast-Radius Reliability.
Verifies:
- Snapshot lifecycle states and backward compatibility
- Git ancestry and same-commit contracts
- Blast-radius precondition enforcement (409 Conflict, proper error codes)
- Analysis provenance and evidence completeness
- Zero-impact vs fake-success elimination
"""

import os
import sys

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

import unittest
import uuid
from datetime import datetime, timezone

# Setup path and imports
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.entities import (
    Base,
    Repository,
    RepositorySnapshot,
    SnapshotStatus,
    StructuralArtifact,
    ArtifactRelationship,
    User,
    Project,
)
from app.services.acquisition.git_provider import check_git_ancestry
from app.services.impact.models import (
    ImpactResult,
    ImpactFinding,
    ImpactSummary,
    ImpactPreconditionError,
    ImpactConfig,
)
from app.services.impact.service import ChangeImpactService
from app.services.impact.analyzer import ChangeImpactAnalyzer


class TestSnapshotLifecycleAndPreconditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.session = self.Session()
        self.project_id = f"proj-{uuid.uuid4().hex[:8]}"
        self.repo_id = f"repo-{uuid.uuid4().hex[:8]}"

        proj = Project(id=self.project_id, name=f"Test Project {uuid.uuid4().hex[:8]}")
        repo = Repository(
            id=self.repo_id,
            project_id=self.project_id,
            name=f"test-repo-{uuid.uuid4().hex[:8]}",
            default_branch="main",
            local_path="/tmp/test-repo-path",
        )
        self.session.add(proj)
        self.session.add(repo)
        self.session.commit()

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    # -------------------------------------------------------------------------
    # 1. Snapshot Lifecycle Tests
    # -------------------------------------------------------------------------
    def test_snapshot_lifecycle_status_property(self):
        """Snapshots must properly read and write lifecycle status to snapshot_metadata."""
        snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="abc1234",
            branch_name="main",
            total_symbols=10,
        )
        self.session.add(snap)
        self.session.commit()

        # Explicit transitions
        for st in [
            SnapshotStatus.QUEUED,
            SnapshotStatus.SCANNING,
            SnapshotStatus.PARSING,
            SnapshotStatus.PERSISTING,
            SnapshotStatus.READY,
        ]:
            snap.status = st
            self.assertEqual(snap.status, st)
            self.assertEqual(snap.snapshot_metadata["status"], st)

        snap.status = SnapshotStatus.FAILED
        snap.error_message = "Parser crashed on AST node"
        snap.failed_at = datetime.now(timezone.utc).isoformat()
        self.assertEqual(snap.status, SnapshotStatus.FAILED)
        self.assertEqual(snap.error_message, "Parser crashed on AST node")
        self.assertIsNotNone(snap.failed_at)

    def test_legacy_snapshot_with_symbols_but_no_relationships(self):
        """Legacy snapshot with symbols but missing relationship graph must NOT be marked READY."""
        snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="leg_sym_no_rel",
            branch_name="main",
            total_symbols=15,
            total_files=2,
            snapshot_metadata={},  # No explicit status
        )
        self.session.add(snap)
        self.session.flush()

        # Add artifact but NO relationships
        art = StructuralArtifact(
            id=f"art-{uuid.uuid4().hex[:8]}",
            repository_id=self.repo_id,
            snapshot_id=snap.id,
            artifact_type="CLASS",
            language="python",
            name="OrphanClass",
            qualified_name="app.OrphanClass",
        )
        self.session.add(art)
        self.session.commit()

        # Must classify as INCOMPLETE_DATA, not READY
        self.assertEqual(snap.status, SnapshotStatus.INCOMPLETE_DATA)
        self.assertFalse(snap.is_ready)

    def test_legacy_snapshot_with_partial_persistence(self):
        """Legacy snapshot known to have partial persistence must be classified as INCOMPLETE_DATA."""
        snap_partial = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="leg_partial_123",
            branch_name="main",
            total_symbols=50,
            snapshot_metadata={"partial": True},
        )
        self.session.add(snap_partial)
        self.session.commit()
        self.assertEqual(snap_partial.status, SnapshotStatus.INCOMPLETE_DATA)
        self.assertFalse(snap_partial.is_ready)

        snap_stage = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="leg_stage_persisting",
            branch_name="main",
            total_symbols=50,
            snapshot_metadata={"stage": "PERSISTING"},
        )
        self.session.add(snap_stage)
        self.session.commit()
        self.assertEqual(snap_stage.status, SnapshotStatus.INCOMPLETE_DATA)
        self.assertFalse(snap_stage.is_ready)

    def test_legacy_snapshot_with_complete_artifacts_and_relationships(self):
        """Legacy snapshot with proven artifacts and relationships must classify as READY."""
        snap_complete = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="leg_complete_ok",
            branch_name="main",
            total_symbols=2,
            total_files=1,
            snapshot_metadata={},  # Legacy: no status field
        )
        self.session.add(snap_complete)
        self.session.flush()

        art1 = StructuralArtifact(
            id=f"art-{uuid.uuid4().hex[:8]}",
            repository_id=self.repo_id,
            snapshot_id=snap_complete.id,
            artifact_type="CLASS",
            language="python",
            name="ClassA",
            qualified_name="pkg.ClassA",
        )
        art2 = StructuralArtifact(
            id=f"art-{uuid.uuid4().hex[:8]}",
            repository_id=self.repo_id,
            snapshot_id=snap_complete.id,
            artifact_type="CLASS",
            language="python",
            name="ClassB",
            qualified_name="pkg.ClassB",
        )
        rel = ArtifactRelationship(
            id=f"rel-{uuid.uuid4().hex[:8]}",
            repository_id=self.repo_id,
            snapshot_id=snap_complete.id,
            source_artifact_id=art1.id,
            target_artifact_id=art2.id,
            relationship_type="CALLS",
        )
        self.session.add_all([art1, art2, rel])
        self.session.commit()

        # Database evidence confirms both artifacts and relationships exist
        self.assertEqual(snap_complete.status, SnapshotStatus.READY)
        self.assertTrue(snap_complete.is_ready)

    def test_legacy_snapshot_empty_needs_reindex(self):
        """Legacy snapshot with 0 artifacts must classify as NEEDS_REINDEX."""
        snap_empty = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="leg_empty_000",
            branch_name="main",
            total_symbols=0,
            total_files=0,
            snapshot_metadata={},
        )
        self.session.add(snap_empty)
        self.session.commit()
        self.assertEqual(snap_empty.status, SnapshotStatus.NEEDS_REINDEX)
        self.assertFalse(snap_empty.is_ready)

    # -------------------------------------------------------------------------
    # 2. Git Ancestry and Same-Commit Contract Tests
    # -------------------------------------------------------------------------
    def test_same_commit_ancestry_contract(self):
        """Same commit SHA must return False with the exact Phase 1 error contract message."""
        ok, reason = check_git_ancestry(
            workspace_path=None,
            base_sha="d3b07384d113edec49eaa6238ad5ff00",
            target_sha="d3b07384d113edec49eaa6238ad5ff00",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "Baseline and target refer to the same commit; no change can be computed.")

    def test_missing_commit_sha_ancestry(self):
        """Missing or empty SHAs must be rejected."""
        ok, reason = check_git_ancestry(workspace_path=None, base_sha="", target_sha="abc1234")
        self.assertFalse(ok)
        self.assertIn("Both baseline and target commit SHAs must be provided", reason)

    # -------------------------------------------------------------------------
    # 3. Preconditions Enforcement in Service Layer (409 Conflict)
    # -------------------------------------------------------------------------
    def test_precondition_baseline_not_ready_blocked(self):
        """Blast radius must be blocked if baseline snapshot is not READY."""
        base_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="base0001",
            branch_name="main",
            total_symbols=10,
        )
        base_snap.status = SnapshotStatus.SCANNING  # NOT READY

        target_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="targ0002",
            branch_name="main",
            total_symbols=15,
        )
        target_snap.status = SnapshotStatus.READY

        self.session.add_all([base_snap, target_snap])
        self.session.commit()

        svc = ChangeImpactService()
        with self.assertRaises(ImpactPreconditionError) as ctx:
            svc.run_impact_analysis(
                db=self.session,
                repository_id=self.repo_id,
                base_snapshot_id=base_snap.id,
                target_snapshot_id=target_snap.id,
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.error_code, "SNAPSHOT_NOT_READY")
        self.assertIn("Baseline snapshot", ctx.exception.message)

    def test_precondition_target_not_ready_blocked(self):
        """Blast radius must be blocked if target snapshot is not READY."""
        base_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="base0001",
            branch_name="main",
            total_symbols=10,
        )
        base_snap.status = SnapshotStatus.READY

        target_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="targ0002",
            branch_name="main",
            total_symbols=15,
        )
        target_snap.status = SnapshotStatus.PARSING  # NOT READY

        self.session.add_all([base_snap, target_snap])
        self.session.commit()

        svc = ChangeImpactService()
        with self.assertRaises(ImpactPreconditionError) as ctx:
            svc.run_impact_analysis(
                db=self.session,
                repository_id=self.repo_id,
                base_snapshot_id=base_snap.id,
                target_snapshot_id=target_snap.id,
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.error_code, "SNAPSHOT_NOT_READY")
        self.assertIn("Target snapshot", ctx.exception.message)

    def test_precondition_same_commit_blocked(self):
        """Same commit SHA must be blocked with 409 Conflict and NO_CHANGE message."""
        base_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="identical_commit_hash_123",
            branch_name="main",
            total_symbols=10,
        )
        base_snap.status = SnapshotStatus.READY

        target_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="identical_commit_hash_123",
            branch_name="main",
            total_symbols=10,
        )
        target_snap.status = SnapshotStatus.READY

        self.session.add_all([base_snap, target_snap])
        self.session.commit()

        svc = ChangeImpactService()
        with self.assertRaises(ImpactPreconditionError) as ctx:
            svc.run_impact_analysis(
                db=self.session,
                repository_id=self.repo_id,
                base_snapshot_id=base_snap.id,
                target_snapshot_id=target_snap.id,
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.error_code, "SAME_COMMIT")
        self.assertEqual(ctx.exception.message, "Baseline and target refer to the same commit; no change can be computed.")

    def test_precondition_cross_repo_mismatch_blocked(self):
        """Snapshots from different repositories must be rejected with 400 Bad Request."""
        other_repo_id = f"repo-{uuid.uuid4().hex[:8]}"
        other_repo = Repository(
            id=other_repo_id,
            project_id=self.project_id,
            name="other-repo",
            default_branch="main",
            local_path="/tmp/other-repo-path",
        )
        self.session.add(other_repo)

        base_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="base0001",
            branch_name="main",
            total_symbols=10,
        )
        base_snap.status = SnapshotStatus.READY

        target_snap = RepositorySnapshot(
            repository_id=other_repo_id,
            commit_hash="targ0002",
            branch_name="main",
            total_symbols=15,
        )
        target_snap.status = SnapshotStatus.READY

        self.session.add_all([base_snap, target_snap])
        self.session.commit()

        svc = ChangeImpactService()
        with self.assertRaises(ImpactPreconditionError) as ctx:
            svc.run_impact_analysis(
                db=self.session,
                repository_id=self.repo_id,
                base_snapshot_id=base_snap.id,
                target_snapshot_id=target_snap.id,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "CROSS_REPO_MISMATCH")

    # -------------------------------------------------------------------------
    # 4. Provenance and Finding Traceability Tests
    # -------------------------------------------------------------------------
    def test_impact_result_provenance_and_evidence(self):
        """ImpactResult must populate provenance metadata and ImpactFinding must expose evidence completeness."""
        base_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="sha_base_001",
            branch_name="main",
            total_symbols=2,
        )
        base_snap.status = SnapshotStatus.READY

        target_snap = RepositorySnapshot(
            repository_id=self.repo_id,
            commit_hash="sha_target_002",
            branch_name="main",
            total_symbols=3,
        )
        target_snap.status = SnapshotStatus.READY

        # Add structural artifacts to target
        art_service = StructuralArtifact(
            id="art_service_01",
            repository_id=self.repo_id,
            snapshot_id=target_snap.id,
            artifact_type="CLASS",
            language="python",
            name="OrderService",
            qualified_name="app.services.OrderService",
            location="app/services/order.py",
            line_start=15,
            line_end=60,
        )
        art_controller = StructuralArtifact(
            id="art_controller_01",
            repository_id=self.repo_id,
            snapshot_id=target_snap.id,
            artifact_type="CLASS",
            language="python",
            name="OrderController",
            qualified_name="app.controllers.OrderController",
            location="app/controllers/order.py",
            line_start=10,
            line_end=45,
        )
        rel = ArtifactRelationship(
            id="rel_01",
            repository_id=self.repo_id,
            snapshot_id=target_snap.id,
            source_artifact_id=art_controller.id,
            target_artifact_id=art_service.id,
            relationship_type="CALLS",
            confidence=1.0,
            source_location="app/controllers/order.py:25",
        )

        self.session.add_all([base_snap, target_snap, art_service, art_controller, rel])
        self.session.commit()

        svc = ChangeImpactService()
        result = svc.run_impact_analysis(
            db=self.session,
            repository_id=self.repo_id,
            base_snapshot_id=base_snap.id,
            target_snapshot_id=target_snap.id,
        )

        # Provenance verification
        self.assertEqual(result.base_commit_sha, "sha_base_001")
        self.assertEqual(result.target_commit_sha, "sha_target_002")
        self.assertEqual(result.base_snapshot_id, base_snap.id)
        self.assertEqual(result.target_snapshot_id, target_snap.id)
        self.assertIsNotNone(result.analysis_id)
        self.assertEqual(result.analysis_status, "COMPLETED")
        self.assertEqual(result.total_affected_count, result.summary.unique_affected)
        self.assertEqual(result.changed_count, result.summary.changed)

        # Finding evidence completeness verification
        for f in result.findings:
            self.assertIn(f.evidence_completeness, {"COMPLETE", "PARTIAL", "MISSING", "UNKNOWN"})
            self.assertIsNotNone(f.relationship_used)
            if f.source_file:
                self.assertTrue(len(f.source_file) > 0)


if __name__ == "__main__":
    unittest.main()
