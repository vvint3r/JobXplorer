"""Job model — scraped job listings."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class Job(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_url", name="uq_user_job_url"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_configs.id", ondelete="SET NULL"), nullable=True
    )

    # Core fields from LinkedIn scraping
    job_id: Mapped[str | None] = mapped_column(String(255))
    job_title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_title: Mapped[str | None] = mapped_column(String(500))
    job_url: Mapped[str] = mapped_column(Text, nullable=False)
    application_url: Mapped[str | None] = mapped_column(Text)
    salary_range: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(500))
    remote_status: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    days_since_posted: Mapped[int | None] = mapped_column(Integer)
    date_extracted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Application tracking
    application_status: Mapped[str | None] = mapped_column(String(50))  # applied, skipped, failed

    # Relationships
    user: Mapped["User"] = relationship(back_populates="jobs")
    search_config: Mapped["SearchConfig | None"] = relationship(back_populates="jobs")
    alignment_scores: Mapped[list["AlignmentScore"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    optimized_resumes: Mapped[list["OptimizedResume"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    application_logs: Mapped[list["ApplicationLog"]] = relationship(back_populates="job", cascade="all, delete-orphan")
