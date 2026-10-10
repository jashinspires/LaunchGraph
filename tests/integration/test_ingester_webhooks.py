"""
Integration tests for Ingester microservice webhook routes.
"""

import json
import time
import hmac
import hashlib
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models import WebhookInbox, SourceEvent


@pytest.mark.asyncio
async def test_github_webhook_endpoint_valid_and_invalid_hmac(
    ingester_client: AsyncClient,
    test_connections: dict,
    db_session: AsyncSession
):
    gh_conn = test_connections["github"]
    secret = "test-github-secret"

    payload = {
        "action": "closed",
        "number": 142,
        "pull_request": {
            "id": 101,
            "number": 142,
            "title": "PROJ-1024: Add OAuth support",
            "body": "Fixes #139. Dev AWS key AKIAIOSFODNN7EXAMPLE",
            "state": "closed",
            "merged": True
        },
        "repository": {"id": 1, "name": "backend", "full_name": "acme/backend", "html_url": "https://github.com/acme/backend"},
        "sender": {"login": "octocat", "id": 1}
    }
    payload_bytes = json.dumps(payload).encode("utf-8")

    # 1. Invalid signature -> 401
    bad_res = await ingester_client.post(
        f"/webhooks/github/{gh_conn.id}",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": "sha256=invalidhex",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-uuid-001"
        }
    )
    assert bad_res.status_code == 401

    # 2. Valid HMAC signature -> 200 accepted
    mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    valid_sig = "sha256=" + mac.hexdigest()

    good_res = await ingester_client.post(
        f"/webhooks/github/{gh_conn.id}",
        content=payload_bytes,
        headers={
            "X-Hub-Signature-256": valid_sig,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-uuid-001",
            "Content-Type": "application/json"
        }
    )
    assert good_res.status_code == 200
    res_data = good_res.json()
    assert res_data["status"] == "accepted"
    assert res_data["duplicate"] is False

    # 3. Verify SourceEvent was created and secret was scrubbed!
    source_stmt = select(SourceEvent).where(SourceEvent.connection_id == gh_conn.id)
    source_event = (await db_session.execute(source_stmt)).scalar_one()
    assert source_event.external_id == "PR-142"
    assert "AKIAIOSFODNN7EXAMPLE" not in source_event.raw_payload["pull_request"]["body"]
    assert "[REDACTED_SECRET]" in source_event.raw_payload["pull_request"]["body"]


@pytest.mark.asyncio
async def test_slack_challenge_handshake(ingester_client: AsyncClient, test_connections: dict):
    slack_conn = test_connections["slack"]
    challenge_payload = {
        "token": "verification_token",
        "challenge": "sample_challenge_token_xyz_123",
        "type": "url_verification"
    }

    res = await ingester_client.post(
        f"/webhooks/slack/{slack_conn.id}",
        json=challenge_payload
    )
    assert res.status_code == 200
    assert res.json()["challenge"] == "sample_challenge_token_xyz_123"
