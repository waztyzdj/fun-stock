"""Fix nullable title in raw Tushare manager rewards.

Revision ID: 20260524_0004
Revises: 20260524_0003
Create Date: 2026-05-24 23:25:00.000000
"""

from alembic import op

revision = "20260524_0004"
down_revision = "20260524_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("stk_rewards_pkey", "stk_rewards", schema="tushare", type_="primary")
    op.alter_column("stk_rewards", "title", nullable=True, schema="tushare")
    op.create_primary_key(
        "stk_rewards_pkey",
        "stk_rewards",
        ["ts_code", "ann_date", "name"],
        schema="tushare",
    )


def downgrade() -> None:
    op.drop_constraint("stk_rewards_pkey", "stk_rewards", schema="tushare", type_="primary")
    op.execute("UPDATE tushare.stk_rewards SET title = '' WHERE title IS NULL")
    op.alter_column("stk_rewards", "title", nullable=False, schema="tushare")
    op.create_primary_key(
        "stk_rewards_pkey",
        "stk_rewards",
        ["ts_code", "ann_date", "name", "title"],
        schema="tushare",
    )
