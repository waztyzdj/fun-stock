from datetime import date
from typing import Annotated, cast

import typer

from app.adapters.tushare.registry import TUSHARE_API_SPECS_BY_NAME
from app.core.db import SessionLocal
from app.engines.data_sync.tushare.market_data_sync import DEFAULT_START_DATE
from app.engines.data_sync.tushare.scheduler import (
    DEFAULT_TS_CODE,
    TushareSyncScheduler,
)
from app.models.data_sync import DataQualityCheck, DataSyncJob, DataSyncRun
from app.repositories.data_sync import DataSyncRepository
from app.services.data_completeness import CompletenessLayer, CoreMarketCompletenessService
from app.services.data_repair import CoreMarketDataRepairService

cli = typer.Typer(help="Run planned Tushare synchronization tasks.")
PROVIDER = "tushare"


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


@cli.command("run-once")
def run_once(
    run_date: Annotated[
        str | None,
        typer.Option(help="Scheduler run date, YYYY-MM-DD. Defaults to today."),
    ] = None,
    api: Annotated[
        list[str] | None,
        typer.Option(help="Only run selected API. Repeat for multiple APIs."),
    ] = None,
    max_items: Annotated[
        int | None,
        typer.Option(help="Maximum due plan items to execute."),
    ] = None,
    ts_code: Annotated[
        str,
        typer.Option(help="Default stock code for stock-scoped APIs."),
    ] = DEFAULT_TS_CODE,
    dry_run: Annotated[
        bool,
        typer.Option(help="Preview due work without calling Tushare."),
    ] = False,
    include_manual: Annotated[
        bool,
        typer.Option(help="Include manual realtime/minute APIs."),
    ] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option(help="Continue remaining plans after a failure."),
    ] = True,
) -> None:
    api_names = set(api or [])
    unknown_api_names = sorted(api_names - set(TUSHARE_API_SPECS_BY_NAME))
    if unknown_api_names:
        raise typer.BadParameter(f"Unsupported Tushare APIs: {', '.join(unknown_api_names)}")

    with SessionLocal() as session:
        result = TushareSyncScheduler(session, ts_code=ts_code).run_once(
            run_date=parse_date(run_date) or date.today(),
            max_items=max_items,
            dry_run=dry_run,
            continue_on_error=continue_on_error,
            include_manual=include_manual,
            api_names=api_names or None,
        )

    for item in result.items:
        typer.echo(
            " ".join(
                [
                    item.status.upper(),
                    f"api={item.window.api_name}",
                    f"schedule={item.window.schedule}",
                    f"reason={item.window.reason}",
                    f"trade_date={item.window.trade_date}",
                    f"start_date={item.window.start_date}",
                    f"end_date={item.window.end_date}",
                    f"month={item.window.month}",
                    f"rows_fetched={item.rows_fetched}",
                    f"rows_upserted={item.rows_upserted}",
                    f"error={item.error_message}",
                ]
            )
        )

    typer.echo(
        "Tushare scheduler finished: "
        f"success={result.successes}, "
        f"failed={result.failures}, "
        f"blocked={result.blocked}, "
        f"skipped={result.skipped}, "
        f"rows_fetched={result.rows_fetched}, "
        f"rows_upserted={result.rows_upserted}"
    )


@cli.command("alerts")
def alerts(
    limit: Annotated[
        int,
        typer.Option(help="Maximum rows per alert section."),
    ] = 10,
) -> None:
    with SessionLocal() as session:
        repository = DataSyncRepository(session)
        problem_runs = repository.list_recent_problem_runs(provider=PROVIDER, limit=limit)
        blocked_jobs = repository.list_blocked_jobs(provider=PROVIDER, limit=limit)
        quality_alerts = repository.list_recent_quality_alerts(provider=PROVIDER, limit=limit)

    typer.echo("== 最近失败或阻塞的同步记录 ==")
    if problem_runs:
        for run in problem_runs:
            typer.echo(_format_problem_run(run))
    else:
        typer.echo("暂无记录")

    typer.echo("== 当前需要人工处理的阻塞接口 ==")
    if blocked_jobs:
        for job in blocked_jobs:
            typer.echo(_format_blocked_job(job))
    else:
        typer.echo("暂无记录")

    typer.echo("== 最近数据质量告警 ==")
    if quality_alerts:
        for check in quality_alerts:
            typer.echo(_format_quality_alert(check))
    else:
        typer.echo("暂无记录")


