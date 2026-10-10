"""
Domain 3: Immutable LaunchRecord snapshot model grounded in the Mem0 long-term memory architecture.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB, CompatibleVector


class LaunchRecord(Base):
    """
    Immutable historical snapshot of an approved launch.
    Serves as the foundational unit of memory for downstream A2A agents and few-shot generation.
    """
    __tablename__ = "launch_records"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gtm_pack_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("gtm_packs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    final_tier: Mapped[str] = mapped_column(String(16), nullable=False)  # T1, T2, T3
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    assets_snapshot: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(CompatibleVector(dim=1536), nullable=True)
    mem0_entities: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    mem0_relations: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    is_retracted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    retracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retraction_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
