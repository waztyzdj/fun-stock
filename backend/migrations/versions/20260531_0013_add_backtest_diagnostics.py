"""add backtest diagnostics

Revision ID: 20260531_0013
Revises: 20260531_0012
Create Date: 2026-05-31 22:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260531_0013"
down_revision: str | None = "20260531_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_runs",
        sa.Column(
            "max_drawdown",
            sa.Numeric(24, 10),
            server_default="0",
            nullable=False,
        ),
        schema="app",
    )
    op.add_column(
        "backtest_runs",
        sa.Column(
            "win_rate",
            sa.Numeric(24, 10),
            server_default="0",
            nullable=False,
        ),
        schema="app",
    )
    op.add_column(
        "backtest_runs",
        sa.Column(
            "average_turnover",
            sa.Numeric(24, 10),
            server_default="0",
            nullable=False,
        ),
        schema="app",
    )
    op.add_column(
        "backtest_periods",
        sa.Column(
            "turnover_rate",
            sa.Numeric(24, 10),
            server_default="0",
            nullable=False,
        ),
        schema="app",
    )
    op.alter_column("backtest_runs", "max_drawdown", server_default=None, schema="app")
    op.alter_column("backtest_runs", "win_rate", server_default=None, schema="app")
    op.alter_column("backtest_runs", "average_turnover", server_default=None, schema="app")
    op.alter_column("backtest_periods", "turnover_rate", server_default=None, schema="app")


def downgrade() -> None:
    op.drop_column("backtest_periods", "turnover_rate", schema="app")
    op.drop_column("backtest_runs", "average_turnover", schema="app")
    op.drop_column("backtest_runs", "win_rate", schema="app")
    op.drop_column("backtest_runs", "max_drawdown", schema="app")
