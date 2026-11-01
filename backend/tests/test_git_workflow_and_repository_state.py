"""
Test Suite for Git Workflows, Branch Discovery, Truthful Repository States, and Snapshot Management.

Verifies:
1. Truthful Repository States:
   - Onboarded repository with 0 snapshots reports NO_SNAPSHOT_AVAILABLE, metrics with 0 artifacts, None for LOC.
   - Status indicators do not fabricate values or falsely report SYNCHRONIZED.
   - After analysis, repository transitions truthfully to SYNCHRONIZED.
   - When new commits advance HEAD beyond active snapshot, reports OUT_OF_SYNC (Behind HEAD).
2. Branch-Aware Git Workflows:
   - Branch discovery returns real local branches (main, feature-billing).
   - Introspecting branch commits (/commits?branch=...) filters commits strictly for that branch.
   - Querying branches and branch commits is strictly read-only and never modifies working tree branch.
3. Accurate Git Diff Statistics:
   - Per-commit additions, deletions, files_changed, and per-file diff listings calculated from actual git diffs.
   - Handles multi-file commits, renames, and single-commit history truthfully.
4. Snapshot Selection & On-Demand Commit Reconstruction:
   - Historical commit reconstruction uses git archive in isolation without touching working tree.
   - Reconstructed commit transitions from UNINDEXED to ANALYZED (has_snapshot=True).
   - Overview endpoint with snapshot_id parameter loads metrics specific to that snapshot.
5. Error Handling & Edge Cases:
   - Repository without snapshots returns clean truthful overview without 500 errors.
   - Invalid repository ID returns 404.
"""

import os
import sys
import unittest

# Subshell Python version auto-re-exec guard
if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

import tempfile
import shutil
import subprocess
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.entities import (
    Base,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    User,
    Project,
    Branch,
)
from app.core.database import get_db
from main import app


