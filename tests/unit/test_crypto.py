"""
Unit tests for Cryptographic Verification & API Key Hashing.
"""

import time
import hmac
import hashlib
from launchgraph_core.security.crypto import (
    verify_github_signature,
    verify_slack_signature,
    verify_jira_signature,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


def test_github_hmac_verification():
    secret = "my-secret-key"
    payload = b'{"action": "closed", "number": 42}'
    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    valid_sig = "sha256=" + mac.hexdigest()

    assert verify_github_signature(payload, secret, valid_sig) is True
    assert verify_github_signature(payload, secret, "sha256=invalid") is False
    assert verify_github_signature(payload, "wrong-secret", valid_sig) is False


def test_slack_signature_and_replay_prevention():
    secret = "slack-secret-123"
    payload = b'{"type": "event_callback"}'
    now_ts = str(int(time.time()))

    sig_basestring = f"v0:{now_ts}:{payload.decode('utf-8')}"
    mac = hmac.new(secret.encode("utf-8"), msg=sig_basestring.encode("utf-8"), digestmod=hashlib.sha256)
    valid_sig = "v0=" + mac.hexdigest()

    # Valid current timestamp
    assert verify_slack_signature(payload, secret, now_ts, valid_sig) is True

    # Expired timestamp (10 minutes ago) -> must fail due to replay prevention
    old_ts = str(int(time.time()) - 600)
    assert verify_slack_signature(payload, secret, old_ts, valid_sig) is False


def test_api_key_generation_and_verification():
    raw_key, key_prefix, key_hash = generate_api_key(prefix="launchgraph_live_")
    assert raw_key.startswith("launchgraph_live_")
    assert key_prefix == raw_key[:16]
    assert len(key_hash) == 64

    # Verify timing attack resistant helper
    assert verify_api_key(raw_key, key_hash) is True
    assert verify_api_key(raw_key + "tampered", key_hash) is False
