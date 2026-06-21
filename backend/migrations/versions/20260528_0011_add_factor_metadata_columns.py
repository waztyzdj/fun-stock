"""add factor metadata columns

Revision ID: 20260528_0011
Revises: 20260527_0010
Create Date: 2026-05-28 16:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0011"
down_revision: str | None = "20260527_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "factor_definitions",
        sa.Column(
            "calculation_method",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        schema="app",
    )
    op.add_column(
        "factor_values",
        sa.Column("report_end_date", sa.Date(), nullable=True),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("factor_values", "report_end_date", schema="app")
    op.drop_column("factor_definitions", "calculation_method", schema="app")
