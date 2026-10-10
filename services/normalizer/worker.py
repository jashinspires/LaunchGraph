"""
Stage 2 Normalizer Autonomous Worker.
Consumes unprocessed SourceEvents, resolves change anchors, attaches ledger records, and computes lifecycle state.
"""

import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models.connection import SourceEvent
from launchgraph_core.db.models.change_graph import ChangeEvent
from services.normalizer.services.extractor import ReferenceExtractor
from services.normalizer.services.link_typing import LinkTypingEngine, LinkType
from services.normalizer.services.anchor_resolver import AnchorResolver
from services.normalizer.services.ledger_manager import LedgerManager
from services.normalizer.services.lifecycle import LifecycleTracker

logger = logging.getLogger("launchgraph.normalizer.worker")


async def process_unprocessed_source_events(session: AsyncSession, limit: int = 25) -> int:
    """
    Main processing step for normalization. Claims unhandled source events and attaches them to the context graph.
    """
    stmt = (
        select(SourceEvent)
        .where(SourceEvent.is_processed == False)
        .order_by(SourceEvent.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    source_events = list(result.scalars().all())

    if not source_events:
        return 0

    processed_count = 0
    for event in source_events:
        try:
            payload = event.raw_payload
            title = ""
            description = ""
            branch_name = None
            is_revert = False

            if event.source_type == "GITHUB":
                pr = payload.get("pull_request")
                if pr:
                    title = pr.get("title", "")
                    description = pr.get("body", "")
                    branch_name = pr.get("head", {}).get("ref")
                elif "commits" in payload and payload["commits"]:
                    first_commit = payload["commits"][0]
                    title = first_commit.get("message", "").split("\n")[0]
                    description = first_commit.get("message", "")
                elif "release" in payload:
                    title = payload["release"].get("name") or payload["release"].get("tag_name", "")
                    description = payload["release"].get("body", "")

            elif event.source_type == "JIRA":
                issue = payload.get("issue", {})
                fields = issue.get("fields", {})
                title = fields.get("summary", "")
                desc_field = fields.get("description")
                description = desc_field if isinstance(desc_field, str) else str(desc_field or "")

            elif event.source_type == "SLACK":
                slack_event = payload.get("event", {})
                title = (slack_event.get("text") or "").split("\n")[0][:100]
                description = slack_event.get("text", "")

            if not title:
                title = f"{event.source_type} Event {event.external_id}"

            # 1. Resolve Anchor and ChangeEvent
            change_event = await AnchorResolver.resolve_or_create_change_event(
                session=session,
                source_event=event,
                title=title,
                description=description
            )

            # 2. Determine Link Type
            link_type = LinkTypingEngine.determine_link_type(
                title=title,
                body=description,
                branch_name=branch_name,
                is_revert=is_revert
            )

            # 3. Attach Reference in Append-Only Ledger
            await LedgerManager.attach_reference(
                session=session,
                change_event=change_event,
                ref_type=f"{event.source_type}_{event.external_id.split(':')[0]}",
                ref_key=event.external_id,
                link_type=link_type.value,
                role="implements" if link_type == LinkType.L1_IMPLEMENTS else "context",
                source_event=event,
                attached_by="system",
                reason=f"Normalized from inbound {event.source_type} event."
            )

            # 4. Lifecycle State Update
            new_state = LifecycleTracker.evaluate_state(
                current_state=change_event.state,
                source_type=event.source_type,
                event_payload=payload
            )
            change_event.state = new_state

            # Mark processed
            event.is_processed = True
            processed_count += 1

        except Exception as exc:
            logger.error("Failed to normalize source event %s: %s", event.id, exc, exc_info=True)

    await session.flush()
    return processed_count
