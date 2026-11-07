"""
Integration tests for the Stage 3 Decisioner Pipeline.
Tests end-to-end evaluation: ChangeEvent -> Fact/Sensitivity -> 12k Pack -> Consensus -> Policy -> Candidate & DecisionRun.
"""

import pytest
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from launchgraph_core.db.models.workspace import Workspace
from launchgraph_core.db.models.connection import Connection, SourceEvent
from launchgraph_core.db.models.change_graph import ChangeEvent, ChangeMembership
from launchgraph_core.db.models.candidates import LaunchCandidate, DecisionRun
from services.decisioner.worker import evaluate_change_event


@pytest.mark.asyncio
async def test_decisioner_pipeline_end_to_end(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_connections: dict
):
    # 1. Create Jira and GitHub source events
    jira_event = SourceEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        connection_id=test_connections["jira"].id,
        source_type="JIRA",
        external_id="JIRA:KAN-101",
        raw_payload={
            "issue": {
                "key": "KAN-101",
                "fields": {
                    "summary": "Enterprise SSO SAML 2.0 Integration",
                    "description": "Enables corporate SSO via Okta and Azure AD.",
                    "priority": {"name": "Highest"},
                    "issuetype": {"name": "Epic"},
                    "assignee": {"displayName": "Bob Security"}
                }
            }
        },
        trust_label="INTERNAL",
        is_processed=True
    )

    gh_event = SourceEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        connection_id=test_connections["github"].id,
        source_type="GITHUB",
        external_id="PR-88",
        raw_payload={
            "pull_request": {
                "number": 88,
                "title": "KAN-101: Add SAML 2.0 assertion consumer service",
                "body": "Implements SAML 2.0 authentication endpoints.",
                "state": "closed",
                "merged": True,
                "changed_files": [
                    "auth/saml.py",
                    "auth/routes.py",
                    "docs/sso_setup.md"
                ]
            }
        },
        trust_label="INTERNAL",
        is_processed=True
    )
    db_session.add_all([jira_event, gh_event])
    await db_session.flush()

    # 2. Create Canonical ChangeEvent
    change_event = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        anchor_ref="JIRA:KAN-101",
        title="Enterprise SSO SAML 2.0 Integration",
        description="Enables corporate SSO via Okta and Azure AD.",
        state="merged",
        availability="ga",
        is_processed=False
    )
    db_session.add(change_event)
    await db_session.flush()

    # 3. Attach in ChangeMembership ledger
    mem_jira = ChangeMembership(
        id=uuid.uuid4(),
        change_event_id=change_event.id,
        source_event_id=jira_event.id,
        ref_type="JIRA_ISSUE",
        ref_key="JIRA:KAN-101",
        link_type="contains",
        role="anchor"
    )
    mem_gh = ChangeMembership(
        id=uuid.uuid4(),
        change_event_id=change_event.id,
        source_event_id=gh_event.id,
        ref_type="GITHUB_PR",
        ref_key="PR-88",
        link_type="implements",
        role="implements"
    )
    db_session.add_all([mem_jira, mem_gh])
    await db_session.commit()

    # 4. Execute Stage 3 Decisioning Pipeline
    candidate, decision_run = await evaluate_change_event(
        session=db_session,
        change_event=change_event
    )
    await db_session.commit()

    # 5. Assert database persistence & invariants
    assert candidate.id is not None
    assert candidate.change_event_id == change_event.id
    assert candidate.workspace_id == test_workspace.id
    assert candidate.tier in ("T1", "T2")
    assert candidate.confidence in ("high", "medium")
    assert 70 <= candidate.score <= 100
    assert len(candidate.reasons) >= 1
    assert change_event.is_processed is True

    # Check DecisionRun audit record
    assert decision_run.id is not None
    assert decision_run.launch_candidate_id == candidate.id
    assert decision_run.k_samples == 3
    assert decision_run.evidence_pack_tokens > 0
    assert len(decision_run.evidence_pack_hash) == 64
    assert "consensus_answers" in decision_run.raw_answers
    assert len(decision_run.raw_answers["consensus_answers"]) == 9

    # Verify queryable from DB
    persisted_cand = (
        await db_session.execute(
            select(LaunchCandidate).where(LaunchCandidate.id == candidate.id)
        )
    ).scalar_one()
    assert persisted_cand.tier == candidate.tier
