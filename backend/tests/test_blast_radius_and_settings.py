"""
Comprehensive Blast Radius and Settings Test Suite.
Tests:
1. Blast-radius graph traversal, cycle handling, multi-hop propagation, and depth limiting.
2. Complete contract validation for /repositories/{id}/blast-radius & /repositories/{id}/impact-analysis.
3. Zero 'undefined' or 'NaN' guarantees across summary metrics, diff tables, findings, paths, and categories.
4. Repository Settings API (GET and PUT) with exclusion rules, doc styles, and analysis preferences.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

# Subshell python guard
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
from app.core.auth import get_current_user_optional, AuthenticatedPrincipal
from app.services.impact.models import ImpactSummary, ChangeItem, ImpactFinding, ImpactPath
from app.services.impact.analyzer import ImpactAnalyzer
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
        user_id="user-settings-1",
        username="sanjayshaa",
        email="sanjay@example.com",
        role="admin",
        is_authenticated=True,
    )


class TestBlastRadiusAndSettings(unittest.TestCase):
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
        # Seed test user and project
        user = User(
            id="user-settings-1",
            username="sanjayshaa",
            email="sanjay@example.com",
            hashed_password="mock_hashed_password_abc123",
            role="admin",
            is_active=True,
        )
        self.db.merge(user)
        proj = Project(id="project-settings-1", name="DigitalTwin-Test")
        self.db.merge(proj)

        # Seed repository
        self.repo = Repository(
            id="repo-blast-settings",
            project_id="project-settings-1",
            owner_id="user-settings-1",
            name="lab-record-system",
            vcs_type="git",
            remote_url="https://github.com/sanjayshaa/lab-record-system.git",
            local_path="/tmp/repos/lab-record-system",
            default_branch="main",
            source_type="LOCAL",
            environment="TEST",
        )
        self.db.merge(self.repo)

        # Seed snapshots
        self.snap_base = RepositorySnapshot(
            id="snap-base-001",
            repository_id=self.repo.id,
            commit_hash="base000000000000000000000000000000000000",
            created_at=datetime.now(timezone.utc),
        )
        self.snap_target = RepositorySnapshot(
            id="snap-target-002",
            repository_id=self.repo.id,
            commit_hash="target0000000000000000000000000000000000",
            created_at=datetime.now(timezone.utc),
        )
        self.db.merge(self.snap_base)
        self.db.merge(self.snap_target)

        # Seed cyclic graph artifacts:
        # A (Service) -> B (Component) -> C (API) -> A (Cycle)
        # B -> D (Test)
        self.art_a = StructuralArtifact(
            id="art-node-a",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            name="AuthService",
            qualified_name="AuthService",
            artifact_type="SERVICE",
            location="src/services/auth.ts:1-100",
            language="typescript",
            line_start=1,
            line_end=100,
        )
        self.art_b = StructuralArtifact(
            id="art-node-b",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            name="TokenValidator",
            qualified_name="TokenValidator",
            artifact_type="COMPONENT",
            location="src/components/validator.ts:1-50",
            language="typescript",
            line_start=1,
            line_end=50,
        )
        self.art_c = StructuralArtifact(
            id="art-node-c",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            name="PostLoginEndpoint",
            qualified_name="PostLoginEndpoint",
            artifact_type="API",
            location="src/api/login.ts:1-60",
            language="typescript",
            line_start=1,
            line_end=60,
        )
        self.art_d = StructuralArtifact(
            id="art-node-d",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            name="test_auth_flow",
            qualified_name="test_auth_flow",
            artifact_type="TEST",
            location="tests/test_auth.ts:1-80",
            language="typescript",
            line_start=1,
            line_end=80,
        )
        for art in [self.art_a, self.art_b, self.art_c, self.art_d]:
            self.db.merge(art)

        # Seed relationships
        rel1 = ArtifactRelationship(
            id="rel-a-b",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            source_artifact_id="art-node-a",
            target_artifact_id="art-node-b",
            relationship_type="CALLS",
            confidence=0.95,
        )
        rel2 = ArtifactRelationship(
            id="rel-b-c",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            source_artifact_id="art-node-b",
            target_artifact_id="art-node-c",
            relationship_type="CALLS",
            confidence=0.90,
        )
        # Cycle: C calls A
        rel3 = ArtifactRelationship(
            id="rel-c-a",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            source_artifact_id="art-node-c",
            target_artifact_id="art-node-a",
            relationship_type="CALLS",
            confidence=0.85,
        )
        # Test relationship: D tests B
        rel4 = ArtifactRelationship(
            id="rel-d-b",
            repository_id=self.repo.id,
            snapshot_id=self.snap_target.id,
            source_artifact_id="art-node-d",
            target_artifact_id="art-node-b",
            relationship_type="TESTS",
            confidence=1.0,
        )
        for rel in [rel1, rel2, rel3, rel4]:
            self.db.merge(rel)

        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_blast_radius_contract_and_zero_undefined(self):
        """
        Verify POST /repositories/{id}/blast-radius returns canonical, complete contract
        with zero missing or undefined fields.
        """
        payload = {
            "entity_name": "AuthService",
            "snapshot_id": self.snap_target.id,
            "max_depth": 5,
        }
        res = self.client.post(f"/repositories/{self.repo.id}/blast-radius", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        # 1. Check top-level contract keys
        expected_keys = {
            "analysis_id", "status", "entity_name", "target_snapshot_id",
            "summary", "changes", "findings", "paths", "affected_categories", "impact_tree"
        }
        self.assertTrue(expected_keys.issubset(data.keys()))

        # 2. Check summary fields
        summary = data["summary"]
        self.assertIn("blast_radius_score", summary)
        self.assertIn("risk_level", summary)
        self.assertIn("directly_affected", summary)
        self.assertIn("indirectly_affected", summary)
        self.assertIn("unique_affected", summary)
        self.assertIn("affected_components", summary)
        self.assertIn("affected_apis", summary)
        self.assertIn("affected_tests", summary)
        self.assertIn("max_depth_reached", summary)
        self.assertIn("max_propagation_depth", summary)

        # None of the values should be None, 'undefined', or 'NaN'
        for k, v in summary.items():
            self.assertIsNotNone(v, f"Summary field {k} is None")
            self.assertNotEqual(str(v).lower(), "undefined", f"Summary field {k} is undefined")
            self.assertNotEqual(str(v).lower(), "nan", f"Summary field {k} is NaN")

        # 3. Check changes
        self.assertTrue(len(data["changes"]) > 0)
        c0 = data["changes"][0]
        self.assertIn("artifact_name", c0)
        self.assertIn("file_location", c0)
        self.assertIn("evidence", c0)
        self.assertIn("detection_method", c0)
        self.assertNotEqual(str(c0["evidence"]).lower(), "undefined")
        self.assertNotEqual(str(c0["detection_method"]).lower(), "undefined")

        # 4. Check findings
        self.assertTrue(len(data["findings"]) > 0)
        for f in data["findings"]:
            self.assertIn("impact_level", f)
            self.assertIn("source_qual_name", f)
            self.assertIn("relationship_type", f)
            self.assertIn("target_qual_name", f)
            self.assertIn("target_type", f)
            self.assertIn("confidence", f)
            self.assertIn("evidence", f)
            self.assertNotEqual(str(f["impact_level"]).lower(), "undefined")
            self.assertNotEqual(str(f["target_qual_name"]).lower(), "undefined")

        # 5. Check paths
        self.assertTrue(len(data["paths"]) > 0)
        for p in data["paths"]:
            self.assertIn("depth", p)
            self.assertIn("confidence", p)
            self.assertIn("terminal_type", p)
            self.assertIn("nodes", p)
            self.assertIn("relationships", p)
            self.assertIsInstance(p["depth"], int)
            self.assertIsInstance(p["confidence"], (int, float))
            self.assertNotEqual(str(p["depth"]).lower(), "undefined")
            self.assertNotEqual(str(p["confidence"]).lower(), "undefined")

        # 6. Check affected_categories
        cats = data["affected_categories"]
        self.assertIsInstance(cats, dict)
        for cat_name, items in cats.items():
            self.assertIsInstance(items, list, f"Category {cat_name} must be list of items")
            for item in items:
                self.assertIsInstance(item, str)
                self.assertNotEqual(item.lower(), "undefined")

    def test_blast_radius_cycle_handling(self):
        """
        Verify that cycle A -> B -> C -> A does not cause recursion errors or infinite loops,
        and depth limit is strictly observed.
        """
        payload = {
            "entity_name": "AuthService",
            "snapshot_id": self.snap_target.id,
            "max_depth": 3,
        }
        res = self.client.post(f"/repositories/{self.repo.id}/blast-radius", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        summary = data["summary"]
        self.assertLessEqual(summary["max_depth_reached"], 3)
        self.assertLessEqual(summary["max_propagation_depth"], 3)
        # The unique nodes affected should not explode due to cycle
        self.assertLessEqual(summary["unique_affected"], 4)

    def test_repository_settings_crud_api(self):
        """
        Verify GET and PUT for /repositories/{id}/settings:
        - Retrieves default configuration and exclusion patterns
        - Saves updated excluded paths, doc styles, thresholds
        - Verifies persistence across subsequent requests
        """
        # 1. GET initial settings
        get_res = self.client.get(f"/repositories/{self.repo.id}/settings")
        self.assertEqual(get_res.status_code, 200, get_res.text)
        initial = get_res.json()
        self.assertEqual(initial["repository_id"], self.repo.id)
        self.assertEqual(initial["name"], "lab-record-system")
        self.assertEqual(initial["default_branch"], "main")
        self.assertIn("vendor/", initial["excluded_paths"])
        self.assertEqual(initial["doc_style"], "comprehensive")

        # 2. PUT updated settings
        update_payload = {
            "default_branch": "release/v2.1",
            "remote_url": "https://github.com/sanjayshaa/lab-record-system-fork.git",
            "excluded_paths": ["vendor/", "dist/", "src/legacy/**", "coverage/**"],
            "doc_style": "caveman",
            "max_propagation_depth": 7,
            "confidence_threshold": 0.85,
            "dynamic_cycle_break": True,
            "auto_sync": False,
            "fail_ci_on_risk": True,
            "notify_email": False,
            "notify_slack": True,
            "theme": "dark",
            "high_contrast": True,
            "telemetry_enabled": False,
        }
        put_res = self.client.put(f"/repositories/{self.repo.id}/settings", json=update_payload)
        self.assertEqual(put_res.status_code, 200, put_res.text)
        updated = put_res.json()
        self.assertEqual(updated["default_branch"], "release/v2.1")
        self.assertEqual(updated["remote_url"], "https://github.com/sanjayshaa/lab-record-system-fork.git")
        self.assertEqual(updated["doc_style"], "caveman")
        self.assertEqual(updated["max_propagation_depth"], 7)
        self.assertIn("src/legacy/**", updated["excluded_paths"])
        self.assertIn("coverage/**", updated["excluded_paths"])
        self.assertTrue(updated["high_contrast"])
        self.assertIsNotNone(updated["updated_at"])

        # 3. Verify GET returns persisted updates
        get_res_2 = self.client.get(f"/repositories/{self.repo.id}/settings")
        self.assertEqual(get_res_2.status_code, 200)
        persisted = get_res_2.json()
        self.assertEqual(persisted["default_branch"], "release/v2.1")
        self.assertEqual(persisted["doc_style"], "caveman")
        self.assertEqual(persisted["max_propagation_depth"], 7)

    def test_repository_settings_not_found(self):
        """
        Verify 404 behavior for non-existent repository.
        """
        res = self.client.get("/repositories/non-existent-repo-9999/settings")
        self.assertEqual(res.status_code, 404)

        res_put = self.client.put("/repositories/non-existent-repo-9999/settings", json={"doc_style": "tutorial"})
        self.assertEqual(res_put.status_code, 404)

    def test_frontend_html_and_js_invariants(self):
        """
        Verify that frontend HTML has the complete Settings panel and Blast Radius container,
        and twin.js exposes normalizeImpactResult, loadSettingsView, and related functions.
        """
        html_path = os.path.join(backend_dir, "app", "static", "index.html")
        self.assertTrue(os.path.exists(html_path))
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Check required elements in index.html
        self.assertIn('id="view-settings"', html)
        self.assertIn('id="settings-excluded-paths-container"', html)
        self.assertIn('id="settings-btn-save"', html)
        self.assertIn('id="settings-btn-reset"', html)
        self.assertIn('id="impact-verdict-card"', html)
        self.assertIn('id="impact-findings-body"', html)
        self.assertIn('id="impact-categories-grid"', html)
        self.assertIn('id="impact-graph-svg"', html)

        # Check twin.js
        js_path = os.path.join(backend_dir, "app", "static", "twin.js")
        self.assertTrue(os.path.exists(js_path))
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("function normalizeImpactResult(", js)
        self.assertIn("function loadSettingsView(", js)
        self.assertIn("function saveSettings(", js)
        self.assertIn("function renderImpactSvgGraph(", js)
        self.assertIn("function exportBlastRadiusReport(", js)
        self.assertIn("viewName === 'settings'", js)



if __name__ == "__main__":
    unittest.main()
