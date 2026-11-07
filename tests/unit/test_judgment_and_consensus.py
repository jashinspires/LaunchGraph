"""
Unit tests for Stage 3 Judgment Client and Consensus Engine.
"""

import pytest
import uuid
from launchgraph_core.contracts.decisioner import (
    EvidencePack,
    EvidenceChunk,
    LaunchTier,
    ConfidenceBand,
)
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.judgment_client import DeterministicJudgmentClient
from services.decisioner.services.consensus import ConsensusEngine


@pytest.mark.asyncio
async def test_judgment_client_q1_to_q9():
    client = DeterministicJudgmentClient()

    pack = EvidencePack(
        workspace_id=str(uuid.uuid4()),
        change_event_id=str(uuid.uuid4()),
        context_hash="hash-123",
        chunks=[
            EvidenceChunk(
                chunk_id="chk_facts_001",
                source_ref="PROJ-1",
                content="Security Flags: False\nCompliance Flag: False",
                token_count=20
            )
        ]
    )

    facts = ChangeFacts(
        changed_files_count=12,
        has_customer_docs=True,
        is_breaking_change=False,
        ticket_priority="highest",
        issue_type="epic",
        availability="ga"
    )

    answers = await client.evaluate_sample(pack=pack, facts=facts, sample_index=0)

    assert len(answers) == 9
    assert answers["Q1"].answer == "USER_FACING_FEATURE"
    assert answers["Q2"].answer == "NEW_CAPABILITY"
    assert answers["Q3"].answer == "BACKWARD_COMPATIBLE"
    assert answers["Q5"].answer == "STRATEGIC_FLAGSHIP"
    assert answers["Q7"].answer == "GA_GENERAL_AVAILABILITY"
    assert answers["Q9"].answer == "T1"


@pytest.mark.asyncio
async def test_consensus_engine_k3_agreement():
    client = DeterministicJudgmentClient()

    pack = EvidencePack(
        workspace_id=str(uuid.uuid4()),
        change_event_id=str(uuid.uuid4()),
        context_hash="hash-456",
        chunks=[
            EvidenceChunk(
                chunk_id="chk_facts_001",
                source_ref="PROJ-2",
                content="Facts",
                token_count=10
            )
        ]
    )

    facts = ChangeFacts(
        changed_files_count=6,
        has_customer_docs=True,
        is_breaking_change=True,
        availability="ga"
    )

    consensus = await ConsensusEngine.evaluate_consensus(
        client=client,
        pack=pack,
        facts=facts,
        k_samples=3
    )

    assert consensus.k_samples == 3
    assert consensus.consensus_tier in (LaunchTier.T1, LaunchTier.T2)
    assert consensus.agreement_score >= 0.6
    assert consensus.confidence in (ConfidenceBand.HIGH, ConfidenceBand.MEDIUM)
    assert 50 <= consensus.score <= 100
    assert len(consensus.raw_samples) == 3

