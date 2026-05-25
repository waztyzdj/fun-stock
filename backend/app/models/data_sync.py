from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class DataSyncJob(Base):
    __tablename__ = "data_sync_jobs"
    __table_args__ = (
        UniqueConstraint("provider", "api_name", name="uq_data_sync_jobs_provider_api_name"),
        Index("ix_data_sync_jobs_status", "status"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    api_name: Mapped[str] = mapped_column(String(64), nullable=False)
    sync_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    cursor_value: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    error_message: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list["DataSyncRun"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class DataSyncRun(Base):
    __tablename__ = "data_sync_runs"
    __table_args__ = (
        Index("ix_data_sync_runs_job_id_started_at", "job_id", "started_at"),
        Index("ix_data_sync_runs_status", "status"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("app.data_sync_jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    window_start: Mapped[str | None] = mapped_column(String(32))
    window_end: Mapped[str | None] = mapped_column(String(32))
    rows_fetched: Mapped[int] = mapped_column(nullable=False, default=0)
    rows_upserted: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[DataSyncJob] = relationship(back_populates="runs")
    quality_checks: Mapped[list["DataQualityCheck"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"
    __table_args__ = (
        Index("ix_data_quality_checks_run_id", "run_id"),
        Index("ix_data_quality_checks_status", "status"),
        Index("ix_data_quality_checks_check_name", "check_name"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("app.data_sync_runs.id"), nullable=False)
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    observed_value: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[DataSyncRun] = relationship(back_populates="quality_checks")
