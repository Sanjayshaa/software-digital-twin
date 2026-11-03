"""
Phase 2 — Webhook Security, Signature Verification & Credential Redaction.
"""

import hmac
import hashlib
import re
import logging
from typing import Optional, Set
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("twincore.pr_security")

MAX_WEBHOOK_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
REPLAY_WINDOW_MINUTES = 10

# In-memory delivery ID cache for replay protection
_SEEN_DELIVERIES: Set[str] = set()

# Secret redaction patterns
REDACTION_PATTERNS = [
    re.compile(r"(?i)(token|secret|password|bearer|authorization|api[-_]?key)[\"':\s=]+([a-zA-Z0-9_\-\.]{8,})"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{82}"),
    re.compile(r"glpat-[a-zA-Z0-9_\-]{20}"),
]


def verify_github_signature(payload_bytes: bytes, signature_header: Optional[str], secret: Optional[str]) -> bool:
    """
    Constant-time HMAC-SHA256 signature verification for GitHub webhooks.
    Zero leakage: never logs secret, returns boolean.
    """
    if not secret or not secret.strip():
        logger.warning("Webhook verification failed: No webhook secret configured.")
        return False

    if not signature_header or not signature_header.strip():
        logger.warning("Webhook verification failed: Missing X-Hub-Signature-256 header.")
        return False

    sig_parts = signature_header.strip().split("=", 1)
    if len(sig_parts) != 2 or sig_parts[0].lower() != "sha256":
        logger.warning("Webhook verification failed: Invalid signature header format.")
        return False

    expected_sig = sig_parts[1].strip()
    computed_sig = hmac.new(
        secret.strip().encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(expected_sig.lower(), computed_sig.lower())
    if not is_valid:
        logger.warning("Webhook verification failed: Signature mismatch.")
    return is_valid


def check_and_record_delivery(delivery_id: Optional[str], event_timestamp: Optional[datetime] = None) -> bool:
    """
    Prevents replay attacks by verifying delivery GUID uniqueness and timestamp freshness.
    Returns True if delivery is fresh and unique; False if duplicate or stale.
    """
    if not delivery_id:
        return True  # If no delivery ID provided, allow through (e.g. manual CLI trigger)

    if delivery_id in _SEEN_DELIVERIES:
        logger.warning("Replay detected: delivery ID %s has already been processed.", delivery_id)
        return False

    if event_timestamp:
        now = datetime.now(timezone.utc)
        if event_timestamp.tzinfo is None:
            event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)
        if now - event_timestamp > timedelta(minutes=REPLAY_WINDOW_MINUTES):
            logger.warning("Stale webhook event detected: timestamp %s exceeds window.", event_timestamp)
            return False

    _SEEN_DELIVERIES.add(delivery_id)
    # Prevent unbounded memory growth
    if len(_SEEN_DELIVERIES) > 10000:
        _SEEN_DELIVERIES.clear()
    return True


def redact_secrets(text: Optional[str]) -> str:
    """
    Redacts tokens, API keys, and sensitive content from markdown and logs.
    """
    if not text:
        return ""
    redacted = text
    for pattern in REDACTION_PATTERNS:
        if pattern.groups > 0:
            redacted = pattern.sub(r"\1: [REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
