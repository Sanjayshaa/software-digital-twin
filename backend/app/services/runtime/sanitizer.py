"""
Phase 8.8 — Runtime Privacy Gateway & Sanitization Service.
Strict technical enforcement of zero customer-data leakage:
- Redacts credentials, tokens, cookies, auth headers, and secret keys
- Redacts PII: emails, phone numbers, payment card numbers, addresses, customer/account IDs, SSNs
- Recursively sanitizes nested dictionaries, lists, and raw log message strings
- Preserves technical telemetry: service, route, method, status, latency, error_type, trace_id, span_id
"""

import re
from typing import Dict, Any, Tuple, List, Union

# Keys matching any of these patterns have their values completely redacted to "[REDACTED]"
SENSITIVE_KEY_PATTERNS = [
    re.compile(r"^password$", re.IGNORECASE),
    re.compile(r"passwd", re.IGNORECASE),
    re.compile(r"^pwd$", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"private[-_]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"^jwt$", re.IGNORECASE),
    re.compile(r"api[-_]?key", re.IGNORECASE),
    re.compile(r"auth(?:orization)?", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"session[-_]?(?:id|token)?$", re.IGNORECASE),
    re.compile(r"email", re.IGNORECASE),
    re.compile(r"phone", re.IGNORECASE),
    re.compile(r"mobile", re.IGNORECASE),
    re.compile(r"telephone", re.IGNORECASE),
    re.compile(r"cell", re.IGNORECASE),
    re.compile(r"customer[-_]?id", re.IGNORECASE),
    re.compile(r"client[-_]?id", re.IGNORECASE),
    re.compile(r"user[-_]?id", re.IGNORECASE),
    re.compile(r"account[-_]?(?:number|id)", re.IGNORECASE),
    re.compile(r"ssn", re.IGNORECASE),
    re.compile(r"social[-_]?security", re.IGNORECASE),
    re.compile(r"tax[-_]?id", re.IGNORECASE),
    re.compile(r"card[-_]?(?:number|no)", re.IGNORECASE),
    re.compile(r"credit[-_]?card", re.IGNORECASE),
    re.compile(r"debit[-_]?card", re.IGNORECASE),
    re.compile(r"cvv|cvc", re.IGNORECASE),
    re.compile(r"pan[-_]?number", re.IGNORECASE),
    re.compile(r"address", re.IGNORECASE),
    re.compile(r"street", re.IGNORECASE),
    re.compile(r"zip[-_]?code|postal[-_]?code", re.IGNORECASE),
    re.compile(r"billing[-_]?address", re.IGNORECASE),
    re.compile(r"dob|birth[-_]?date|date[-_]?of[-_]?birth", re.IGNORECASE),
]

# In-string value regex patterns matching sensitive strings embedded in arbitrary text
SENSITIVE_VALUE_REGEXES = [
    # JWT tokens: header.payload.signature
    (re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"), "[REDACTED_JWT]"),
    # Bearer tokens in headers or logs
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    # Key=value token / secret pairs
    (re.compile(r"((?:password|token|secret|api_key|access_token|refresh_token|auth)=)([^\s&]+)", re.IGNORECASE), r"\1[REDACTED]"),
    # GitHub personal access tokens
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    # OpenAI / Anthropic / SaaS API keys
    (re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\b(?:sk_live|pk_live)_[0-9a-zA-Z]{24,}\b"), "[REDACTED_STRIPE_KEY]"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"), "[REDACTED_EMAIL]"),
    # Credit Card numbers (13 to 19 digits with spaces or hyphens)
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CARD]"),
    (re.compile(r"\b\d{15,16}\b"), "[REDACTED_CARD]"),
    # Phone numbers (domestic & international formats)
    (re.compile(r"(?:\+\d{1,3}[-.\s]*)?(?:\(?\d{2,4}\)?[-.\s]*)?\d{3,4}[-.\s]*\d{4}\b"), "[REDACTED_PHONE]"),
]


class SensitiveDataSanitizer:
    """
    Runtime Privacy Gateway:
    Enforces that zero customer-data or credentials enter the Digital Twin.
    """

    def sanitize_event(
        self,
        attributes: Dict[str, Any],
        message: str = None,
    ) -> Tuple[Dict[str, Any], str, bool]:
        """
        Recursively redacts sensitive values from attributes dictionary and message.
        Returns: (sanitized_attributes, sanitized_message, was_redacted)
        """
        was_redacted = False

        sanitized_attrs, attr_redacted = self._sanitize_dict(attributes or {})
        if attr_redacted:
            was_redacted = True

        sanitized_message = message
        if message:
            for pattern, replacement in SENSITIVE_VALUE_REGEXES:
                if pattern.search(sanitized_message):
                    sanitized_message = pattern.sub(replacement, sanitized_message)
                    was_redacted = True

        return sanitized_attrs, sanitized_message, was_redacted

    def sanitize_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method to sanitize an attributes dictionary directly."""
        sanitized_attrs, _, _ = self.sanitize_event(attributes=attributes)
        return sanitized_attrs

    def sanitize_text(self, text: str) -> Tuple[str, bool]:
        """Sanitizes an arbitrary text string against all value regexes."""
        if not text or not isinstance(text, str):
            return text, False
        cleaned = text
        was_redacted = False
        for pattern, replacement in SENSITIVE_VALUE_REGEXES:
            if pattern.search(cleaned):
                cleaned = pattern.sub(replacement, cleaned)
                was_redacted = True
        return cleaned, was_redacted

    def _sanitize_dict(self, d: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        sanitized = {}
        redacted = False

        for k, v in d.items():
            key_str = str(k)
            if self._is_sensitive_key(key_str):
                sanitized[k] = "[REDACTED]"
                redacted = True
            elif isinstance(v, dict):
                sub_dict, sub_redacted = self._sanitize_dict(v)
                sanitized[k] = sub_dict
                if sub_redacted:
                    redacted = True
            elif isinstance(v, list):
                sub_list, sub_redacted = self._sanitize_list(v)
                sanitized[k] = sub_list
                if sub_redacted:
                    redacted = True
            elif isinstance(v, str):
                cleaned_str, val_redacted = self.sanitize_text(v)
                sanitized[k] = cleaned_str
                if val_redacted:
                    redacted = True
            else:
                sanitized[k] = v

        return sanitized, redacted

    def _sanitize_list(self, lst: List[Any]) -> Tuple[List[Any], bool]:
        sanitized_list = []
        redacted = False
        for item in lst:
            if isinstance(item, dict):
                sub_dict, sub_red = self._sanitize_dict(item)
                sanitized_list.append(sub_dict)
                if sub_red:
                    redacted = True
            elif isinstance(item, list):
                sub_lst, sub_red = self._sanitize_list(item)
                sanitized_list.append(sub_lst)
                if sub_red:
                    redacted = True
            elif isinstance(item, str):
                cleaned_str, val_red = self.sanitize_text(item)
                sanitized_list.append(cleaned_str)
                if val_red:
                    redacted = True
            else:
                sanitized_list.append(item)
        return sanitized_list, redacted

    def _is_sensitive_key(self, key: str) -> bool:
        return any(pattern.search(key) for pattern in SENSITIVE_KEY_PATTERNS)


sensitive_sanitizer = SensitiveDataSanitizer()
