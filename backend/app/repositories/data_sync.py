from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.data_sync import DataQualityCheck, DataSyncJob, DataSyncRun

BLOCKED_INSUFFICIENT_POINTS_STATUS = "blocked_insufficient_points"
MAX_OBSERVED_VALUE_LENGTH = 128
RETRYABLE_FAILED_STATUSES = frozenset({"failed"})
PROBLEM_RUN_STATUSES = frozenset({"failed", BLOCKED_INSUFFICIENT_POINTS_STATUS})
QUALITY_ALERT_STATUSES = frozenset({"warning", "failed"})


def is_retryable_sync_job(job: DataSyncJob) -> bool:
    return job.status in RETRYABLE_FAILED_STATUSES


def _truncate_observed_value(value: str | None) -> str | None:
    if value is None or len(value) <= MAX_OBSERVED_VALUE_LENGTH:
        return value
    return f"{value[: MAX_OBSERVED_VALUE_LENGTH - 3]}..."


class DataSyncRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_job(
        self,
        *,
        provider: str,
        api_name: str,
        sync_mode: str,
        default_cursor_value: str | None = None,
    ) -> DataSyncJob:
        job = self.session.scalar(
            select(DataSyncJob).where(
                DataSyncJob.provider == provider,
                DataSyncJob.api_name == api_name,
            )
        )
        if job is not None:
            job.sync_mode = sync_mode
            return job

        job = DataSyncJob(
            provider=provider,
            api_name=api_name,
            sync_mode=sync_mode,
            cursor_value=default_cursor_value,
            status="idle",
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_job(self, *, provider: str, api_name: str) -> DataSyncJob | None:
        return self.session.scalar(
            select(DataSyncJob).where(
                DataSyncJob.provider == provider,
                DataSyncJob.api_name == api_name,
            )
        )

    def list_jobs(self, *, provider: str, limit: int = 100) -> list[DataSyncJob]:
        return list(
            self.session.scalars(
                select(DataSyncJob)
                .where(DataSyncJob.provider == provider)
                .order_by(DataSyncJob.updated_at.desc(), DataSyncJob.api_name)
                .limit(limit)
            )
        )

    def list_blocked_jobs(self, *, provider: str, limit: int) -> list[DataSyncJob]:
        return list(
            self.session.scalars(
                select(DataSyncJob)
                .where(
                    DataSyncJob.provider == provider,
                    DataSyncJob.status == BLOCKED_INSUFFICIENT_POINTS_STATUS,
                )
                .order_by(DataSyncJob.updated_at.desc(), DataSyncJob.api_name)
                .limit(limit)
            )
        )

    def list_recent_problem_runs(self, *, provider: str, limit: int) -> list[DataSyncRun]:
        return list(
            self.session.scalars(
                select(DataSyncRun)
                .join(DataSyncRun.job)
                .options(joinedload(DataSyncRun.job))
                .where(
                    DataSyncJob.provider == provider,
                    DataSyncRun.status.in_(PROBLEM_RUN_STATUSES),
                )
                .order_by(DataSyncRun.started_at.desc(), DataSyncRun.id.desc())
                .limit(limit)
            )
        )

    def list_recent_quality_alerts(
        self,
        *,
        provider: str,
        limit: int,
    ) -> list[DataQualityCheck]:
        return list(
            self.session.scalars(
                select(DataQualityCheck)
                .join(DataQualityCheck.run)
                .join(DataSyncRun.job)
                .options(joinedload(DataQualityCheck.run).joinedload(DataSyncRun.job))
                .where(
                    DataSyncJob.provider == provider,
                    DataQualityCheck.status.in_(QUALITY_ALERT_STATUSES),
                )
                .order_by(DataQualityCheck.created_at.desc(), DataQualityCheck.id.desc())
                .limit(limit)
            )
        )

    def list_retryable_failed_jobs(
        self,
        *,
        provider: str,
        api_names: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[DataSyncJob]:
        statement = (
            select(DataSyncJob)
            .where(
                DataSyncJob.provider == provider,
                DataSyncJob.status.in_(RETRYABLE_FAILED_STATUSES),
            )
            .order_by(DataSyncJob.updated_at.desc(), DataSyncJob.api_name)
        )
        if api_names is not None:
            statement = statement.where(DataSyncJob.api_name.in_(api_names))
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement))

    def start_run(
        self,
        job: DataSyncJob,
        *,
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> DataSyncRun:
        job.status = "running"
        job.error_message = None
        run = DataSyncRun(
            job_id=job.id,
            status="running",
            window_start=window_start,
            window_end=window_end,
            rows_fetched=0,
            rows_upserted=0,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def mark_success(
        self,
        job: DataSyncJob,
        run: DataSyncRun,
        *,
        rows_fetched: int,
        rows_upserted: int,
        cursor_value: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        job.status = "success"
        job.error_message = None
        job.last_success_at = now
        if cursor_value is not None:
            job.cursor_value = cursor_value

        run.status = "success"
        run.rows_fetched = rows_fetched
        run.rows_upserted = rows_upserted
        run.finished_at = now

    def mark_failure(self, job: DataSyncJob, run: DataSyncRun, *, error_message: str) -> None:
        now = datetime.now(UTC)
        job.status = "failed"
        job.error_message = error_message

        run.status = "failed"
        run.error_message = error_message
        run.finished_at = now

    def mark_blocked(self, job: DataSyncJob, run: DataSyncRun, *, error_message: str) -> None:
        now = datetime.now(UTC)
        job.status = BLOCKED_INSUFFICIENT_POINTS_STATUS
        job.error_message = error_message

        run.status = BLOCKED_INSUFFICIENT_POINTS_STATUS
        run.error_message = error_message
        run.finished_at = now

    def add_quality_check(
        self,
        run: DataSyncRun,
        *,
        check_name: str,
        status: str,
        severity: str,
        message: str | None = None,
        observed_value: str | None = None,
    ) -> DataQualityCheck:
        check = DataQualityCheck(
            run_id=run.id,
            check_name=check_name,
            status=status,
            severity=severity,
            message=message,
            observed_value=_truncate_observed_value(observed_value),
        )
        self.session.add(check)
        self.session.flush()
        return check
