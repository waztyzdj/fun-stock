"""Fix raw Tushare idempotent keys.

Revision ID: 20260524_0003
Revises: 20260524_0002
Create Date: 2026-05-24 23:10:00.000000
"""

from alembic import op

revision = "20260524_0003"
down_revision = "20260524_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM tushare.bse_mapping WHERE o_code IS NULL OR n_code IS NULL")
    op.alter_column("bse_mapping", "o_code", nullable=False, schema="tushare")
    op.alter_column("bse_mapping", "n_code", nullable=False, schema="tushare")
    op.create_primary_key(
        "bse_mapping_pkey",
        "bse_mapping",
        ["o_code", "n_code"],
        schema="tushare",
    )


def downgrade() -> None:
    op.drop_constraint("bse_mapping_pkey", "bse_mapping", schema="tushare", type_="primary")
    op.alter_column("bse_mapping", "n_code", nullable=True, schema="tushare")
    op.alter_column("bse_mapping", "o_code", nullable=True, schema="tushare")
