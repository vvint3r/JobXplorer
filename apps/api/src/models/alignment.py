"""Alignment score and input index models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class AlignmentScore(Base, UUIDPrimaryKey):
    __tablename__ = "alignment_scores"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )

    alignment_score: Mapped[float] = mapped_column(Float, nullable=False)
    alignment_grade: Mapped[str] = mapped_column(String(5), nullable=False)
    matched_inputs: Mapped[dict | None] = mapped_column(JSONB)
    gaps: Mapped[dict | None] = mapped_column(JSONB)

    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship()
    job: Mapped["Job"] = relationship(back_populates="alignment_scores")
    resume: Mapped["Resume"] = relationship(back_populates="alignment_scores")


class InputIndex(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "input_indices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    master_job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)  # The full index array
    index_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
