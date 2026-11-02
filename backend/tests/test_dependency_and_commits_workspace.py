"""Tests for TwinCore Dependency Intelligence and Commits & History Workspace."""

import os
import sys

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app
from app.services.impact.change_detector import ChangeDetector, ChangeType, ChangeItem
from app.models.entities import StructuralArtifact


class TestDependencyAndCommitsWorkspace(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_dependency_map_endpoint_structure(self):
        """Verify GET /repositories/{id}/dependency-map returns Repowise clusters & health scores."""
        resp = self.client.get("/repositories/demo-repo-xyz/dependency-map")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("clusters", data)
        self.assertIn("summary", data)

        clusters = data["clusters"]
        self.assertGreater(len(clusters), 0)

        # Check expected cluster fields matching Repowise
        first_cluster = clusters[0]
        self.assertIn("id", first_cluster)
        self.assertIn("name", first_cluster)
        self.assertIn("health_score", first_cluster)
        self.assertIn("health_tier", first_cluster)
        self.assertIn("languages", first_cluster)
        self.assertIn("files_count", first_cluster)
        self.assertIn("symbols_count", first_cluster)
        self.assertIn("dependencies", first_cluster)

        # Health score must be a number between 0 and 10
        for c in clusters:
            self.assertGreaterEqual(c["health_score"], 0.0)
            self.assertLessEqual(c["health_score"], 10.0)

    def test_change_detector_filters_external_dependency_noise(self):
        """Verify detect_changes filters out synthetic EXTERNAL_DEPENDENCY placeholders with <external>."""
        detector = ChangeDetector()
        mock_db = MagicMock()

        # Mock snapshots
        base_snap = MagicMock(id="snap-base", commit_sha="base123")
        target_snap = MagicMock(id="snap-target", commit_sha="target456")
        mock_db.query.return_value.filter.return_value.first.side_effect = [base_snap, target_snap]

        base_artifacts = [
            StructuralArtifact(
                id="art1",
                snapshot_id="snap-base",
                name="main.py",
                qualified_name="src/main.py",
                artifact_type="FILE",
                location="src/main.py",
                source_hash="h1",
            ),
        ]

        target_artifacts = [
            StructuralArtifact(
                id="art1",
                snapshot_id="snap-target",
                name="main.py",
                qualified_name="src/main.py",
                artifact_type="FILE",
                location="src/main.py",
                source_hash="h1",
            ),
            StructuralArtifact(
                id="art2",
                snapshot_id="snap-target",
                name="auth.py",
                qualified_name="src/auth.py",
                artifact_type="FILE",
                location="src/auth.py",
                source_hash="h2",
            ),
            # Noisy synthetic artifacts that should be skipped
            StructuralArtifact(
                id="art3",
                snapshot_id="snap-target",
                name="../AuthProvider",
                qualified_name="../AuthProvider",
                artifact_type="EXTERNAL_DEPENDENCY",
                location="<external>",
                source_hash="h3",
            ),
            StructuralArtifact(
                id="art4",
                snapshot_id="snap-target",
                name="../../components/Button",
                qualified_name="../../components/Button",
                artifact_type="EXTERNAL_DEPENDENCY",
                location="<external>",
                source_hash="h4",
            ),
        ]

        # Call detect_changes with explicit base and target artifacts
        change_set = detector.detect_changes(
            db=mock_db,
            repository_id="repo-1",
            base_snapshot_id="snap-base",
            target_snapshot_id="snap-target",
            base_artifacts=base_artifacts,
            target_artifacts=target_artifacts,
        )

        artifact_names = [c.qualified_name for c in change_set.changes]
        self.assertIn("src/auth.py", artifact_names)
        self.assertNotIn("../AuthProvider", artifact_names)
        self.assertNotIn("../../components/Button", artifact_names)

    def test_html_contains_workspace_elements(self):
        """Verify index.html contains necessary DOM containers for the updated experience."""
        html_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Dependencies workspace elements
        self.assertIn('id="view-dependencies"', html)
        self.assertIn('id="btn-dep-mode-2d"', html)
        self.assertIn('id="btn-dep-mode-3d"', html)
        self.assertIn('id="dep-risk-filter"', html)
        self.assertIn('id="dep-clusters-grid"', html)
        self.assertIn('id="dep-connections-svg"', html)
        self.assertIn('id="dep-inspect-name"', html)
        self.assertIn('id="dep-inspect-score"', html)
        self.assertIn('id="btn-dep-analyze-impact"', html)

        # Changes workspace elements
        self.assertIn('id="view-changes"', html)
        self.assertIn('id="btn-changes-tab-history"', html)
        self.assertIn('id="btn-changes-tab-diff"', html)
        self.assertIn('id="history-commits-tbody"', html)
        self.assertIn('id="diff-table-body"', html)

        # Floating Ask Twin elements
        self.assertIn('id="floating-ask-twin-container"', html)
        self.assertIn('id="floating-ask-twin-btn"', html)
        self.assertIn('id="floating-ask-twin-panel"', html)

        # Settings modal tabs
        self.assertIn('id="settings-tab-btn-profile"', html)
        self.assertIn('id="settings-tab-btn-prefs"', html)
        self.assertIn('id="settings-tab-btn-integrations"', html)
        self.assertIn('id="settings-tab-btn-usage"', html)


if __name__ == "__main__":
    unittest.main()
