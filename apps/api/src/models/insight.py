"""JD Insights model."""

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class JDInsight(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "jd_insights"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_configs.id", ondelete="CASCADE"), nullable=False
    )

    total_jobs_analysed: Mapped[int] = mapped_column(Integer, server_default="0")
    categorised_phrases: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    user: Mapped["User"] = relationship()
    search_config: Mapped["SearchConfig"] = relationship(back_populates="jd_insights")
