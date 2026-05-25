"""Fix raw Tushare minute quote keys.

Revision ID: 20260524_0005
Revises: 20260524_0004
Create Date: 2026-05-24 23:40:00.000000
"""

from alembic import op

revision = "20260524_0005"
down_revision = "20260524_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("stk_mins_pkey", "stk_mins", schema="tushare", type_="primary")
    op.drop_constraint("rt_min_pkey", "rt_min", schema="tushare", type_="primary")
    op.drop_constraint("rt_min_daily_pkey", "rt_min_daily", schema="tushare", type_="primary")

    op.execute("DELETE FROM tushare.stk_mins WHERE trade_time IS NULL")
    op.execute("DELETE FROM tushare.rt_min WHERE time IS NULL")
    op.execute("DELETE FROM tushare.rt_min_daily WHERE freq IS NULL OR time IS NULL")

    op.alter_column("stk_mins", "trade_time", nullable=False, schema="tushare")
    op.alter_column("rt_min", "time", nullable=False, schema="tushare")
    op.alter_column("rt_min_daily", "freq", nullable=False, schema="tushare")
    op.alter_column("rt_min_daily", "time", nullable=False, schema="tushare")

    op.create_primary_key(
        "stk_mins_pkey",
        "stk_mins",
        ["ts_code", "trade_time"],
        schema="tushare",
    )
    op.create_primary_key(
        "rt_min_pkey",
        "rt_min",
        ["ts_code", "time"],
        schema="tushare",
    )
    op.create_primary_key(
        "rt_min_daily_pkey",
        "rt_min_daily",
        ["ts_code", "freq", "time"],
        schema="tushare",
    )


def downgrade() -> None:
    op.drop_constraint("rt_min_daily_pkey", "rt_min_daily", schema="tushare", type_="primary")
    op.drop_constraint("rt_min_pkey", "rt_min", schema="tushare", type_="primary")
    op.drop_constraint("stk_mins_pkey", "stk_mins", schema="tushare", type_="primary")

    op.alter_column("rt_min_daily", "time", nullable=True, schema="tushare")
    op.alter_column("rt_min_daily", "freq", nullable=True, schema="tushare")
    op.alter_column("rt_min", "time", nullable=True, schema="tushare")
    op.alter_column("stk_mins", "trade_time", nullable=True, schema="tushare")

    op.create_primary_key("stk_mins_pkey", "stk_mins", ["ts_code"], schema="tushare")
    op.create_primary_key("rt_min_pkey", "rt_min", ["ts_code"], schema="tushare")
    op.create_primary_key(
        "rt_min_daily_pkey",
        "rt_min_daily",
        ["ts_code"],
        schema="tushare",
    )
