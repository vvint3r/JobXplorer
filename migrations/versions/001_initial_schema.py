"""Initial schema — all core tables.

Revision ID: 001
Revises: None
Create Date: 2026-02-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("personal_info", JSONB),
        sa.Column("application_info", JSONB),
        sa.Column("work_authorization", JSONB),
        sa.Column("voluntary_disclosures", JSONB),
        sa.Column("custom_answers", JSONB),
        sa.Column("search_preferences", JSONB),
        sa.Column("openai_api_key_encrypted", sa.Text),
        sa.Column("linkedin_cookies_storage_path", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- resumes ---
    op.create_table(
        "resumes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pdf_storage_path", sa.Text),
        sa.Column("components_json", JSONB),
        sa.Column("resume_text", sa.Text),
        sa.Column("is_default", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- search_configs ---
    op.create_table(
        "search_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("job_title_clean", sa.String(255), nullable=False),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("job_type", sa.String(50)),
        sa.Column("search_type", sa.String(50)),
        sa.Column("work_geo_codes", ARRAY(sa.String)),
        sa.Column("remote_filter", sa.String(50)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- jobs ---
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("search_config_id", UUID(as_uuid=True), sa.ForeignKey("search_configs.id", ondelete="SET NULL")),
        sa.Column("job_id", sa.String(255)),
        sa.Column("job_title", sa.String(500), nullable=False),
        sa.Column("company_title", sa.String(500)),
        sa.Column("job_url", sa.Text, nullable=False),
        sa.Column("application_url", sa.Text),
        sa.Column("salary_range", sa.String(255)),
        sa.Column("location", sa.String(500)),
        sa.Column("remote_status", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("days_since_posted", sa.Integer),
        sa.Column("date_extracted", sa.DateTime(timezone=True)),
        sa.Column("application_status", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "job_url", name="uq_user_job_url"),
    )

    # --- alignment_scores ---
    op.create_table(
        "alignment_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alignment_score", sa.Float, nullable=False),
        sa.Column("alignment_grade", sa.String(5), nullable=False),
        sa.Column("matched_inputs", JSONB),
        sa.Column("gaps", JSONB),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- jd_insights ---
    op.create_table(
        "jd_insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("search_config_id", UUID(as_uuid=True), sa.ForeignKey("search_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_jobs_analysed", sa.Integer, server_default="0"),
        sa.Column("categorised_phrases", JSONB),
        sa.Column("summary", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- input_indices ---
    op.create_table(
        "input_indices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("master_job_title", sa.String(255), nullable=False),
        sa.Column("inputs", JSONB, nullable=False),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- optimized_resumes ---
    op.create_table(
        "optimized_resumes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("optimized_json", JSONB, nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- pipeline_runs ---
    op.create_table(
        "pipeline_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("search_config_id", UUID(as_uuid=True), sa.ForeignKey("search_configs.id", ondelete="SET NULL")),
        sa.Column("pipeline_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("current_stage", sa.String(100)),
        sa.Column("progress", sa.Float, server_default="0.0"),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- RLS policies ---
    # These use auth.uid() which is Supabase-specific and only runs on Supabase cloud.
    # Skipped here so migrations work against plain PostgreSQL in local dev.
    pass


def downgrade() -> None:
    for table in ["pipeline_runs", "optimized_resumes", "input_indices",
                  "jd_insights", "alignment_scores", "jobs",
                  "search_configs", "resumes", "users"]:
        op.drop_table(table)
