"""
LaunchGraph Stage 2: Normalizer Microservice (:8002)
Normalizes raw telemetry into the anchored context graph and serves triage queue endpoints.
"""

import uuid
from typing import Optional, List
from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.session import get_async_session
from launchgraph_core.db.models.change_graph import ChangeEvent, LinkSuggestion
from services.normalizer.config import normalizer_settings
from services.normalizer.worker import process_unprocessed_source_events

app = FastAPI(
    title="LaunchGraph Normalizer Service",
    description="Context Graph Assembly, Reference Extraction, and Triage Queues",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)


@app.get("/health", tags=["System"])
async def health_check():
    """Service liveness probe."""
    return {"status": "healthy", "service": "normalizer", "port": normalizer_settings.PORT}


@app.post("/api/normalizer/process", tags=["Processing"])
async def trigger_normalization(
    batch_size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Manually triggers a normalization pass across pending SourceEvents.
    """
    processed = await process_unprocessed_source_events(session, limit=batch_size)
    await session.commit()
    return {"status": "success", "processed_events": processed}


@app.get("/api/triage/unlinked", tags=["Triage Queues"])
async def get_unlinked_queue(
    workspace_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Returns unconfirmed candidate link suggestions awaiting human triage.
    """
    stmt = (
        select(LinkSuggestion)
        .where(LinkSuggestion.workspace_id == workspace_id, LinkSuggestion.status == "pending")
        .order_by(LinkSuggestion.score.desc())
    )
    results = list((await session.execute(stmt)).scalars().all())
    return {
        "workspace_id": str(workspace_id),
        "count": len(results),
        "items": [
            {
                "id": str(r.id),
                "change_event_id": str(r.change_event_id),
                "source_event_id": str(r.source_event_id),
                "score": r.score,
                "feature_breakdown": r.feature_breakdown,
                "status": r.status,
                "created_at": r.created_at.isoformat()
            }
            for r in results
        ]
    }


@app.get("/api/changes/{change_id}", tags=["Context Graph"])
async def get_change_event(
    change_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Retrieves a change event with its active ledger memberships.
    """
    stmt = select(ChangeEvent).where(ChangeEvent.id == change_id)
    change = (await session.execute(stmt)).scalar_one_or_none()
    if not change:
        raise HTTPException(status_code=404, detail="ChangeEvent not found.")

    return {
        "id": str(change.id),
        "anchor_ref": change.anchor_ref,
        "title": change.title,
        "description": change.description,
        "state": change.state,
        "availability": change.availability,
        "last_activity_at": change.last_activity_at.isoformat(),
        "created_at": change.created_at.isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=normalizer_settings.HOST, port=normalizer_settings.PORT)
