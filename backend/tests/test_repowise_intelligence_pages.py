import sys
import os

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import unittest
from fastapi.testclient import TestClient
from main import app


class TestRepowiseIntelligencePages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.demo_repo_id = "repo-demo-ecommerce-001"

    def test_stats_by_the_numbers_and_records(self):
        """Verifies GET /{repo}/stats returns 'By the Numbers' and 'Records' matching Repowise."""
        res = self.client.get(f"/repositories/{self.demo_repo_id}/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("by_the_numbers", data)
        btn = data["by_the_numbers"]
        self.assertIn("lines_of_code", btn)
        self.assertIn("scale_moniker", btn)
        self.assertIn("test_ratio_label", btn)
        self.assertIn("root_commit", btn)
        self.assertIn("churn", btn)
        self.assertEqual(btn["scale_moniker"], "City")

        self.assertIn("records", data)
        recs = data["records"]
        self.assertIn("files", recs)
        self.assertIn("functions", recs)
        self.assertIn("commits", recs)
        self.assertIn("largest_file", recs["files"])
        self.assertIn("most_changed_file", recs["files"])
        self.assertIn("longest_function", recs["functions"])
        self.assertIn("documented_symbols", recs["functions"])

    def test_docs_system_map_and_3_column_navigation(self):
        """Verifies GET /{repo}/docs provides 3-column navigation, system map, and related links."""
        res = self.client.get(f"/repositories/{self.demo_repo_id}/docs")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("metadata", data)
        self.assertIn("system_map", data)
        self.assertIn("on_this_page", data)
        self.assertIn("related_items", data)
        self.assertIn("linked_by", data)
        self.assertIsInstance(data["system_map"], list)
        self.assertGreater(len(data["system_map"]), 0)
        self.assertGreater(len(data["on_this_page"]), 0)

    def test_security_hierarchy_and_scan(self):
        """Verifies GET /{repo}/security returns severity-based hierarchy and scanner metadata."""
        res = self.client.get(f"/repositories/{self.demo_repo_id}/security")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("scan_status", data)
        self.assertIn("summary", data)
        self.assertIn("findings", data)
        self.assertIn("scanner_info", data)

        summary = data["summary"]
        self.assertIn("critical", summary)
        self.assertIn("high", summary)
        self.assertIn("medium", summary)
        self.assertIn("low", summary)

        for finding in data["findings"]:
            self.assertIn("id", finding)
            self.assertIn("severity", finding)
            self.assertIn("title", finding)
            self.assertIn("file", finding)
            self.assertIn("evidence", finding)
            self.assertIn("remediation", finding)

    def test_test_reachability_scatter_and_weak_files(self):
        """Verifies GET /{repo}/test-reachability matches Repowise scatter and weak files list."""
        res = self.client.get(f"/repositories/{self.demo_repo_id}/test-reachability")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("summary", data)
        summary = data["summary"]
        self.assertEqual(summary["total_files"], 262)
        self.assertEqual(summary["reached_count"], 3)
        self.assertEqual(summary["weak_unreached_count"], 48)

        self.assertIn("points", data)
        self.assertGreater(len(data["points"]), 0)
        sample_point = data["points"][0]
        self.assertIn("health", sample_point)
        self.assertIn("reached", sample_point)
        self.assertIn("loc", sample_point)

        self.assertIn("weak_unreached_files", data)
        self.assertEqual(len(data["weak_unreached_files"]), 48)


if __name__ == "__main__":
    unittest.main()

