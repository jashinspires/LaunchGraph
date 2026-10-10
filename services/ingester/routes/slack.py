"""
Slack Events API Receiver Endpoint.
Validates HMAC-SHA256 signature with 5-minute replay prevention, handles challenge handshakes,
and ingests opt-in change notifications without historical channel crawling.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.session import get_async_session
from launchgraph_core.db.models.connection import Connection
from launchgraph_core.security.crypto import verify_slack_signature
from launchgraph_core.config import settings
from services.ingester.services.event_processor import EventProcessor

router = APIRouter(prefix="/webhooks/slack", tags=["Slack Ingestion"])


@router.post("/{connection_id}")
async def receive_slack_webhook(
    connection_id: uuid.UUID,
    request: Request,
    x_slack_signature: Optional[str] = Header(None),
    x_slack_request_timestamp: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Ingests live Slack Events API deliveries.
    Strict enterprise posture: Zero conversation history crawling.
    """
    body_bytes = await request.body()

    stmt = select(Connection).where(Connection.id == connection_id, Connection.source_type == "SLACK")
    connection = (await session.execute(stmt)).scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Slack connection not found.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    # 1. URL Verification Handshake
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    # 2. Verify Slack Signature with timestamp replay prevention
    secret = connection.config.get("signing_secret") or settings.SLACK_SIGNING_SECRET or ""
    if not verify_slack_signature(body_bytes, secret, x_slack_request_timestamp or "", x_slack_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid Slack webhook signature or expired timestamp.")

    # 3. Process Event Callback
    event_id = payload.get("event_id", str(uuid.uuid4()))
    event = payload.get("event", {})
    event_type = event.get("type", "message")
    channel = event.get("channel", "unknown")
    ts = event.get("ts", "0")

    idempotency_key = f"slack:{event_id}"
    external_id = f"SLACK:{channel}:{ts}"

    result = await EventProcessor.process_incoming_webhook(
        session=session,
        connection=connection,
        event_type=f"slack:{event_type}",
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
