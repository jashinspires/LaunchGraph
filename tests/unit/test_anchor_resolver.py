"""
Unit tests for Anchor Resolution Engine.
"""

import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models import Workspace, Connection, SourceEvent
from services.normalizer.services.anchor_resolver import AnchorResolver


@pytest.mark.asyncio
async def test_resolve_jira_epic_anchor(db_session: AsyncSession, test_workspace: Workspace):
    source_event = SourceEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        connection_id=uuid.uuid4(),
        source_type="JIRA",
        external_id="JIRA:PROJ-1024",
        raw_payload={"epic_key": "PROJ-1000", "summary": "OAuth Support"},
        is_processed=False
    )
    db_session.add(source_event)
    await db_session.flush()

    change = await AnchorResolver.resolve_or_create_change_event(
        session=db_session,
        source_event=source_event,
        title="Support OAuth 2.0 PKCE",
        description="Epic level feature"
    )

    assert change.anchor_ref == "JIRA:PROJ-1000"
    assert change.title == "Support OAuth 2.0 PKCE"


@pytest.mark.asyncio
async def test_resolve_github_pr_anchor_when_no_jira(db_session: AsyncSession, test_workspace: Workspace):
    source_event = SourceEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        connection_id=uuid.uuid4(),
        source_type="GITHUB",
        external_id="PR-42",
        raw_payload={"number": 42},
        is_processed=False
    )
    db_session.add(source_event)
    await db_session.flush()

    change = await AnchorResolver.resolve_or_create_change_event(
        session=db_session,
        source_event=source_event,
        title="Update README and setup guide",
        description="Docs improvement"
    )

    assert change.anchor_ref == "GITHUB:PR-42"
