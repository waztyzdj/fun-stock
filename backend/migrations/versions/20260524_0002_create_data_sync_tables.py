"""create data sync tables

Revision ID: 20260524_0002
Revises: 20260524_0001
Create Date: 2026-05-24 17:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260524_0002"
down_revision: str | None = "20260524_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_sync_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("api_name", sa.String(length=64), nullable=False),
        sa.Column("sync_mode", sa.String(length=32), nullable=False),
        sa.Column("cursor_value", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_sync_jobs"),
        sa.UniqueConstraint("provider", "api_name", name="uq_data_sync_jobs_provider_api_name"),
        schema="app",
    )
    op.create_index("ix_data_sync_jobs_status", "data_sync_jobs", ["status"], schema="app")

    op.create_table(
        "data_sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("window_start", sa.String(length=32), nullable=True),
        sa.Column("window_end", sa.String(length=32), nullable=True),
        sa.Column("rows_fetched", sa.Integer(), nullable=False),
        sa.Column("rows_upserted", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["app.data_sync_jobs.id"],
            name="fk_data_sync_runs_job_id_data_sync_jobs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_data_sync_runs"),
        schema="app",
    )
    op.create_index(
        "ix_data_sync_runs_job_id_started_at",
        "data_sync_runs",
        ["job_id", "started_at"],
        schema="app",
    )
    op.create_index("ix_data_sync_runs_status", "data_sync_runs", ["status"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_data_sync_runs_status", table_name="data_sync_runs", schema="app")
    op.drop_index(
        "ix_data_sync_runs_job_id_started_at",
        table_name="data_sync_runs",
        schema="app",
    )
    op.drop_table("data_sync_runs", schema="app")

    op.drop_index("ix_data_sync_jobs_status", table_name="data_sync_jobs", schema="app")
    op.drop_table("data_sync_jobs", schema="app")
