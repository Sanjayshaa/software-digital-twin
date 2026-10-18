"""
Phase 8.6.2 — Security Domain A & B: Authentication, JWT & Session Security Tests.

Validates all 10 mandatory authentication test cases:
1. Missing authentication
2. Invalid authentication credentials
3. Expired authentication token
4. Malformed token
5. Invalid signature / wrong signing key
6. Valid authentication & login
7. Authenticated principal identity extraction (/auth/me)
8. Logout / token revocation
9. Protected endpoint access
10. Public endpoint behavior
"""

import time
import uuid
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    revoke_token,
    is_token_revoked,
)
from app.models.entities import User
from main import app

client = TestClient(app)


def test_password_hashing_and_verification():
    """Verifies PBKDF2-HMAC-SHA256 password hashing and secure verification."""
    password = "CorrectHorseBatteryStaple123!"
    hashed = hash_password(password)

    assert hashed != password
    assert "$" in hashed
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "invalid_hash_string") is False


def test_user_registration_and_login_flow(db_session):
    """Verifies registration and login flow issuing valid JWT access tokens."""
    unique_suffix = uuid.uuid4().hex[:8]
    username = f"user_{unique_suffix}"
    email = f"user_{unique_suffix}@example.com"
    password = "StrongPassword987!"

    # 1. Register new user
    reg_resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "role": "engineer",
    })
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["username"] == username
    assert user_data["email"] == email

    # 2. Duplicate registration rejected
    dup_resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
    })
    assert dup_resp.status_code == 409

    # 3. Invalid credentials rejected
    bad_login = client.post("/api/v1/auth/login", json={
        "username": username,
        "password": "WrongPassword!",
    })
    assert bad_login.status_code == 401
    assert "Invalid username or password" in bad_login.json()["detail"]

    # 4. Valid credentials succeed and issue Bearer token
    login_resp = client.post("/api/v1/auth/login", json={
        "username": username,
        "password": password,
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"
    token = login_data["access_token"]

    # 5. Authenticated principal identity extraction (/auth/me)
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == username
    assert me_data["role"] == "engineer"
    assert me_data["is_admin"] is False

    # 6. Logout / token revocation
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "logged_out"

    # 7. Revoked token access rejected
    post_logout = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert post_logout.status_code == 401
    assert "revoked" in post_logout.json()["detail"].lower()

    # Clean up DB
    db_user = db_session.query(User).filter_by(username=username).first()
    if db_user:
        db_session.delete(db_user)
        db_session.commit()


def test_missing_and_malformed_token():
    """Verifies that missing or malformed tokens are deterministically rejected with 401."""
    # Missing token on protected endpoint
    resp_missing = client.get("/api/v1/auth/me")
    assert resp_missing.status_code == 401
    assert "Authentication required" in resp_missing.json()["detail"]

    # Malformed token formats
    for bad_token in [
        "not_a_valid_token",
        "header.only",
        "too.many.segments.in.this.token.here",
        "invalid_base64!?.invalid_base64!?.invalid_sig",
    ]:
        resp_bad = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad_token}"})
        assert resp_bad.status_code == 401


def test_expired_token():
    """Verifies that an expired access token is rejected with 401."""
    expired_token = create_access_token(
        user_id="user-expired-001",
        username="expired_user",
        expires_in_seconds=-60,  # Expired 60 seconds ago
    )

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_wrong_signature_and_forged_token():
    """Verifies that a token signed with a foreign key or tampered payload is rejected."""
    # 1. Token signed with wrong secret key
    forged_token = create_access_token(
        user_id="admin-fake-001",
        username="admin",
        role="admin",
        secret_key="attacker_secret_key_1234567890",
    )

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 401
    assert "signature" in resp.json()["detail"].lower()

    # 2. Tampered token payload with valid header and signature
    valid_token = create_access_token(
        user_id="user-tamper-001",
        username="normal_user",
        role="engineer",
    )
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.tampered_payload_data.{parts[2]}"
    resp_tampered = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp_tampered.status_code == 401


def test_public_endpoint_behavior():
    """Verifies that public system/health endpoints remain accessible without auth."""
    # Health check
    resp_health = client.get("/health")
    assert resp_health.status_code == 200

    # System Root info
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "version" in resp_root.json()


def test_login_brute_force_lockout(db_session):
    """
    Verifies that excessive failed login attempts trigger HTTP 429 rate limiting (SEC-05 abuse deterrence).
    """
    from app.core.auth import login_rate_limiter
    login_rate_limiter.reset()

    target_user = "brute_force_target"

    # Attempt 5 invalid logins
    for i in range(5):
        resp = client.post("/api/v1/auth/login", json={
            "username": target_user,
            "password": f"wrong_password_{i}",
        })
        assert resp.status_code == 401

    # 6th attempt must be rejected with 429 Too Many Requests
    resp_locked = client.post("/api/v1/auth/login", json={
        "username": target_user,
        "password": "wrong_password_6",
    })
    assert resp_locked.status_code == 429
    assert "temporarily locked" in resp_locked.json()["detail"].lower()
    assert "Retry-After" in resp_locked.headers

    # Reset limiter
    login_rate_limiter.reset()


def test_registration_input_validation():
    """Verifies that registration rejects malformed usernames, invalid emails, and weak passwords."""
    # Malformed username with special characters
    resp_bad_user = client.post("/api/v1/auth/register", json={
        "username": "user<script>alert(1)</script>",
        "email": "valid@example.com",
        "password": "ValidPassword123!",
    })
    assert resp_bad_user.status_code == 422

    # Malformed email
    resp_bad_email = client.post("/api/v1/auth/register", json={
        "username": "valid_user",
        "email": "not-an-email",
        "password": "ValidPassword123!",
    })
    assert resp_bad_email.status_code == 422

    # Weak/short password (<8 chars)
    resp_short_pw = client.post("/api/v1/auth/register", json={
        "username": "valid_user_2",
        "email": "valid2@example.com",
        "password": "short",
    })
    assert resp_short_pw.status_code == 422


def test_oversized_auth_payload_rejected():
    """Verifies that an auth request body exceeding MAX_AUTH_BODY_BYTES (64 KB) is rejected with 413."""
    oversized_padding = "A" * (70 * 1024)  # 70 KB
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": "admin",
            "password": oversized_padding,
        },
    )
    assert resp.status_code == 413
    assert resp.json().get("code") == "PAYLOAD_TOO_LARGE"