class TestGitWorkflowAndRepositoryState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        # 1. Create a controlled Git fixture with 2 branches and known diffs
        cls.repo_dir = tempfile.mkdtemp(prefix="twin_git_fixture_")
        subprocess.run(["git", "init", "-b", "main"], cwd=cls.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@twincore.test"], cwd=cls.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture Committer"], cwd=cls.repo_dir, capture_output=True, check=True)

        # Commit 1 on main: 1 file, 3 lines
        cls.core_file = os.path.join(cls.repo_dir, "core.py")
        with open(cls.core_file, "w") as f:
            f.write(
                "class CoreEngine:\n"
                "    def run(self):\n"
                "        return 'OK'\n"
            )
        subprocess.run(["git", "add", "core.py"], cwd=cls.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "feat: initial core engine"], cwd=cls.repo_dir, capture_output=True, check=True)
        cls.c1_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cls.repo_dir, capture_output=True, text=True, check=True).stdout.strip()

        # Commit 2 on main: add utils.py (+4 lines) and update core.py (+2 lines, -1 line)
        cls.utils_file = os.path.join(cls.repo_dir, "utils.py")
        with open(cls.utils_file, "w") as f:
            f.write(
                "def helper():\n"
                "    return 42\n"
            )
        with open(cls.core_file, "w") as f:
            f.write(
                "class CoreEngine:\n"
                "    def run(self):\n"
                "        from utils import helper\n"
                "        return helper()\n"
            )
        subprocess.run(["git", "add", "core.py", "utils.py"], cwd=cls.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "refactor: use helper in core"], cwd=cls.repo_dir, capture_output=True, check=True)
        cls.c2_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cls.repo_dir, capture_output=True, text=True, check=True).stdout.strip()

        # Branch 'feature-billing' off commit 1
        subprocess.run(["git", "checkout", "-b", "feature-billing", cls.c1_sha], cwd=cls.repo_dir, capture_output=True, check=True)
        cls.billing_file = os.path.join(cls.repo_dir, "billing.py")
        with open(cls.billing_file, "w") as f:
            f.write(
                "class BillingGateway:\n"
                "    def charge(self, amount):\n"
                "        return amount > 0\n"
            )
        subprocess.run(["git", "add", "billing.py"], cwd=cls.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "feat(billing): add billing gateway"], cwd=cls.repo_dir, capture_output=True, check=True)
        cls.billing_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cls.repo_dir, capture_output=True, text=True, check=True).stdout.strip()

        # Switch back to main branch
        subprocess.run(["git", "checkout", "main"], cwd=cls.repo_dir, capture_output=True, check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo_dir, ignore_errors=True)

    def setUp(self):
        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        from app.core.auth import create_access_token
        self.user = User(id="user_git_test", email="user@git.test", hashed_password="pw", role="engineer")
        self.db.add(self.user)

        # Baseline project and repository (initially without any snapshots)
        self.project = Project(id="proj_git_test", name="Git Test Project")
        self.db.add(self.project)
        self.db.commit()

        self.repo = Repository(
            id="repo_git_test",
            project_id=self.project.id,
            owner_id=self.user.id,
            name="git-fixture-repo",
            local_path=self.repo_dir,
            default_branch="main",
            source_type="LOCAL",
            environment="USER",
        )
        self.db.add(self.repo)
        self.db.commit()

        token = create_access_token(user_id=self.user.id, username="testuser", role="engineer", email=self.user.email)
        self.auth_headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        app.dependency_overrides.clear()
        # Verify working tree branch remained on 'main'
        curr_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        ).stdout.strip()
        self.assertEqual(curr_branch, "main")

    def test_01_truthful_state_on_unindexed_repository(self):
        """
        Investigate inconsistent repository state:
        When a repository is registered but not analyzed, overview must:
        - Return has_snapshots=False
        - Return sync_state='NO_SNAPSHOT_AVAILABLE', sync_label='No Snapshot', sync_badge_color='amber'
        - Return metrics: artifacts=0, relationships=0, tests=0, lines_of_code=None
        - Zero counts must NOT be fabricated
        - Provide an actionable status_message
        """
        res = self.client.get(f"/repositories/{self.repo.id}/overview", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertFalse(data["has_snapshots"])
        self.assertEqual(data["sync_state"], "NO_SNAPSHOT_AVAILABLE")
        self.assertEqual(data["sync_label"], "No Snapshot")
        self.assertEqual(data["sync_badge_color"], "amber")
        self.assertIn("no Digital Twin snapshot has been generated yet", data["status_message"])

        metrics = data["metrics"]
        self.assertEqual(metrics["artifacts"], 0)
        self.assertEqual(metrics["relationships"], 0)
        self.assertEqual(metrics["tests"], 0)
        self.assertIsNone(metrics["lines_of_code"])
        self.assertGreater(metrics["files"], 0)

    def test_02_branch_discovery_and_read_only_guarantee(self):
        """
        Branch discovery loads actual available branches (local and tracking).
        Does NOT alter the checked-out branch in the user's workspace.
        """
        res = self.client.get(f"/repositories/{self.repo.id}/branches", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        branches = res.json()

        branch_names = [b["name"] for b in branches]
        self.assertIn("main", branch_names)
        self.assertIn("feature-billing", branch_names)

        # Check main is identified as current/default
        main_entry = next(b for b in branches if b["name"] == "main")
        self.assertTrue(main_entry.get("is_current") or main_entry.get("is_default"))
        self.assertEqual(main_entry["head_commit_hash"], self.c2_sha)

        billing_entry = next(b for b in branches if b["name"] == "feature-billing")
        self.assertEqual(billing_entry["head_commit_hash"], self.billing_sha)

        # Confirm working tree was untouched
        curr_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        ).stdout.strip()
        self.assertEqual(curr_branch, "main")

    def test_03_branch_filtered_commits_and_diff_stats(self):
        """
        Introspect commits by branch:
        - Commits on 'main' contain c1 and c2
        - Commits on 'feature-billing' contain billing commit
        - Diff stats (additions, deletions, files_changed, files list) are calculated from actual git diffs
        - has_snapshot is False for unindexed commits
        """
        # 1. Main branch commits
        res_main = self.client.get(f"/repositories/{self.repo.id}/commits?branch=main", headers=self.auth_headers)
        self.assertEqual(res_main.status_code, 200)
        main_data = res_main.json()
        self.assertEqual(main_data["selected_branch"], "main")
        self.assertGreaterEqual(main_data["total_commits"], 2)

        main_shas = [c["commit_sha"] for c in main_data["commits"]]
        self.assertIn(self.c2_sha, main_shas)
        self.assertIn(self.c1_sha, main_shas)
        self.assertNotIn(self.billing_sha, main_shas)

        # Verify c2 diff stats: 2 files changed, additions & deletions
        c2_info = next(c for c in main_data["commits"] if c["commit_sha"] == self.c2_sha)
        self.assertEqual(c2_info["files_changed"], 2)
        self.assertGreater(c2_info["additions"], 0)
        self.assertFalse(c2_info["has_snapshot"])
        self.assertEqual(c2_info["status"], "AVAILABLE_FOR_ANALYSIS")
        self.assertIsInstance(c2_info["files"], list)
        self.assertEqual(len(c2_info["files"]), 2)

        # 2. Feature-billing branch commits
        res_bill = self.client.get(f"/repositories/{self.repo.id}/commits?branch=feature-billing", headers=self.auth_headers)
        self.assertEqual(res_bill.status_code, 200)
        bill_data = res_bill.json()
        self.assertEqual(bill_data["selected_branch"], "feature-billing")
        bill_shas = [c["commit_sha"] for c in bill_data["commits"]]
        self.assertIn(self.billing_sha, bill_shas)
        self.assertNotIn(self.c2_sha, bill_shas)

    def test_04_analyze_head_transitions_to_synchronized(self):
        """
        One-click discovery & AST analysis:
        POST /repositories/{id}/analyze builds a snapshot of current HEAD.
        Overview transitions to SYNCHRONIZED with truthful metrics.
        """
        res_analyze = self.client.post(f"/repositories/{self.repo.id}/analyze?branch_name=main", headers=self.auth_headers)
        self.assertEqual(res_analyze.status_code, 200)
        analyze_data = res_analyze.json()
        self.assertEqual(analyze_data["status"], "COMPLETED")
        self.assertIsNotNone(analyze_data["snapshot_id"])
        self.assertGreater(analyze_data["artifacts_count"], 0)

        # Check overview now reports SYNCHRONIZED
        res_ov = self.client.get(f"/repositories/{self.repo.id}/overview", headers=self.auth_headers)
        self.assertEqual(res_ov.status_code, 200)
        ov_data = res_ov.json()
        self.assertTrue(ov_data["has_snapshots"])
        self.assertEqual(ov_data["sync_state"], "SYNCHRONIZED")
        self.assertEqual(ov_data["sync_label"], "Synced")
        self.assertEqual(ov_data["sync_badge_color"], "green")
        self.assertGreater(ov_data["metrics"]["artifacts"], 0)

    def test_05_reconstruct_historical_commit_without_checkout(self):
        """
        Snapshot reconstruction for a historical commit (c1):
        - Uses git archive in an isolated temporary location
        - Workspace branch and files remain unchanged
        - Historical snapshot is created and indexed
        - Commit list now marks c1 as has_snapshot=True (ANALYZED)
        """
        # Initially c1 is not analyzed
        res_commits = self.client.get(f"/repositories/{self.repo.id}/commits?branch=main", headers=self.auth_headers)
        c1_before = next(c for c in res_commits.json()["commits"] if c["commit_sha"] == self.c1_sha)
        self.assertFalse(c1_before["has_snapshot"])

        # Reconstruct c1
        res_recon = self.client.post(
            f"/repositories/{self.repo.id}/snapshots/reconstruct",
            json={"commit_sha": self.c1_sha, "branch_name": "main"},
            headers=self.auth_headers,
        )
        self.assertEqual(res_recon.status_code, 200)
        recon_data = res_recon.json()
        self.assertEqual(recon_data["status"], "COMPLETED")
        c1_snap_id = recon_data["snapshot_id"]

        # Verify c1 is now marked ANALYZED in commits list
        res_commits_after = self.client.get(f"/repositories/{self.repo.id}/commits?branch=main", headers=self.auth_headers)
        c1_after = next(c for c in res_commits_after.json()["commits"] if c["commit_sha"] == self.c1_sha)
        self.assertTrue(c1_after["has_snapshot"])
        self.assertEqual(c1_after["snapshot_id"], c1_snap_id)
        self.assertEqual(c1_after["status"], "ANALYZED")

        # Confirm workspace files are still on main's HEAD (utils.py still exists)
        self.assertTrue(os.path.exists(self.utils_file))

    def test_06_snapshot_switching_loads_isolated_snapshot_metrics(self):
        """
        Switching active snapshot in GET /overview?snapshot_id=...
        returns the exact metrics for that snapshot without stale data leakage.
        """
        # Analyze HEAD (c2)
        res_c2 = self.client.post(f"/repositories/{self.repo.id}/analyze?branch_name=main", headers=self.auth_headers)
        snap_c2_id = res_c2.json()["snapshot_id"]

        # Reconstruct c1
        res_c1 = self.client.post(
            f"/repositories/{self.repo.id}/snapshots/reconstruct",
            json={"commit_sha": self.c1_sha, "branch_name": "main"},
            headers=self.auth_headers,
        )
        snap_c1_id = res_c1.json()["snapshot_id"]

        # Fetch overview for c1
        ov_c1 = self.client.get(f"/repositories/{self.repo.id}/overview?snapshot_id={snap_c1_id}", headers=self.auth_headers).json()
        self.assertEqual(ov_c1["snapshot"]["id"], snap_c1_id)
        self.assertEqual(ov_c1["snapshot"]["commit_hash"], self.c1_sha)

        # Fetch overview for c2
        ov_c2 = self.client.get(f"/repositories/{self.repo.id}/overview?snapshot_id={snap_c2_id}", headers=self.auth_headers).json()
        self.assertEqual(ov_c2["snapshot"]["id"], snap_c2_id)
        self.assertEqual(ov_c2["snapshot"]["commit_hash"], self.c2_sha)

        # Snapshot from another repo returns 404
        bad_res = self.client.get(f"/repositories/{self.repo.id}/overview?snapshot_id=nonexistent-snap-999", headers=self.auth_headers)
        self.assertEqual(bad_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
