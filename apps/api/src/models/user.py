"""User model — synced from Supabase Auth."""

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, UUIDPrimaryKey


class User(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(50), server_default="free")

    # Replaces config/user_config.json per-user
    personal_info: Mapped[dict | None] = mapped_column(JSONB)
    application_info: Mapped[dict | None] = mapped_column(JSONB)
    work_authorization: Mapped[dict | None] = mapped_column(JSONB)
    voluntary_disclosures: Mapped[dict | None] = mapped_column(JSONB)
    custom_answers: Mapped[dict | None] = mapped_column(JSONB)
    search_preferences: Mapped[dict | None] = mapped_column(JSONB)

    # Supplementary terms for alignment scoring (skills not on resume)
    # Format: [{"term": "python", "proficiency": "expert"}, ...]
    supplementary_terms: Mapped[dict | None] = mapped_column(JSONB)

    # Encrypted secrets
    openai_api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    linkedin_cookies_storage_path: Mapped[str | None] = mapped_column(Text)

    # Relationships
    resumes: Mapped[list["Resume"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    search_configs: Mapped[list["SearchConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    application_logs: Mapped[list["ApplicationLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
