"""Pipeline run model — tracks async pipeline execution."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class PipelineRun(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "pipeline_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_configs.id", ondelete="SET NULL"), nullable=True
    )

    pipeline_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full, search, insights, alignment, optimize
    status: Mapped[str] = mapped_column(String(50), server_default="pending")  # pending, running, completed, failed, cancelled
    current_stage: Mapped[str | None] = mapped_column(String(100))
    progress: Mapped[float] = mapped_column(Float, server_default="0.0")  # 0.0–1.0

    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="pipeline_runs")
    search_config: Mapped["SearchConfig | None"] = relationship(back_populates="pipeline_runs")
