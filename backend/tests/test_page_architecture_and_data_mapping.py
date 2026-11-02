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

class TestPageArchitectureAndDataMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.demo_repo_id = "repo-demo-ecommerce-001"

    def test_report_endpoint_demo_payload(self):
        """Verifies GET /{repo_id}/report returns whole-repo architecture report without duplicating Overview."""
        response = self.client.get(f"/repositories/{self.demo_repo_id}/report")
        self.assertEqual(response.status_code, 200, f"Failed: {response.text}")
        data = response.json()
        
        self.assertIn("repository", data)
        self.assertEqual(data["repository"]["id"], self.demo_repo_id)

        # Verify mandatory architecture report keys
        expected_keys = [
            "repository", "project_purpose", "tech_stack", "scale_and_metrics",
            "startup_flow", "architecture_layers", "important_files",
            "key_dependencies", "database_entities", "limitations_and_coverage", "report_markdown"
        ]
        for key in expected_keys:
            self.assertIn(key, data, f"Missing key in report data: {key}")
            
        # Verify developer report content quality
        self.assertIsInstance(data["architecture_layers"], list)
        self.assertGreater(len(data["architecture_layers"]), 0)
        self.assertIsInstance(data["important_files"], list)
        self.assertGreater(len(data["important_files"]), 0)
        self.assertIn("# repository architecture analysis report", data["report_markdown"].lower())
        self.assertIn("## 1. application purpose", data["report_markdown"].lower())
        self.assertNotIn("{{", data["report_markdown"])  # No raw template leaks

    def test_docs_endpoint_demo_payload(self):
        """Verifies GET /{repo_id}/docs returns living documentation with routes, models, services."""
        response = self.client.get(f"/repositories/{self.demo_repo_id}/docs")
        self.assertEqual(response.status_code, 200, f"Failed: {response.text}")
        data = response.json()

        self.assertIn("repository", data)
        self.assertEqual(data["repository"]["id"], self.demo_repo_id)

        expected_keys = [
            "repository", "project_purpose", "folder_guide",
            "startup_flows", "routes_and_apis", "services_and_logic",
            "database_structures", "config_and_env", "inferred_notes"
        ]
        for key in expected_keys:
            self.assertIn(key, data, f"Missing key in docs data: {key}")

        # Ensure docs has distinct structured sections
        self.assertIsInstance(data["folder_guide"], list)
        self.assertIsInstance(data["routes_and_apis"], list)
        self.assertIsInstance(data["database_structures"], list)
        self.assertGreater(len(data["routes_and_apis"]), 0)

    def test_stats_endpoint_demo_payload_and_separation(self):
        """Verifies GET /{repo_id}/stats returns empirical evidence and does NOT duplicate Discovery health."""
        response = self.client.get(f"/repositories/{self.demo_repo_id}/stats")
        self.assertEqual(response.status_code, 200, f"Failed: {response.text}")
        data = response.json()

        self.assertIn("repository", data)
        self.assertEqual(data["repository"]["id"], self.demo_repo_id)

        # Must contain timeline, work patterns, project records, analysis coverage
        expected_keys = [
            "repository", "size_and_composition", "timeline",
            "work_patterns", "project_records", "analysis_coverage"
        ]
        for key in expected_keys:
            self.assertIn(key, data, f"Missing key in stats data: {key}")

        timeline = data["timeline"]
        self.assertIn("earliest_commit_date", timeline)
        self.assertIn("earliest_commit_hash", timeline)
        self.assertIn("latest_commit_date", timeline)
        self.assertIn("history_span_days", timeline)

        work = data["work_patterns"]
        self.assertIn("commits_by_day_of_week", work)
        self.assertIn("commits_by_hour_of_day", work)

        cov = data["analysis_coverage"]
        self.assertIn("unanalyzed_file_types", cov)

        # Explicit non-duplication check: Stats must NOT contain Discovery Health scorecards
        self.assertNotIn("score_breakdown", data)
        self.assertNotIn("overall_score", data)
        self.assertNotIn("maturity_grade", data)

    def test_frontend_ui_elements_integrity(self):
        """Validates that index.html contains required toggle, search bar, and distinct page sections."""
        html_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Top of sidebar toggle pill
        self.assertIn('id="btn-sidebar-toggle"', html)
        self.assertIn('sidebar-toggle-pill', html)
        self.assertIn('sidebar-collapse-icon', html)

        # Compact Search bar matching reference (Search twin graphs, artifacts... ⌘K)
        self.assertIn('id="top-search-btn"', html)
        self.assertIn('Search twin graphs, artifacts...', html)
        self.assertIn('⌘K', html)

        # Mobile drawer support
        self.assertIn('id="sidebar-backdrop"', html)
        self.assertIn('id="btn-sidebar-mobile-toggle"', html)

        # Distinct views for Report, Docs, and Stats
        self.assertIn('id="view-report"', html)
        self.assertIn('id="btn-copy-report-md"', html)
        self.assertIn('id="btn-download-report-md"', html)

        self.assertIn('id="view-docs"', html)
        self.assertIn('docs-nav-item', html)

        self.assertIn('id="view-stats"', html)
        self.assertIn('id="stats-earliest-date"', html)
        self.assertIn('id="stats-history-span"', html)

    def test_frontend_js_and_css_integrity(self):
        """Validates that twin.js and twin.css contain distinct view loaders, collapse styling, and dark theme."""
        js_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "twin.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("loadReportView", js)
        self.assertIn("copyReportMarkdown", js)
        self.assertIn("downloadReportMarkdown", js)
        self.assertIn("loadDocsView", js)
        self.assertIn("loadStatsView", js)
        self.assertIn("renderDocsCategoryContent", js)

        css_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "twin.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("body.sidebar-desktop-collapsed", css)
        self.assertIn(".sidebar-toggle-pill", css)
        self.assertIn("html.dark body", css)

if __name__ == "__main__":
    unittest.main()
