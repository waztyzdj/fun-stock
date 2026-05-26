from datetime import date
from time import sleep
from typing import Annotated

import typer
from redis import Redis

from app.adapters.tushare import TushareInsufficientPointsError
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.engines.data_sync.tushare.market_data_sync import TushareMarketDataSyncService
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
    while True:
        with SessionLocal() as session:
            service = TushareMarketDataSyncService(session, normalize=False)
            plan = service.plan_daily_quote_backfill(
                end_date=end_date,
                max_trade_days=batch_trade_days,
            )
            if not plan.trade_dates:
                _echo_final_status()
                typer.echo(f"DONE quote backfill completed through {end_date.isoformat()}.")
                return
            batch_index += 1
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
                typer.echo(f"BLOCKED insufficient points or permission: {str(exc).splitlines()[0]}")
                _echo_final_status()
                raise typer.Exit(code=2) from exc
            except Exception as exc:
                consecutive_failures += 1
                typer.echo(
                    "FAILED "
                    f"batch={batch_index} "
                    f"consecutive_failures={consecutive_failures} "
                    f"error={str(exc).splitlines()[0]}"
                )
                if consecutive_failures >= max_consecutive_failures:
                    _echo_final_status()
                    raise
                sleep(between_batch_sleep_seconds)
                continue

        consecutive_failures = 0
        typer.echo(
            "SUCCESS "
            f"batch={batch_index} "
            f"windows={len(summaries)} "
            f"rows_fetched={sum(summary.rows_fetched for summary in summaries)} "
            f"rows_upserted={sum(summary.rows_upserted for summary in summaries)}"
        )
        sleep(between_batch_sleep_seconds)


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


if __name__ == "__main__":
    cli()
