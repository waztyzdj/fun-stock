"""create factor and strategy tables

Revision ID: 20260527_0010
Revises: 20260527_0009
Create Date: 2026-05-27 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_0010"
down_revision: str | None = "20260527_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "factor_definitions",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("period_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("calculation_method", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_direction", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("code", name="pk_factor_definitions"),
        schema="app",
    )
    op.create_index(
        "ix_factor_definitions_category",
        "factor_definitions",
        ["category"],
        schema="app",
    )

    op.create_table(
        "factor_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("factor_code", sa.String(length=64), nullable=False),
        sa.Column("ts_code", sa.String(length=16), nullable=False),
        sa.Column("factor_date", sa.Date(), nullable=False),
        sa.Column("report_end_date", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(24, 8), nullable=False),
        sa.Column("period_type", sa.String(length=32), nullable=False),
        sa.Column("ann_date", sa.Date(), nullable=True),
        sa.Column("source_table", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["factor_code"],
            ["app.factor_definitions.code"],
            name="fk_factor_values_factor_code",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_factor_values"),
        sa.UniqueConstraint(
            "factor_code",
            "ts_code",
            "factor_date",
            name="uq_factor_values_factor_stock_date",
        ),
        schema="app",
    )
    op.create_index(
        "ix_factor_values_factor_code_date",
        "factor_values",
        ["factor_code", "factor_date"],
        schema="app",
    )
    op.create_index(
        "ix_factor_values_ts_code_date",
        "factor_values",
        ["ts_code", "factor_date"],
        schema="app",
    )

    op.create_table(
        "strategy_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("strategy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_definitions"),
        schema="app",
    )
    op.create_index(
        "ix_strategy_definitions_status",
        "strategy_definitions",
        ["status"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_definitions_status",
        table_name="strategy_definitions",
        schema="app",
    )
    op.drop_table("strategy_definitions", schema="app")
    op.drop_index("ix_factor_values_ts_code_date", table_name="factor_values", schema="app")
    op.drop_index("ix_factor_values_factor_code_date", table_name="factor_values", schema="app")
    op.drop_table("factor_values", schema="app")
    op.drop_index(
        "ix_factor_definitions_category",
        table_name="factor_definitions",
        schema="app",
    )
    op.drop_table("factor_definitions", schema="app")
