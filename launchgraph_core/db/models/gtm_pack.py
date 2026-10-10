"""
Domain 3: GTM asset packs, individual deliverables, revisions, lint findings, and approvals.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB, TimestampMixin


class GtmPack(Base):
    """
    Container for all marketing copy generated for an approved launch candidate.
    """
    __tablename__ = "gtm_packs"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    launch_candidate_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("launch_candidates.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)  # DRAFT, IN_REVIEW, FINALIZED, RETRACTED
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assets: Mapped[List["GtmAsset"]] = relationship(back_populates="pack", cascade="all, delete-orphan")


class GtmAsset(Base, TimestampMixin):
    """
    Individual marketing deliverable (e.g. CHANGELOG, EMAIL, LINKEDIN, INTERNAL_BRIEF).
    """
    __tablename__ = "gtm_assets"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    gtm_pack_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("gtm_packs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)  # CHANGELOG, EMAIL, LINKEDIN, etc.
    audience_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        CompatibleUUID, ForeignKey("audience_segments.id", ondelete="SET NULL"), nullable=True
    )
    content_draft: Mapped[str] = mapped_column(Text, nullable=False)
    content_final: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)
    citations: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)  # Sentence-level evidence chunk links
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)  # DRAFT, APPROVED, REJECTED

    pack: Mapped["GtmPack"] = relationship(back_populates="assets")
    revisions: Mapped[List["AssetRevision"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    lint_findings: Mapped[List["LintFinding"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    approvals: Mapped[List["ApprovalEvent"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class AssetRevision(Base):
    """
    Versioned snapshots of copy revisions created by reviewers.
    """
    __tablename__ = "asset_revisions"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    gtm_asset_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("gtm_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    asset: Mapped["GtmAsset"] = relationship(back_populates="revisions")


class LintFinding(Base):
    """
    Deterministic safety and style violations detected on generated copy.
    """
    __tablename__ = "lint_findings"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    gtm_asset_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("gtm_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. LINT-CODENAME
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # BLOCKER, WARNING
    message: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    asset: Mapped["GtmAsset"] = relationship(back_populates="lint_findings")


class ApprovalEvent(Base):
    """
    Audit trail of human reviewer interactions with assets, capturing reason chips and diffs.
    """
    __tablename__ = "approval_events"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    gtm_asset_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("gtm_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # APPROVED_AS_IS, APPROVED_WITH_EDITS, REJECTED
    reason_chips: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    edit_diff: Mapped[Optional[dict]] = mapped_column(CompatibleJSONB, nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    asset: Mapped["GtmAsset"] = relationship(back_populates="approvals")
