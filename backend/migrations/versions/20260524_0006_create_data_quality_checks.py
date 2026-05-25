"""create data quality checks

Revision ID: 20260524_0006
Revises: 20260524_0005
Create Date: 2026-05-24 23:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260524_0006"
down_revision: str | None = "20260524_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_quality_checks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("check_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("observed_value", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["app.data_sync_runs.id"],
            name="fk_data_quality_checks_run_id_data_sync_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_quality_checks"),
        schema="app",
    )
    op.create_index(
        "ix_data_quality_checks_run_id",
        "data_quality_checks",
        ["run_id"],
        schema="app",
    )
    op.create_index(
        "ix_data_quality_checks_status",
        "data_quality_checks",
        ["status"],
        schema="app",
    )
    op.create_index(
        "ix_data_quality_checks_check_name",
        "data_quality_checks",
        ["check_name"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_quality_checks_check_name",
        table_name="data_quality_checks",
        schema="app",
    )
    op.drop_index(
        "ix_data_quality_checks_status",
        table_name="data_quality_checks",
        schema="app",
    )
    op.drop_index(
        "ix_data_quality_checks_run_id",
        table_name="data_quality_checks",
        schema="app",
    )
    op.drop_table("data_quality_checks", schema="app")
