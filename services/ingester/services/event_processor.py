"""
Stage 1 Ingestion: Event Processor Service
Handles deduplication via webhook_inbox, secret scrubbing, and source_event creation.
"""

import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models.connection import Connection, WebhookInbox, SourceEvent
from launchgraph_core.security.scrubber import SecretScrubber


class IngestionResult:
    def __init__(self, is_duplicate: bool, source_event_id: Optional[uuid.UUID] = None, message: str = ""):
        self.is_duplicate = is_duplicate
        self.source_event_id = source_event_id
        self.message = message


class EventProcessor:
    """
    Coordinates atomic ingress from raw webhook to deduplicated, scrubbed source_event.
    """

    @classmethod
    async def process_incoming_webhook(
        cls,
        session: AsyncSession,
        connection: Connection,
        event_type: str,
        idempotency_key: str,
        external_id: str,
        raw_payload: Dict[str, Any],
        trust_label: str = "INTERNAL"
    ) -> IngestionResult:
        """
        Processes an inbound payload:
        1. Checks for idempotency key collision in webhook_inbox.
        2. Records raw verified payload into webhook_inbox buffer.
        3. Sanitizes payload using SecretScrubber.
        4. Writes clean SourceEvent ready for normalization.
        """
        # 1. Deduplication check
        existing_stmt = select(WebhookInbox).where(
            WebhookInbox.connection_id == connection.id,
            WebhookInbox.idempotency_key == idempotency_key
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            return IngestionResult(
                is_duplicate=True,
                message=f"Event already processed with idempotency key: {idempotency_key}"
            )

        # 2. Append to webhook_inbox
        inbox_record = WebhookInbox(
            connection_id=connection.id,
            idempotency_key=idempotency_key,
            event_type=event_type,
            payload=raw_payload,
            status="processed",
            received_at=datetime.now(timezone.utc)
        )
        session.add(inbox_record)

        # 3. Secret scrubbing
        scrubbed_payload = SecretScrubber.scrub_payload(raw_payload)

        # 4. Insert into source_events
        source_event = SourceEvent(
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
            source_type=connection.source_type,
            external_id=external_id,
            trust_label=trust_label,
            raw_payload=scrubbed_payload,
            is_processed=False,
            created_at=datetime.now(timezone.utc)
        )
        session.add(source_event)
        await session.flush()

        return IngestionResult(
            is_duplicate=False,
            source_event_id=source_event.id,
            message="Event successfully ingested and scrubbed."
        )
