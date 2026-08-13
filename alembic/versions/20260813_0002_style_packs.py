"""create style_packs table

Revision ID: 20260813_0002
Revises: 20260812_0001
Create Date: 2026-08-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260813_0002"
down_revision: str | Sequence[str] | None = "20260812_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "style_packs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("examples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", name="uq_style_packs_key"),
    )
    op.create_index("ix_style_packs_updated_at", "style_packs", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_style_packs_updated_at", table_name="style_packs")
    op.drop_table("style_packs")
