"""add backfill batch metadata

Revision ID: 20260527_0009
Revises: 20260526_0008
Create Date: 2026-05-27 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0009"
down_revision: str | None = "20260526_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backfill_batches",
        sa.Column("api_name", sa.String(length=64), nullable=True),
        schema="app",
    )
    op.add_column(
        "backfill_batches",
        sa.Column("cursor_value", sa.String(length=64), nullable=True),
        schema="app",
    )
    op.create_index(
        "ix_backfill_batches_api_name_status",
        "backfill_batches",
        ["api_name", "status"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_backfill_batches_api_name_status",
        table_name="backfill_batches",
        schema="app",
    )
    op.drop_column("backfill_batches", "cursor_value", schema="app")
    op.drop_column("backfill_batches", "api_name", schema="app")
