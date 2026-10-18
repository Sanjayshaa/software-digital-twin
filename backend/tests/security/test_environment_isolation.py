"""
Phase 8.6.3 — Security Domain O: Subprocess Environment Sanitization & Secret Isolation Tests.

Verifies:
1. Step 11: Subprocess operations do not inherit sensitive server environment variables.
2. Synthetic canary credentials (DB passwords, JWT secrets, GitHub PATs, Cloud Keys)
   are strictly stripped from subprocess environments.
3. Safe system environment variables (PATH, HOME, Git controls) are preserved.
"""

import os
import pytest
from app.services.acquisition.git_provider import _get_sanitized_git_env


def test_subprocess_environment_sanitization():
    """
    Step 11 — Environment Sanitization Verification:
    Injects synthetic canary secrets into os.environ.
    Verifies that _get_sanitized_git_env() strips them completely.
    """
    canary_keys = {
        "POSTGRES_PASSWORD": "canary_db_secret_password_123",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        "SECRET_KEY": "canary_jwt_secret_key_456",
        "GITHUB_TOKEN": "ghp_canary_github_token_789",
        "AWS_SECRET_ACCESS_KEY": "canary_aws_secret_key_000",
        "GEMINI_API_KEY": "canary_gemini_api_key_abc",
        "JWT_SECRET": "canary_jwt_auth_secret_xyz",
    }

    # Inject canaries into active os.environ
    for k, v in canary_keys.items():
        os.environ[k] = v

    try:
        clean_env = _get_sanitized_git_env()

        # 1. Verify all sensitive canary keys and values are absent
        for k, v in canary_keys.items():
            assert k not in clean_env, f"CRITICAL LEAK: Sensitive variable '{k}' retained in subprocess env!"
            for env_val in clean_env.values():
                assert v not in env_val, f"CRITICAL LEAK: Sensitive value of '{k}' leaked in subprocess env!"

        # 2. Verify safe controls are present
        assert clean_env.get("GIT_TERMINAL_PROMPT") == "0"
        assert clean_env.get("GIT_OPTIONAL_LOCKS") == "0"
        assert "PATH" in clean_env

    finally:
        # Clean up canary environment variables
        for k in canary_keys:
            os.environ.pop(k, None)
