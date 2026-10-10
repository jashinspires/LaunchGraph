"""
Domain 1: Brand profile and audience segment models.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from launchgraph_core.db.base import Base, CompatibleUUID, CompatibleJSONB, TimestampMixin


class BrandProfile(Base, TimestampMixin):
    """
    Living brand voice guidelines, product summary, and claim constraints.
    """
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("brands.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    product_summary: Mapped[str] = mapped_column(Text, nullable=False)
    voice_tone: Mapped[str] = mapped_column(String(128), default="authoritative, concise, helpful", nullable=False)
    tone_rules: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    allowed_claims: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    disallowed_claims: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    codenames: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)

    brand: Mapped["Brand"] = relationship(back_populates="profile")


class AudienceSegment(Base):
    """
    Target buyer and user persona definitions.
    """
    __tablename__ = "audience_segments"

    id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        CompatibleUUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    pain_points: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    desired_outcomes: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    objections: Mapped[list] = mapped_column(CompatibleJSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
