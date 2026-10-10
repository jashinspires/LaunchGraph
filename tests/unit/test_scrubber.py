"""
Unit tests for Secret Scrubber Engine.
"""

from launchgraph_core.security.scrubber import SecretScrubber, REDACTION_MARKER


def test_scrub_aws_access_key():
    text = "Deployment failed with AWS credential AKIAIOSFODNN7EXAMPLE on region us-west-2."
    scrubbed = SecretScrubber.scrub_text(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert REDACTION_MARKER in scrubbed


def test_scrub_github_token():
    text = "Configured remote auth using ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    scrubbed = SecretScrubber.scrub_text(text)
    assert "ghp_" not in scrubbed
    assert REDACTION_MARKER in scrubbed


def test_scrub_jwt_token():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    text = f"Bearer token received: {jwt}"
    scrubbed = SecretScrubber.scrub_text(text)
    assert jwt not in scrubbed
    assert REDACTION_MARKER in scrubbed


def test_scrub_private_key():
    pk = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Y...\n-----END RSA PRIVATE KEY-----"
    text = f"Server loaded key:\n{pk}\nReady to accept connections."
    scrubbed = SecretScrubber.scrub_text(text)
    assert "MIIEow" not in scrubbed
    assert REDACTION_MARKER in scrubbed


def test_recursive_payload_scrubbing():
    payload = {
        "repository": "acme/backend",
        "author": "dev@acme.com",
        "commit": {
            "message": "Update AWS secret AKIA1111111111111111 in production",
            "files": ["config.py"],
            "metadata": {
                "access_token": "secret_live_token_99999999999999999999"
            }
        },
        "tags": ["release", "ghp_111111111111111111111111111111111111"]
    }

    scrubbed = SecretScrubber.scrub_payload(payload)
    assert scrubbed["repository"] == "acme/backend"
    assert "AKIA1111111111111111" not in scrubbed["commit"]["message"]
    assert REDACTION_MARKER in scrubbed["commit"]["message"]
    assert scrubbed["commit"]["metadata"]["access_token"] == REDACTION_MARKER
    assert scrubbed["tags"][1] == REDACTION_MARKER
