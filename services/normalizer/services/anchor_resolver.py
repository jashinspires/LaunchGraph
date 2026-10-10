"""
Anchor Resolution Engine.
Resolves primary change identity following the authoritative hierarchy:
Jira Epic -> Jira Issue -> GitHub PR -> Promoted Slack Thread.
"""

import uuid
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models.change_graph import ChangeEvent
from launchgraph_core.db.models.connection import SourceEvent
from services.normalizer.services.extractor import ReferenceExtractor


class AnchorResolver:
    """
    Selects or creates the canonical ChangeEvent for a given SourceEvent.
    """

    @classmethod
    async def resolve_or_create_change_event(
        cls,
        session: AsyncSession,
        source_event: SourceEvent,
        title: str,
        description: Optional[str] = None
    ) -> ChangeEvent:
        """
        Determines the anchor entity and links or instantiates the ChangeEvent.
        """
        payload = source_event.raw_payload
        refs = ReferenceExtractor.extract_from_text(f"{title} {description or ''}")

        # 1. Jira Epic (checked in payload fields if available)
        epic_key = payload.get("epic_key") or payload.get("fields", {}).get("epic", {}).get("key")
        if epic_key:
            anchor_ref = f"JIRA:{epic_key}"
        # 2. Jira Issue
        elif refs.jira_keys:
            anchor_ref = f"JIRA:{refs.jira_keys[0]}"
        elif source_event.source_type == "JIRA" and source_event.external_id.startswith("JIRA:"):
            anchor_ref = source_event.external_id
        # 3. GitHub PR
        elif refs.pr_numbers:
            anchor_ref = f"GITHUB:PR-{refs.pr_numbers[0]}"
        elif source_event.source_type == "GITHUB" and source_event.external_id.startswith("PR-"):
            anchor_ref = f"GITHUB:{source_event.external_id}"
        # 4. Promoted Slack Thread or other
        else:
            anchor_ref = source_event.external_id

        # Query existing ChangeEvent by anchor_ref in this workspace
        stmt = select(ChangeEvent).where(
            ChangeEvent.workspace_id == source_event.workspace_id,
            ChangeEvent.anchor_ref == anchor_ref
        )
        change_event = (await session.execute(stmt)).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if change_event:
            change_event.last_activity_at = now
            # Update description if currently empty
            if not change_event.description and description:
                change_event.description = description
        else:
            change_event = ChangeEvent(
                workspace_id=source_event.workspace_id,
                anchor_ref=anchor_ref,
                title=title,
                description=description,
                state="discovered",
                availability="unknown",
                last_activity_at=now,
                is_processed=False,
                created_at=now
            )
            session.add(change_event)
            await session.flush()

        return change_event
