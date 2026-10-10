"""
Mem0 Long-Term Memory Graph & Operation Models.
Grounded in Chhikara et al. (2025): Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory.
Implements the graph representation G = (V, E, L) and Algorithm 1 operations.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB, CompatibleVector, TimestampMixin


class Mem0EntityNode(Base, TimestampMixin):
    """
    Graph Node v in V representing an extracted entity, capability claim, or persona.
    Includes dense embedding e_v for dual-approach similarity search.
    """
    __tablename__ = "mem0_entity_nodes"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # FEATURE, TICKET, EPIC, PERSONA, CLAIM
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    attributes: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(CompatibleVector(dim=1536), nullable=True)
    information_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    out_edges: Mapped[List["Mem0RelationEdge"]] = relationship(
        "Mem0RelationEdge",
        foreign_keys="Mem0RelationEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan"
    )
    in_edges: Mapped[List["Mem0RelationEdge"]] = relationship(
        "Mem0RelationEdge",
        foreign_keys="Mem0RelationEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan"
    )


class Mem0RelationEdge(Base):
    """
    Graph Edge e in E representing a directed relationship triplet (v_s, r, v_d) labeled r.
    """
    __tablename__ = "mem0_relation_edges"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("mem0_entity_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("mem0_entity_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # implements, deprecates, targets_persona, delivers
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    attributes: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    source_node: Mapped["Mem0EntityNode"] = relationship("Mem0EntityNode", foreign_keys=[source_node_id], back_populates="out_edges")
    target_node: Mapped["Mem0EntityNode"] = relationship("Mem0EntityNode", foreign_keys=[target_node_id], back_populates="in_edges")


class Mem0MemoryOperation(Base):
    """
    Audit log of Mem0 Algorithm 1 operation executions (ADD, UPDATE, DELETE, NOOP).
    """
    __tablename__ = "mem0_memory_operations"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    launch_record_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("launch_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False)  # ADD, UPDATE, DELETE, NOOP
    candidate_fact: Mapped[dict] = mapped_column(CompatibleJSONB, nullable=False)
    target_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        CompatibleUUID, ForeignKey("mem0_entity_nodes.id", ondelete="SET NULL"), nullable=True
    )
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class BrandProfileEvolution(Base):
    """
    Suggested voice and claim evolutions derived from repeated human reviewer edits.
    """
    __tablename__ = "brand_profile_evolutions"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    suggested_rules: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    source_approval_events: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, accepted, rejected
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        CompatibleUUID, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
