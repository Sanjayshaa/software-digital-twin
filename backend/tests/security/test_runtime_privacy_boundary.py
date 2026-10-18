"""
Phase 8.8 — Adversarial Runtime Privacy Boundary Tests.
Strict technical validation of the Privacy Gateway:
Verifies that no PII, credentials, or customer data can cross into the Runtime Twin.
"""

import pytest
from app.services.runtime.sanitizer import sensitive_sanitizer


class TestRuntimePrivacyBoundary:
    """Adversarial test suite challenging the Runtime Privacy Gateway."""

    def test_email_redaction_in_keys_and_values(self):
        """Validates that emails in keys and values are redacted."""
        payload = {
            "email": "customer.alice@enterprise.com",
            "user_email": "bob.smith@fintech.io",
            "log": "Failed checkout for user test.account+123@gmail.com with error 500",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        assert sanitized["email"] == "[REDACTED]"
        assert sanitized["user_email"] == "[REDACTED]"
        assert "test.account+123@gmail.com" not in sanitized["log"]
        assert "[REDACTED_EMAIL]" in sanitized["log"]

    def test_phone_number_redaction(self):
        """Validates that international and domestic phone numbers are sanitized."""
        payload = {
            "phone": "+1-800-555-0199",
            "mobile_number": "(415) 555-2671",
            "sms_log": "Verification code sent to +44 20 7946 0912 successfully.",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        assert sanitized["phone"] == "[REDACTED]"
        assert sanitized["mobile_number"] == "[REDACTED]"
        assert "+44 20 7946 0912" not in sanitized["sms_log"]
        assert "[REDACTED_PHONE]" in sanitized["sms_log"]

    def test_customer_and_account_id_redaction(self):
        """Validates that customer IDs, client IDs, SSNs, and account IDs are redacted."""
        payload = {
            "customer_id": "cust_99214_omega",
            "client_id": "client_secret_xyz",
            "user_id": "usr_internal_4821",
            "account_number": "ACC-9921-4810-12",
            "ssn": "000-12-3456",
            "tax_id": "99-1234567",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        for key in payload.keys():
            assert sanitized[key] == "[REDACTED]", f"Expected {key} to be redacted!"

    def test_address_and_postal_redaction(self):
        """Validates that street addresses and postal codes are redacted."""
        payload = {
            "address": "123 Market St, Suite 400",
            "street": "742 Evergreen Terrace",
            "zip_code": "94105",
            "postal_code": "SW1A 1AA",
            "billing_address": "PO Box 4410",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        for key in payload.keys():
            assert sanitized[key] == "[REDACTED]", f"Expected {key} to be redacted!"

    def test_payment_and_credit_card_redaction(self):
        """Validates that 16-digit credit cards, CVVs, and PAN numbers are redacted."""
        payload = {
            "card_number": "4111-2222-3333-4444",
            "credit_card": "5500 0000 0000 0004",
            "cvv": "991",
            "log": "Transaction rejected on card 4111222233334444 due to insufficient funds.",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        assert sanitized["card_number"] == "[REDACTED]"
        assert sanitized["credit_card"] == "[REDACTED]"
        assert sanitized["cvv"] == "[REDACTED]"
        assert "4111222233334444" not in sanitized["log"]
        assert "[REDACTED_CARD]" in sanitized["log"]

    def test_jwt_token_redaction(self):
        """Validates that signed JWT tokens in strings are redacted."""
        sample_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        payload = {
            "jwt": sample_jwt,
            "error": f"Authorization verification failed for token {sample_jwt} at gateway",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        assert sanitized["jwt"] == "[REDACTED]"
        assert sample_jwt not in sanitized["error"]
        assert "[REDACTED_JWT]" in sanitized["error"]

    def test_api_keys_and_secret_redaction(self):
        """Validates that GitHub PATs, OpenAI keys, AWS keys, and Stripe keys are redacted."""
        gh_pat = "".join(["ghp_", "1234567890abcdefghijklmnopqrstuvwxyz"])
        openai_key = "".join(["sk-", "abcdefghijklmnopqrstuvwxyz1234567890"])
        aws_key = "AKIAIOSFODNN7EXAMPLE"
        stripe_key = "".join(["sk_", "live_", "51A2B3C4D5E6F7G8H9I0J1K2L3"])

        payload = {
            "api_key": "some_generic_key_here",
            "msg": f"Failed with {gh_pat} and {openai_key} using {aws_key} on {stripe_key}",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        assert sanitized["api_key"] == "[REDACTED]"
        assert gh_pat not in sanitized["msg"]
        assert openai_key not in sanitized["msg"]
        assert aws_key not in sanitized["msg"]
        assert stripe_key not in sanitized["msg"]

    def test_cookies_and_authorization_headers(self):
        """Validates that cookie headers and Bearer auth tokens are redacted."""
        oauth_dummy = "".join(["ya29.", "a0AfH6SMD_very_secret_oauth_token"])
        payload = {
            "cookie": "sessionid=xyz123; tracking=abc456",
            "authorization": f"Bearer {oauth_dummy}",
            "log": "Request header: Authorization: Bearer secret_access_token_value_here",
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)
        assert sanitized["cookie"] == "[REDACTED]"
        assert sanitized["authorization"] == "[REDACTED]"
        assert "secret_access_token_value_here" not in sanitized["log"]
        assert "Bearer [REDACTED_TOKEN]" in sanitized["log"]

    def test_deeply_nested_adversarial_payload(self):
        """Validates that nested dicts and lists with mixed PII are recursively sanitized."""
        payload = {
            "service": "checkout_service",
            "status": 500,
            "latency_ms": 142.5,
            "route": "/api/v1/checkout",
            "environment": "production",
            "meta": {
                "user": {
                    "email": "nested.user@company.org",
                    "cards": [
                        {"credit_card": "4111-2222-3333-4444", "cvv": "123"},
                        {"card_number": "5500 0000 0000 0004"},
                    ],
                },
                "audit": [
                    "User with email admin@corp.net updated phone to +1-555-888-9999",
                    {"session_token": "secret_session_token_123"},
                ],
            },
        }
        sanitized = sensitive_sanitizer.sanitize_attributes(payload)

        # Operational metrics preserved
        assert sanitized["service"] == "checkout_service"
        assert sanitized["status"] == 500
        assert sanitized["latency_ms"] == 142.5
        assert sanitized["route"] == "/api/v1/checkout"
        assert sanitized["environment"] == "production"

        # PII and credentials redacted
        assert sanitized["meta"]["user"]["email"] == "[REDACTED]"
        assert sanitized["meta"]["user"]["cards"][0]["credit_card"] == "[REDACTED]"
        assert sanitized["meta"]["user"]["cards"][0]["cvv"] == "[REDACTED]"
        assert sanitized["meta"]["user"]["cards"][1]["card_number"] == "[REDACTED]"
        assert "admin@corp.net" not in sanitized["meta"]["audit"][0]
        assert "[REDACTED_EMAIL]" in sanitized["meta"]["audit"][0]
        assert "+1-555-888-9999" not in sanitized["meta"]["audit"][0]
        assert "[REDACTED_PHONE]" in sanitized["meta"]["audit"][0]
        assert sanitized["meta"]["audit"][1]["session_token"] == "[REDACTED]"
