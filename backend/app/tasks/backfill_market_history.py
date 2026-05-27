from datetime import date
from time import sleep
from typing import Annotated

import typer
from redis import Redis

from app.adapters.tushare import TushareInsufficientPointsError
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.engines.data_sync.tushare.market_data_sync import (
    DEFAULT_START_DATE,
    TushareMarketDataSyncService,
)
from app.models.backfill import BackfillBatch
from app.repositories.backfill import BackfillRepository
from app.repositories.data_sync import DataSyncRepository
from app.services.distributed_lock import RedisDistributedLock
from app.tasks.sync_tushare_scheduler import PROVIDER

cli = typer.Typer(help="Run unattended historical market data backfill.")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


@cli.command("quotes")
def quotes(
    end_date: Annotated[
        str,
        typer.Option(help="Inclusive backfill end date, YYYY-MM-DD."),
    ],
    batch_trade_days: Annotated[
        int,
        typer.Option(help="Maximum trade days per batch."),
    ] = 100,
    sleep_seconds: Annotated[
        float,
        typer.Option(help="Sleep seconds between trade days inside a batch."),
    ] = 5,
    between_batch_sleep_seconds: Annotated[
        float,
        typer.Option(help="Sleep seconds between completed batches."),
    ] = 30,
    max_consecutive_failures: Annotated[
        int,
        typer.Option(help="Stop after this many consecutive non-blocked failures."),
    ] = 5,
) -> None:
    if batch_trade_days <= 0:
        raise typer.BadParameter("batch-trade-days must be greater than 0.")
    parsed_end_date = parse_date(end_date)

    settings = get_settings()
    lock = RedisDistributedLock(Redis.from_url(settings.redis_url, decode_responses=True))
    with lock.acquire("history-backfill", ttl_seconds=24 * 60 * 60) as backfill_acquired:
        if not backfill_acquired:
            typer.echo("SKIPPED another historical backfill task is already running.")
            raise typer.Exit(code=0)
        with lock.acquire("due-small-batch", ttl_seconds=24 * 60 * 60) as sync_acquired:
            if not sync_acquired:
                typer.echo("SKIPPED scheduler sync lock is already held.")
                raise typer.Exit(code=0)
            _run_quotes_backfill(
                end_date=parsed_end_date,
                batch_trade_days=batch_trade_days,
                sleep_seconds=sleep_seconds,
                between_batch_sleep_seconds=between_batch_sleep_seconds,
                max_consecutive_failures=max_consecutive_failures,
            )


def _run_quotes_backfill(
    *,
    end_date: date,
    batch_trade_days: int,
    sleep_seconds: float,
    between_batch_sleep_seconds: float,
    max_consecutive_failures: int,
) -> None:
    batch_index = 0
    consecutive_failures = 0
    job_id = _create_backfill_job(end_date=end_date)
    while True:
        with SessionLocal() as session:
            service = TushareMarketDataSyncService(session, normalize=False)
            plan = service.plan_daily_quote_backfill(
                end_date=end_date,
                max_trade_days=batch_trade_days,
            )
            if not plan.trade_dates:
                _mark_backfill_job_success(job_id)
                _echo_final_status()
                typer.echo(f"DONE quote backfill completed through {end_date.isoformat()}.")
                return
            batch_index += 1
            batch_id = _start_backfill_batch(
                job_id=job_id,
                batch_index=batch_index,
                cursor_date=plan.cursor_date,
                trade_dates=plan.trade_dates,
            )
            typer.echo(
                "START "
                f"batch={batch_index} "
                f"cursor={plan.cursor_date.isoformat()} "
                f"trade_days={len(plan.trade_dates)} "
                f"next={plan.next_trade_date.isoformat() if plan.next_trade_date else 'none'}"
            )
            try:
                summaries = service.sync_quote_data(
                    end_date=end_date,
                    max_trade_days=batch_trade_days,
                    sleep_seconds=sleep_seconds,
                    normalize=True,
                )
            except TushareInsufficientPointsError as exc:
                error_message = _single_line(str(exc))
                _mark_backfill_batch_failure(
                    job_id=job_id,
                    batch_id=batch_id,
                    error_message=error_message,
                    blocked=True,
                )
                _mark_backfill_job_failure(
                    job_id=job_id,
                    error_message=error_message,
                    blocked=True,
                )
                typer.echo(f"BLOCKED insufficient points or permission: {error_message}")
                _echo_final_status()
                raise typer.Exit(code=2) from exc
            except Exception as exc:
                consecutive_failures += 1
                error_message = _single_line(str(exc))
                _mark_backfill_batch_failure(
                    job_id=job_id,
                    batch_id=batch_id,
                    error_message=error_message,
                )
                typer.echo(
                    "FAILED "
                    f"batch={batch_index} "
                    f"consecutive_failures={consecutive_failures} "
                    f"error={error_message}"
                )
                if consecutive_failures >= max_consecutive_failures:
                    _mark_backfill_job_failure(job_id=job_id, error_message=error_message)
                    _echo_final_status()
                    raise
                sleep(between_batch_sleep_seconds)
                continue

        consecutive_failures = 0
        _mark_backfill_batch_success(
            job_id=job_id,
            batch_id=batch_id,
            windows=len(summaries),
            rows_fetched=sum(summary.rows_fetched for summary in summaries),
            rows_upserted=sum(summary.rows_upserted for summary in summaries),
            cursor_date=plan.trade_dates[-1],
        )
        typer.echo(
            "SUCCESS "
            f"batch={batch_index} "
            f"windows={len(summaries)} "
            f"rows_fetched={sum(summary.rows_fetched for summary in summaries)} "
            f"rows_upserted={sum(summary.rows_upserted for summary in summaries)}"
        )
        sleep(between_batch_sleep_seconds)


