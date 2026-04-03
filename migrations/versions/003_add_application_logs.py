"""Add application_logs table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "optimized_resume_id",
            UUID(as_uuid=True),
            sa.ForeignKey("optimized_resumes.id", ondelete="SET NULL"),
        ),
        sa.Column("board_type", sa.String(50), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("fields_filled", sa.Integer),
        sa.Column("fields_total", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # RLS policy
    op.execute(
        "ALTER TABLE application_logs ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "CREATE POLICY application_logs_user_isolation ON application_logs "
        "USING (user_id = current_setting('app.current_user_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS application_logs_user_isolation ON application_logs")
    op.drop_table("application_logs")
