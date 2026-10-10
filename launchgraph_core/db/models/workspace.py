"""
Domain 1: Workspace, Brand, User, and Identity models.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB, TimestampMixin


class Workspace(Base, TimestampMixin):
    """
    Root multi-tenant container for all customer data.
    """
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="pilot", nullable=False)
    settings: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)

    # Relationships
    brands: Mapped[List["Brand"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    users: Mapped[List["AppUser"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    identities: Mapped[List["PersonIdentity"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Brand(Base):
    """
    Brand namespace within a tenant workspace.
    """
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="brands")
    profile: Mapped[Optional["BrandProfile"]] = relationship(back_populates="brand", uselist=False)


class AppUser(Base):
    """
    Users authorized to interact with the LaunchGraph platform.
    """
    __tablename__ = "app_users"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="reviewer", nullable=False)  # owner, admin, pmm, reviewer, reader
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="users")


class PersonIdentity(Base):
    """
    Maps developer identities across external systems for accurate attribution.
    """
    __tablename__ = "person_identities"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    github_username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    jira_account_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    slack_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="identities")
