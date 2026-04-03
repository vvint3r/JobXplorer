"""Resume model — uploaded PDFs + parsed components."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class Resume(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_storage_path: Mapped[str | None] = mapped_column(Text)

    # Parsed resume structure (mirrors config/resumes/base_resume/ JSON)
    components_json: Mapped[dict | None] = mapped_column(JSONB)
    resume_text: Mapped[str | None] = mapped_column(Text)

    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Relationships
    user: Mapped["User"] = relationship(back_populates="resumes")
    alignment_scores: Mapped[list["AlignmentScore"]] = relationship(back_populates="resume", cascade="all, delete-orphan")
    optimized_resumes: Mapped[list["OptimizedResume"]] = relationship(back_populates="resume", cascade="all, delete-orphan")