@cli.command("retry-failed")
def retry_failed(
    run_date: Annotated[
        str | None,
        typer.Option(help="Scheduler retry date, YYYY-MM-DD. Defaults to today."),
    ] = None,
    api: Annotated[
        list[str] | None,
        typer.Option(help="Only retry selected failed API. Repeat for multiple APIs."),
    ] = None,
    max_items: Annotated[
        int | None,
        typer.Option(help="Maximum retryable failed jobs to execute."),
    ] = None,
    ts_code: Annotated[
        str,
        typer.Option(help="Default stock code for stock-scoped APIs."),
    ] = DEFAULT_TS_CODE,
    dry_run: Annotated[
        bool,
        typer.Option(help="Preview retry candidates without calling Tushare."),
    ] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option(help="Continue remaining retries after a failure."),
    ] = True,
) -> None:
    api_names = set(api or [])
    unknown_api_names = sorted(api_names - set(TUSHARE_API_SPECS_BY_NAME))
    if unknown_api_names:
        raise typer.BadParameter(f"Unsupported Tushare APIs: {', '.join(unknown_api_names)}")

    with SessionLocal() as session:
        repository = DataSyncRepository(session)
        jobs = repository.list_retryable_failed_jobs(
            provider=PROVIDER,
            api_names=sorted(api_names) if api_names else None,
            limit=max_items,
        )
        retry_api_names = {job.api_name for job in jobs}

        if not retry_api_names:
            typer.echo("No retryable failed Tushare jobs found.")
            return

        typer.echo("Retryable failed Tushare jobs: " + ", ".join(sorted(retry_api_names)))
        result = TushareSyncScheduler(session, ts_code=ts_code).run_once(
            run_date=parse_date(run_date) or date.today(),
            max_items=max_items,
            dry_run=dry_run,
            continue_on_error=continue_on_error,
            include_manual=True,
            api_names=retry_api_names,
            force_selected=True,
        )

    for item in result.items:
        typer.echo(
            " ".join(
                [
                    item.status.upper(),
                    f"api={item.window.api_name}",
                    f"reason={item.window.reason}",
                    f"trade_date={item.window.trade_date}",
                    f"start_date={item.window.start_date}",
                    f"end_date={item.window.end_date}",
                    f"month={item.window.month}",
                    f"rows_fetched={item.rows_fetched}",
                    f"rows_upserted={item.rows_upserted}",
                    f"error={item.error_message}",
                ]
            )
        )

    typer.echo(
        "Tushare retry finished: "
        f"success={result.successes}, "
        f"failed={result.failures}, "
        f"blocked={result.blocked}, "
        f"skipped={result.skipped}, "
        f"rows_fetched={result.rows_fetched}, "
        f"rows_upserted={result.rows_upserted}"
    )


@cli.command("plan")
def plan(
    run_date: Annotated[
        str | None,
        typer.Option(help="Scheduler run date, YYYY-MM-DD. Defaults to today."),
    ] = None,
    api: Annotated[
        list[str] | None,
        typer.Option(help="Only preview selected API. Repeat for multiple APIs."),
    ] = None,
    include_manual: Annotated[
        bool,
        typer.Option(help="Include manual realtime/minute APIs."),
    ] = False,
) -> None:
    api_names = set(api or [])
    unknown_api_names = sorted(api_names - set(TUSHARE_API_SPECS_BY_NAME))
    if unknown_api_names:
        raise typer.BadParameter(f"Unsupported Tushare APIs: {', '.join(unknown_api_names)}")

    with SessionLocal() as session:
        windows = TushareSyncScheduler(session).plan_due_windows(
            run_date=parse_date(run_date) or date.today(),
            include_manual=include_manual,
            api_names=api_names or None,
        )

    for window in windows:
        typer.echo(
            " ".join(
                [
                    f"api={window.api_name}",
                    f"schedule={window.schedule}",
                    f"reason={window.reason}",
                    f"trade_date={window.trade_date}",
                    f"start_date={window.start_date}",
                    f"end_date={window.end_date}",
                    f"month={window.month}",
                ]
            )
        )
    typer.echo(f"Tushare scheduler due plans: {len(windows)}")


