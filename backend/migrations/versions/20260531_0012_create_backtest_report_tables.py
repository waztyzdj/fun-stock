"""create backtest report tables

Revision ID: 20260531_0012
Revises: 20260528_0011
Create Date: 2026-05-31 21:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260531_0012"
down_revision: str | None = "20260528_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("strategy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["app.strategy_definitions.id"],
            name="fk_strategy_versions_strategy_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_versions"),
        sa.UniqueConstraint(
            "strategy_id",
            "version_no",
            name="uq_strategy_versions_strategy_version",
        ),
        schema="app",
    )
    op.create_index(
        "ix_strategy_versions_strategy_id",
        "strategy_versions",
        ["strategy_id"],
        schema="app",
    )

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_version_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("initial_cash", sa.Numeric(24, 6), nullable=False),
        sa.Column("final_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("benchmark_final_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("total_return", sa.Numeric(24, 10), nullable=False),
        sa.Column("benchmark_return", sa.Numeric(24, 10), nullable=False),
        sa.Column("excess_return", sa.Numeric(24, 10), nullable=False),
        sa.Column("annualized_return", sa.Numeric(24, 10), nullable=False),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "finished_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"],
            ["app.strategy_versions.id"],
            name="fk_backtest_runs_strategy_version_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backtest_runs"),
        schema="app",
    )
    op.create_index("ix_backtest_runs_status", "backtest_runs", ["status"], schema="app")
    op.create_index(
        "ix_backtest_runs_strategy_version_id",
        "backtest_runs",
        ["strategy_version_id"],
        schema="app",
    )

    op.create_table(
        "backtest_periods",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("rebalance_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("period_return", sa.Numeric(24, 10), nullable=False),
        sa.Column("benchmark_return", sa.Numeric(24, 10), nullable=False),
        sa.Column("excess_return", sa.Numeric(24, 10), nullable=False),
        sa.Column("portfolio_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("benchmark_value", sa.Numeric(24, 6), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["app.backtest_runs.id"],
            name="fk_backtest_periods_run_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backtest_periods"),
        schema="app",
    )
    op.create_index("ix_backtest_periods_run_id", "backtest_periods", ["run_id"], schema="app")

    op.create_table(
        "backtest_holdings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("ts_code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Numeric(24, 10), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("exit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("return_ratio", sa.Numeric(24, 10), nullable=True),
        sa.ForeignKeyConstraint(
            ["period_id"],
            ["app.backtest_periods.id"],
            name="fk_backtest_holdings_period_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backtest_holdings"),
        schema="app",
    )
    op.create_index(
        "ix_backtest_holdings_period_id",
        "backtest_holdings",
        ["period_id"],
        schema="app",
    )
    op.create_index(
        "ix_backtest_holdings_ts_code",
        "backtest_holdings",
        ["ts_code"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_holdings_ts_code", table_name="backtest_holdings", schema="app")
    op.drop_index(
        "ix_backtest_holdings_period_id",
        table_name="backtest_holdings",
        schema="app",
    )
    op.drop_table("backtest_holdings", schema="app")
    op.drop_index("ix_backtest_periods_run_id", table_name="backtest_periods", schema="app")
    op.drop_table("backtest_periods", schema="app")
    op.drop_index(
        "ix_backtest_runs_strategy_version_id",
        table_name="backtest_runs",
        schema="app",
    )
    op.drop_index("ix_backtest_runs_status", table_name="backtest_runs", schema="app")
    op.drop_table("backtest_runs", schema="app")
    op.drop_index(
        "ix_strategy_versions_strategy_id",
        table_name="strategy_versions",
        schema="app",
    )
    op.drop_table("strategy_versions", schema="app")
