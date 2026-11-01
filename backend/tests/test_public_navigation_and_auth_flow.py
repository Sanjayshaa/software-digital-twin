"""
Deterministic Tests for TwinCore Public Landing Page, Standalone Demo Route,
Authentication Entry Points, and Protected Workspace Flow.

Verifies:
1. Public Landing Page at GET / serves landing.html to browsers with exact headline & copy.
2. Direct REST/API callers to GET / receive structured JSON metadata.
3. GET /landing serves landing.html.
4. Standalone Demo route GET /demo serves index.html and requires no credentials.
5. Demo API endpoints (/api/v1/demo/*) require no authentication and do not mutate real repositories.
6. GET /login, GET /signin, GET /register, and GET /signup serve login.html.
7. Unconfigured OAuth endpoints handle missing client IDs safely without fabrication.
8. Protected workspace route GET /app serves index.html, while unauthenticated /api/v1/auth/me yields 401.
9. Separation between synthetic demo fixture and active user repositories.
"""

import os
import sys
import unittest

# Subshell Python version auto-re-exec guard
if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app


class TestPublicNavigationAndAuthFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_public_landing_browser_request(self):
        """Browser requesting GET / receives landing.html with required headlines and CTAs."""
        res = self.client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
        body = res.text
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("Understand the Impact Before You Change Code.", body)
        self.assertIn(
            "TwinCore builds an evidence-backed model of your software architecture to help developers investigate dependencies",
            body,
        )
        self.assertIn('href="/demo"', body)
        self.assertIn('href="/login"', body)
        self.assertIn('href="/register"', body)
        self.assertIn("Knowledge Graph", body)
        self.assertIn("Blast Radius", body)
        self.assertIn("What-If", body)
        self.assertIn("Test Impact", body)
        self.assertIn("Evidence Ledger", body)

    def test_02_public_landing_explicit_route(self):
        """GET /landing explicitly returns landing.html."""
        res = self.client.get("/landing")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("Understand the Impact Before You Change Code.", res.text)

    def test_03_root_api_json_response(self):
        """API client requesting GET / without text/html receives JSON route index."""
        res = self.client.get("/", headers={"Accept": "application/json"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("Software Digital Twin", data.get("name", ""))
        self.assertEqual(data.get("landing"), "/")
        self.assertEqual(data.get("demo"), "/demo")
        self.assertEqual(data.get("ui"), "/app")
        self.assertEqual(data.get("login"), "/login")
        self.assertEqual(data.get("register"), "/register")

    def test_04_dedicated_demo_route(self):
        """GET /demo returns 200 serving the application shell."""
        res = self.client.get("/demo")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("TwinCore", res.text)
        self.assertIn('id="view-demo"', res.text)

    def test_05_demo_api_unauthenticated_access(self):
        """Demo API endpoints are completely accessible without tokens or sessions."""
        res_overview = self.client.get("/api/v1/demo/overview")
        self.assertEqual(res_overview.status_code, 200)
        overview_data = res_overview.json()
        self.assertTrue(overview_data.get("is_demo"))
        self.assertEqual(overview_data["repository"]["name"], "ecommerce-microservices-reference")

        res_graph = self.client.get("/api/v1/demo/graph")
        self.assertEqual(res_graph.status_code, 200)
        graph_data = res_graph.json()
        self.assertEqual(len(graph_data.get("nodes", [])), 22)
        self.assertEqual(len(graph_data.get("edges", [])), 22)

    def test_06_login_and_registration_routes(self):
        """GET /login, /signin, /register, and /signup serve login.html."""
        for path in ["/login", "/signin", "/register", "/signup"]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f"Route {path} failed")
            self.assertIn("text/html", res.headers.get("content-type", ""))
            self.assertIn("Sign In", res.text)
            self.assertIn("Create Account", res.text)
            self.assertIn("Continue with GitHub", res.text)
            self.assertIn("Continue with Google", res.text)

    def test_07_oauth_not_fabricated_when_unconfigured(self):
        """OAuth buttons do not fabricate credentials and state clear configuration requirements."""
        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        body = res_login.text
        # Honest modal messaging for unconfigured OAuth providers
        self.assertIn("GitHub OAuth Configuration Required", body)
        self.assertIn("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET", body)
        self.assertIn("Google OAuth Configuration Required", body)
        self.assertIn("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET", body)

    def test_08_protected_workspace_route(self):
        """GET /app serves index.html shell for authenticated workspace."""
        res = self.client.get("/app")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("TwinCore", res.text)

    def test_09_unauthenticated_api_me_rejected(self):
        """GET /api/v1/auth/me returns 401 when no token or an invalid token is provided."""
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)

        res_bad = self.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_token_12345"})
        self.assertEqual(res_bad.status_code, 401)

    def test_10_synthetic_demo_isolation_from_real_repositories(self):
        """Running demo simulations does not inject or alter real user repositories."""
        # Fetch initial user repositories
        initial_repos_res = self.client.get("/repositories")
        self.assertEqual(initial_repos_res.status_code, 200)
        initial_repos = initial_repos_res.json()
        initial_ids = {r["id"] for r in initial_repos}

        # Verify demo synthetic repository ID is NOT in the active user repo list
        self.assertNotIn("synthetic-online-shop", initial_ids)
        self.assertNotIn("ecommerce-microservices-reference", initial_ids)

        # Execute demo blast radius and what-if simulation
        blast_res = self.client.post("/api/v1/demo/blast-radius", json={"root_identifier": "art-payment"})
        self.assertEqual(blast_res.status_code, 200)

        whatif_res = self.client.post(
            "/api/v1/demo/simulate",
            json={"scenario_id": "SCENARIO_SERVICE_OUTAGE"}
        )
        self.assertEqual(whatif_res.status_code, 200)

        # Verify user repository list remains unchanged and isolated
        after_repos_res = self.client.get("/repositories")
        self.assertEqual(after_repos_res.status_code, 200)
        after_repos = after_repos_res.json()
        after_ids = {r["id"] for r in after_repos}
        self.assertEqual(initial_ids, after_ids)

    def test_11_login_with_email_and_case_insensitivity(self):
        """Email and username login is case-insensitive, accepts RFC email lengths, and rejects invalid credentials."""
        import uuid
        test_uid = uuid.uuid4().hex[:8]
        mixed_username = f"EngUser_{test_uid}"
        # 80-character RFC-compliant email to test beyond previous 64-char limit
        long_email = f"verified_dev_lead_{test_uid}_continuous_integration@enterprise-architecture-cloud.internal"
        test_pwd = "StrongSecurePassword123!"

        reg_res = self.client.post("/api/v1/auth/register", json={
            "username": mixed_username,
            "email": long_email,
            "password": test_pwd,
            "role": "engineer"
        })
        self.assertIn(reg_res.status_code, [200, 201])

        # 1. Login with exact email
        login_exact = self.client.post("/api/v1/auth/login", json={
            "email": long_email,
            "password": test_pwd
        })
        self.assertEqual(login_exact.status_code, 200)
        self.assertIn("access_token", login_exact.json())

        # 2. Login with uppercase email
        login_upper_email = self.client.post("/api/v1/auth/login", json={
            "email": long_email.upper(),
            "password": test_pwd
        })
        self.assertEqual(login_upper_email.status_code, 200)
        self.assertIn("access_token", login_upper_email.json())

        # 3. Login using email in the 'username' field (legacy client form behavior)
        login_email_as_username = self.client.post("/api/v1/auth/login", json={
            "username": long_email.lower(),
            "password": test_pwd
        })
        self.assertEqual(login_email_as_username.status_code, 200)
        self.assertIn("access_token", login_email_as_username.json())

        # 4. Login with lowercase username
        login_lower_user = self.client.post("/api/v1/auth/login", json={
            "username": mixed_username.lower(),
            "password": test_pwd
        })
        self.assertEqual(login_lower_user.status_code, 200)
        self.assertIn("access_token", login_lower_user.json())

        # 5. Invalid credentials rejected with 401
        login_bad = self.client.post("/api/v1/auth/login", json={
            "email": long_email,
            "password": "WrongPassword999!"
        })
        self.assertEqual(login_bad.status_code, 401)
        self.assertIn("Invalid username or password", login_bad.json().get("detail", ""))

    def test_12_demo_architecture_graph_projection_levels(self):
        """Demo architecture graph returns non-empty nodes and edges across Level 1 Macro and Level 2 Components."""
        for repo_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
            # Level 1 Macro View
            res_l1 = self.client.get(f"/repositories/{repo_id}/graph?level=1&depth=2")
            self.assertEqual(res_l1.status_code, 200, f"Failed for {repo_id} at Level 1")
            data_l1 = res_l1.json()
            self.assertTrue(data_l1.get("is_demo"))
            self.assertGreaterEqual(len(data_l1.get("nodes", [])), 6)
            self.assertGreaterEqual(len(data_l1.get("edges", [])), 5)

            node_ids_l1 = {n["id"] for n in data_l1["nodes"]}
            self.assertIn("art-gw", node_ids_l1)
            self.assertIn("art-auth", node_ids_l1)
            self.assertIn("art-order", node_ids_l1)

            # Level 2 Components View
            res_l2 = self.client.get(f"/repositories/{repo_id}/graph?level=2&depth=2")
            self.assertEqual(res_l2.status_code, 200, f"Failed for {repo_id} at Level 2")
            data_l2 = res_l2.json()
            self.assertGreaterEqual(len(data_l2.get("nodes", [])), 16)
            self.assertGreaterEqual(len(data_l2.get("edges", [])), 14)


if __name__ == "__main__":
    unittest.main()

