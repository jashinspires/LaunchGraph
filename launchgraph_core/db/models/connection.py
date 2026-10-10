"""
Domain 2: Ingestion connections, webhook inbox buffer, and scrubbed source events.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, LargeBinary, ForeignKey, DateTime, Integer, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB


class Connection(Base):
    """
    Configuration and KMS-encrypted credentials for external providers (GitHub, Jira, Slack).
    """
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # GITHUB, JIRA, SLACK
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, ERROR, DISCONNECTED
    credentials: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    config: Mapped[dict] = mapped_column(CompatibleJSONB, default=dict, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    inbox_items: Mapped[List["WebhookInbox"]] = relationship(back_populates="connection", cascade="all, delete-orphan")
    source_events: Mapped[List["SourceEvent"]] = relationship(back_populates="connection", cascade="all, delete-orphan")


class WebhookInbox(Base):
    """
    Raw, append-only buffer for incoming webhook payloads with deduplication keys.
    """
    __tablename__ = "webhook_inbox"
    __table_args__ = (
        UniqueConstraint("connection_id", "idempotency_key", name="uq_webhook_inbox_dedupe"),
    )

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(CompatibleJSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, processed, failed, dead_letter
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    connection: Mapped["Connection"] = relationship(back_populates="inbox_items")


class SourceEvent(Base):
    """
    Scrubbed and validated development activity events ready for normalization.
    """
    __tablename__ = "source_events"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # GITHUB, JIRA, SLACK
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    trust_label: Mapped[str] = mapped_column(String(32), default="INTERNAL", nullable=False)  # INTERNAL, EXTERNAL_UNTRUSTED
    raw_payload: Mapped[dict] = mapped_column(CompatibleJSONB, nullable=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    connection: Mapped["Connection"] = relationship(back_populates="source_events")
