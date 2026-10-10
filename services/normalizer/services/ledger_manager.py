"""
Append-Only Membership Ledger Manager.
Enforces the strict invariant that entity attachments are immutable and soft-unlinked with audit rationale.
"""

import uuid
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models.change_graph import ChangeMembership, ChangeEvent
from launchgraph_core.db.models.connection import SourceEvent


class LedgerManager:
    """
    Manages attachments in the change_membership ledger table.
    """

    @classmethod
    async def attach_reference(
        cls,
        session: AsyncSession,
        change_event: ChangeEvent,
        ref_type: str,
        ref_key: str,
        link_type: str,
        role: str = "implements",
        source_event: Optional[SourceEvent] = None,
        attached_by: str = "system",
        reason: Optional[str] = None
    ) -> ChangeMembership:
        """
        Attaches a reference to a change event. Idempotent: checks for active matching entry.
        """
        existing_stmt = select(ChangeMembership).where(
            ChangeMembership.change_event_id == change_event.id,
            ChangeMembership.ref_key == ref_key,
            ChangeMembership.is_active == True
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            return existing

        membership = ChangeMembership(
            change_event_id=change_event.id,
            source_event_id=source_event.id if source_event else None,
            ref_type=ref_type,
            ref_key=ref_key,
            link_type=link_type,
            role=role,
            attached_by=attached_by,
            reason=reason,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        session.add(membership)
        await session.flush()
        return membership

    @classmethod
    async def soft_unlink_reference(
        cls,
        session: AsyncSession,
        membership_id: uuid.UUID,
        unlinked_by: str,
        unlink_reason: str
    ) -> bool:
        """
        Soft-unlinks a reference with mandatory audit rationale.
        Destructive database DELETE operations are prohibited by platform invariants.
        """
        if not unlink_reason or len(unlink_reason.strip()) < 5:
            raise ValueError("Mandatory audit unlink_reason of at least 5 characters is required.")

        stmt = select(ChangeMembership).where(
            ChangeMembership.id == membership_id,
            ChangeMembership.is_active == True
        )
        membership = (await session.execute(stmt)).scalar_one_or_none()
        if not membership:
            return False

        membership.is_active = False
        membership.unlinked_at = datetime.now(timezone.utc)
        membership.unlinked_by = unlinked_by
        membership.unlink_reason = unlink_reason
        await session.flush()
        return True
