"""create market core tables

Revision ID: 20260524_0001
Revises: None
Create Date: 2026-05-24 15:50:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260524_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS app"))

    op.create_table(
        "stocks",
        sa.Column("ts_code", sa.String(length=16), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("area", sa.String(length=64), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("market", sa.String(length=32), nullable=True),
        sa.Column("exchange", sa.String(length=16), nullable=True),
        sa.Column("list_status", sa.String(length=8), nullable=True),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("delist_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("ts_code", name="pk_stocks"),
        schema="app",
    )
    op.create_index("ix_stocks_exchange", "stocks", ["exchange"], schema="app")
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"], schema="app")

    op.create_table(
        "trade_calendars",
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("cal_date", sa.Date(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("pretrade_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("exchange", "cal_date", name="pk_trade_calendars"),
        schema="app",
    )
    op.create_index("ix_trade_calendars_cal_date", "trade_calendars", ["cal_date"], schema="app")

    op.create_table(
        "daily_quotes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ts_code", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(18, 4), nullable=True),
        sa.Column("high", sa.Numeric(18, 4), nullable=True),
        sa.Column("low", sa.Numeric(18, 4), nullable=True),
        sa.Column("close", sa.Numeric(18, 4), nullable=True),
        sa.Column("pre_close", sa.Numeric(18, 4), nullable=True),
        sa.Column("change", sa.Numeric(18, 4), nullable=True),
        sa.Column("pct_chg", sa.Numeric(18, 6), nullable=True),
        sa.Column("vol", sa.Numeric(20, 4), nullable=True),
        sa.Column("amount", sa.Numeric(20, 4), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_quotes"),
        sa.UniqueConstraint("ts_code", "trade_date", name="uq_daily_quotes_ts_code_trade_date"),
        schema="app",
    )
    op.create_index("ix_daily_quotes_trade_date", "daily_quotes", ["trade_date"], schema="app")
    op.create_index("ix_daily_quotes_ts_code", "daily_quotes", ["ts_code"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_daily_quotes_ts_code", table_name="daily_quotes", schema="app")
    op.drop_index("ix_daily_quotes_trade_date", table_name="daily_quotes", schema="app")
    op.drop_table("daily_quotes", schema="app")

    op.drop_index("ix_trade_calendars_cal_date", table_name="trade_calendars", schema="app")
    op.drop_table("trade_calendars", schema="app")

    op.drop_index("ix_stocks_symbol", table_name="stocks", schema="app")
    op.drop_index("ix_stocks_exchange", table_name="stocks", schema="app")
    op.drop_table("stocks", schema="app")
    op.execute(sa.text("DROP SCHEMA IF EXISTS app"))
