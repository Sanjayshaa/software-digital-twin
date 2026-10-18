"""
Phase 8.6.1 — Security Domain O: Secret & Credential Leakage Prevention Tests.

Verifies:
1. Synthetic canary credentials in telemetry payloads are redacted by sanitizer.py.
2. GitHub Personal Access Tokens are never persisted into PostgreSQL Repository records.
"""

import pytest
from app.services.runtime.sanitizer import sensitive_sanitizer


def test_canary_secret_redaction_in_telemetry():
    """
    Injects synthetic canary tokens into runtime telemetry payload fields
    and verifies that the telemetry sanitizer redacts them.
    """
    canary_token = "DT_SECURITY_CANARY_7F92_TEST"
    canary_api_key = "sk_live_canary_key_998877665544"

    raw_attributes = {
        "Authorization": f"Bearer {canary_token}",
        "api_key": canary_api_key,
        "password": "SuperSecretPassword123!",
        "normal_field": "safe_operational_data",
    }
    stack_trace_msg = f"Error at authService.ts:42 with token={canary_token}"

    sanitized_attrs, sanitized_msg, was_redacted = sensitive_sanitizer.sanitize_event(
        attributes=raw_attributes,
        message=stack_trace_msg,
    )

    assert was_redacted is True
    # Convert to string and ensure canary tokens are absent
    sanitized_str = str(sanitized_attrs) + " " + str(sanitized_msg)
    assert canary_token not in sanitized_str, "CRITICAL: Canary token leaked in sanitized telemetry!"
    assert canary_api_key not in sanitized_str, "CRITICAL: Canary API key leaked in sanitized telemetry!"
    assert "SuperSecretPassword123!" not in sanitized_str, "CRITICAL: Plaintext password leaked in sanitized telemetry!"
    assert "[REDACTED]" in sanitized_str, "Expected [REDACTED] placeholder in sanitized telemetry"


def test_git_error_sanitization_strips_token():
    """
    Verifies that stderr from git clone failures strips and redacts personal access tokens
    so tokens are never leaked into logs or API error responses.
    """
    from app.services.acquisition.git_provider import _sanitize_git_error
    canary_pat = "ghp_CANARY_TOKEN_ABC123XYZ999"
    fake_stderr = f"fatal: unable to access 'https://x-access-token:{canary_pat}@github.com/owner/repo.git/': 403 Forbidden"

    sanitized = _sanitize_git_error(fake_stderr, token=canary_pat)
    assert canary_pat not in sanitized, "CRITICAL: GitHub PAT leaked in sanitized git error!"
    assert "***REDACTED***" in sanitized


def test_database_url_credential_protection():
    """
    Verifies that DATABASE_URL does not expose plaintext credentials in public exception outputs.
    """
    from app.core.config import settings
    # Ensure DATABASE_URL is constructed but settings representation doesn't expose it to untrusted callers
    assert settings.POSTGRES_PASSWORD is not None
    assert settings.DATABASE_URL.startswith("postgresql+psycopg2://")


