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
import tempfile
import shutil
import subprocess
from datetime import datetime, timezone
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
from app.core.auth import create_access_token
from main import app


class TestDocsStatsBranchIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo_repo_id = "repo-demo-ecommerce-001"
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        # Create temporary Git fixture repository
        cls.repo_dir = tempfile.mkdtemp(prefix="twin_docs_stats_test_")
        subprocess.run(["git", "init", "-b", "main"], cwd=cls.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "dev@twincore.test"], cwd=cls.repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "TwinCore Dev"], cwd=cls.repo_dir, capture_output=True, check=True)

        # Add .env.example configuration file
        env_file = os.path.join(cls.repo_dir, ".env.example")
        with open(env_file, "w") as f:
            f.write("PORT=8000\nDATABASE_URL=sqlite:///./dev.db\n")

        # Add main source file
        app_file = os.path.join(cls.repo_dir, "main.py")
        with open(app_file, "w") as f:
            f.write("from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef root(): return {'status': 'ok'}\n")

        subprocess.run(["git", "add", "."], cwd=cls.repo_dir, capture_output=True, check=True)
        # Commit with fixed authored date in UTC midnight hours (01:00 UTC) to test Batman Hours
        env_vars = os.environ.copy()
        env_vars["GIT_AUTHOR_DATE"] = "2026-11-01T01:30:00Z"
        env_vars["GIT_COMMITTER_DATE"] = "2026-11-01T01:30:00Z"
        subprocess.run(["git", "commit", "-m", "feat: initial service setup"], cwd=cls.repo_dir, env=env_vars, capture_output=True, check=True)

        # Second commit (02:15 UTC) to firmly establish Batman Hours / Night Owl
        with open(os.path.join(cls.repo_dir, "service.py"), "w") as f:
            f.write("class UserService:\n    def get_user(self): return {'id': 1}\n")
        subprocess.run(["git", "add", "service.py"], cwd=cls.repo_dir, capture_output=True, check=True)
        env_vars["GIT_AUTHOR_DATE"] = "2026-11-02T02:15:00Z"
        env_vars["GIT_COMMITTER_DATE"] = "2026-11-02T02:15:00Z"
        subprocess.run(["git", "commit", "-m", "feat: add user service logic"], cwd=cls.repo_dir, env=env_vars, capture_output=True, check=True)

        # Seed in-memory DB fixture
        db = cls.SessionLocal()
        cls.user_id = "user_test_doc_stats"
        cls.user_email = "tester@twincore.test"
        cls.repo_id = "repo_real_fixture_001"
        cls.snapshot_id = "snap_real_fixture_001"

        user = User(id=cls.user_id, email=cls.user_email, hashed_password="pw", role="engineer")
        db.add(user)
        project = Project(id="proj_doc_stats", name="Docs & Stats Project")
        db.add(project)
        db.commit()

        repo = Repository(
            id=cls.repo_id,
            project_id=project.id,
            owner_id=user.id,
            name="real-fixture-repo",
            local_path=cls.repo_dir,
            default_branch="main",
            source_type="LOCAL",
            environment="USER",
        )
        db.add(repo)
        db.commit()

        snapshot = RepositorySnapshot(
            id=cls.snapshot_id,
            repository_id=repo.id,
            commit_hash="c0ffee123456",
            branch_name="main",
            snapshot_metadata={"label": "main baseline"},
            created_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.commit()
        db.close()

        token = create_access_token(user_id=cls.user_id, username="tester", role="engineer", email=cls.user_email)
        cls.auth_headers = {"Authorization": f"Bearer {token}"}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo_dir, ignore_errors=True)
        Base.metadata.drop_all(cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_docs_all_eight_categories_and_branch_support(self):
        """Verifies GET /{repo}/docs returns all 8 distinct documentation categories and accepts branch parameter."""
        res = self.client.get(f"/repositories/{self.demo_repo_id}/docs?branch=main")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # All 8 category data keys must be present and well-structured
        self.assertIn("summary_narrative", data)
        self.assertIn("system_map", data)
        self.assertIn("folder_guide", data)
        self.assertIn("startup_flows", data)
        self.assertIn("routes_and_apis", data)
        self.assertIn("services_and_logic", data)
        self.assertIn("database_structures", data)
        self.assertIn("config_and_env", data)

        # Check types
        self.assertIsInstance(data["system_map"], list)
        self.assertIsInstance(data["folder_guide"], list)
        self.assertIsInstance(data["startup_flows"], list)
        self.assertIsInstance(data["routes_and_apis"], list)
        self.assertIsInstance(data["services_and_logic"], list)
        self.assertIsInstance(data["database_structures"], list)
        self.assertIsInstance(data["config_and_env"], list)

    def test_stats_utc_distributions_and_playful_activity_tags(self):
        """Verifies GET /{repo}/stats returns UTC distributions and evidence-based activity tags."""
        res = self.client.get(f"/repositories/{self.demo_repo_id}/stats?branch=main")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("timeline", data)
        self.assertIn("work_patterns", data)

        tl = data["timeline"]
        wp = data["work_patterns"]

        # Verify activity_tags presence in both timeline and work_patterns
        self.assertIn("activity_tags", tl)
        self.assertIn("activity_tags", wp)
        self.assertIsInstance(wp["activity_tags"], list)
        self.assertGreater(len(wp["activity_tags"]), 0)

        # Check activity tag structure (playful naming + evidence description)
        for tag in wp["activity_tags"]:
            self.assertIn("tag", tag)
            self.assertIn("name", tag)
            self.assertIn("description", tag)
            self.assertIn("badge_class", tag)
            # Ensure name has playful emoji or persona moniker
            self.assertTrue(any(sym in tag["name"] for sym in ["🦇", "🦉", "🌅", "⚔️", "☕", "⚡"]))

        # Verify UTC hour-of-day distribution buckets
        self.assertIn("commits_by_hour_of_day", wp)
        hod = wp["commits_by_hour_of_day"]
        self.assertIsInstance(hod, dict)
        self.assertIn("00-04", hod)
        self.assertIn("08-12", hod)

    def test_repository_branches_api(self):
        """Verifies GET /{repo}/branches returns a list of branches."""
        res = self.client.get(f"/repositories/{self.demo_repo_id}/branches")
        self.assertEqual(res.status_code, 200)
        branches = res.json()
        self.assertIsInstance(branches, list)
        self.assertGreater(len(branches), 0)
        self.assertIn("name", branches[0])
        self.assertIn("is_current", branches[0])

    def test_real_repo_docs_discovers_configuration_files(self):
        """Verifies real repository scanning on disk populates config_and_env."""
        res = self.client.get(
            f"/repositories/{self.repo_id}/docs?snapshot_id={self.snapshot_id}&branch=main",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        docs = res.json()
        self.assertIn("config_and_env", docs)
        configs = docs["config_and_env"]
        self.assertIsInstance(configs, list)
        # Should have found .env.example in real disk fixture
        config_names = [c.get("key") or c.get("name") or c.get("file") for c in configs]
        self.assertTrue(any(".env" in str(name) for name in config_names))

    def test_real_repo_stats_calculates_batman_hours_and_real_commits(self):
        """Verifies real Git repository discovery calculates real span days and Batman Hours tag."""
        res = self.client.get(
            f"/repositories/{self.repo_id}/stats?snapshot_id={self.snapshot_id}&branch=main",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        stats = res.json()
        self.assertIn("timeline", stats)
        self.assertIn("work_patterns", stats)

        tl = stats["timeline"]
        wp = stats["work_patterns"]

        # Commits were discovered directly from Git disk history
        self.assertGreaterEqual(tl.get("total_commits_indexed", 0), 2)
        self.assertIn("activity_tags", wp)
        tag_names = [t["name"] for t in wp["activity_tags"]]
        # Since commits were committed at 01:30 and 02:15 UTC, Batman Hours / Night Owl must be detected!
        self.assertTrue(any("Batman" in name or "Night Owl" in name for name in tag_names))


if __name__ == "__main__":
    unittest.main()
