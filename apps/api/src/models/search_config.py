"""Search configuration model — replaces interactive job_title prompt."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class SearchConfig(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "search_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title_clean: Mapped[str] = mapped_column(String(255), nullable=False)

    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    job_type: Mapped[str | None] = mapped_column(String(50))  # full_time, contract, etc.
    search_type: Mapped[str | None] = mapped_column(String(50))  # exact, broad
    work_geo_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    remote_filter: Mapped[str | None] = mapped_column(String(50))  # remote, hybrid, onsite

    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Relationships
    user: Mapped["User"] = relationship(back_populates="search_configs")
    jobs: Mapped[list["Job"]] = relationship(back_populates="search_config", cascade="all, delete-orphan")
    jd_insights: Mapped[list["JDInsight"]] = relationship(back_populates="search_config", cascade="all, delete-orphan")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="search_config")
