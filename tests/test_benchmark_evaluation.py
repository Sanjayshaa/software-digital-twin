"""
Controlled Benchmark Evaluation Regression Suite.
Automated validation of Digital Twin engines against the isolated synthetic_shop fixture.
Ensures zero-regression on Git history, change impact, test selection, what-if simulation,
risk intelligence, and negative control safety guardrails.
"""

import os
import sys
import unittest

# Ensure backend and venv site-packages are accessible
BACKEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

VENV_SITE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python3.12", "site-packages"))
if os.path.isdir(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

try:
    from app.core.database import SessionLocal
    from app.evaluation.benchmark_lab import benchmark_lab_service
    from app.evaluation.ground_truth import BENCHMARK_SCENARIOS, GROUND_TRUTH_DIR
    from fastapi.testclient import TestClient
    from main import app
    DEPS_LOADED = True
except ImportError:
    DEPS_LOADED = False


class TestBenchmarkEvaluationRegression(unittest.TestCase):
    """
    Regression test suite for the Controlled Benchmark Evaluation Lab.
    """

    @classmethod
    def setUpClass(cls):
        if DEPS_LOADED:
            cls.db = SessionLocal()
            cls.client = TestClient(app)
        else:
            cls.db = None
            cls.client = None

    @classmethod
    def tearDownClass(cls):
        if cls.db:
            cls.db.close()

    def test_00_subprocess_runner_if_deps_missing(self):
        """If run under an unconfigured Python environment, re-executes cleanly inside project virtualenv."""
        if not DEPS_LOADED:
            import subprocess
            venv_python = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python"))
            if os.path.isfile(venv_python):
                res = subprocess.run([venv_python, "-m", "unittest", __file__], capture_output=True, text=True)
                print(res.stdout)
                print(res.stderr)
                self.assertEqual(res.returncode, 0, f"Venv unittest failed: {res.stderr}")
            else:
                self.skipTest("Virtualenv not found and dependencies not loaded.")

    def test_01_fixture_integrity(self):
        """Validates that the synthetic fixture exists with all 8 commits, 3 tags, and branches."""
        if not DEPS_LOADED:
            self.skipTest("Handled by test_00_subprocess_runner_if_deps_missing")
        manifest = benchmark_lab_service.ensure_fixture()
        self.assertIsNotNone(manifest)
        self.assertGreaterEqual(manifest["total_commits"], 8)
        for tag in ["v1.0.0", "v1.1.0-defect", "v1.1.1"]:
            self.assertIn(tag, manifest["tags"])
        self.assertTrue(os.path.isdir(manifest["fixture_path"]))

    def test_02_ground_truth_isolation(self):
        """Verifies ground truth rules and negative control definitions are immutable and isolated."""
        if not DEPS_LOADED:
            self.skipTest("Handled by test_00_subprocess_runner_if_deps_missing")
        self.assertEqual(len(BENCHMARK_SCENARIOS), 5)
        for scen_id, scen in BENCHMARK_SCENARIOS.items():
            self.assertTrue(scen_id.startswith("SCENARIO_"))
            self.assertGreater(len(scen["expected_direct_impact"]), 0)
            self.assertGreater(len(scen["negative_controls"]), 0)
            self.assertIn("risk_expectation", scen)

    def test_03_history_and_snapshot_lifecycle(self):
        """Executes all 10 History and Snapshot lifecycle tests."""
        if not DEPS_LOADED:
            self.skipTest("Handled by test_00_subprocess_runner_if_deps_missing")
        report = benchmark_lab_service.run_history_and_snapshot_tests(self.db)
        self.assertEqual(report["total_tests"], 10)
        self.assertEqual(report["passed_tests"], 10)
        self.assertEqual(report["failed_tests"], 0)
        self.assertTrue(report["all_passed"])

    def test_04_payment_scenario_evaluation(self):
        """Evaluates SCENARIO_PAYMENT_FEE_MODIFICATION against production TwinCore engines."""
        if not DEPS_LOADED:
            self.skipTest("Handled by test_00_subprocess_runner_if_deps_missing")
        report = benchmark_lab_service.run_scenario(self.db, "SCENARIO_PAYMENT_FEE_MODIFICATION")
        self.assertTrue(report["is_synthetic_benchmark"])
        # Negative controls must have 0 violations
        self.assertTrue(report["negative_controls"]["passed"])
        self.assertEqual(len(report["negative_controls"]["violations"]), 0)
        # Architecture graph edges must be 100% valid
        self.assertEqual(report["architecture_graph"]["edge_validity_percent"], 100.0)
        # Impact analysis must have discovered changes
        self.assertGreater(report["impact_analysis"]["total_changes"], 0)

    def test_05_api_endpoints(self):
        """Verifies the Benchmark Evaluation Lab API endpoints."""
        if not DEPS_LOADED:
            self.skipTest("Handled by test_00_subprocess_runner_if_deps_missing")
        # GET /api/v1/evaluation/scenarios
        r_scen = self.client.get("/api/v1/evaluation/scenarios")
        self.assertEqual(r_scen.status_code, 200)
        scen_data = r_scen.json()
        self.assertTrue(scen_data["is_synthetic_benchmark"])
        self.assertEqual(scen_data["total_scenarios"], 5)

        # GET /api/v1/evaluation/summary
        r_sum = self.client.get("/api/v1/evaluation/summary")
        self.assertEqual(r_sum.status_code, 200)
        sum_data = r_sum.json()
        self.assertTrue(sum_data["is_synthetic_benchmark"])
        self.assertIn("SYNTHETIC BENCHMARK LAB", sum_data["provenance_statement"])


if __name__ == "__main__":
    unittest.main()