def _create_backfill_job(*, end_date: date) -> int:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.create_job(
            provider=PROVIDER,
            task_type="market_quote_history",
            name=f"日行情历史回填至 {end_date.isoformat()}",
            start_date=DEFAULT_START_DATE,
            end_date=end_date,
            cursor_date=None,
        )
        session.commit()
        return job.id


def _start_backfill_batch(
    *,
    job_id: int,
    batch_index: int,
    cursor_date: date,
    trade_dates: list[date],
) -> int:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        if job is None:
            msg = f"Backfill job {job_id} not found."
            raise RuntimeError(msg)
        batch = repository.start_batch(
            job,
            batch_index=batch_index,
            cursor_date=cursor_date,
            trade_dates=trade_dates,
        )
        session.commit()
        return batch.id


def _mark_backfill_batch_success(
    *,
    job_id: int,
    batch_id: int,
    windows: int,
    rows_fetched: int,
    rows_upserted: int,
    cursor_date: date,
) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        batch = session.get(BackfillBatch, batch_id)
        if job is None or batch is None:
            msg = f"Backfill job {job_id} or batch {batch_id} not found."
            raise RuntimeError(msg)
        repository.mark_batch_success(
            job,
            batch,
            windows=windows,
            rows_fetched=rows_fetched,
            rows_upserted=rows_upserted,
            cursor_date=cursor_date,
        )
        session.commit()


def _mark_backfill_batch_failure(
    *,
    job_id: int,
    batch_id: int,
    error_message: str,
    blocked: bool = False,
) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        batch = session.get(BackfillBatch, batch_id)
        if job is None or batch is None:
            msg = f"Backfill job {job_id} or batch {batch_id} not found."
            raise RuntimeError(msg)
        repository.mark_batch_failure(
            job,
            batch,
            error_message=error_message,
            blocked=blocked,
        )
        session.commit()


def _mark_backfill_job_success(job_id: int) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        if job is None:
            msg = f"Backfill job {job_id} not found."
            raise RuntimeError(msg)
        repository.mark_job_success(job)
        session.commit()


def _mark_backfill_job_failure(
    *,
    job_id: int,
    error_message: str,
    blocked: bool = False,
) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        if job is None:
            msg = f"Backfill job {job_id} not found."
            raise RuntimeError(msg)
        repository.mark_job_failure(job, error_message=error_message, blocked=blocked)
        session.commit()


def _echo_final_status() -> None:
    with SessionLocal() as session:
        repository = DataSyncRepository(session)
        blocked_jobs = repository.list_blocked_jobs(provider=PROVIDER, limit=100)
        retryable_jobs = repository.list_retryable_failed_jobs(provider=PROVIDER)
        jobs = repository.list_jobs(provider=PROVIDER, limit=200)
        non_success_jobs = [job for job in jobs if job.status != "success"]

    typer.echo(
        "CHECK "
        f"blocked={len(blocked_jobs)} "
        f"retryable_failed={len(retryable_jobs)} "
        f"non_success={len(non_success_jobs)}"
    )
    for job in non_success_jobs:
        typer.echo(
            "CHECK_NON_SUCCESS "
            f"api={job.api_name} "
            f"status={job.status} "
            f"cursor={job.cursor_value} "
            f"error={str(job.error_message).splitlines()[0] if job.error_message else None}"
        )


def _single_line(value: str) -> str:
    stripped = value.strip()
    return stripped.splitlines()[0] if stripped else "Unknown error"


if __name__ == "__main__":
    cli()
