"""
GitHub Webhook Receiver Endpoint.
Validates HMAC-SHA256 signature, deduplicates deliveries, scrubs secrets, and creates SourceEvents.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.session import get_async_session
from launchgraph_core.db.models.connection import Connection
from launchgraph_core.security.crypto import verify_github_signature
from launchgraph_core.config import settings
from services.ingester.services.event_processor import EventProcessor

router = APIRouter(prefix="/webhooks/github", tags=["GitHub Ingestion"])


@router.post("/{connection_id}")
async def receive_github_webhook(
    connection_id: uuid.UUID,
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Ingests live GitHub webhook deliveries:
    - pull_request.closed
    - push
    - release.published
    """
    body_bytes = await request.body()

    # 1. Fetch Connection
    stmt = select(Connection).where(Connection.id == connection_id, Connection.source_type == "GITHUB")
    connection = (await session.execute(stmt)).scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="GitHub connection not found.")

    # 2. Verify HMAC-SHA256 Signature
    # Credentials or default settings secret
    secret = connection.config.get("webhook_secret") or settings.GITHUB_WEBHOOK_SECRET or ""
    if not verify_github_signature(body_bytes, secret, x_hub_signature_256 or ""):
        raise HTTPException(status_code=401, detail="Invalid X-Hub-Signature-256 HMAC signature.")

    # 3. Parse JSON
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_type = x_github_event or payload.get("action", "unknown")
    delivery_id = x_github_delivery or str(uuid.uuid4())
    idempotency_key = f"github:{delivery_id}:{event_type}"

    # Handle ping event
    if event_type == "ping":
        return {"status": "ok", "message": "Pong! Connection verified."}

    # 4. Extract external ID (PR number, commit sha, release tag)
    external_id = "unknown"
    if "pull_request" in payload:
        external_id = f"PR-{payload['pull_request'].get('number')}"
    elif "release" in payload:
        external_id = f"REL-{payload['release'].get('tag_name')}"
    elif "after" in payload:
        external_id = f"COMMIT-{payload['after'][:12]}"

    # 5. Process through EventProcessor
    result = await EventProcessor.process_incoming_webhook(
        session=session,
        connection=connection,
        event_type=event_type,
        idempotency_key=idempotency_key,
        external_id=external_id,
        raw_payload=payload,
        trust_label="INTERNAL"
    )

    await session.commit()

    return {
        "status": "accepted",
        "duplicate": result.is_duplicate,
        "source_event_id": str(result.source_event_id) if result.source_event_id else None,
        "message": result.message
    }
