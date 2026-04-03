"""Optimized resume model."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class OptimizedResume(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "optimized_resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )

    optimized_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # "llm" or "keyword"

    # Relationships
    user: Mapped["User"] = relationship()
    job: Mapped["Job"] = relationship(back_populates="optimized_resumes")
    resume: Mapped["Resume"] = relationship(back_populates="optimized_resumes")
