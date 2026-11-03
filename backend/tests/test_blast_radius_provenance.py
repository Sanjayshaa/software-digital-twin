import os
import sys

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

import unittest
import uuid
from datetime import datetime, timezone

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.entities import (
    Base,
    User,
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    SnapshotStatus,
)
from app.core.database import get_db
from app.core.auth import get_current_user_optional, AuthenticatedPrincipal
from main import app

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    return AuthenticatedPrincipal(
        user_id="user-provenance-test",
        username="tester",
        role="admin",
        is_admin=True,
    )


class TestBlastRadiusProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_optional] = override_get_current_user
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.clear()

    def setUp(self):
        self.db = TestingSessionLocal()
        # Seed test user, project, repo
        self.user = User(
            id="user-provenance-test",
            email="test@twincore.io",
            username="tester",
            hashed_password="mock_hashed_password_123",
            is_active=True,
        )
        self.db.merge(self.user)
        self.project = Project(
            id="proj-provenance-1",
            name="Test Provenance Project",
        )
        self.db.merge(self.project)
        self.repo = Repository(
            id="repo-provenance-1",
            project_id=self.project.id,
            owner_id=self.user.id,
            name="twincore-provenance-test",
            default_branch="main",
            local_path="/tmp/twincore_fake_repo",
        )
        self.repo2 = Repository(
            id="repo-provenance-2",
            project_id=self.project.id,
            owner_id=self.user.id,
            name="twincore-foreign-repo",
            default_branch="main",
            local_path="/tmp/twincore_foreign_repo",
        )
        self.db.merge(self.repo)
        self.db.merge(self.repo2)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # Case 1: Analysis blocked if baseline snapshot is missing
    def test_01_baseline_missing_blocks_analysis(self):
        target = RepositorySnapshot(
            id="snap_target_1",
            repository_id=self.repo.id,
            commit_hash="abc2222",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(target)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/impact-analysis",
            json={"base_snapshot_id": "nonexistent_base", "target_snapshot_id": target.id},
        )
        self.assertIn(res.status_code, [400, 404])
        data = res.json()
        self.assertTrue("detail" in data)

    # Case 2: Analysis blocked if baseline snapshot status is not READY
    def test_02_baseline_not_ready_blocks_analysis(self):
        base = RepositorySnapshot(
            id="snap_base_2",
            repository_id=self.repo.id,
            commit_hash="abc1111",
            snapshot_metadata={"status": SnapshotStatus.PARSING},
        )
        target = RepositorySnapshot(
            id="snap_target_2",
            repository_id=self.repo.id,
            commit_hash="abc2222",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(base)
        self.db.merge(target)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/impact-analysis",
            json={"base_snapshot_id": base.id, "target_snapshot_id": target.id},
        )
        self.assertIn(res.status_code, [400, 409])
        self.assertTrue(any("expected READY" in pf for pf in res.json()["detail"]["preconditions_failed"]))

    # Case 3: Analysis blocked if target snapshot is missing
    def test_03_target_missing_blocks_analysis(self):
        base = RepositorySnapshot(
            id="snap_base_3",
            repository_id=self.repo.id,
            commit_hash="abc1111",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(base)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/impact-analysis",
            json={"base_snapshot_id": base.id, "target_snapshot_id": "nonexistent_target"},
        )
        self.assertIn(res.status_code, [400, 404])
        self.assertTrue("detail" in res.json())

    # Case 4: Analysis blocked if target snapshot status is not READY
    def test_04_target_not_ready_blocks_analysis(self):
        base = RepositorySnapshot(
            id="snap_base_4",
            repository_id=self.repo.id,
            commit_hash="abc1111",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        target = RepositorySnapshot(
            id="snap_target_4",
            repository_id=self.repo.id,
            commit_hash="abc2222",
            snapshot_metadata={"status": SnapshotStatus.SCANNING},
        )
        self.db.merge(base)
        self.db.merge(target)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/impact-analysis",
            json={"base_snapshot_id": base.id, "target_snapshot_id": target.id},
        )
        self.assertIn(res.status_code, [400, 409])
        self.assertTrue(any("expected READY" in pf for pf in res.json()["detail"]["preconditions_failed"]))

    # Case 5: Analysis blocked if baseline and target belong to different repositories
    def test_05_different_repositories_blocks_analysis(self):
        base = RepositorySnapshot(
            id="snap_base_5",
            repository_id=self.repo.id,
            commit_hash="abc1111",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        target = RepositorySnapshot(
            id="snap_target_5",
            repository_id=self.repo2.id,
            commit_hash="abc2222",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(base)
        self.db.merge(target)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/impact-analysis",
            json={"base_snapshot_id": base.id, "target_snapshot_id": target.id},
        )
        # Cross-repository snapshot mismatch contract strictly returns HTTP 400 Bad Request
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not belong to repository", str(res.json()["detail"]))

    # Case 6: Analysis blocked if baseline and target commit SHAs are identical
    def test_06_identical_commits_blocks_analysis(self):
        base = RepositorySnapshot(
            id="snap_base_6",
            repository_id=self.repo.id,
            commit_hash="abcidentical",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        target = RepositorySnapshot(
            id="snap_target_6",
            repository_id=self.repo.id,
            commit_hash="abcidentical",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(base)
        self.db.merge(target)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/impact-analysis",
            json={"base_snapshot_id": base.id, "target_snapshot_id": target.id},
        )
        self.assertIn(res.status_code, [400, 409])
        detail = res.json()["detail"]
        if isinstance(detail, dict):
            self.assertIn(detail.get("status"), ["NO_CHANGE", "IDENTICAL_COMMITS"])

    # Case 7: Single-entity blast radius works on a single READY snapshot
    def test_07_single_entity_blast_radius_single_ready_snapshot(self):
        snap = RepositorySnapshot(
            id="snap_single_7",
            repository_id=self.repo.id,
            commit_hash="single777",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(snap)

        art_a = StructuralArtifact(
            id="art_root_a",
            snapshot_id=snap.id,
            name="AuthService",
            qualified_name="services.AuthService",
            artifact_type="SERVICE",
            location="services/auth.py",
        )
        art_b = StructuralArtifact(
            id="art_caller_b",
            snapshot_id=snap.id,
            name="LoginController",
            qualified_name="controllers.LoginController",
            artifact_type="COMPONENT",
            location="controllers/login.py",
        )
        rel = ArtifactRelationship(
            id="rel_b_calls_a",
            snapshot_id=snap.id,
            source_artifact_id=art_b.id,
            target_artifact_id=art_a.id,
            relationship_type="CALLS",
        )
        self.db.merge(art_a)
        self.db.merge(art_b)
        self.db.merge(rel)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/blast-radius",
            json={"artifact_id": art_a.id, "snapshot_id": snap.id, "max_depth": 5},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["root_name"], "AuthService")
        self.assertEqual(data["summary"]["unique_affected"], 1)
        self.assertIn("evidence_confidence", data)

    # Case 8: Zero affected returned truthfully when disconnected node
    def test_08_zero_affected_truthfully_returned(self):
        snap = RepositorySnapshot(
            id="snap_single_8",
            repository_id=self.repo.id,
            commit_hash="single888",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(snap)

        isolated = StructuralArtifact(
            id="art_isolated_8",
            snapshot_id=snap.id,
            name="IsolatedUtil",
            qualified_name="utils.IsolatedUtil",
            artifact_type="COMPONENT",
            location="utils/isolated.py",
        )
        self.db.merge(isolated)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/blast-radius",
            json={"artifact_id": isolated.id, "snapshot_id": snap.id},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["summary"]["unique_affected"], 0)
        self.assertEqual(data["summary"]["changed"], 1)

    # Case 9: Multi-hop propagation correctly accumulates transitive affected
    def test_09_multihop_propagation_accumulates_transitive(self):
        snap = RepositorySnapshot(
            id="snap_single_9",
            repository_id=self.repo.id,
            commit_hash="single999",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(snap)

        art_a = StructuralArtifact(
            id="art_a_9",
            snapshot_id=snap.id,
            name="DatabasePool",
            qualified_name="db.DatabasePool",
            artifact_type="COMPONENT",
            location="db/pool.py",
        )
        art_b = StructuralArtifact(
            id="art_b_9",
            snapshot_id=snap.id,
            name="UserRepository",
            qualified_name="repo.UserRepository",
            artifact_type="COMPONENT",
            location="repo/user.py",
        )
        art_c = StructuralArtifact(
            id="art_c_9",
            snapshot_id=snap.id,
            name="AuthService",
            qualified_name="services.AuthService",
            artifact_type="SERVICE",
            location="services/auth.py",
        )
        # B calls A (depth 1 from A), C calls B (depth 2 from A)
        rel1 = ArtifactRelationship(id="r1_9", snapshot_id=snap.id, source_artifact_id=art_b.id, target_artifact_id=art_a.id, relationship_type="CALLS")
        rel2 = ArtifactRelationship(id="r2_9", snapshot_id=snap.id, source_artifact_id=art_c.id, target_artifact_id=art_b.id, relationship_type="CALLS")

        self.db.merge(art_a)
        self.db.merge(art_b)
        self.db.merge(art_c)
        self.db.merge(rel1)
        self.db.merge(rel2)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/blast-radius",
            json={"artifact_id": art_a.id, "snapshot_id": snap.id, "max_depth": 5},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["summary"]["unique_affected"], 2)
        self.assertEqual(data["summary"]["directly_affected"], 1)
        self.assertEqual(data["summary"]["indirectly_affected"], 1)
        self.assertEqual(data["summary"]["max_depth_reached"], 2)

    # Case 10: Cycle protection terminates safely without infinite recursion
    def test_10_cycle_protection_terminates_safely(self):
        snap = RepositorySnapshot(
            id="snap_cycle_10",
            repository_id=self.repo.id,
            commit_hash="cycle1010",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(snap)

        n1 = StructuralArtifact(id="n1", snapshot_id=snap.id, name="Node1", qualified_name="n1", artifact_type="COMPONENT")
        n2 = StructuralArtifact(id="n2", snapshot_id=snap.id, name="Node2", qualified_name="n2", artifact_type="COMPONENT")
        # Cyclic dependency: n1 calls n2, n2 calls n1
        r1 = ArtifactRelationship(id="rc1", snapshot_id=snap.id, source_artifact_id=n1.id, target_artifact_id=n2.id, relationship_type="CALLS")
        r2 = ArtifactRelationship(id="rc2", snapshot_id=snap.id, source_artifact_id=n2.id, target_artifact_id=n1.id, relationship_type="CALLS")

        self.db.merge(n1)
        self.db.merge(n2)
        self.db.merge(r1)
        self.db.merge(r2)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/blast-radius",
            json={"artifact_id": n1.id, "snapshot_id": snap.id, "max_depth": 5},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Node 2 is the caller of Node 1
        self.assertEqual(data["summary"]["unique_affected"], 1)

    # Case 11: Affected test suites and APIs categorized accurately
    def test_11_test_suites_and_apis_categorized(self):
        snap = RepositorySnapshot(
            id="snap_types_11",
            repository_id=self.repo.id,
            commit_hash="types1111",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(snap)

        root = StructuralArtifact(id="t_root", snapshot_id=snap.id, name="PaymentLogic", qualified_name="core.PaymentLogic", artifact_type="COMPONENT")
        api_ep = StructuralArtifact(id="t_api", snapshot_id=snap.id, name="PostPaymentRoute", qualified_name="routes.PostPaymentRoute", artifact_type="API_ENDPOINT")
        test_case = StructuralArtifact(id="t_test", snapshot_id=snap.id, name="TestPaymentFlow", qualified_name="tests.TestPaymentFlow", artifact_type="TEST_CASE")

        r_api = ArtifactRelationship(id="ra1", snapshot_id=snap.id, source_artifact_id=api_ep.id, target_artifact_id=root.id, relationship_type="CALLS")
        r_test = ArtifactRelationship(id="rt1", snapshot_id=snap.id, source_artifact_id=test_case.id, target_artifact_id=root.id, relationship_type="CALLS")

        self.db.merge(root)
        self.db.merge(api_ep)
        self.db.merge(test_case)
        self.db.merge(r_api)
        self.db.merge(r_test)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/blast-radius",
            json={"artifact_id": root.id, "snapshot_id": snap.id},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["summary"]["affected_apis"], 1)
        self.assertEqual(data["summary"]["affected_tests"], 1)
        self.assertIn("tests.TestPaymentFlow", data["affected_categories"]["affected_tests"])
        self.assertIn("routes.PostPaymentRoute", data["affected_categories"]["affected_apis"])

    # Case 12: Provenance metadata included and evidence confidence derived (never hardcoded)
    def test_12_provenance_and_evidence_confidence_derived(self):
        base = RepositorySnapshot(
            id="snap_base_12",
            repository_id=self.repo.id,
            commit_hash="sha12000001",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        target = RepositorySnapshot(
            id="snap_target_12",
            repository_id=self.repo.id,
            commit_hash="sha12000002",
            snapshot_metadata={"status": SnapshotStatus.READY},
        )
        self.db.merge(base)
        self.db.merge(target)
        self.db.commit()

        # Seed artifact in base and modified in target
        art1 = StructuralArtifact(id="a12_1", snapshot_id=base.id, name="OrderService", qualified_name="srv.OrderService", artifact_type="SERVICE", location="srv/orders.py")
        art2 = StructuralArtifact(id="a12_2", snapshot_id=target.id, name="OrderService", qualified_name="srv.OrderService", artifact_type="SERVICE", location="srv/orders.py")
        self.db.merge(art1)
        self.db.merge(art2)
        self.db.commit()

        res = self.client.post(
            f"/repositories/{self.repo.id}/impact-analysis",
            json={"base_snapshot_id": base.id, "target_snapshot_id": target.id},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check full provenance fields
        self.assertIn("analysis_id", data)
        self.assertEqual(data["repository_id"], self.repo.id)
        self.assertEqual(data["baseline_commit_sha"], "sha12000001")
        self.assertEqual(data["target_commit_sha"], "sha12000002")
        self.assertIn("propagation_rules_used", data)
        self.assertIn("generated_at", data)
        self.assertIn("evidence_confidence", data)
        conf = data["evidence_confidence"]
        self.assertIn("score", conf)
        self.assertIn("label", conf)
        self.assertNotEqual(conf["score"], 0.98) # Verify it is dynamically calculated and not hardcoded 98%

if __name__ == "__main__":
    unittest.main()
