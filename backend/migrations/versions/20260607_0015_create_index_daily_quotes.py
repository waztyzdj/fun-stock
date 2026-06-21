"""create index daily quote tables

Revision ID: 20260607_0015
Revises: 20260607_0014
Create Date: 2026-06-07 21:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260607_0015"
down_revision: str | None = "20260607_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS tushare")
    op.create_table(
        "index_daily",
        sa.Column("ts_code", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=True),
        sa.Column("high", sa.Numeric(), nullable=True),
        sa.Column("low", sa.Numeric(), nullable=True),
        sa.Column("close", sa.Numeric(), nullable=True),
        sa.Column("pre_close", sa.Numeric(), nullable=True),
        sa.Column("change", sa.Numeric(), nullable=True),
        sa.Column("pct_chg", sa.Numeric(), nullable=True),
        sa.Column("vol", sa.Numeric(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ts_code", "trade_date", name="pk_tushare_index_daily"),
        schema="tushare",
    )
    op.create_index(
        "ix_tushare_index_daily_trade_date",
        "index_daily",
        ["trade_date"],
        schema="tushare",
    )
    op.create_index(
        "ix_tushare_index_daily_ts_code",
        "index_daily",
        ["ts_code"],
        schema="tushare",
    )
    op.execute(
        "SELECT create_hypertable("
        "'tushare.index_daily', 'trade_date', if_not_exists => TRUE, migrate_data => TRUE)"
    )

    op.create_table(
        "index_daily_quotes",
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
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_index_daily_quotes"),
        sa.UniqueConstraint(
            "ts_code",
            "trade_date",
            name="uq_index_daily_quotes_ts_code_trade_date",
        ),
        schema="app",
    )
    op.create_index(
        "ix_index_daily_quotes_trade_date",
        "index_daily_quotes",
        ["trade_date"],
        schema="app",
    )
    op.create_index(
        "ix_index_daily_quotes_ts_code",
        "index_daily_quotes",
        ["ts_code"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_index_daily_quotes_ts_code",
        table_name="index_daily_quotes",
        schema="app",
    )
    op.drop_index(
        "ix_index_daily_quotes_trade_date",
        table_name="index_daily_quotes",
        schema="app",
    )
    op.drop_table("index_daily_quotes", schema="app")
    op.drop_index("ix_tushare_index_daily_ts_code", table_name="index_daily", schema="tushare")
    op.drop_index(
        "ix_tushare_index_daily_trade_date",
        table_name="index_daily",
        schema="tushare",
    )
    op.drop_table("index_daily", schema="tushare")
