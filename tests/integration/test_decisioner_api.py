"""
Integration tests for Stage 3 Decisioner REST API (:8003).
"""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from launchgraph_core.db.models.workspace import Workspace
from launchgraph_core.db.models.change_graph import ChangeEvent
from launchgraph_core.db.models.candidates import LaunchCandidate, DecisionRun


@pytest.mark.asyncio
async def test_decisioner_health(decisioner_client: AsyncClient):
    res = await decisioner_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "decisioner"
    assert data["port"] == 8003


@pytest.mark.asyncio
async def test_decisioner_evaluate_and_confirm_endpoints(
    decisioner_client: AsyncClient,
    db_session: AsyncSession,
    test_workspace: Workspace
):
    # 1. Create a change event
    change_event = ChangeEvent(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        anchor_ref="PROD-77",
        title="Add Real-Time Webhook Monitoring",
        description="Tracks delivery latency and dropouts for webhooks.",
        state="merged",
        availability="ga",
        is_processed=False
    )
    db_session.add(change_event)
    await db_session.commit()

    # 2. Trigger evaluate endpoint
    res_eval = await decisioner_client.post(f"/api/decisioner/evaluate/{change_event.id}")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["status"] == "success"
    candidate_id = eval_data["candidate"]["id"]
    assert eval_data["candidate"]["tier"] in ("T1", "T2", "T3")

    # 3. List candidates
    res_list = await decisioner_client.get(f"/api/candidates?workspace_id={test_workspace.id}")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["count"] >= 1
    assert any(c["id"] == candidate_id for c in list_data["items"])

    # 4. Get candidate detail with decision run
    res_detail = await decisioner_client.get(f"/api/candidates/{candidate_id}")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["candidate"]["id"] == candidate_id
    assert detail_data["latest_decision_run"] is not None
    assert detail_data["latest_decision_run"]["evidence_pack_tokens"] > 0

    # 5. Confirm candidate tier (PMM override)
    res_confirm = await decisioner_client.post(
        f"/api/candidates/{candidate_id}/confirm",
        json={"confirmed_tier": "T2", "override_reason": "Strategic alignment with Q4 roadmap"}
    )
    assert res_confirm.status_code == 200
    confirm_data = res_confirm.json()
    assert confirm_data["confirmed_tier"] == "T2"
    assert confirm_data["status"] == "CONFIRMED"

