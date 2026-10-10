"""
Declarative Base and common model mixins for LaunchGraph.
Supports PostgreSQL natively while providing SQLite compatibility for testing.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, TypeDecorator, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy entities."""
    pass


class CompatibleUUID(TypeDecorator):
    """
    Platform-independent UUID type.
    Uses PostgreSQL's native UUID type, otherwise CHAR(36) or String.
    """
    impl = PG_UUID(as_uuid=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            from sqlalchemy import String
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value) if dialect.name != "postgresql" else value
        if isinstance(value, str):
            return uuid.UUID(value) if dialect.name == "postgresql" else value
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class CompatibleJSONB(TypeDecorator):
    """
    Platform-independent JSONB type.
    Uses PostgreSQL JSONB natively, otherwise standard SQLAlchemy JSON.
    """
    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


class CompatibleVector(TypeDecorator):
    """
    Platform-independent Vector type.
    Uses pgvector Vector when available on PostgreSQL, otherwise JSON or String.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 1536, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(self.dim))
            except ImportError:
                return dialect.type_descriptor(JSON())
        else:
            return dialect.type_descriptor(JSON())


class TimestampMixin:
    """Provides created_at and updated_at audit columns."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
