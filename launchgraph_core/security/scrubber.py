"""
B0.12 Secret Scrubber Engine
Sanitizes raw webhook payloads by redacting sensitive tokens, keys, and credentials
prior to persistence in the database or exposure to LLM contexts.
"""

import re
from typing import Any, Dict, List, Union

REDACTION_MARKER = "[REDACTED_SECRET]"

# Compiled high-performance regex patterns
PATTERNS = [
    # AWS Access Keys
    re.compile(r"\b(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b"),
    # GitHub Tokens
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
    # Slack Tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    # JSON Web Tokens (JWT)
    re.compile(r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]{10,}\.[A-Za-z0-9._-]{10,}\b"),
    # RSA / EC Private Keys
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"),
    # Generic API Tokens / Secrets
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|secret|password)[\s:=]+['\"]?([a-zA-Z0-9_\-]{20,})['\"]?"),
]


class SecretScrubber:
    """
    Recursive secret scrubbing engine for text strings, dictionaries, and nested structures.
    """

    @classmethod
    def scrub_text(cls, text: str) -> str:
        """Sanitizes text by replacing matching credentials with REDACTION_MARKER."""
        if not text or not isinstance(text, str):
            return text

        scrubbed = text
        for pattern in PATTERNS:
            # For the generic pattern, preserve key name and redact only the secret value
            if pattern.pattern.startswith("(?i)"):
                scrubbed = pattern.sub(r"\1: " + REDACTION_MARKER, scrubbed)
            else:
                scrubbed = pattern.sub(REDACTION_MARKER, scrubbed)

        return scrubbed

    @classmethod
    def scrub_payload(cls, data: Union[Dict[str, Any], List[Any], str, Any]) -> Any:
        """
        Recursively walks JSON structures, scrubbing any sensitive values.
        """
        if isinstance(data, dict):
            scrubbed_dict = {}
            for k, v in data.items():
                # Redact keys that obviously contain secrets
                if any(sec in k.lower() for sec in ["secret", "password", "token", "api_key", "auth", "private_key"]):
                    scrubbed_dict[k] = REDACTION_MARKER
                else:
                    scrubbed_dict[k] = cls.scrub_payload(v)
            return scrubbed_dict
        elif isinstance(data, list):
            return [cls.scrub_payload(item) for item in data]
        elif isinstance(data, str):
            return cls.scrub_text(data)
        return data
