"""
Unit tests for Append-Only Membership Ledger.
"""

import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models import Workspace, ChangeEvent
from services.normalizer.services.ledger_manager import LedgerManager


@pytest.mark.asyncio
async def test_ledger_attach_and_soft_unlink(db_session: AsyncSession, test_workspace: Workspace):
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        anchor_ref="JIRA:PROJ-1024",
        title="OAuth Flow"
    )
    db_session.add(change)
    await db_session.flush()

    # 1. Attach reference
    membership = await LedgerManager.attach_reference(
        session=db_session,
        change_event=change,
        ref_type="GITHUB_PR",
        ref_key="PR-142",
        link_type="implements",
        role="implements",
        attached_by="system",
        reason="Detected in branch name"
    )

    assert membership.is_active is True
    assert membership.ref_key == "PR-142"

    # 2. Soft-unlink with valid rationale
    success = await LedgerManager.soft_unlink_reference(
        session=db_session,
        membership_id=membership.id,
        unlinked_by="pmm-lead-uuid",
        unlink_reason="Incorrectly associated by automated test script"
    )
    assert success is True
    assert membership.is_active is False
    assert membership.unlink_reason == "Incorrectly associated by automated test script"


@pytest.mark.asyncio
async def test_ledger_soft_unlink_requires_mandatory_reason(db_session: AsyncSession, test_workspace: Workspace):
    change = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        anchor_ref="JIRA:PROJ-1025",
        title="Rate Limiter"
    )
    db_session.add(change)
    await db_session.flush()

    membership = await LedgerManager.attach_reference(
        session=db_session,
        change_event=change,
        ref_type="GITHUB_PR",
        ref_key="PR-143",
        link_type="implements"
    )

    # Empty or too short reason must fail
    with pytest.raises(ValueError, match="Mandatory audit unlink_reason"):
        await LedgerManager.soft_unlink_reference(
            session=db_session,
            membership_id=membership.id,
            unlinked_by="user-uuid",
            unlink_reason=" "
        )
