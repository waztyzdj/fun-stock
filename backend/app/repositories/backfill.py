from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.backfill import BackfillBatch, BackfillJob

BACKFILL_RUNNING_STATUS = "running"
BACKFILL_SUCCESS_STATUS = "success"
BACKFILL_FAILED_STATUS = "failed"
BACKFILL_BLOCKED_STATUS = "blocked_insufficient_points"


class BackfillRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        provider: str,
        task_type: str,
        name: str,
        start_date: date | None,
        end_date: date | None,
        cursor_date: date | None = None,
    ) -> BackfillJob:
        job = BackfillJob(
            provider=provider,
            task_type=task_type,
            name=name,
            status=BACKFILL_RUNNING_STATUS,
            start_date=start_date,
            end_date=end_date,
            cursor_date=cursor_date,
            total_batches=0,
            succeeded_batches=0,
            failed_batches=0,
            blocked_batches=0,
            total_windows=0,
            rows_fetched=0,
            rows_upserted=0,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_job(self, job_id: int) -> BackfillJob | None:
        return self.session.get(BackfillJob, job_id)

    def list_recent_jobs(self, *, provider: str, limit: int = 20) -> list[BackfillJob]:
        return list(
            self.session.scalars(
                select(BackfillJob)
                .where(BackfillJob.provider == provider)
                .options(joinedload(BackfillJob.batches))
                .order_by(BackfillJob.started_at.desc(), BackfillJob.id.desc())
                .limit(limit)
            )
            .unique()
            .all()
        )

    def latest_running_job(self, *, provider: str, task_type: str) -> BackfillJob | None:
        return self.session.scalar(
            select(BackfillJob)
            .where(
                BackfillJob.provider == provider,
                BackfillJob.task_type == task_type,
                BackfillJob.status == BACKFILL_RUNNING_STATUS,
            )
            .order_by(BackfillJob.started_at.desc(), BackfillJob.id.desc())
            .limit(1)
        )

    def mark_stale_running_batches_failed(
        self,
        *,
        provider: str,
        before: datetime,
        error_message: str,
    ) -> int:
        stale_batches = list(
            self.session.scalars(
                select(BackfillBatch)
                .join(BackfillBatch.job)
                .where(
                    BackfillJob.provider == provider,
                    BackfillBatch.status == BACKFILL_RUNNING_STATUS,
                    BackfillBatch.started_at < before,
                )
            )
        )
        for batch in stale_batches:
            batch.status = BACKFILL_FAILED_STATUS
            batch.error_message = error_message
            batch.finished_at = datetime.now(UTC)
        return len(stale_batches)

    def latest_succeeded_cursor_date(self, *, provider: str, task_type: str) -> date | None:
        return self.session.scalar(
            select(func.max(BackfillJob.cursor_date)).where(
                BackfillJob.provider == provider,
                BackfillJob.task_type == task_type,
                BackfillJob.status.in_([BACKFILL_RUNNING_STATUS, BACKFILL_SUCCESS_STATUS]),
            )
        )

    def start_batch(
        self,
        job: BackfillJob,
        *,
        batch_index: int,
        cursor_date: date | None,
        trade_dates: list[date],
    ) -> BackfillBatch:
        batch = BackfillBatch(
            job_id=job.id,
            batch_index=batch_index,
            status=BACKFILL_RUNNING_STATUS,
            cursor_date=cursor_date,
            start_date=trade_dates[0] if trade_dates else None,
            end_date=trade_dates[-1] if trade_dates else None,
            trade_days=len(trade_dates),
            windows=0,
            rows_fetched=0,
            rows_upserted=0,
        )
        job.total_batches += 1
        self.session.add(batch)
        self.session.flush()
        return batch

    def mark_batch_success(
        self,
        job: BackfillJob,
        batch: BackfillBatch,
        *,
        windows: int,
        rows_fetched: int,
        rows_upserted: int,
        cursor_date: date | None,
    ) -> None:
        now = datetime.now(UTC)
        batch.status = BACKFILL_SUCCESS_STATUS
        batch.windows = windows
        batch.rows_fetched = rows_fetched
        batch.rows_upserted = rows_upserted
        batch.finished_at = now

        job.status = BACKFILL_RUNNING_STATUS
        job.succeeded_batches += 1
        job.total_windows += windows
        job.rows_fetched += rows_fetched
        job.rows_upserted += rows_upserted
        job.cursor_date = cursor_date
        job.error_message = None

    def mark_batch_failure(
        self,
        job: BackfillJob,
        batch: BackfillBatch,
        *,
        error_message: str,
        blocked: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        batch.status = BACKFILL_BLOCKED_STATUS if blocked else BACKFILL_FAILED_STATUS
        batch.error_message = error_message
        batch.finished_at = now

        if blocked:
            job.blocked_batches += 1
        else:
            job.failed_batches += 1
        job.status = batch.status
        job.error_message = error_message

    def mark_job_success(self, job: BackfillJob) -> None:
        job.status = BACKFILL_SUCCESS_STATUS
        job.error_message = None
        job.finished_at = datetime.now(UTC)

    def mark_job_failure(
        self,
        job: BackfillJob,
        *,
        error_message: str,
        blocked: bool = False,
    ) -> None:
        job.status = BACKFILL_BLOCKED_STATUS if blocked else BACKFILL_FAILED_STATUS
        job.error_message = error_message
        job.finished_at = datetime.now(UTC)
