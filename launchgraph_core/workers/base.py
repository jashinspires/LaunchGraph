"""
Worker loop abstractions and PostgreSQL SKIP LOCKED job coordination.
"""

import asyncio
import logging
from typing import Callable, Awaitable, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.session import async_session_scope
from launchgraph_core.db.models.platform import Job

logger = logging.getLogger("launchgraph.workers")


async def claim_next_jobs(
    session: AsyncSession,
    worker_id: str,
    job_type: Optional[str] = None,
    limit: int = 10
) -> list[Job]:
    """
    Atomically claims scheduled jobs using PostgreSQL SKIP LOCKED semantics.
    Falls back gracefully when running in SQLite test mode.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(Job)
        .where(Job.status == "pending")
        .where(Job.scheduled_at <= now)
        .order_by(Job.scheduled_at.asc())
        .limit(limit)
    )

    if job_type:
        stmt = stmt.where(Job.job_type == job_type)

    # Use with_for_update(skip_locked=True) on PostgreSQL
    try:
        stmt = stmt.with_for_update(skip_locked=True)
        result = await session.execute(stmt)
        jobs = list(result.scalars().all())
    except Exception:
        # Fallback for dialects without skip_locked support (like SQLite in tests)
        stmt_fallback = select(Job).where(Job.status == "pending").limit(limit)
        if job_type:
            stmt_fallback = stmt_fallback.where(Job.job_type == job_type)
        result = await session.execute(stmt_fallback)
        jobs = list(result.scalars().all())

    for job in jobs:
        job.status = "processing"
        job.locked_at = now
        job.locked_by = worker_id

    if jobs:
        await session.flush()

    return jobs


async def autonomous_worker_loop(
    service_name: str,
    process_fn: Callable[[AsyncSession], Awaitable[int]],
    poll_interval_seconds: float = 2.0,
    stop_event: Optional[asyncio.Event] = None
) -> None:
    """
    Perpetual background worker loop enforcing backpressure and transactional isolation.
    """
    logger.info("Starting autonomous worker loop for %s", service_name)
    while stop_event is None or not stop_event.is_set():
        try:
            async with async_session_scope() as session:
                processed_count = await process_fn(session)
                if processed_count > 0:
                    logger.debug("%s processed %d records.", service_name, processed_count)
                    # Loop immediately to drain work without idling
                    continue
        except asyncio.CancelledError:
            logger.info("Worker loop for %s cancelled.", service_name)
            break
        except Exception as exc:
            logger.error("Error in %s worker loop: %s", service_name, exc, exc_info=True)

        try:
            await asyncio.sleep(poll_interval_seconds)
        except asyncio.CancelledError:
            break
