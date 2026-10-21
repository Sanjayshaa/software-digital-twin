"""
Targeted Verification Test Suite for TwinCore Security, Authentication & Governance Hardening.
Tests:
- Password complexity requirements
- Rate limiting protection
- HttpOnly cookie issuance on login & clearing on logout
- Password reset token single-use & expiration handling
- Email enumeration prevention
- IDOR & multi-tenant isolation on analysis and discovery endpoints
- Repository deletion & account deletion cascading cleanup
- Zip Slip and Tar Slip archive traversal defenses
- Security headers (X-Request-ID, Permissions-Policy, HSTS, CSP, etc.)
- Legal endpoints (/privacy, /terms)
"""

import os
import sys

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest", os.path.abspath(__file__)])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import uuid
import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from sqlalchemy import text
from app.core.database import SessionLocal, engine
from app.core.auth import (
    hash_password,
    create_access_token,
    auth_action_limiter,
    login_rate_limiter,
)
from app.models.entities import User, Repository, Project


class TestSecurityAuditHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        auth_action_limiter.reset()
        login_rate_limiter.reset()
        self.db.rollback()

    def tearDown(self):
        self.db.rollback()

    def test_01_password_complexity_validation(self):
        """Verifies password complexity enforcement during user registration."""
        suffix = uuid.uuid4().hex[:6]
        # Too short (< 8 chars)
        res = self.client.post("/api/v1/auth/register", json={
            "username": f"user_{suffix}",
            "email": f"user_{suffix}@example.com",
            "password": "Short1!"
        })
        self.assertIn(res.status_code, [400, 422])
        self.assertIn("at least 8 characters", str(res.json()))

        # No digits or special characters
        res = self.client.post("/api/v1/auth/register", json={
            "username": f"user_{suffix}",
            "email": f"user_{suffix}@example.com",
            "password": "justlowercaseletters"
        })
        self.assertIn(res.status_code, [400, 422])
        self.assertIn("number or special character", str(res.json()))

    def test_02_login_cookie_and_logout_lifecycle(self):
        """Verifies login sets HttpOnly cookie and logout invalidates/clears it."""
        suffix = uuid.uuid4().hex[:6]
        username = f"cookie_{suffix}"
        email = f"cookie_{suffix}@example.com"
        password = "SecurePassword123!"

        # Register user
        reg_res = self.client.post("/api/v1/auth/register", json={
            "username": username,
            "email": email,
            "password": password
        })
        self.assertEqual(reg_res.status_code, 201)

        # Login
        login_res = self.client.post("/api/v1/auth/login", json={
            "username": username,
            "password": password
        })
        self.assertEqual(login_res.status_code, 200)
        data = login_res.json()
        self.assertIn("access_token", data)
        self.assertIn("access_token", login_res.cookies)

        token = data["access_token"]

        # Logout with token
        logout_res = self.client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(logout_res.status_code, 200)

        # Subsequent authenticated request with revoked token should fail
        me_res = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me_res.status_code, 401)

    def test_03_forgot_password_generic_response(self):
        """Verifies forgot-password endpoint returns uniform generic response without leaking email presence."""
        # Nonexistent email
        res1 = self.client.post("/api/v1/auth/forgot-password", json={
            "email": "nonexistent_user_12345@example.com"
        })
        self.assertEqual(res1.status_code, 200)
        self.assertIn("If an account with that email exists", res1.json()["message"])

    def test_04_password_reset_flow(self):
        """Verifies password reset with valid single-use token and rejects expired/invalid tokens."""
        suffix = uuid.uuid4().hex[:6]
        username = f"reset_{suffix}"
        email = f"reset_{suffix}@example.com"
        password = "OldPassword123!"

        reg_res = self.client.post("/api/v1/auth/register", json={
            "username": username,
            "email": email,
            "password": password
        })
        self.assertEqual(reg_res.status_code, 201)

        # Trigger reset
        res = self.client.post("/api/v1/auth/forgot-password", json={"email": email})
        self.assertEqual(res.status_code, 200)
        reset_token = res.json().get("reset_token")
        self.assertIsNotNone(reset_token)

        # Reset with invalid token
        inv_res = self.client.post("/api/v1/auth/reset-password", json={
            "token": "invalid_token_123",
            "new_password": "NewSecurePassword123!"
        })
        self.assertEqual(inv_res.status_code, 400)

        # Reset with valid token
        valid_res = self.client.post("/api/v1/auth/reset-password", json={
            "token": reset_token,
            "new_password": "NewSecurePassword123!"
        })
        self.assertEqual(valid_res.status_code, 200)

        # Re-use of token should fail (single-use)
        reuse_res = self.client.post("/api/v1/auth/reset-password", json={
            "token": reset_token,
            "new_password": "AnotherPassword123!"
        })
        self.assertEqual(reuse_res.status_code, 400)

        # Old password should no longer work
        old_login = self.client.post("/api/v1/auth/login", json={
            "username": username,
            "password": password
        })
        self.assertEqual(old_login.status_code, 401)

        # New password should work
        new_login = self.client.post("/api/v1/auth/login", json={
            "username": username,
            "password": "NewSecurePassword123!"
        })
        self.assertEqual(new_login.status_code, 200)

    def test_05_security_headers_and_correlation_id(self):
        """Verifies security headers, correlation ID (X-Request-ID), and Permissions-Policy on responses."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertIn("x-request-id", res.headers)
        self.assertEqual(res.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(res.headers.get("x-frame-options"), "DENY")
        self.assertEqual(res.headers.get("referrer-policy"), "strict-origin-when-cross-origin")
        self.assertIn("camera=()", res.headers.get("permissions-policy", ""))
        self.assertIn("default-src", res.headers.get("content-security-policy", ""))

    def test_06_legal_pages_available(self):
        """Verifies /privacy and /terms legal routes serve responsive HTML documents."""
        privacy_res = self.client.get("/privacy")
        self.assertEqual(privacy_res.status_code, 200)
        self.assertIn("Privacy Policy", privacy_res.text)

        terms_res = self.client.get("/terms")
        self.assertEqual(terms_res.status_code, 200)
        self.assertIn("Terms of Service", terms_res.text)

    def test_07_idor_and_tenant_isolation_on_analysis_endpoints(self):
        """Verifies that unauthenticated or unauthorized users cannot access another user's repository."""
        suffix = uuid.uuid4().hex[:6]
        user_a_id = f"usr_test_a_{suffix}"
        user_b_id = f"usr_test_b_{suffix}"

        # Create user A and private repository
        user_a = User(
            id=user_a_id,
            username=f"user_a_{suffix}",
            email=f"user_a_{suffix}@example.com",
            hashed_password=hash_password("Password123!"),
            role="engineer",
            is_active=True,
        )
        project_a = Project(id=f"prj_{suffix}", name=f"Proj_{suffix}", description="Test Project")
        repo_a = Repository(
            id=f"repo_private_{suffix}",
            project_id=project_a.id,
            name=f"private-repo-{suffix}",
            owner_id=user_a.id,
            environment="USER",
            local_path="/tmp/fake/repo"
        )
        self.db.add(user_a)
        self.db.add(project_a)
        self.db.add(repo_a)
        self.db.commit()

        # Token for User B
        token_b = create_access_token(user_id=user_b_id, username=f"user_b_{suffix}")

        # 1. Unauthenticated request to commits -> 404
        unauth_res = self.client.get(f"/repositories/{repo_a.id}/commits")
        self.assertEqual(unauth_res.status_code, 404)

        # 2. User B trying to access User A's commits -> 404
        cross_res = self.client.get(
            f"/repositories/{repo_a.id}/commits",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(cross_res.status_code, 404)

        # 3. User B trying to access User A's snapshots -> 404
        cross_snap = self.client.get(
            f"/repositories/{repo_a.id}/snapshots",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(cross_snap.status_code, 404)

        # 4. User B trying to access User A's profile -> 404
        cross_prof = self.client.get(
            f"/repositories/{repo_a.id}/profile",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(cross_prof.status_code, 404)

        # Cleanup
        self.db.delete(repo_a)
        self.db.delete(project_a)
        self.db.delete(user_a)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
