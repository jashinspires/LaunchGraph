"""
Domain 3: Launch candidate proposals and decision run audit models.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB, TimestampMixin


class LaunchCandidate(Base, TimestampMixin):
    """
    Automated evaluation proposing launch tier, confidence band, and external safety.
    """
    __tablename__ = "launch_candidates"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("change_events.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tier: Mapped[str] = mapped_column(String(16), nullable=False)  # T0, T1, T2, T3
    confirmed_tier: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # Human confirmed tier
    confidence: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)  # high, medium, low
    score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)  # 1 - 100
    reasons: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    is_external_safe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    safety_warnings: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", nullable=False)  # PENDING_REVIEW, CONFIRMED, REJECTED, SUPPRESSED
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    decision_runs: Mapped[List["DecisionRun"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class DecisionRun(Base):
    """
    Immutable audit record of a Stage 3 decisioning run (Q1-Q9 k=3 consensus execution).
    """
    __tablename__ = "decision_runs"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    launch_candidate_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("launch_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    k_samples: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    evidence_pack_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_pack_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hash
    raw_answers: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)
    policy_hits: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    candidate: Mapped["LaunchCandidate"] = relationship(back_populates="decision_runs")
