"""
Deterministic Unit Tests for TwinCore Demo Walkthrough & Fixture Engine.

Verifies:
1. Demo repository metadata, language breakdown, and extraction boundaries (Stage 1).
2. Knowledge graph nodes, edges, categories, and verified AST status (Stage 2 & 3).
3. Deterministic blast radius traversal, direct vs indirect classification, and exclusion reasons (Stage 4).
4. What-If scenario simulation, baseline isolation, and virtual twin deltas (Stage 5).
5. Truthful test impact analysis (suggested vs executed vs passed/failed) (Stage 6).
6. Transparent mathematical risk score formula and evidence categories (Stage 7).
7. Final engineering review report generation (Stage 8).
8. Architectural extension points declarations.
"""

import os
import sys
import unittest

# Subshell Python version auto-re-exec guard
if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest", os.path.abspath(__file__)])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app
from app.services.demo.fixture import (
    demo_graph_engine,
    DEMO_REPO_METADATA,
    DEMO_NODES,
    DEMO_EDGES,
    DEMO_SCENARIOS,
    DEMO_TEST_RESULTS,
)


class TestDemoWalkthrough(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_stage_1_repository_discovery_overview(self):
        """GET /api/v1/demo/overview returns complete discovery summary with recognized languages."""
        res = self.client.get("/api/v1/demo/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_demo"])
        repo = data["repository"]
        self.assertEqual(repo["name"], "ecommerce-microservices-reference")
        self.assertIn("discovery_summary", repo)
        summary = repo["discovery_summary"]
        self.assertEqual(summary["total_files"], 48)
        self.assertIn("Python", summary["languages"])
        self.assertIn("TypeScript / React", summary["languages"])
        self.assertIn("SQL", summary["languages"])
        self.assertTrue(summary["is_precomputed_demo"])

    def test_stage_2_and_3_knowledge_graph_consistency(self):
        """GET /api/v1/demo/graph returns all 22 nodes, 22 edges, with verified AST statuses."""
        res = self.client.get("/api/v1/demo/graph")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        nodes = data["nodes"]
        edges = data["edges"]
        self.assertEqual(len(nodes), 22)
        self.assertEqual(len(edges), 22)

        # Check required microservices exist
        node_names = {n["name"] for n in nodes}
        self.assertIn("ApiGateway", node_names)
        self.assertIn("AuthService", node_names)
        self.assertIn("ProductService", node_names)
        self.assertIn("OrderService", node_names)
        self.assertIn("PaymentService", node_names)
        self.assertIn("InventoryService", node_names)

        # Check evidence status is verified
        for n in nodes:
            self.assertEqual(n["evidence_status"], "VERIFIED_AST")

    def test_stage_4_blast_radius_traversal_payment_service(self):
        """POST /api/v1/demo/blast-radius computes direct and indirect caller reachability."""
        res = self.client.post("/api/v1/demo/blast-radius", json={"root_identifier": "art-payment"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        result = data["result"]
        self.assertEqual(result["status"], "DOWNSTREAM_IMPACT_DETECTED")
        self.assertEqual(result["root_entity"]["name"], "PaymentService")

        # Directly affected (Depth 1)
        direct_names = {d["name"] for d in result["directly_affected"]}
        self.assertIn("OrderService", direct_names)
        self.assertIn("POST /api/v1/payments/charge", direct_names)
        self.assertIn("test_process_payment", direct_names)

        # Indirectly affected (Depth 2 & 3)
        indirect_names = {d["name"] for d in result["indirectly_affected"]}
        self.assertIn("POST /api/v1/orders", indirect_names)
        self.assertIn("POST /api/v1/checkout", indirect_names)
        self.assertIn("ApiGateway", indirect_names)

        # Excluded unaffected entities
        excluded_names = {e["name"] for e in result["excluded_entities"]}
        self.assertIn("ProductService", excluded_names)
        self.assertIn("AuthService", excluded_names)
        self.assertIn("InventoryService", excluded_names)

        # Check exclusion reasons are explicit
        for excl in result["excluded_entities"]:
            self.assertTrue(len(excl["exclusion_reason"]) > 10)

    def test_stage_5_what_if_simulation_service_outage(self):
        """POST /api/v1/demo/simulate runs isolated virtual twin simulation."""
        res = self.client.post("/api/v1/demo/simulate", json={"scenario_id": "SCENARIO_SERVICE_OUTAGE"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        scenario = data["scenario"]
        self.assertEqual(scenario["mutation_type"], "SERVICE_OUTAGE")
        self.assertEqual(scenario["target"], "services.payment.PaymentService")

        delta = data["virtual_twin_delta"]
        self.assertTrue(delta["is_baseline_stationary"])
        self.assertGreater(delta["affected_components_count"], 0)
        self.assertEqual(delta["risk_breakdown"]["overall_score"], 70.0)

    def test_stage_5_what_if_zero_impact_component_removal(self):
        """POST /api/v1/demo/simulate on isolated leaf produces verified zero impact."""
        res = self.client.post("/api/v1/demo/simulate", json={"scenario_id": "SCENARIO_COMPONENT_REMOVAL"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        blast = data["blast_radius"]
        self.assertEqual(blast["total_affected"], 0)
        self.assertEqual(blast["status"], "VERIFIED_ZERO_IMPACT")
        self.assertEqual(data["virtual_twin_delta"]["risk_breakdown"]["structural_impact_score"], 0.0)

    def test_stage_6_truthful_test_impact_status(self):
        """GET /api/v1/demo/test-impact returns truthful test execution metrics without fabrication."""
        res = self.client.get("/api/v1/demo/test-impact?scenario_id=SCENARIO_SERVICE_OUTAGE")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        impact = data["test_impact"]
        self.assertEqual(impact["execution_summary"]["total_executed"], 3)
        self.assertEqual(impact["execution_summary"]["passed"], 1)
        self.assertEqual(impact["execution_summary"]["failed"], 2)
        self.assertTrue(impact["execution_summary"]["is_precomputed_demo_data"])

        # Check unexecuted tests are recorded
        self.assertEqual(len(impact["unexecuted_tests"]), 3)
        unexec_reasons = [u["reason"] for u in impact["unexecuted_tests"]]
        self.assertTrue(any("AuthService outside blast radius" in r for r in unexec_reasons))

    def test_stage_7_and_8_final_audit_report(self):
        """GET /api/v1/demo/report synthesizes formal engineering report with action items."""
        res = self.client.get("/api/v1/demo/report?scenario_id=SCENARIO_SERVICE_OUTAGE")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        report = data["report"]
        self.assertEqual(report["verification_status"], "VERIFIED_PASS")
        self.assertEqual(report["scenario_title"], "Payment Service Cluster Outage")
        self.assertIn("pytest tests/test_payment.py", report["actionable_next_steps"][0])
        self.assertIn("risk_evaluation", report)

    def test_web_demo_route_serves_html(self):
        """GET /demo serves the web UI index.html."""
        res = self.client.get("/demo")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
