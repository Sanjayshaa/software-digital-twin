"""
Zero-Friction GitHub Repository Integration Test Suite.
Verifies:
1. Repository discovery with mock GitHub API responses (pagination, query filter, private/public visibility).
2. Rate limit handling (429) and 401 invalid token recovery.
3. Automatic default branch detection and accessible branch listing.
4. Pre-flight repository and branch validation.
5. Zero-leak token security (tokens are never returned in responses or saved to DB).
6. Multi-tenant repository isolation and access control.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch

# Python version auto-re-exec guard for subshell execution
if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest", os.path.abspath(__file__)])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models.entities import Base, Repository, Project, User
from app.core.database import get_db
from app.core.auth import AuthenticatedPrincipal, resolve_authorized_repo

# In-memory SQLite for deterministic, sandbox-safe testing without external network
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create schema in SQLite
Base.metadata.create_all(bind=test_engine)

from main import app

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


class TestGitHubZeroFrictionIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = TestingSessionLocal()
        # Seed default project
        default_proj = self.db.query(Project).filter_by(id="default-project").first()
        if not default_proj:
            default_proj = Project(
                id="default-project",
                name="Default System Test Project",
                description="Seeded test project for unassigned repositories",
            )
            self.db.add(default_proj)
            self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch("app.api.github._call_github_api")
    def test_discover_repositories_success(self, mock_api):
        mock_repos = [
            {
                "id": 101,
                "name": "twincore-monorepo",
                "full_name": "acme-corp/twincore-monorepo",
                "private": True,
                "default_branch": "develop",
                "clone_url": "https://github.com/acme-corp/twincore-monorepo.git",
                "html_url": "https://github.com/acme-corp/twincore-monorepo",
                "description": "Living Digital Twin Engine",
                "language": "Python",
                "stargazers_count": 42,
                "fork": False,
                "updated_at": "2026-10-25T12:00:00Z",
                "permissions": {"admin": True, "push": True, "pull": True},
            },
            {
                "id": 102,
                "name": "public-docs",
                "full_name": "acme-corp/public-docs",
                "private": False,
                "default_branch": "main",
                "clone_url": "https://github.com/acme-corp/public-docs.git",
                "html_url": "https://github.com/acme-corp/public-docs",
                "description": "Architecture guides",
                "language": "Markdown",
                "stargazers_count": 12,
                "fork": False,
                "updated_at": "2026-10-24T10:00:00Z",
                "permissions": {"admin": False, "push": False, "pull": True},
            },
        ]
        mock_api.return_value = (200, mock_repos, {"Link": ""})

        response = self.client.post(
            "/github/discover",
            json={"github_token": "ghp_valid_mock_token_12345", "page": 1, "per_page": 30},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_count"], 2)
        repos = data["repositories"]
        self.assertEqual(len(repos), 2)
        self.assertEqual(repos[0]["full_name"], "acme-corp/twincore-monorepo")
        self.assertTrue(repos[0]["private"])
        self.assertEqual(repos[0]["default_branch"], "develop")
        self.assertEqual(repos[1]["default_branch"], "main")
        self.assertFalse(repos[1]["private"])

        # Security check: Ensure token is never echoed back in the response
        self.assertNotIn("ghp_valid_mock_token_12345", json.dumps(data))

    @patch("app.api.github._call_github_api")
    def test_discover_repositories_query_filter(self, mock_api):
        mock_repos = [
            {
                "id": 201,
                "name": "frontend-dashboard",
                "full_name": "acme-corp/frontend-dashboard",
                "private": False,
                "default_branch": "main",
                "clone_url": "https://github.com/acme-corp/frontend-dashboard.git",
                "html_url": "https://github.com/acme-corp/frontend-dashboard",
                "description": "Vue/Vite dashboard",
                "language": "TypeScript",
                "stargazers_count": 5,
                "fork": False,
                "updated_at": "2026-10-25T10:00:00Z",
                "permissions": {"pull": True},
            },
            {
                "id": 202,
                "name": "backend-api",
                "full_name": "acme-corp/backend-api",
                "private": True,
                "default_branch": "master",
                "clone_url": "https://github.com/acme-corp/backend-api.git",
                "html_url": "https://github.com/acme-corp/backend-api",
                "description": "FastAPI core",
                "language": "Python",
                "stargazers_count": 18,
                "fork": False,
                "updated_at": "2026-10-25T11:00:00Z",
                "permissions": {"pull": True},
            },
        ]
        mock_api.return_value = (200, mock_repos, {})

        # Filtering by "dashboard"
        response = self.client.post(
            "/github/discover",
            json={"github_token": "ghp_mock_token", "query": "dashboard"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["repositories"][0]["name"], "frontend-dashboard")

    @patch("app.api.github._call_github_api")
    def test_discover_repositories_invalid_token(self, mock_api):
        mock_api.return_value = (401, {"message": "Bad credentials"}, {})

        response = self.client.post(
            "/github/discover",
            json={"github_token": "ghp_invalid_token"},
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("Invalid or expired GitHub", data["detail"])

    @patch("app.api.github._call_github_api")
    def test_discover_repositories_rate_limit(self, mock_api):
        mock_api.return_value = (
            403,
            {"message": "API rate limit exceeded"},
            {"x-ratelimit-reset": "1730000000"},
        )

        response = self.client.post(
            "/github/discover",
            json={"github_token": "ghp_rate_limited"},
        )
        self.assertEqual(response.status_code, 429)
        data = response.json()
        self.assertIn("rate limit exceeded", data["detail"].lower())

    @patch("app.api.github._call_github_api")
    def test_discover_branches_and_default(self, mock_api):
        # Mock repo metadata endpoint
        repo_meta = {
            "name": "twincore",
            "default_branch": "release-v2",
        }
        # Mock branch list endpoint
        branches_list = [
            {"name": "release-v2", "commit": {"sha": "aaa111"}},
            {"name": "develop", "commit": {"sha": "bbb222"}},
            {"name": "feature/graph-sync", "commit": {"sha": "ccc333"}},
        ]

        def side_effect(endpoint, token=None):
            if "branches" in endpoint:
                return (200, branches_list, {})
            return (200, repo_meta, {})

        mock_api.side_effect = side_effect

        response = self.client.post(
            "/github/branches",
            json={"owner": "acme", "repo": "twincore", "github_token": "ghp_mock"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["default_branch"], "release-v2")
        self.assertEqual(len(data["branches"]), 3)
        self.assertTrue(data["branches"][0]["is_default"])
        self.assertEqual(data["branches"][0]["name"], "release-v2")

    @patch("app.api.github._call_github_api")
    def test_discover_branches_repo_not_found(self, mock_api):
        mock_api.return_value = (404, {"message": "Not Found"}, {})

        response = self.client.post(
            "/github/branches",
            json={"owner": "nonexistent", "repo": "ghost-repo"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    @patch("app.api.github._call_github_api")
    def test_validate_repository_and_branch(self, mock_api):
        repo_data = {
            "name": "core-engine",
            "private": True,
            "default_branch": "trunk",
            "permissions": {"admin": True, "push": True, "pull": True},
        }

        def side_effect(endpoint, token=None):
            if "branches/trunk" in endpoint:
                return (200, {"name": "trunk", "commit": {"sha": "123"}}, {})
            if "branches/ghost-branch" in endpoint:
                return (404, {"message": "Branch not found"}, {})
            return (200, repo_data, {})

        mock_api.side_effect = side_effect

        # Validate with valid branch
        res_valid = self.client.post(
            "/github/validate",
            json={"owner": "acme", "repo": "core-engine", "branch": "trunk", "github_token": "ghp_test"},
        )
        self.assertEqual(res_valid.status_code, 200)
        valid_json = res_valid.json()
        self.assertTrue(valid_json["valid"])
        self.assertEqual(valid_json["selected_branch"], "trunk")
        self.assertTrue(valid_json["private"])

        # Validate with non-existent branch
        res_invalid_branch = self.client.post(
            "/github/validate",
            json={"owner": "acme", "repo": "core-engine", "branch": "ghost-branch", "github_token": "ghp_test"},
        )
        self.assertEqual(res_invalid_branch.status_code, 200)
        invalid_json = res_invalid_branch.json()
        self.assertFalse(invalid_json["valid"])
        self.assertIn("does not exist", invalid_json["error"])

    def test_multi_tenant_repository_isolation(self):
        """
        Verify that user A cannot inspect or access repositories belonging to user B.
        """
        repo_a = Repository(
            id="repo-tenant-alice-1",
            name="Alice Private Repo",
            project_id="default-project",
            vcs_type="git",
            local_path="/tmp/alice_repo",
            owner_id="user-alice-123",
            environment="USER",
        )
        repo_b = Repository(
            id="repo-tenant-bob-1",
            name="Bob Private Repo",
            project_id="default-project",
            vcs_type="git",
            local_path="/tmp/bob_repo",
            owner_id="user-bob-456",
            environment="USER",
        )
        self.db.add(repo_a)
        self.db.add(repo_b)
        self.db.commit()

        principal_alice = AuthenticatedPrincipal(
            user_id="user-alice-123",
            username="alice",
            role="engineer",
            is_authenticated=True,
        )
        principal_bob = AuthenticatedPrincipal(
            user_id="user-bob-456",
            username="bob",
            role="engineer",
            is_authenticated=True,
        )

        # Alice resolves her own repo
        resolved_a = resolve_authorized_repo(self.db, repo_a.id, principal_alice)
        self.assertIsNotNone(resolved_a)
        self.assertEqual(resolved_a.id, repo_a.id)

        # Alice cannot access Bob's repo (zero-trust 404 non-disclosure)
        resolved_b_for_alice = resolve_authorized_repo(self.db, repo_b.id, principal_alice)
        self.assertIsNone(resolved_b_for_alice)

        # Bob cannot access Alice's repo
        resolved_a_for_bob = resolve_authorized_repo(self.db, repo_a.id, principal_bob)
        self.assertIsNone(resolved_a_for_bob)

        # Unauthenticated guest cannot access either repo
        self.assertIsNone(resolve_authorized_repo(self.db, repo_a.id, None))
        self.assertIsNone(resolve_authorized_repo(self.db, repo_b.id, None))

    def test_token_not_persisted_in_database(self):
        """
        Verify that Repository records never store access tokens in plaintext in the database.
        """
        repo_record = Repository(
            id="repo-token-safety-check",
            name="Security Hardened Repo",
            project_id="default-project",
            vcs_type="git",
            remote_url="https://github.com/company/repo.git",
            local_path="/tmp/token_check_repo",
            environment="TEST",
        )
        self.db.add(repo_record)
        self.db.commit()

        fetched = self.db.query(Repository).filter_by(id="repo-token-safety-check").first()
        self.assertIsNotNone(fetched)
        # Verify no token attribute or field exists on model
        self.assertFalse(hasattr(fetched, "github_token"))
        self.assertFalse(hasattr(fetched, "access_token"))
        self.assertFalse(hasattr(fetched, "token"))


if __name__ == "__main__":
    unittest.main()
