"""create market indicator tables

Revision ID: 20260525_0007
Revises: 20260524_0006
Create Date: 2026-05-25 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0007"
down_revision: str | None = "20260524_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_indicators",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ts_code", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=True),
        sa.Column("turnover_rate", sa.Numeric(18, 6), nullable=True),
        sa.Column("turnover_rate_f", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume_ratio", sa.Numeric(18, 6), nullable=True),
        sa.Column("pe", sa.Numeric(18, 6), nullable=True),
        sa.Column("pe_ttm", sa.Numeric(18, 6), nullable=True),
        sa.Column("pb", sa.Numeric(18, 6), nullable=True),
        sa.Column("ps", sa.Numeric(18, 6), nullable=True),
        sa.Column("ps_ttm", sa.Numeric(18, 6), nullable=True),
        sa.Column("dv_ratio", sa.Numeric(18, 6), nullable=True),
        sa.Column("dv_ttm", sa.Numeric(18, 6), nullable=True),
        sa.Column("total_share", sa.Numeric(24, 4), nullable=True),
        sa.Column("float_share", sa.Numeric(24, 4), nullable=True),
        sa.Column("free_share", sa.Numeric(24, 4), nullable=True),
        sa.Column("total_mv", sa.Numeric(24, 4), nullable=True),
        sa.Column("circ_mv", sa.Numeric(24, 4), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_indicators"),
        sa.UniqueConstraint(
            "ts_code",
            "trade_date",
            name="uq_daily_indicators_ts_code_trade_date",
        ),
        schema="app",
    )
    op.create_index(
        "ix_daily_indicators_trade_date",
        "daily_indicators",
        ["trade_date"],
        schema="app",
    )
    op.create_index(
        "ix_daily_indicators_ts_code",
        "daily_indicators",
        ["ts_code"],
        schema="app",
    )

    op.create_table(
        "adj_factors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ts_code", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("adj_factor", sa.Numeric(24, 8), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_adj_factors"),
        sa.UniqueConstraint(
            "ts_code",
            "trade_date",
            name="uq_adj_factors_ts_code_trade_date",
        ),
        schema="app",
    )
    op.create_index("ix_adj_factors_trade_date", "adj_factors", ["trade_date"], schema="app")
    op.create_index("ix_adj_factors_ts_code", "adj_factors", ["ts_code"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_adj_factors_ts_code", table_name="adj_factors", schema="app")
    op.drop_index("ix_adj_factors_trade_date", table_name="adj_factors", schema="app")
    op.drop_table("adj_factors", schema="app")
    op.drop_index("ix_daily_indicators_ts_code", table_name="daily_indicators", schema="app")
    op.drop_index("ix_daily_indicators_trade_date", table_name="daily_indicators", schema="app")
    op.drop_table("daily_indicators", schema="app")
