"""
Cryptographic verification and API key hashing utilities.
"""

import hmac
import hashlib
import time
import secrets
from typing import Tuple


def verify_github_signature(payload_bytes: bytes, secret: str, header_signature: str) -> bool:
    """
    Verifies GitHub's X-Hub-Signature-256 HMAC-SHA256 signature.
    """
    if not header_signature or not secret:
        return False

    mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, header_signature)


def verify_slack_signature(payload_bytes: bytes, secret: str, timestamp_str: str, signature: str) -> bool:
    """
    Verifies Slack's X-Slack-Signature with mandatory 5-minute replay window check.
    """
    if not signature or not secret or not timestamp_str:
        return False

    try:
        ts = int(timestamp_str)
        # Reject requests older or newer than 5 minutes to prevent replay attacks
        if abs(time.time() - ts) > 300:
            return False
    except ValueError:
        return False

    sig_basestring = f"v0:{timestamp_str}:{payload_bytes.decode('utf-8')}"
    mac = hmac.new(secret.encode("utf-8"), msg=sig_basestring.encode("utf-8"), digestmod=hashlib.sha256)
    expected = "v0=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_jira_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:
    """
    Verifies Jira webhook payload signature if HMAC configured, or verifies bearer token.
    """
    if not signature or not secret:
        return False

    mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    # Support both raw hex and sha256= prefix
    if signature.startswith("sha256="):
        expected = "sha256=" + expected
    return hmac.compare_digest(expected, signature)


def generate_api_key(prefix: str = "launchgraph_live_") -> Tuple[str, str, str]:
    """
    Generates a secure API key, its cleartext prefix, and its SHA-256 hash.
    Returns: (raw_key, key_prefix, key_hash)
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{random_part}"
    key_prefix = raw_key[:16]
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return raw_key, key_prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    """Computes SHA-256 hash of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Timing-attack-resistant verification of an API key against its stored hash."""
    computed_hash = hash_api_key(raw_key)
    return hmac.compare_digest(computed_hash, stored_hash)
