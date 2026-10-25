"""
Comprehensive Blast Radius and What-If Scenario Test Suite.
Verifies:
1. Deterministic Blast Radius endpoint (POST/GET /{repo_id}/blast-radius)
2. Single-component blast radius tracing without requiring dual commits
3. What-If Scenario Orchestration resilience and fallback target resolution
4. Architectural Graph Projection retaining affected blast radius nodes across all levels
"""

import os
import sys
import unittest
from datetime import datetime, timezone

# Python version auto-re-exec guard for subshell execution
if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest", os.path.abspath(__file__)])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.entities import (
    Base, Repository, RepositorySnapshot, Project,
    StructuralArtifact, ArtifactRelationship, User
)
from app.core.database import get_db
from app.services.analysis.graph.projection import twin_graph_projection

# In-memory SQLite with StaticPool so all connections share the same in-memory DB
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)

from main import app

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


class TestBlastRadiusAndWhatIf(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = TestingSessionLocal()

        # Seed Project
        proj = self.db.query(Project).filter_by(id="test-proj-1").first()
        if not proj:
            proj = Project(id="test-proj-1", name="Test Project")
            self.db.add(proj)

        # Seed Repository
        self.repo = self.db.query(Repository).filter_by(id="repo-blast-1").first()
        if not self.repo:
            self.repo = Repository(
                id="repo-blast-1",
                name="TwinCore-Test-Repo",
                project_id="test-proj-1",
                vcs_type="git",
                local_path="/tmp/test-repo",
            )
            self.db.add(self.repo)

        # Seed Snapshot
        self.snapshot = self.db.query(RepositorySnapshot).filter_by(id="snap-blast-1").first()
        if not self.snapshot:
            self.snapshot = RepositorySnapshot(
                id="snap-blast-1",
                repository_id="repo-blast-1",
                commit_hash="abc1234567890",
                branch_name="main",
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(self.snapshot)

        # Seed Artifacts:
        # 1. PaymentService (SERVICE)
        # 2. CheckoutController (API_ENDPOINT) -> calls PaymentService
        # 3. OrderRouter (MODULE) -> calls CheckoutController
        # 4. TestPaymentSuite (TEST_CASE) -> tests PaymentService
        # 5. InventoryService (SERVICE) -> independent
        art_payment = StructuralArtifact(
            id="art-payment-svc",
            snapshot_id="snap-blast-1",
            name="PaymentService",
            qualified_name="app.services.PaymentService",
            artifact_type="SERVICE",
            language="python",
            location="backend/app/services/payment.py",
        )
        art_checkout = StructuralArtifact(
            id="art-checkout-api",
            snapshot_id="snap-blast-1",
            name="CheckoutController",
            qualified_name="app.api.checkout.post",
            artifact_type="API_ENDPOINT",
            language="python",
            location="backend/app/api/checkout.py",
        )
        art_router = StructuralArtifact(
            id="art-order-router",
            snapshot_id="snap-blast-1",
            name="OrderRouter",
            qualified_name="app.routers.order",
            artifact_type="MODULE",
            language="python",
            location="backend/app/routers/order.py",
        )
        art_test = StructuralArtifact(
            id="art-test-payment",
            snapshot_id="snap-blast-1",
            name="test_payment_flow",
            qualified_name="tests.test_payment.test_payment_flow",
            artifact_type="TEST_CASE",
            language="python",
            location="backend/tests/test_payment.py",
        )
        art_inventory = StructuralArtifact(
            id="art-inventory-svc",
            snapshot_id="snap-blast-1",
            name="InventoryService",
            qualified_name="app.services.InventoryService",
            artifact_type="SERVICE",
            language="python",
            location="backend/app/services/inventory.py",
        )

        for art in [art_payment, art_checkout, art_router, art_test, art_inventory]:
            if not self.db.query(StructuralArtifact).filter_by(id=art.id).first():
                self.db.add(art)

        # Seed Relationships (Callers -> Callee):
        # CheckoutController CALLS PaymentService
        # OrderRouter CALLS CheckoutController
        # TestPaymentSuite TESTS PaymentService
        rel1 = ArtifactRelationship(
            id="rel-1",
            snapshot_id="snap-blast-1",
            source_artifact_id="art-checkout-api",
            target_artifact_id="art-payment-svc",
            relationship_type="CALLS",
        )
        rel2 = ArtifactRelationship(
            id="rel-2",
            snapshot_id="snap-blast-1",
            source_artifact_id="art-order-router",
            target_artifact_id="art-checkout-api",
            relationship_type="CALLS",
        )
        rel3 = ArtifactRelationship(
            id="rel-3",
            snapshot_id="snap-blast-1",
            source_artifact_id="art-test-payment",
            target_artifact_id="art-payment-svc",
            relationship_type="TESTS",
        )

        for rel in [rel1, rel2, rel3]:
            if not self.db.query(ArtifactRelationship).filter_by(id=rel.id).first():
                self.db.add(rel)

        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_blast_radius_candidates_discovery(self):
        """GET /blast-radius returns candidate components when no target is passed."""
        res = self.client.get(f"/repositories/{self.repo.id}/blast-radius")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "AWAITING_TARGET")
        self.assertGreaterEqual(len(data["candidates"]), 3)
        candidate_names = [c["name"] for c in data["candidates"]]
        self.assertIn("PaymentService", candidate_names)

    def test_blast_radius_computation_for_service(self):
        """POST /blast-radius computes forward and transitive caller blast radius."""
        payload = {
            "artifact_id": "art-payment-svc",
            "snapshot_id": "snap-blast-1",
            "max_depth": 5,
        }
        res = self.client.post(f"/repositories/{self.repo.id}/blast-radius", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["root_artifact"]["name"], "PaymentService")

        # CheckoutController (hop 1), OrderRouter (hop 2), TestPayment (hop 1)
        affected_names = [n["name"] for n in data["affected_nodes"]]
        self.assertIn("PaymentService", affected_names)
        self.assertIn("CheckoutController", affected_names)
        self.assertIn("OrderRouter", affected_names)
        self.assertIn("test_payment_flow", affected_names)
        # InventoryService is independent and must NOT be in blast radius
        self.assertNotIn("InventoryService", affected_names)

        # APIs and Tests categorization
        self.assertIn("app.api.checkout.post", data["affected_apis"])
        self.assertIn("tests.test_payment.test_payment_flow", data["affected_tests"])

        # Risk score must be calculated
        self.assertGreater(data["summary"]["blast_radius_score"], 0)
        self.assertIn(data["summary"]["risk_level"], ["LOW", "MEDIUM", "HIGH", "CRITICAL"])

    def test_projection_retains_blast_radius_nodes_at_level_1(self):
        """Level 1 projection must retain impacted nodes even if they are methods or lower tier."""
        proj = twin_graph_projection.project_graph(
            db=self.db,
            repository_id=self.repo.id,
            snapshot_id=self.snapshot.id,
            level=1,
            impact_artifact_id="art-payment-svc",
        )
        projected_ids = [n["id"] for n in proj["nodes"]]
        self.assertIn("art-payment-svc", projected_ids)
        self.assertIn("art-checkout-api", projected_ids)

        # Verify summary contains impact_summary
        self.assertIsNotNone(proj["summary"].get("impact_summary"))
        self.assertEqual(proj["summary"]["impact_summary"]["root_artifact"], "app.services.PaymentService")

    def test_what_if_orchestration_resilience_and_execution(self):
        """Orchestrate scenario should automatically resolve targets and execute successfully."""
        payload = {
            "query": "What if we remove PaymentService?",
            "base_snapshot_id": self.snapshot.id,
            "target_override": "PaymentService",
            "mutation_type_override": "MODIFY_SYMBOL",
        }
        res = self.client.post(f"/repositories/{self.repo.id}/scenarios/orchestrate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("scenario_id", data)
        self.assertIn("plan", data)
        self.assertTrue(data["plan"]["can_execute"])
        self.assertIn("PaymentService", data["plan"]["resolved_target_name"])

        # Verify impact and risk reports are synthesized
        self.assertIn("simulation", data)
        sim = data["simulation"]
        self.assertIn("impact", sim)
        self.assertIn("guardrails", sim)
        self.assertIn("risk", sim)


if __name__ == "__main__":
    unittest.main()
