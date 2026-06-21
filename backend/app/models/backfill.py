from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class BackfillJob(Base):
    __tablename__ = "backfill_jobs"
    __table_args__ = (
        Index("ix_backfill_jobs_provider_status", "provider", "status"),
        Index("ix_backfill_jobs_started_at", "started_at"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    cursor_date: Mapped[date | None] = mapped_column(Date)
    total_batches: Mapped[int] = mapped_column(nullable=False, default=0)
    succeeded_batches: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_batches: Mapped[int] = mapped_column(nullable=False, default=0)
    blocked_batches: Mapped[int] = mapped_column(nullable=False, default=0)
    total_windows: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_fetched: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rows_upserted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    batches: Mapped[list["BackfillBatch"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class BackfillBatch(Base):
    __tablename__ = "backfill_batches"
    __table_args__ = (
        UniqueConstraint("job_id", "batch_index", name="uq_backfill_batches_job_batch_index"),
        Index("ix_backfill_batches_job_id_started_at", "job_id", "started_at"),
        Index("ix_backfill_batches_status", "status"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("app.backfill_jobs.id"), nullable=False)
    batch_index: Mapped[int] = mapped_column(nullable=False)
    api_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    cursor_value: Mapped[str | None] = mapped_column(String(64))
    cursor_date: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    trade_days: Mapped[int] = mapped_column(nullable=False, default=0)
    windows: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_fetched: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rows_upserted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[BackfillJob] = relationship(back_populates="batches")
