import re
from typing import Dict, Any, Tuple

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"passwd", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[-_]?key", re.IGNORECASE),
    re.compile(r"auth(?:orization)?", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
    re.compile(r"session", re.IGNORECASE),
    re.compile(r"private[-_]?key", re.IGNORECASE),
]

SENSITIVE_VALUE_REGEXES = [
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"(password|token|secret|api_key)=([^\s&]+)", re.IGNORECASE),
]


class SensitiveDataSanitizer:
    """
    Sanitizes and redacts sensitive credentials, tokens, and PII from runtime events
    before database persistence.
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

        sanitized_attrs, attr_redacted = self._sanitize_dict(attributes)
        if attr_redacted:
            was_redacted = True

        sanitized_message = message
        if message:
            for pattern in SENSITIVE_VALUE_REGEXES:
                if pattern.search(sanitized_message):
                    sanitized_message = pattern.sub(r"\1=[REDACTED]", sanitized_message)
                    was_redacted = True

        return sanitized_attrs, sanitized_message, was_redacted

    def sanitize_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method to sanitize an attributes dictionary directly."""
        sanitized_attrs, _, _ = self.sanitize_event(attributes=attributes)
        return sanitized_attrs

    def _sanitize_dict(self, d: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        sanitized = {}
        redacted = False

        for k, v in d.items():
            if self._is_sensitive_key(str(k)):
                sanitized[k] = "[REDACTED]"
                redacted = True
            elif isinstance(v, dict):
                sub_dict, sub_redacted = self._sanitize_dict(v)
                sanitized[k] = sub_dict
                if sub_redacted:
                    redacted = True
            elif isinstance(v, list):
                sub_list = []
                for item in v:
                    if isinstance(item, dict):
                        item_dict, item_redacted = self._sanitize_dict(item)
                        sub_list.append(item_dict)
                        if item_redacted:
                            redacted = True
                    else:
                        sub_list.append(item)
                sanitized[k] = sub_list
            elif isinstance(v, str):
                cleaned_str = v
                for pattern in SENSITIVE_VALUE_REGEXES:
                    if pattern.search(cleaned_str):
                        cleaned_str = pattern.sub(r"\1=[REDACTED]", cleaned_str)
                        redacted = True
                sanitized[k] = cleaned_str
            else:
                sanitized[k] = v

        return sanitized, redacted

    def _is_sensitive_key(self, key: str) -> bool:
        return any(pattern.search(key) for pattern in SENSITIVE_KEY_PATTERNS)


sensitive_sanitizer = SensitiveDataSanitizer()
