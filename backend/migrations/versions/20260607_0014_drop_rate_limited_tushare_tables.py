"""drop rate-limited Tushare raw tables

Revision ID: 20260607_0014
Revises: 20260531_0013
Create Date: 2026-06-07 19:20:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260607_0014"
down_revision: str | None = "20260531_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REMOVED_TABLES = (
    "stock_hsgt",
    "bak_basic",
    "bak_daily",
    "cashflow_vip",
)


def upgrade() -> None:
    for table_name in REMOVED_TABLES:
        op.execute(f"DROP TABLE IF EXISTS tushare.{table_name} CASCADE")


def downgrade() -> None:
    pass
