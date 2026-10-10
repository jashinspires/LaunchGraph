"""
Milestone M1 Verification Gate: Replay Storm Test.
Processes 1,000 duplicate and out-of-order webhook events verifying zero duplicate source_events.
"""

import random
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models import SourceEvent, WebhookInbox
from services.ingester.services.event_processor import EventProcessor


@pytest.mark.asyncio
async def test_replay_storm_zero_duplicate_source_events(
    db_session: AsyncSession,
    test_connections: dict
):
    gh_conn = test_connections["github"]

    # 1. Prepare 10 distinct events
    distinct_count = 10
    total_storm_events = 1000

    distinct_events = [
        {
            "delivery_id": f"storm-deliv-{i:03d}",
            "external_id": f"PR-{100 + i}",
            "payload": {
                "action": "closed",
                "number": 100 + i,
                "pull_request": {"title": f"Feature {i}", "merged": True}
            }
        }
        for i in range(distinct_count)
    ]

    # 2. Build 1,000 events by replicating the distinct events 100 times each
    storm_queue = []
    for _ in range(total_storm_events // distinct_count):
        storm_queue.extend(distinct_events)

    # Shuffle to simulate completely out-of-order delivery storms
    random.seed(42)
    random.shuffle(storm_queue)

    duplicate_counts = 0
    accepted_counts = 0

    # 3. Process all 1,000 events
    for evt in storm_queue:
        idempotency_key = f"github:{evt['delivery_id']}:pull_request"
        res = await EventProcessor.process_incoming_webhook(
            session=db_session,
            connection=gh_conn,
            event_type="pull_request",
            idempotency_key=idempotency_key,
            external_id=evt["external_id"],
            raw_payload=evt["payload"]
        )
        if res.is_duplicate:
            duplicate_counts += 1
        else:
            accepted_counts += 1

    await db_session.commit()

    # 4. Strict assertions
    assert accepted_counts == distinct_count
    assert duplicate_counts == (total_storm_events - distinct_count)

    # Invariant: exactly 10 source_events must exist in database
    stmt = select(func.count(SourceEvent.id)).where(SourceEvent.connection_id == gh_conn.id)
    total_source_events = (await db_session.execute(stmt)).scalar_one()
    assert total_source_events == distinct_count, f"Expected {distinct_count} source_events, found {total_source_events}"
