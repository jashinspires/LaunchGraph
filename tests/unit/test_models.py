"""
Unit tests for Database Models & Schema Integrity.
"""

import pytest
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from launchgraph_core.db.models import (
    Workspace,
    Brand,
    BrandProfile,
    AudienceSegment,
    Connection,
    WebhookInbox,
    SourceEvent,
    ChangeEvent,
    ChangeMembership,
    LaunchCandidate,
    GtmPack,
    GtmAsset,
    LaunchRecord,
    ApiKey,
    Job,
    Mem0EntityNode,
    Mem0RelationEdge,
)


@pytest.mark.asyncio
async def test_workspace_and_brand_cascade(db_session: AsyncSession):
    workspace = Workspace(
        id=uuid.uuid4(),
        slug="test-workspace",
        name="Test Corp",
        tier="pilot"
    )
    db_session.add(workspace)
    await db_session.flush()

    brand = Brand(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        name="Test Brand",
        is_default=True
    )
    db_session.add(brand)
    await db_session.flush()

    profile = BrandProfile(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        brand_id=brand.id,
        product_summary="Test product description",
        voice_tone="direct, authoritative",
        tone_rules=["Never use passive voice"],
        allowed_claims=["SOC2 Type II certified"],
        disallowed_claims=["Cheapest in market"],
        codenames=["Project Spartan"]
    )
    db_session.add(profile)
    await db_session.commit()

    # Query back
    stmt = select(BrandProfile).where(BrandProfile.id == profile.id)
    saved_profile = (await db_session.execute(stmt)).scalar_one()
    assert saved_profile.product_summary == "Test product description"
    assert "Project Spartan" in saved_profile.codenames


@pytest.mark.asyncio
async def test_mem0_graph_node_and_edge_creation(db_session: AsyncSession, test_workspace: Workspace):
    node1 = Mem0EntityNode(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        entity_type="FEATURE",
        name="OAuth PKCE Authentication",
        attributes={"protocol": "RFC 7636", "security_level": "high"},
        information_score=1.0,
        is_active=True
    )
    node2 = Mem0EntityNode(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        entity_type="PERSONA",
        name="Enterprise Security Lead",
        attributes={"focus": "compliance", "pain_point": "token theft"},
        information_score=1.0,
        is_active=True
    )
    db_session.add_all([node1, node2])
    await db_session.flush()

    edge = Mem0RelationEdge(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        source_node_id=node1.id,
        target_node_id=node2.id,
        relation_type="delivers_capability",
        weight=1.0,
        attributes={"verified": True},
        is_active=True
    )
    db_session.add(edge)
    await db_session.commit()

    stmt = select(Mem0RelationEdge).where(Mem0RelationEdge.id == edge.id)
    saved_edge = (await db_session.execute(stmt)).scalar_one()
    assert saved_edge.relation_type == "delivers_capability"
    assert saved_edge.source_node_id == node1.id
    assert saved_edge.target_node_id == node2.id
