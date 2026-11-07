"""
Stage 3 Decisioner Autonomous Worker & Pipeline Orchestrator.
Processes ChangeEvents, compiles 12k evidence packs, executes Q1-Q9 consensus sampling,
evaluates policy rules, and persists LaunchCandidate proposals and immutable DecisionRun audits.
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from launchgraph_core.db.models.change_graph import ChangeEvent, ChangeMembership
from launchgraph_core.db.models.connection import SourceEvent
from launchgraph_core.db.models.candidates import LaunchCandidate, DecisionRun
from services.decisioner.config import decisioner_settings
from services.decisioner.services.fact_extractor import DeterministicFactExtractor
from services.decisioner.services.sensitivity_detector import SensitivityDetector
from services.decisioner.services.evidence_assembler import EvidencePackAssembler
from services.decisioner.services.judgment_client import (
    BaseJudgmentClient,
    DeterministicJudgmentClient,
    ClaudeJudgmentClient,
)
from services.decisioner.services.consensus import ConsensusEngine
from services.decisioner.services.policy_engine import PolicyEngine
from services.decisioner.services.tier_evaluator import TierEvaluator

logger = logging.getLogger("launchgraph.decisioner.worker")


def get_default_judgment_client() -> BaseJudgmentClient:
    if decisioner_settings.JUDGMENT_BACKEND == "claude" and decisioner_settings.ANTHROPIC_API_KEY:
        return ClaudeJudgmentClient(
            api_key=decisioner_settings.ANTHROPIC_API_KEY,
            model=decisioner_settings.MODEL_NAME
        )
    return DeterministicJudgmentClient()


async def evaluate_change_event(
    session: AsyncSession,
    change_event: ChangeEvent,
    client: Optional[BaseJudgmentClient] = None
) -> Tuple[LaunchCandidate, DecisionRun]:
    """
    Executes the full Stage 3 pipeline for a single ChangeEvent:
    1. Gather linked SourceEvents from ledger.
    2. Extract deterministic facts & sensitivity flags.
    3. Assemble 12,000 token bounded EvidencePack.
    4. Execute Q1-Q9 consensus sampling across k=3 samples.
    5. Evaluate Restrict-Only Policy rules.
    6. Synthesize final proposed tier, external safety, and reasons.
    7. Atomically persist LaunchCandidate and DecisionRun audit record.
    """
    judgment_client = client or get_default_judgment_client()

    # 1. Fetch active memberships and linked source events
    mem_stmt = (
        select(ChangeMembership)
        .where(ChangeMembership.change_event_id == change_event.id)
        .where(ChangeMembership.is_active == True)
    )
    memberships = list((await session.execute(mem_stmt)).scalars().all())

    source_event_ids = [m.source_event_id for m in memberships if m.source_event_id is not None]
    source_events: List[SourceEvent] = []
    if source_event_ids:
        src_stmt = select(SourceEvent).where(SourceEvent.id.in_(source_event_ids))
        source_events = list((await session.execute(src_stmt)).scalars().all())

    # 2. Extract facts and sensitivity
    facts = DeterministicFactExtractor.extract_facts(
        change_event=change_event,
        source_events=source_events
    )

    source_texts = [
        str(se.raw_payload) for se in source_events if se.raw_payload
    ]
    sensitivity = SensitivityDetector.scan_change_context(
        title=change_event.title or "",
        description=change_event.description,
        source_texts=source_texts
    )

    # 3. Assemble 12k EvidencePack
    evidence_pack = EvidencePackAssembler.assemble_pack(
        change_event=change_event,
        facts=facts,
        sensitivity=sensitivity,
        source_events=source_events,
        memberships=memberships
    )

    # 4. Consensus Sampling across k=3 samples
    consensus = await ConsensusEngine.evaluate_consensus(
        client=judgment_client,
        pack=evidence_pack,
        facts=facts,
        k_samples=decisioner_settings.K_SAMPLES
    )

    # 5. Restrict-Only Policy Engine
    policy_result = PolicyEngine.evaluate(
        facts=facts,
        sensitivity=sensitivity,
        proposed_tier=consensus.consensus_tier,
        pack=evidence_pack
    )

    # 6. Deterministic Tier Evaluator
    evaluated_decision = TierEvaluator.evaluate_candidate(
        facts=facts,
        sensitivity=sensitivity,
        consensus=consensus,
        policy_result=policy_result
    )

    # 7. Upsert LaunchCandidate
    cand_stmt = select(LaunchCandidate).where(LaunchCandidate.change_event_id == change_event.id)
    candidate = (await session.execute(cand_stmt)).scalar_one_or_none()

    if not candidate:
        candidate = LaunchCandidate(
            workspace_id=change_event.workspace_id,
            change_event_id=change_event.id,
            tier=evaluated_decision.tier.value,
            confidence=evaluated_decision.confidence.value,
            score=evaluated_decision.score,
            reasons=evaluated_decision.reasons,
            is_external_safe=evaluated_decision.is_external_safe,
            safety_warnings=evaluated_decision.safety_warnings,
            status=evaluated_decision.status,
            is_processed=False
        )
        session.add(candidate)
        await session.flush()
    else:
        candidate.tier = evaluated_decision.tier.value
        candidate.confidence = evaluated_decision.confidence.value
        candidate.score = evaluated_decision.score
        candidate.reasons = evaluated_decision.reasons
        candidate.is_external_safe = evaluated_decision.is_external_safe
        candidate.safety_warnings = evaluated_decision.safety_warnings
        candidate.status = evaluated_decision.status
        candidate.is_processed = False
        await session.flush()

    # 8. Create Immutable DecisionRun Audit Record
    decision_run = DecisionRun(
        launch_candidate_id=candidate.id,
        model_name=decisioner_settings.MODEL_NAME,
        k_samples=consensus.k_samples,
        evidence_pack_tokens=evidence_pack.total_tokens,
        evidence_pack_hash=evidence_pack.context_hash,
        raw_answers={
            "agreement_score": consensus.agreement_score,
            "consensus_answers": [a.model_dump() for a in consensus.answers],
            "samples": consensus.raw_samples,
        },
        policy_hits=evaluated_decision.policy_hits,
        created_at=datetime.now(timezone.utc)
    )
    session.add(decision_run)

    # 9. Mark change event as evaluated
    change_event.is_processed = True
    await session.flush()

    logger.info(
        "Stage 3 evaluated ChangeEvent %s -> Candidate %s (Tier: %s, Score: %d, Safe: %s)",
        change_event.id, candidate.id, candidate.tier, candidate.score, candidate.is_external_safe
    )

    return candidate, decision_run


async def process_unprocessed_change_events(session: AsyncSession, limit: int = 10) -> int:
    """
    Background batch processor claiming un-evaluated ChangeEvents.
    """
    stmt = (
        select(ChangeEvent)
        .where(ChangeEvent.is_processed == False)
        .order_by(ChangeEvent.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    change_events = list(result.scalars().all())

    if not change_events:
        return 0

    evaluated_count = 0
    for ch in change_events:
        try:
            await evaluate_change_event(session=session, change_event=ch)
            evaluated_count += 1
        except Exception as exc:
            logger.error("Failed to evaluate ChangeEvent %s: %s", ch.id, exc, exc_info=True)

    await session.flush()
    return evaluated_count

