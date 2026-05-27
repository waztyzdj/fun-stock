"""create backfill tables

Revision ID: 20260526_0008
Revises: 20260525_0007
Create Date: 2026-05-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0008"
down_revision: str | None = "20260525_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backfill_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("cursor_date", sa.Date(), nullable=True),
        sa.Column("total_batches", sa.Integer(), nullable=False),
        sa.Column("succeeded_batches", sa.Integer(), nullable=False),
        sa.Column("failed_batches", sa.Integer(), nullable=False),
        sa.Column("blocked_batches", sa.Integer(), nullable=False),
        sa.Column("total_windows", sa.Integer(), nullable=False),
        sa.Column("rows_fetched", sa.BigInteger(), nullable=False),
        sa.Column("rows_upserted", sa.BigInteger(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backfill_jobs"),
        schema="app",
    )
    op.create_index(
        "ix_backfill_jobs_provider_status",
        "backfill_jobs",
        ["provider", "status"],
        schema="app",
    )
    op.create_index(
        "ix_backfill_jobs_started_at",
        "backfill_jobs",
        ["started_at"],
        schema="app",
    )

    op.create_table(
        "backfill_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cursor_date", sa.Date(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("trade_days", sa.Integer(), nullable=False),
        sa.Column("windows", sa.Integer(), nullable=False),
        sa.Column("rows_fetched", sa.BigInteger(), nullable=False),
        sa.Column("rows_upserted", sa.BigInteger(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["app.backfill_jobs.id"],
            name="fk_backfill_batches_job_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backfill_batches"),
        sa.UniqueConstraint("job_id", "batch_index", name="uq_backfill_batches_job_batch_index"),
        schema="app",
    )
    op.create_index(
        "ix_backfill_batches_job_id_started_at",
        "backfill_batches",
        ["job_id", "started_at"],
        schema="app",
    )
    op.create_index(
        "ix_backfill_batches_status",
        "backfill_batches",
        ["status"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index("ix_backfill_batches_status", table_name="backfill_batches", schema="app")
    op.drop_index(
        "ix_backfill_batches_job_id_started_at",
        table_name="backfill_batches",
        schema="app",
    )
    op.drop_table("backfill_batches", schema="app")
    op.drop_index("ix_backfill_jobs_started_at", table_name="backfill_jobs", schema="app")
    op.drop_index("ix_backfill_jobs_provider_status", table_name="backfill_jobs", schema="app")
    op.drop_table("backfill_jobs", schema="app")
