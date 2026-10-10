"""
Domain 2: Context graph models, append-only membership ledger, and suggestion rankings.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Text, ForeignKey, DateTime, Boolean, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB


class ChangeEvent(Base):
    """
    Primary business entity representing a distinct product change anchored to a Jira Epic/Issue or PR.
    """
    __tablename__ = "change_events"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anchor_ref: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False)  # discovered, in_progress, merged, closed
    availability: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)  # unknown, internal, beta, ga
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    memberships: Mapped[List["ChangeMembership"]] = relationship(back_populates="change_event", cascade="all, delete-orphan")
    suggestions: Mapped[List["LinkSuggestion"]] = relationship(back_populates="change_event", cascade="all, delete-orphan")


class ChangeMembership(Base):
    """
    Append-only ledger binding source events and external references to a change event.
    Soft-unlinking is enforced; destructive deletes are prohibited.
    """
    __tablename__ = "change_membership"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        CompatibleUUID, ForeignKey("source_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ref_type: Mapped[str] = mapped_column(String(32), nullable=False)  # JIRA_ISSUE, GITHUB_PR, GITHUB_COMMIT, SLACK_MSG
    ref_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)  # implements, mentions, fixes, reverts, etc.
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # anchor, implements, release, context
    attached_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Soft-deletion flag for audit trail
    unlinked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    unlinked_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    unlink_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    change_event: Mapped["ChangeEvent"] = relationship(back_populates="memberships")


class LinkSuggestion(Base):
    """
    Unconfirmed link predictions calculated by the suggestion ranking formula awaiting human triage.
    """
    __tablename__ = "link_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_event_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("source_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    feature_breakdown: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, accepted, rejected
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        CompatibleUUID, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    change_event: Mapped["ChangeEvent"] = relationship(back_populates="suggestions")


class ChangeRelation(Base):
    """
    High-level graph relationship between two distinct change events.
    """
    __tablename__ = "change_relations"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_change_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_change_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)  # blocks, depends_on, supersedes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
