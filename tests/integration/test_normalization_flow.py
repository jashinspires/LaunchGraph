"""
Integration tests for End-to-End Normalization Flow.
Verifies SourceEvent -> ChangeEvent -> Append-Only Membership Ledger.
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models import SourceEvent, ChangeEvent, ChangeMembership
from services.normalizer.worker import process_unprocessed_source_events


@pytest.mark.asyncio
async def test_end_to_end_normalization_pipeline(
    db_session: AsyncSession,
    test_connections: dict,
    test_workspace
):
    gh_conn = test_connections["github"]
    jira_conn = test_connections["jira"]

    # 1. Ingest Jira Issue SourceEvent
    jira_event = SourceEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        connection_id=jira_conn.id,
        source_type="JIRA",
        external_id="JIRA:PROJ-1024",
        raw_payload={
            "issue": {
                "key": "PROJ-1024",
                "fields": {
                    "summary": "Implement OAuth PKCE Login Flow",
                    "description": "Enterprise customer requirement for security.",
                    "status": {"statusCategory": {"key": "indeterminate"}}
                }
            }
        },
        is_processed=False
    )
    db_session.add(jira_event)
    await db_session.commit()

    # 2. Run normalization pass 1
    processed_1 = await process_unprocessed_source_events(db_session)
    await db_session.commit()
    assert processed_1 == 1

    # Verify ChangeEvent created
    stmt = select(ChangeEvent).where(ChangeEvent.anchor_ref == "JIRA:PROJ-1024")
    change = (await db_session.execute(stmt)).scalar_one()
    assert change.title == "Implement OAuth PKCE Login Flow"
    assert change.state == "in_progress"

    # 3. Ingest GitHub PR SourceEvent referencing PROJ-1024
    gh_event = SourceEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        connection_id=gh_conn.id,
        source_type="GITHUB",
        external_id="PR-142",
        raw_payload={
            "action": "closed",
            "pull_request": {
                "number": 142,
                "title": "PROJ-1024: Add OAuth PKCE implementation",
                "body": "Fixes #139. Successfully tested.",
                "state": "closed",
                "merged": True,
                "head": {"ref": "feature/PROJ-1024-oauth"}
            }
        },
        is_processed=False
    )
    db_session.add(gh_event)
    await db_session.commit()

    # 4. Run normalization pass 2
    processed_2 = await process_unprocessed_source_events(db_session)
    await db_session.commit()
    assert processed_2 == 1

    # Refresh ChangeEvent and verify state updated to 'merged'
    await db_session.refresh(change)
    assert change.state == "merged"

    # 5. Verify Append-Only Membership Ledger
    ledger_stmt = select(ChangeMembership).where(ChangeMembership.change_event_id == change.id)
    memberships = list((await db_session.execute(ledger_stmt)).scalars().all())

    assert len(memberships) == 2
    ref_keys = {m.ref_key for m in memberships}
    assert "JIRA:PROJ-1024" in ref_keys
    assert "PR-142" in ref_keys

    # Check that PR-142 was classified with link_type == 'implements' (L1)
    pr_membership = next(m for m in memberships if m.ref_key == "PR-142")
    assert pr_membership.link_type == "implements"
    assert pr_membership.is_active is True
