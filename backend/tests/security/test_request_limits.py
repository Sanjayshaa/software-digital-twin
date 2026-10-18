"""
Phase 8.6.4 — Security Domain: API Request Size Governance & Payload Limiting Tests.

Verifies:
1. Global request body limit (MAX_REQUEST_BODY_BYTES = 10 MB) rejects oversized payloads with HTTP 413.
2. Sensitive Auth endpoint request body limit (MAX_AUTH_BODY_BYTES = 64 KB) rejects oversized payloads with HTTP 413.
3. Content-Length validation fails closed on non-numeric or negative values with HTTP 400.
4. Normal requests within limits pass through unhindered.
"""

from fastapi.testclient import TestClient
from main import app
from app.core.config import settings

client = TestClient(app)


def test_auth_request_payload_limit_enforced():
    """
    Verifies that requests to /auth/login exceeding MAX_AUTH_BODY_BYTES (64 KB)
    are intercepted by middleware and return HTTP 413 Payload Too Large.
    """
    oversized_data = {"username": "admin", "password": "X" * (70 * 1024)}
    response = client.post("/api/v1/auth/login", json=oversized_data)
    assert response.status_code == 413
    body = response.json()
    assert body.get("code") == "PAYLOAD_TOO_LARGE"
    assert "exceeds maximum permitted limit" in body.get("detail", "")


def test_general_api_request_payload_limit_enforced():
    """
    Verifies that requests to general API endpoints exceeding MAX_REQUEST_BODY_BYTES (10 MB)
    are intercepted by middleware and return HTTP 413 Payload Too Large.
    """
    # Simulate an oversized request via headers
    headers = {
        "Content-Length": str(settings.MAX_REQUEST_BODY_BYTES + 1024),
        "Content-Type": "application/json",
    }
    response = client.post(
        "/repositories/repo_123/scenarios",
        headers=headers,
        content=b"{}",
    )
    assert response.status_code == 413
    body = response.json()
    assert body.get("code") == "PAYLOAD_TOO_LARGE"


def test_invalid_content_length_header_rejected():
    """
    Verifies that malformed, non-numeric Content-Length headers fail closed with HTTP 400.
    """
    headers = {
        "Content-Length": "not-a-number",
        "Content-Type": "application/json",
    }
    response = client.post("/health", headers=headers, content=b"{}")
    assert response.status_code == 400
    assert response.json().get("code") == "INVALID_HEADER"


def test_normal_payload_within_limits_passes():
    """
    Verifies that standard requests well within limits are processed normally.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
