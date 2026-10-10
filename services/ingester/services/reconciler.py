"""
Stage 1 Ingestion: Reconciler and Retention Sweeper
Handles periodic redelivery sweeps, connection health reconciliation, and 30-day raw payload purges.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models.connection import WebhookInbox, Connection
from launchgraph_core.config import settings

logger = logging.getLogger("launchgraph.ingester.reconciler")


class ReconcilerService:
    """
    Background maintenance routines ensuring data completeness and minimal storage footprint.
    """

    @classmethod
    async def purge_expired_inbox_payloads(
        cls,
        session: AsyncSession,
        retention_days: int = settings.DATA_RETENTION_DAYS
    ) -> int:
        """
        Purges raw webhook_inbox payloads older than retention_days (default 30 days)
        to minimize raw telemetry storage footprint.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = delete(WebhookInbox).where(WebhookInbox.received_at < cutoff_date)
        result = await session.execute(stmt)
        purged_count = result.rowcount
        logger.info("Purged %d raw webhook inbox records older than %d days.", purged_count, retention_days)
        return purged_count

    @classmethod
    async def reconcile_dead_letter_events(
        cls,
        session: AsyncSession,
        max_retries: int = 3
    ) -> int:
        """
        Scans for inbox events in 'failed' status and resets them for redelivery if under max_retries.
        """
        stmt = select(WebhookInbox).where(
            WebhookInbox.status == "failed",
            WebhookInbox.retry_count < max_retries
        )
        result = await session.execute(stmt)
        failed_records = list(result.scalars().all())

        for record in failed_records:
            record.status = "pending"
            record.retry_count += 1

        logger.info("Reconciled %d failed webhook records for redelivery.", len(failed_records))
        return len(failed_records)
