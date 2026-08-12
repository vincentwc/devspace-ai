"""create generation_runs table

Revision ID: 20260812_0001
Revises:
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260812_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_generation_runs_status", "generation_runs", ["status"])
    op.create_index("ix_generation_runs_created_at", "generation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_generation_runs_created_at", table_name="generation_runs")
    op.drop_index("ix_generation_runs_status", table_name="generation_runs")
    op.drop_table("generation_runs")
