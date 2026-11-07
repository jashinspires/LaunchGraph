"""
LaunchGraph Stage 3: Decisioner Microservice (:8003)
Proposes launch significance tiers (T0-T3), executes Q1-Q9 consensus sampling,
and evaluates Restrict-Only enterprise policy rules.
"""

import uuid
from typing import Optional, List
from fastapi import FastAPI, Depends, Query, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from launchgraph_core.db.session import get_async_session
from launchgraph_core.db.models.change_graph import ChangeEvent
from launchgraph_core.db.models.candidates import LaunchCandidate, DecisionRun
from services.decisioner.config import decisioner_settings
from services.decisioner.worker import (
    evaluate_change_event,
    process_unprocessed_change_events,
)

app = FastAPI(
    title="LaunchGraph Decisioner Service",
    description="Deterministic Facts, Consensus Judgment (Q1-Q9), Restrict-Only Policy Engine, and Tier Proposals",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)


class ConfirmTierRequest(BaseModel):
    confirmed_tier: str
    override_reason: Optional[str] = None


@app.get("/health", tags=["System"])
async def health_check():
    """Service liveness probe."""
    return {
        "status": "healthy",
        "service": decisioner_settings.SERVICE_NAME,
        "port": decisioner_settings.PORT,
        "model": decisioner_settings.MODEL_NAME,
        "k_samples": decisioner_settings.K_SAMPLES,
    }


@app.post("/api/decisioner/process", tags=["Processing"])
async def trigger_decisioning(
    batch_size: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Manually triggers a Stage 3 decisioning run across pending ChangeEvents.
    """
    processed = await process_unprocessed_change_events(session, limit=batch_size)
    await session.commit()
    return {"status": "success", "evaluated_changes": processed}


@app.post("/api/decisioner/evaluate/{change_event_id}", tags=["Processing"])
async def evaluate_single_change(
    change_event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Forces immediate Stage 3 evaluation of a specific ChangeEvent.
    """
    stmt = select(ChangeEvent).where(ChangeEvent.id == change_event_id)
    change = (await session.execute(stmt)).scalar_one_or_none()
    if not change:
        raise HTTPException(status_code=404, detail="ChangeEvent not found.")

    candidate, decision_run = await evaluate_change_event(session=session, change_event=change)
    await session.commit()

    return {
        "status": "success",
        "candidate": {
            "id": str(candidate.id),
            "tier": candidate.tier,
            "confidence": candidate.confidence,
            "score": candidate.score,
            "is_external_safe": candidate.is_external_safe,
            "reasons": candidate.reasons,
            "safety_warnings": candidate.safety_warnings,
            "status": candidate.status
        },
        "decision_run": {
            "id": str(decision_run.id),
            "model_name": decision_run.model_name,
            "evidence_pack_tokens": decision_run.evidence_pack_tokens,
            "evidence_pack_hash": decision_run.evidence_pack_hash,
            "policy_hits": decision_run.policy_hits
        }
    }


@app.get("/api/candidates", tags=["Candidates"])
async def list_candidates(
    workspace_id: Optional[uuid.UUID] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Lists proposed LaunchCandidates with optional filters.
    """
    stmt = select(LaunchCandidate).order_by(LaunchCandidate.created_at.desc()).limit(limit)
    if workspace_id:
        stmt = stmt.where(LaunchCandidate.workspace_id == workspace_id)
    if tier:
        stmt = stmt.where(LaunchCandidate.tier == tier.upper())
    if status:
        stmt = stmt.where(LaunchCandidate.status == status.upper())

    results = list((await session.execute(stmt)).scalars().all())
    return {
        "count": len(results),
        "items": [
            {
                "id": str(c.id),
                "workspace_id": str(c.workspace_id),
                "change_event_id": str(c.change_event_id),
                "tier": c.tier,
                "confirmed_tier": c.confirmed_tier,
                "confidence": c.confidence,
                "score": c.score,
                "is_external_safe": c.is_external_safe,
                "status": c.status,
                "reasons": c.reasons,
                "safety_warnings": c.safety_warnings,
                "created_at": c.created_at.isoformat()
            }
            for c in results
        ]
    }


@app.get("/api/candidates/{candidate_id}", tags=["Candidates"])
async def get_candidate_detail(
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Retrieves a LaunchCandidate along with its latest DecisionRun audit.
    """
    stmt = (
        select(LaunchCandidate)
        .options(selectinload(LaunchCandidate.decision_runs))
        .where(LaunchCandidate.id == candidate_id)
    )
    candidate = (await session.execute(stmt)).scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="LaunchCandidate not found.")

    latest_run = candidate.decision_runs[-1] if candidate.decision_runs else None

    return {
        "candidate": {
            "id": str(candidate.id),
            "workspace_id": str(candidate.workspace_id),
            "change_event_id": str(candidate.change_event_id),
            "tier": candidate.tier,
            "confirmed_tier": candidate.confirmed_tier,
            "confidence": candidate.confidence,
            "score": candidate.score,
            "is_external_safe": candidate.is_external_safe,
            "status": candidate.status,
            "reasons": candidate.reasons,
            "safety_warnings": candidate.safety_warnings,
            "created_at": candidate.created_at.isoformat(),
        },
        "latest_decision_run": {
            "id": str(latest_run.id),
            "model_name": latest_run.model_name,
            "k_samples": latest_run.k_samples,
            "evidence_pack_tokens": latest_run.evidence_pack_tokens,
            "evidence_pack_hash": latest_run.evidence_pack_hash,
            "raw_answers": latest_run.raw_answers,
            "policy_hits": latest_run.policy_hits,
            "created_at": latest_run.created_at.isoformat()
        } if latest_run else None
    }


@app.post("/api/candidates/{candidate_id}/confirm", tags=["Governance"])
async def confirm_candidate_tier(
    candidate_id: uuid.UUID,
    request: ConfirmTierRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Allows PMM reviewer to confirm or override a proposed launch tier.
    """
    stmt = select(LaunchCandidate).where(LaunchCandidate.id == candidate_id)
    candidate = (await session.execute(stmt)).scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="LaunchCandidate not found.")

    candidate.confirmed_tier = request.confirmed_tier.upper()
    candidate.status = "CONFIRMED"
    if request.override_reason:
        candidate.reasons.append(f"Human PMM override: {request.override_reason}")

    await session.commit()
    return {
        "status": "success",
        "candidate_id": str(candidate.id),
        "confirmed_tier": candidate.confirmed_tier,
        "status": candidate.status
    }

