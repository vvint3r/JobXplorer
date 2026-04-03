"""Add supplementary_terms column to users.

Revision ID: 002
Revises: 001
Create Date: 2026-02-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("supplementary_terms", JSONB))


def downgrade() -> None:
    op.drop_column("users", "supplementary_terms")
