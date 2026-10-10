"""
Jira Webhook Receiver Endpoint.
Ingests issue created, updated, and version released events with deduplication and secret scrubbing.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.session import get_async_session
from launchgraph_core.db.models.connection import Connection
from launchgraph_core.security.crypto import verify_jira_signature
from launchgraph_core.config import settings
from services.ingester.services.event_processor import EventProcessor

router = APIRouter(prefix="/webhooks/jira", tags=["Jira Ingestion"])


@router.post("/{connection_id}")
async def receive_jira_webhook(
    connection_id: uuid.UUID,
    request: Request,
    x_atlassian_webhook_identifier: Optional[str] = Header(None),
    x_hub_signature: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Ingests live Jira webhooks:
    - jira:issue_created
    - jira:issue_updated
    - version_released
    """
    body_bytes = await request.body()

    stmt = select(Connection).where(Connection.id == connection_id, Connection.source_type == "JIRA")
    connection = (await session.execute(stmt)).scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Jira connection not found.")

    # Verify signature if secret configured
    secret = connection.config.get("webhook_secret") or settings.JIRA_WEBHOOK_SECRET
    if secret and x_hub_signature:
        if not verify_jira_signature(body_bytes, secret, x_hub_signature):
            raise HTTPException(status_code=401, detail="Invalid Jira webhook signature.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_type = payload.get("webhookEvent", "jira:generic")
    timestamp = payload.get("timestamp", 0)

    issue = payload.get("issue")
    version = payload.get("version")

    if issue:
        issue_id = issue.get("id", str(uuid.uuid4()))
        issue_key = issue.get("key", "UNKNOWN")
        external_id = f"JIRA:{issue_key}"
        idempotency_key = f"jira:{issue_id}:{timestamp}"
    elif version:
        version_id = version.get("id", str(uuid.uuid4()))
        version_name = version.get("name", "release")
        external_id = f"JIRA:VER-{version_name}"
        idempotency_key = f"jira:version:{version_id}:{timestamp}"
    else:
        external_id = f"JIRA:{x_atlassian_webhook_identifier or uuid.uuid4()}"
        idempotency_key = f"jira:event:{timestamp}:{external_id}"

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