@cli.command("completeness")
def completeness(
    start_date: Annotated[
        str | None,
        typer.Option(help="Completeness scan start date, YYYY-MM-DD. Defaults to 2000-01-01."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Completeness scan end date, YYYY-MM-DD. Defaults to today."),
    ] = None,
    missing_limit: Annotated[
        int,
        typer.Option(help="Maximum missing dates to print per table."),
    ] = 20,
    layer: Annotated[
        str,
        typer.Option(help="Completeness layer: app or raw."),
    ] = "app",
) -> None:
    with SessionLocal() as session:
        report = CoreMarketCompletenessService(session).scan(
            start_date=parse_date(start_date) or DEFAULT_START_DATE,
            end_date=parse_date(end_date) or date.today(),
            layer=_parse_completeness_layer(layer),
            missing_limit=missing_limit,
        )

    typer.echo(
        "CORE_COMPLETENESS "
        f"layer={report.layer} "
        f"exchange={report.exchange} "
        f"start_date={report.start_date} "
        f"end_date={report.end_date} "
        f"total_missing_trade_days={report.total_missing_trade_days}"
    )
    for table in report.tables:
        missing_dates = ",".join(day.strftime("%Y%m%d") for day in table.missing_dates) or "-"
        repair_ranges = (
            ",".join(
                f"{item.start_date.strftime('%Y%m%d')}-{item.end_date.strftime('%Y%m%d')}"
                for item in table.repair_ranges[:10]
            )
            or "-"
        )
        typer.echo(
            "TABLE "
            f"api={table.api_name} "
            f"expected={table.expected_trade_days} "
            f"present={table.present_trade_days} "
            f"missing={table.missing_trade_days} "
            f"latest_present={table.latest_present_date} "
            f"ratio={table.completeness_ratio:.4f} "
            f"missing_dates={missing_dates} "
            f"repair_ranges={repair_ranges}"
        )


@cli.command("repair-core")
def repair_core(
    start_date: Annotated[
        str,
        typer.Option(help="Repair start date, YYYY-MM-DD."),
    ],
    end_date: Annotated[
        str,
        typer.Option(help="Repair end date, YYYY-MM-DD."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(help="Preview repair plan without writing app tables."),
    ] = True,
    fix_batches: Annotated[
        bool,
        typer.Option(help="Also fix failed or stale running backfill batch statuses."),
    ] = True,
) -> None:
    with SessionLocal() as session:
        service = CoreMarketDataRepairService(session)
        parsed_start_date = date.fromisoformat(start_date)
        parsed_end_date = date.fromisoformat(end_date)
        if fix_batches:
            summary = service.repair_and_fix_batches(
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                dry_run=dry_run,
            )
            result = summary.data_repair
            batch_fix = summary.batch_fix
        else:
            result = service.repair(
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                dry_run=dry_run,
            )
            batch_fix = None

    typer.echo(
        "CORE_REPAIR "
        f"start_date={result.plan.start_date} "
        f"end_date={result.plan.end_date} "
        f"missing_trade_days={result.plan.missing_trade_days} "
        f"executed={result.executed} "
        f"daily_quotes={result.daily_quotes} "
        f"daily_indicators={result.daily_indicators} "
        f"adj_factors={result.adj_factors}"
    )
    for range_start, range_end, days in result.plan.repair_ranges[:20]:
        typer.echo(f"REPAIR_RANGE start_date={range_start} end_date={range_end} days={days}")
    if batch_fix is not None:
        typer.echo(
            "BACKFILL_BATCH_FIX "
            f"scanned={batch_fix.scanned_batches} "
            f"fixed={batch_fix.fixed_batches} "
            f"still_failed={batch_fix.still_failed_batches} "
            f"stale_running={batch_fix.stale_running_batches}"
        )


@cli.command("fix-backfill-batches")
def fix_backfill_batches(
    start_date: Annotated[
        str,
        typer.Option(help="Batch scan start date, YYYY-MM-DD."),
    ],
    end_date: Annotated[
        str,
        typer.Option(help="Batch scan end date, YYYY-MM-DD."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(help="Preview fixes without updating batch status."),
    ] = True,
    stale_after_minutes: Annotated[
        int,
        typer.Option(help="Treat running batches older than this as stale."),
    ] = 180,
) -> None:
    with SessionLocal() as session:
        result = CoreMarketDataRepairService(session).fix_backfill_batches(
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            dry_run=dry_run,
            stale_after_minutes=stale_after_minutes,
        )
    typer.echo(
        "BACKFILL_BATCH_FIX "
        f"scanned={result.scanned_batches} "
        f"fixed={result.fixed_batches} "
        f"still_failed={result.still_failed_batches} "
        f"stale_running={result.stale_running_batches} "
        f"executed={not dry_run}"
    )


def _format_problem_run(run: DataSyncRun) -> str:
    return " ".join(
        [
            f"status={run.status}",
            f"api={run.job.api_name}",
            f"run_id={run.id}",
            f"window_start={run.window_start}",
            f"window_end={run.window_end}",
            f"started_at={run.started_at}",
            f"finished_at={run.finished_at}",
            f"error={_single_line(run.error_message)}",
        ]
    )


def _format_blocked_job(job: DataSyncJob) -> str:
    return " ".join(
        [
            f"status={job.status}",
            f"api={job.api_name}",
            f"cursor={job.cursor_value}",
            f"last_success_at={job.last_success_at}",
            f"updated_at={job.updated_at}",
            f"error={_single_line(job.error_message)}",
        ]
    )


def _format_quality_alert(check: DataQualityCheck) -> str:
    return " ".join(
        [
            f"status={check.status}",
            f"severity={check.severity}",
            f"api={check.run.job.api_name}",
            f"run_id={check.run_id}",
            f"check={check.check_name}",
            f"observed={check.observed_value}",
            f"created_at={check.created_at}",
            f"message={_single_line(check.message)}",
        ]
    )


def _single_line(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().splitlines()[0] if value.strip() else None


def _parse_completeness_layer(value: str) -> CompletenessLayer:
    if value not in {"app", "raw"}:
        raise typer.BadParameter("layer must be app or raw.")
    return cast(CompletenessLayer, value)


if __name__ == "__main__":
    cli()
