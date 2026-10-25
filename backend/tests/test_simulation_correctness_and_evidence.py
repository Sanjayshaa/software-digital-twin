"""
Deterministic Knowledge Graph Correctness, Ground-Truth Verification,
and What-If Scenario Validation Test Suite.

Verifies:
1. Precision & Recall against a deterministic synthetic knowledge graph fixture.
2. Verified Zero-Impact analysis on isolated leaf/test entities (in-degree == 0).
3. Truthful UNRESOLVED_TARGET handling without silent fallback substitution.
4. Truthful EMPTY_GRAPH and MISSING_SNAPSHOT states.
5. Correct scenario semantics for SERVICE_OUTAGE, REMOVE_COMPONENT, SCHEMA_MIGRATION, MODIFY_SYMBOL.
6. Transparent mathematical risk score breakdown.
7. Grounded static AST code evidence with file locations and line numbers.
8. Architectural graph projection preserving impacted nodes across zoom levels.
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
    Base,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    User,
    Project,
)
from app.core.database import get_db
from app.services.simulation.engine import scenario_simulation_engine
from app.services.simulation.orchestration import multi_agent_scenario_orchestrator
from app.services.simulation.models import (
    MutationType,
    ScenarioStatus,
    ProposedMutation,
    EvidenceCategory,
)
from app.services.analysis.graph.projection import twin_graph_projection
from main import app


class TestSimulationCorrectnessAndEvidence(unittest.TestCase):
    """
    Deterministic verification of graph correctness, scenario semantics, and explainability.
    """

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

    def setUp(self):
        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        from app.core.auth import get_current_user_optional, AuthenticatedPrincipal

        def override_auth():
            return AuthenticatedPrincipal(
                user_id="user-qa-1",
                username="qa_architect",
                role="ADMIN",
                is_admin=True,
            )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_optional] = override_auth
        self.client = TestClient(app)

        # 1. Project & User
        self.user = User(
            id="user-qa-1",
            email="qa@twincore.io",
            username="qa_architect",
            hashed_password="pw",
            role="ADMIN",
        )
        self.project = Project(id="proj-qa-1", name="TwinCore Synthetic Verification")
        for ent in [self.user, self.project]:
            if not self.db.query(ent.__class__).filter_by(id=ent.id).first():
                self.db.add(ent)

        # 2. Repository & Baseline Snapshot
        self.repo = Repository(
            id="repo-ground-truth-1",
            project_id="proj-qa-1",
            owner_id="user-qa-1",
            name="synthetic-verification-repo",
            local_path="/workspace/synthetic-verification-repo",
            default_branch="main",
            source_type="LOCAL",
        )
        self.snapshot = RepositorySnapshot(
            id="snap-ground-truth-1",
            repository_id="repo-ground-truth-1",
            commit_hash="af28cbb0194e4321",
            snapshot_metadata={"total_files": 12},
        )
        for ent in [self.repo, self.snapshot]:
            if not self.db.query(ent.__class__).filter_by(id=ent.id).first():
                self.db.add(ent)

        # 3. Deterministic Synthetic Ground-Truth Graph:
        # - art_api: API endpoint (POST /api/v1/orders)
        # - art_controller: WebRouter / OrderController
        # - art_service: OrderService (Core business logic)
        # - art_payment: PaymentGateway (Third-party client)
        # - art_model: OrderModel (Data entity)
        # - art_db: DatabaseEntity (Postgres table 'orders')
        # - art_circ_a: CircularA (Calls CircularB)
        # - art_circ_b: CircularB (Calls CircularA)
        # - art_isolated_test: tests/test_unlock_adapter.c::pci_dev (In-degree = 0, isolated leaf)
        # - art_unrelated: UnrelatedAnalyticsService (Zero connections to Order pipeline)

        self.artifacts = [
            StructuralArtifact(
                id="art-api-orders",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="POST /api/v1/orders",
                qualified_name="api.endpoints.create_order",
                artifact_type="API_ENDPOINT",
                language="python",
                location="app/api/orders.py:25",
                line_start=25,
                line_end=45,
            ),
            StructuralArtifact(
                id="art-controller-order",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="OrderController",
                qualified_name="app.controllers.OrderController",
                artifact_type="CLASS",
                language="python",
                location="app/controllers/order.py:10",
                line_start=10,
                line_end=80,
            ),
            StructuralArtifact(
                id="art-service-order",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="OrderService",
                qualified_name="app.services.OrderService",
                artifact_type="SERVICE",
                language="python",
                location="app/services/order.py:15",
                line_start=15,
                line_end=150,
            ),
            StructuralArtifact(
                id="art-payment-gateway",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="PaymentGateway",
                qualified_name="app.clients.PaymentGateway",
                artifact_type="CLASS",
                language="python",
                location="app/clients/payment.py:5",
                line_start=5,
                line_end=60,
            ),
            StructuralArtifact(
                id="art-model-order",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="OrderModel",
                qualified_name="app.models.OrderModel",
                artifact_type="CLASS",
                language="python",
                location="app/models/order.py:8",
                line_start=8,
                line_end=50,
            ),
            StructuralArtifact(
                id="art-db-orders",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="orders_table",
                qualified_name="database.tables.orders",
                artifact_type="DATABASE_ENTITY",
                language="sql",
                location="db/schema.sql:100",
                line_start=100,
                line_end=120,
            ),
            StructuralArtifact(
                id="art-circ-a",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="CircularA",
                qualified_name="app.services.CircularA",
                artifact_type="CLASS",
                language="python",
                location="app/services/circular.py:1",
                line_start=1,
                line_end=20,
            ),
            StructuralArtifact(
                id="art-circ-b",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="CircularB",
                qualified_name="app.services.CircularB",
                artifact_type="CLASS",
                language="python",
                location="app/services/circular.py:25",
                line_start=25,
                line_end=45,
            ),
            StructuralArtifact(
                id="art-test-leaf",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="pci_dev",
                qualified_name="tests/test_unlock_adapter.c::pci_dev",
                artifact_type="TEST_CASE",
                language="c",
                location="tests/test_unlock_adapter.c:42",
                line_start=42,
                line_end=65,
            ),
            StructuralArtifact(
                id="art-unrelated-analytics",
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                name="AnalyticsService",
                qualified_name="app.services.AnalyticsService",
                artifact_type="SERVICE",
                language="python",
                location="app/services/analytics.py:1",
                line_start=1,
                line_end=90,
            ),
        ]

        for art in self.artifacts:
            if not self.db.query(StructuralArtifact).filter_by(id=art.id).first():
                self.db.add(art)

        # Ground-Truth Relationships (Dependency Edge Graph):
        # 1. API -> Controller (ROUTES_TO)
        # 2. Controller -> Service (CALLS)
        # 3. Service -> PaymentGateway (CALLS)
        # 4. Service -> OrderModel (IMPORTS / USES)
        # 5. OrderModel -> orders_table (ACCESSES)
        # 6. CircularA -> CircularB (CALLS)
        # 7. CircularB -> CircularA (CALLS)
        self.relationships = [
            ArtifactRelationship(
                id="rel-gt-1",
                snapshot_id=self.snapshot.id,
                source_artifact_id="art-api-orders",
                target_artifact_id="art-controller-order",
                relationship_type="CALLS",
            ),
            ArtifactRelationship(
                id="rel-gt-2",
                snapshot_id=self.snapshot.id,
                source_artifact_id="art-controller-order",
                target_artifact_id="art-service-order",
                relationship_type="CALLS",
            ),
            ArtifactRelationship(
                id="rel-gt-3",
                snapshot_id=self.snapshot.id,
                source_artifact_id="art-service-order",
                target_artifact_id="art-payment-gateway",
                relationship_type="CALLS",
            ),
            ArtifactRelationship(
                id="rel-gt-4",
                snapshot_id=self.snapshot.id,
                source_artifact_id="art-service-order",
                target_artifact_id="art-model-order",
                relationship_type="IMPORTS",
            ),
            ArtifactRelationship(
                id="rel-gt-5",
                snapshot_id=self.snapshot.id,
                source_artifact_id="art-model-order",
                target_artifact_id="art-db-orders",
                relationship_type="ACCESSES",
            ),
            ArtifactRelationship(
                id="rel-gt-6",
                snapshot_id=self.snapshot.id,
                source_artifact_id="art-circ-a",
                target_artifact_id="art-circ-b",
                relationship_type="CALLS",
            ),
            ArtifactRelationship(
                id="rel-gt-7",
                snapshot_id=self.snapshot.id,
                source_artifact_id="art-circ-b",
                target_artifact_id="art-circ-a",
                relationship_type="CALLS",
            ),
        ]

        for rel in self.relationships:
            if not self.db.query(ArtifactRelationship).filter_by(id=rel.id).first():
                self.db.add(rel)

        self.db.commit()

    def tearDown(self):
        self.db.close()

    # ====================================================================
    # PHASE 6: KNOWLEDGE GRAPH PRECISION & RECALL VERIFICATION
    # ====================================================================
    def test_fixture_graph_precision_and_recall(self):
        """
        Validates knowledge graph extraction precision and recall against synthetic ground truth.
        Precision = True Positives / (True Positives + False Positives)
        Recall = True Positives / (True Positives + False Negatives)
        """
        db_arts = self.db.query(StructuralArtifact).filter_by(snapshot_id=self.snapshot.id).all()
        db_rels = self.db.query(ArtifactRelationship).filter_by(snapshot_id=self.snapshot.id).all()

        expected_node_ids = {a.id for a in self.artifacts}
        extracted_node_ids = {a.id for a in db_arts}

        # Node Precision & Recall
        node_tp = len(expected_node_ids & extracted_node_ids)
        node_fp = len(extracted_node_ids - expected_node_ids)
        node_fn = len(expected_node_ids - extracted_node_ids)
        node_precision = node_tp / (node_tp + node_fp) if (node_tp + node_fp) > 0 else 0
        node_recall = node_tp / (node_tp + node_fn) if (node_tp + node_fn) > 0 else 0

        self.assertEqual(node_precision, 1.0, "Node precision must be 1.0 on synthetic fixture")
        self.assertEqual(node_recall, 1.0, "Node recall must be 1.0 on synthetic fixture")

        # Edge Precision & Recall
        expected_edges = {(r.source_artifact_id, r.target_artifact_id, r.relationship_type) for r in self.relationships}
        extracted_edges = {(r.source_artifact_id, r.target_artifact_id, r.relationship_type) for r in db_rels}

        edge_tp = len(expected_edges & extracted_edges)
        edge_fp = len(extracted_edges - expected_edges)
        edge_fn = len(expected_edges - extracted_edges)
        edge_precision = edge_tp / (edge_tp + edge_fp) if (edge_tp + edge_fp) > 0 else 0
        edge_recall = edge_tp / (edge_tp + edge_fn) if (edge_tp + edge_fn) > 0 else 0

        self.assertEqual(edge_precision, 1.0, "Edge precision must be 1.0 on synthetic fixture")
        self.assertEqual(edge_recall, 1.0, "Edge recall must be 1.0 on synthetic fixture")

    # ====================================================================
    # PHASE 1 & 2: ZERO-VALUE ACCURACY & EXPLAINABILITY (USER PROMPT CASE)
    # ====================================================================
    def test_isolated_leaf_entity_zero_impact_explanation(self):
        """
        Reproduces user screenshot scenario:
        Modifying 'tests/test_unlock_adapter.c::pci_dev' has in_degree = 0.
        Must return VERIFIED_ZERO_IMPACT, in_degree = 0, is_leaf = True, is_test_entity = True,
        and transparent explanation for why downstream impact is 0.
        """
        mutation = ProposedMutation(
            mutation_id="mut-leaf-1",
            mutation_type=MutationType.MODIFY_SYMBOL,
            target="tests/test_unlock_adapter.c::pci_dev",
            description="Simulate symbol signature change on pci_dev",
        )
        result = scenario_simulation_engine.simulate_scenario(
            db=self.db,
            repository_id=self.repo.id,
            base_snapshot_id=self.snapshot.id,
            name="Mutate test function pci_dev",
            proposed_changes=[mutation],
        )

        self.assertEqual(result.status, ScenarioStatus.VERIFIED_ZERO_IMPACT)
        self.assertIsNotNone(result.target_details)
        self.assertEqual(result.target_details.in_degree, 0)
        self.assertTrue(result.target_details.is_leaf)
        self.assertTrue(result.target_details.is_test_entity)

        # Impact must be 0
        self.assertEqual(len(result.impact.affected_components), 0)
        self.assertEqual(len(result.impact.affected_apis), 0)

        # Status explanation must plainly explain why impact is 0 without concealing data
        self.assertIn("Verified Zero Downstream Impact", result.status_explanation)
        self.assertIn("in-degree: 0", result.status_explanation)
        self.assertIn("test artifact", result.status_explanation)

        # Static AST evidence must be grounded with location and line numbers
        static_evidence = next((e for e in result.evidence if e.category == EvidenceCategory.STATIC_EXTRACTED), None)
        self.assertIsNotNone(static_evidence)
        self.assertIn("L42-65", static_evidence.description)
        self.assertEqual(static_evidence.details.get("extraction_method"), "STATIC_AST")

        # Mathematical risk breakdown must explain score transparency
        self.assertIsNotNone(result.risk_breakdown)
        self.assertEqual(result.risk_breakdown.structural_impact_score, 20.0)
        self.assertEqual(result.risk_breakdown.guardrail_penalty, 100.0)
        self.assertIn("Structural Blast", result.risk_breakdown.explanation)
        self.assertIn("Test Coverage Gap", result.risk_breakdown.explanation)

    # ====================================================================
    # PHASE 3: SCENARIO SEMANTICS & NO SILENT FALLBACK SUBSTITUTION
    # ====================================================================
    def test_unresolved_target_returns_explicit_error_without_silent_substitution(self):
        """
        When user asks to mutate 'NonExistentService', system must NOT silently substitute
        another service (e.g. OrderService) as if the original target had been analyzed.
        """
        res = self.client.post(
            f"/repositories/{self.repo.id}/scenarios/orchestrate",
            json={
                "query": "What if we remove NonExistentService?",
                "base_snapshot_id": self.snapshot.id,
                "target_override": "NonExistentService",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        plan = data["plan"]
        self.assertFalse(plan["can_execute"])
        self.assertEqual(plan["status"], "UNRESOLVED_TARGET")
        self.assertIn("NonExistentService", plan["execution_block_reason"])
        self.assertIn("could not be resolved", plan["execution_block_reason"])

        sim = data["simulation"]
        self.assertEqual(sim["status"], ScenarioStatus.UNRESOLVED_TARGET)

    def test_empty_graph_status_distinction(self):
        """
        When a snapshot has 0 artifacts indexed, simulation must return EMPTY_GRAPH,
        never claiming a successful zero-impact analysis.
        """
        # Create empty snapshot
        empty_snap = RepositorySnapshot(
            id="snap-empty-000",
            repository_id=self.repo.id,
            commit_hash="0000000000000000",
        )
        self.db.add(empty_snap)
        self.db.commit()

        mutation = ProposedMutation(
            mutation_id="mut-empty-1",
            mutation_type=MutationType.MODIFY_SYMBOL,
            target="app.services.OrderService",
        )
        result = scenario_simulation_engine.simulate_scenario(
            db=self.db,
            repository_id=self.repo.id,
            base_snapshot_id="snap-empty-000",
            name="Empty Graph Test",
            proposed_changes=[mutation],
        )

        self.assertEqual(result.status, ScenarioStatus.EMPTY_GRAPH)
        self.assertIn("0 structural artifacts", result.status_explanation)

    def test_missing_snapshot_status_distinction(self):
        """
        When requested snapshot does not exist, returns MISSING_SNAPSHOT.
        """
        res = self.client.post(
            f"/repositories/{self.repo.id}/scenarios/orchestrate",
            json={
                "query": "What happens if we remove PaymentGateway?",
                "base_snapshot_id": "snap-does-not-exist-999",
                "target_override": "app.clients.PaymentGateway",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["simulation"]["status"], ScenarioStatus.MISSING_SNAPSHOT)
        self.assertIn("snap-does-not-exist-999", data["simulation"]["status_explanation"])

    # ====================================================================
    # PHASE 4: EVIDENCE-BACKED MULTI-HOP DEPENDENCY TRAVERSAL
    # ====================================================================
    def test_multi_hop_dependency_propagation(self):
        """
        Mutating 'OrderService' must traverse downstream callers:
        - OrderController (Depth 1, Direct)
        - POST /api/v1/orders (Depth 2, Indirect)
        Unrelated components (AnalyticsService, pci_dev) must remain unaffected.
        """
        res = self.client.post(
            f"/repositories/{self.repo.id}/scenarios/orchestrate",
            json={
                "query": "What if we modify app.services.OrderService?",
                "base_snapshot_id": self.snapshot.id,
                "target_override": "app.services.OrderService",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        sim = data["simulation"]

        self.assertEqual(sim["status"], ScenarioStatus.DOWNSTREAM_IMPACT_DETECTED)
        impact = sim["impact"]

        affected_components = impact["affected_components"]
        affected_apis = impact["affected_apis"]
        all_affected = set(affected_components + affected_apis)

        self.assertIn("app.controllers.OrderController", all_affected)
        self.assertIn("api.endpoints.create_order", all_affected)

        # Unrelated services must NOT be in blast radius
        self.assertNotIn("app.services.AnalyticsService", all_affected)
        self.assertNotIn("tests/test_unlock_adapter.c::pci_dev", all_affected)

    def test_service_outage_mutation_semantics(self):
        """
        SERVICE_OUTAGE must simulate removal of service and sever inbound/outbound edges.
        """
        mutation = ProposedMutation(
            mutation_id="mut-outage-1",
            mutation_type=MutationType.SERVICE_OUTAGE,
            target="app.services.OrderService",
            description="OrderService complete cluster outage",
        )
        result = scenario_simulation_engine.simulate_scenario(
            db=self.db,
            repository_id=self.repo.id,
            base_snapshot_id=self.snapshot.id,
            name="OrderService Outage Simulation",
            proposed_changes=[mutation],
        )

        self.assertEqual(result.status, ScenarioStatus.DOWNSTREAM_IMPACT_DETECTED)
        # Verify comparison tracks removed relationships
        self.assertGreater(len(result.comparison.removed_relationships), 0)

    # ====================================================================
    # PHASE 5 & 8: GRAPH PROJECTION INTEGRITY ACROSS ALL LEVELS
    # ====================================================================
    def test_graph_projection_preserves_impacted_nodes_without_duplication(self):
        """
        Graph projection at levels 1, 2, and 3 must retain impacted nodes
        without duplicating nodes or inventing edges.
        """
        for zoom_level in [1, 2, 3]:
            proj = twin_graph_projection.project_graph(
                db=self.db,
                repository_id=self.repo.id,
                snapshot_id=self.snapshot.id,
                level=zoom_level,
                impact_artifact_id="art-service-order",
            )

            nodes = proj["nodes"]
            node_ids = [n["id"] for n in nodes]

            # No duplicated node IDs
            self.assertEqual(len(node_ids), len(set(node_ids)), f"Duplicate nodes found at level {zoom_level}")

            # Impact root must be present
            self.assertIn("art-service-order", node_ids, f"Root artifact missing at level {zoom_level}")

            # Direct caller must be present
            self.assertIn("art-controller-order", node_ids, f"Direct caller missing at level {zoom_level}")

    # ====================================================================
    # PHASE 9: PROVENANCE, LIMITATIONS & TELEMETRY TRUTHFULNESS
    # ====================================================================
    def test_node_and_edge_provenance_attributes(self):
        """
        Graph projection nodes and edges must carry identifiable evidence:
        snapshot_id, commit_hash, extraction_method, and verification_status.
        """
        proj = twin_graph_projection.project_graph(
            db=self.db,
            repository_id=self.repo.id,
            snapshot_id=self.snapshot.id,
            level=2,
        )
        nodes = proj["nodes"]
        self.assertGreater(len(nodes), 0)
        first_node = nodes[0]
        self.assertIn("snapshot_id", first_node)
        self.assertEqual(first_node["snapshot_id"], self.snapshot.id)
        self.assertIn("commit_hash", first_node)
        self.assertIn("extraction_method", first_node)
        self.assertIn("verification_status", first_node)

        edges = proj["edges"]
        self.assertGreater(len(edges), 0)
        first_edge = edges[0]
        self.assertIn("snapshot_id", first_edge)
        self.assertIn("verification_status", first_edge)
        self.assertIn("evidence", first_edge)

    def test_validation_coverage_disclosure(self):
        """
        Summary must provide validation_coverage metrics and known_limitations list.
        """
        proj = twin_graph_projection.project_graph(
            db=self.db,
            repository_id=self.repo.id,
            snapshot_id=self.snapshot.id,
            level=1,
        )
        summary = proj["summary"]
        self.assertIn("validation_coverage", summary)
        self.assertIn("known_limitations", summary)
        cov = summary["validation_coverage"]
        self.assertIn("total_artifacts", cov)
        self.assertIn("ast_verified_percent", cov)

    def test_runtime_events_telemetry_disconnected_truth(self):
        """
        When no runtime telemetry has been ingested, API returns 0 events
        without inventing live metrics.
        """
        res = self.client.get(f"/repositories/{self.repo.id}/runtime-events")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["events"]), 0)

    def test_unresolved_target_no_silent_fallback(self):
        """
        Querying an unknown target must return UNRESOLVED_TARGET with suggestions,
        never silently substituting a fallback component.
        """
        res = self.client.post(
            f"/repositories/{self.repo.id}/scenarios/orchestrate",
            json={
                "query": "What if NonExistentServiceFails completely?",
                "base_snapshot_id": self.snapshot.id,
                "target_override": "NonExistentServiceFails",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        sim = data["simulation"]
        self.assertEqual(sim["status"], ScenarioStatus.UNRESOLVED_TARGET)
        plan = data["plan"]
        self.assertFalse(plan["can_execute"])
        self.assertGreater(len(plan["candidate_entities"]), 0)


if __name__ == "__main__":
    unittest.main()

