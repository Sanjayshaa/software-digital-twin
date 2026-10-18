"""
Phase 8.6.4 — Security Domain Q & R: CORS Configuration and Security Headers Remediation.

Verifies:
1. SEC-06 closure: Disallowed origins do not receive Access-Control-Allow-Origin headers.
2. Allowed origins (localhost / configured origins) receive proper CORS headers.
3. Preflight OPTIONS requests validate methods and allowed headers.
4. Malicious subdomains and lookalikes are rejected.
5. Invariant: Wildcard origins cannot be combined with credentials.
6. Standard security response headers (nosniff, frame-ancestors, referrer-policy) are enforced.
"""

import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from main import app

client = TestClient(app)


def test_cors_allowed_development_origin():
    """Verifies that an explicitly allowed local development origin receives CORS headers."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_disallowed_origin_rejected():
    """Verifies that an unauthorized origin (e.g. evil.com) does NOT receive Access-Control-Allow-Origin."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_malicious_subdomain_or_suffix_rejected():
    """Verifies that attacker-controlled domains containing 'localhost' (e.g. localhost.evil.com) are rejected."""
    malicious_origins = [
        "http://localhost.evil.com",
        "http://evil-localhost:3000",
        "https://localhost:3000.attacker.com",
        "http://127.0.0.1.attacker.com",
    ]
    for origin in malicious_origins:
        response = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None, (
            f"Permissive CORS header granted to untrusted origin: {origin}"
        )


def test_cors_null_origin_rejected():
    """Verifies that a 'null' origin does not receive permissive CORS headers."""
    response = client.options(
        "/health",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_wildcard_with_credentials_invariant():
    """SEC-06 Invariant: Combining wildcard origin '*' with credentials must raise an error."""
    with pytest.raises(ValueError, match="SEC-06 Invariant"):
        s = Settings(
            CORS_ALLOWED_ORIGINS=["*"],
            CORS_ALLOW_CREDENTIALS=True,
        )
        s.validate_cors()


def test_cors_preflight_allows_authorization_header():
    """Verifies preflight request specifically permits Authorization and Content-Type headers."""
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert response.status_code == 200
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "content-type" in allow_headers


def test_security_headers_present_on_endpoints():
    """Verifies that standard security response headers are present on API responses."""
    endpoints = ["/health", "/", "/auth/me"]
    for ep in endpoints:
        response = client.get(ep)
        headers = response.headers
        assert headers.get("x-content-type-options") == "nosniff", f"Missing X-Content-Type-Options on {ep}"
        assert headers.get("x-frame-options") == "DENY", f"Missing X-Frame-Options on {ep}"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin", f"Missing Referrer-Policy on {ep}"
        assert "frame-ancestors 'none'" in headers.get("content-security-policy", ""), f"Missing CSP frame-ancestors on {ep}"

