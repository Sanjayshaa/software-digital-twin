"""
Test Project Architecture at a Glance & Overview Layout Data Integrity.
Verifies:
1. extract_project_architecture_glance excludes low-value/generic tokens (root, path, pathlib, shutil, HEADER_PATTERN).
2. Proper detection of layers (frontend, api, services, storage, external).
3. Honest reporting of empty/unknown states without guessing or fabricating data.
4. Correct linkage data (locations, node_ids, entry point roles).
"""

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
from unittest.mock import MagicMock
from app.models.entities import StructuralArtifact, ArtifactRelationship
from app.services.discovery.project_overview import extract_project_architecture_glance


class TestArchitectureGlanceAndOverview(unittest.TestCase):

    def test_01_excludes_generic_stdlib_and_folder_tokens(self):
        """Verify generic tokens such as root, path, pathlib, shutil, target, HEADER_PATTERN are excluded."""
        generic_names = ["root", "path", "pathlib", "shutil", "target", "HEADER_PATTERN", "os", "sys", "re", "json"]
        artifacts = []
        for i, name in enumerate(generic_names):
            art = StructuralArtifact(
                id=f"art-gen-{i}",
                repository_id="repo-1",
                snapshot_id="snap-1",
                artifact_type="CLASS" if i % 2 == 0 else "MODULE",
                language="python",
                name=name,
                qualified_name=f"lib.{name}",
                location=f"lib/{name}.py:1",
                metadata_payload={},
            )
            artifacts.append(art)

        # Also add one genuine component
        genuine = StructuralArtifact(
            id="art-real-order",
            repository_id="repo-1",
            snapshot_id="snap-1",
            artifact_type="SERVICE",
            language="python",
            name="OrderProcessingService",
            qualified_name="app.services.order.OrderProcessingService",
            location="backend/app/services/order.py:10",
            metadata_payload={},
        )
        artifacts.append(genuine)

        res = extract_project_architecture_glance(repo_path=None, artifacts=artifacts, relationships=[])
        
        # Check that generic tokens are NOT in major_components
        major_names = [c["name"] for c in res["major_components"]]
        for g in generic_names:
            self.assertNotIn(g, major_names, f"Generic token '{g}' should be excluded from major components")
        
        # Genuine component must be present
        self.assertIn("OrderProcessingService", major_names)

    def test_02_detects_boundaries_accurately_with_real_artifacts(self):
        """Verify layer detection for API, Service, and Storage boundaries."""
        artifacts = [
            StructuralArtifact(
                id="art-api-1",
                repository_id="repo-1",
                snapshot_id="snap-1",
                artifact_type="API_ENDPOINT",
                language="python",
                name="POST /api/v1/checkout",
                qualified_name="app.api.checkout.post_checkout",
                location="app/api/checkout.py:25",
                metadata_payload={"method": "POST", "path": "/api/v1/checkout"},
            ),
            StructuralArtifact(
                id="art-svc-1",
                repository_id="repo-1",
                snapshot_id="snap-1",
                artifact_type="SERVICE",
                language="python",
                name="PaymentService",
                qualified_name="app.services.payment.PaymentService",
                location="app/services/payment.py:15",
                metadata_payload={},
            ),
            StructuralArtifact(
                id="art-db-1",
                repository_id="repo-1",
                snapshot_id="snap-1",
                artifact_type="DATABASE_ENTITY",
                language="python",
                name="TransactionRecord",
                qualified_name="app.models.transaction.TransactionRecord",
                location="app/models/transaction.py:10",
                metadata_payload={},
            ),
        ]

        relationships = [
            ArtifactRelationship(
                id="rel-1",
                repository_id="repo-1",
                snapshot_id="snap-1",
                source_artifact_id="art-api-1",
                target_artifact_id="art-svc-1",
                relationship_type="CALLS",
            ),
            ArtifactRelationship(
                id="rel-2",
                repository_id="repo-1",
                snapshot_id="snap-1",
                source_artifact_id="art-svc-1",
                target_artifact_id="art-db-1",
                relationship_type="PERSISTS",
            ),
        ]

        res = extract_project_architecture_glance(repo_path=None, artifacts=artifacts, relationships=relationships)

        self.assertTrue(res["has_architecture"])
        self.assertEqual(res["layers"]["api"]["status"], "DETECTED")
        self.assertEqual(res["layers"]["api"]["count"], 1)
        self.assertEqual(res["layers"]["services"]["status"], "DETECTED")
        self.assertEqual(res["layers"]["services"]["count"], 1)
        self.assertEqual(res["layers"]["storage"]["status"], "DETECTED")
        self.assertEqual(res["layers"]["storage"]["count"], 1)
        # Frontend was not present in fixture: must be NOT_DETECTED
        self.assertEqual(res["layers"]["frontend"]["status"], "NOT_DETECTED")
        self.assertEqual(res["layers"]["frontend"]["count"], 0)

        # Verify key flows were captured
        self.assertEqual(len(res["key_flows"]), 2)
        flow1 = res["key_flows"][0]
        self.assertEqual(flow1["source"]["name"], "POST /api/v1/checkout")
        self.assertEqual(flow1["target"]["name"], "PaymentService")
        self.assertEqual(flow1["relation"], "CALLS")

    def test_03_empty_and_unknown_state_honest_disclosure(self):
        """Verify empty repository produces honest NOT_DETECTED / unknown states."""
        res = extract_project_architecture_glance(repo_path=None, artifacts=[], relationships=[])
        self.assertFalse(res["has_architecture"])
        self.assertEqual(res["architecture_style"], "Unknown / Not detected")
        self.assertEqual(res["summary"]["detected_layers_count"], 0)
        self.assertEqual(len(res["entry_points"]), 0)
        self.assertEqual(len(res["major_components"]), 0)
        self.assertEqual(len(res["key_flows"]), 0)
        for layer_key, layer_val in res["layers"].items():
            self.assertEqual(layer_val["status"], "NOT_DETECTED")
            self.assertEqual(layer_val["count"], 0)

    def test_04_overview_api_contract_includes_architecture_glance(self):
        """Verify get_repository_overview endpoint includes architecture_glance in its response."""
        from app.api.graph import get_repository_overview

        # Mock db session and request for demo repo
        mock_db = MagicMock()

        overview = get_repository_overview(
            repository_id="repo-demo-ecommerce-001",
            snapshot_id=None,
            db=mock_db,
            principal=None,
        )
        self.assertIn("architecture_glance", overview)
        glance = overview["architecture_glance"]
        self.assertTrue(glance["has_architecture"])
        self.assertIn("layers", glance)
        self.assertIn("frontend", glance["layers"])
        self.assertIn("api", glance["layers"])
        self.assertIn("services", glance["layers"])
        self.assertIn("storage", glance["layers"])
        self.assertIn("entry_points", glance)
        self.assertIn("major_components", glance)
        self.assertIn("key_flows", glance)

    def test_05_static_files_integrity_and_removal_of_macro_packages(self):
        """Verify index.html and twin.js have Project Architecture at a Glance and removed Macro Architecture Packages."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        index_html_path = os.path.join(root_dir, "backend", "app", "static", "index.html")
        twin_js_path = os.path.join(root_dir, "backend", "app", "static", "twin.js")

        self.assertTrue(os.path.exists(index_html_path), "index.html must exist")
        self.assertTrue(os.path.exists(twin_js_path), "twin.js must exist")

        with open(index_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # index.html must have the new architecture glance section
        self.assertIn('id="ov-architecture-glance"', html_content)
        self.assertIn('Project Architecture at a Glance', html_content)
        self.assertIn('id="ov-layers-grid"', html_content)
        self.assertIn('id="ov-entry-points-list"', html_content)
        self.assertIn('id="ov-major-components-list"', html_content)
        self.assertIn('id="ov-flows-grid"', html_content)

        # index.html must NOT have the old Macro Architecture Packages
        self.assertNotIn('Macro Architecture Packages', html_content)
        self.assertNotIn('id="ov-packages-grid"', html_content)

        # index.html Section 5 must be balanced 6/6
        self.assertIn('<!-- LEFT: Recent Changes & Verified Impact (6 cols) -->', html_content)
        self.assertIn('<!-- RIGHT: Operational Status & Telemetry Stream (6 cols) -->', html_content)

        with open(twin_js_path, "r", encoding="utf-8") as f:
            js_content = f.read()

        # twin.js must define the new renderer and navigation helper
        self.assertIn("function renderProjectArchitectureGlance", js_content)
        self.assertIn("function navigateToArchitectureSymbol", js_content)
        self.assertIn("navigateToArchitectureSymbol,", js_content)
        self.assertIn("renderProjectArchitectureGlance,", js_content)


if __name__ == "__main__":
    unittest.main()
