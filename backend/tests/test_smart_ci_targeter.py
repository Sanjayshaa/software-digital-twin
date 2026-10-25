"""
Unit and Integration tests for TwinCore Smart CI Test-Targeter & ROI Exporter.
Verifies CLI command generation, ROI computation, and PR Sticky Markdown formatting.
"""

import unittest
import sys
import os

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest", os.path.abspath(__file__)])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.testing.ci_exporter import (
    generate_ci_test_commands,
    compute_ci_roi_metrics,
    generate_pr_markdown_summary,
)


class TestSmartCITestTargeter(unittest.TestCase):
    def test_generate_ci_test_commands(self):
        sample_affected = [
            {"test_name": "test_checkout_flow", "location": "tests/services/test_orders.py:45"},
            {"test_name": "test_auth_jwt_expiry", "location": "tests/core/test_auth.py:80"},
            {"test_name": "test_payment_intent", "location": "tests/services/test_payment.py:12"},
        ]
        cmds = generate_ci_test_commands(sample_affected)
        
        self.assertIn("pytest", cmds)
        self.assertIn("jest", cmds)
        self.assertIn("gotest", cmds)
        self.assertEqual(cmds["test_count"], 3)
        self.assertIn("tests/services/test_orders.py::test_checkout_flow", cmds["pytest"])
        self.assertIn("tests/core/test_auth.py", cmds["jest"])

    def test_compute_ci_roi_metrics(self):
        roi = compute_ci_roi_metrics(total_catalog_count=100, impacted_test_count=5)
        
        self.assertEqual(roi["total_tests"], 100)
        self.assertEqual(roi["impacted_tests"], 5)
        self.assertEqual(roi["skipped_tests"], 95)
        self.assertEqual(roi["skip_percentage"], 95.0)
        self.assertGreater(roi["time_saved_percentage"], 90.0)
        self.assertGreater(roi["estimated_cost_saved_usd"], 0.0)

    def test_generate_pr_markdown_summary(self):
        sample_impact_data = {
            "summary": {"total_catalog_tests": 50, "potentially_affected_count": 3},
            "affected_tests": [
                {
                    "test_name": "test_user_login",
                    "classification": "DIRECTLY_AFFECTED",
                    "depth": 1,
                    "reason": "Direct reference to changed User model",
                }
            ],
            "unknown_coverage": [],
            "roi_metrics": {
                "total_tests": 50,
                "impacted_tests": 1,
                "skipped_tests": 49,
                "skip_percentage": 98.0,
                "full_suite_duration_seconds": 175.0,
                "targeted_duration_seconds": 3.5,
                "time_saved_seconds": 171.5,
                "time_saved_percentage": 98.0,
                "estimated_cost_saved_usd": 0.0229,
                "speedup_factor": "50.0x",
            },
            "ci_commands": {
                "pytest": "pytest tests/test_auth.py::test_user_login"
            }
        }
        
        pr_md = generate_pr_markdown_summary(
            repository_name="TwinCore-Monorepo",
            base_ref="main",
            head_ref="feature/checkout-v2",
            impact_data=sample_impact_data
        )

        self.assertIn("TwinCore Smart CI Test Intelligence", pr_md)
        self.assertIn("50.0x faster", pr_md)
        self.assertIn("pytest tests/test_auth.py::test_user_login", pr_md)
        self.assertIn("TwinCore-Monorepo", pr_md)


if __name__ == "__main__":
    unittest.main()
