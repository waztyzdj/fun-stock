from datetime import date
from typing import Annotated

import typer

from app.adapters.tushare.registry import TUSHARE_API_SPECS, TUSHARE_API_SPECS_BY_NAME
from app.core.db import SessionLocal
from app.engines.data_sync.tushare import TushareMarketDataSyncService
from app.engines.data_sync.tushare.market_data_sync import FINANCE_TABLES

cli = typer.Typer(help="Fetch market data from Tushare into raw and application tables.")
DEFAULT_BENCHMARK_INDEX_CODES = ("000300.SH", "000905.SH", "000852.SH", "000985.CSI")


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def default_trade_date() -> date:
    return date(2026, 5, 22)


def concise_error_message(exc: Exception) -> str:
    original_error = getattr(exc, "orig", None)
    message = str(original_error or exc).strip()
    return message.splitlines()[0] if message else exc.__class__.__name__


@cli.command()
def all(
    start_date: Annotated[
        str | None,
        typer.Option(help="Optional inclusive start date, YYYY-MM-DD."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Optional inclusive end date, YYYY-MM-DD."),
    ] = None,
    finance_lookback_days: Annotated[
        int,
        typer.Option(help="Finance announcement lookback window when start-date is omitted."),
    ] = 90,
    normalize: Annotated[
        bool,
        typer.Option(help="Normalize supported raw Tushare data into app tables after sync."),
    ] = True,
) -> None:
    with SessionLocal() as session:
        result = TushareMarketDataSyncService(session, normalize=normalize).sync_all(
            start_date=parse_date(start_date),
            end_date=parse_date(end_date),
            finance_lookback_days=finance_lookback_days,
        )

    typer.echo(
        "Synced Tushare market data: "
        f"windows={len(result.summaries)}, "
        f"rows_fetched={result.rows_fetched}, "
        f"rows_upserted={result.rows_upserted}"
    )


@cli.command()
def basic(
    start_date: Annotated[
        str,
        typer.Option(help="Inclusive calendar start date, YYYY-MM-DD."),
    ] = "2000-01-01",
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive calendar end date, YYYY-MM-DD."),
    ] = None,
) -> None:
    with SessionLocal() as session:
        summary = TushareMarketDataSyncService(session, normalize=False).sync_basic_data(
            start_date=parse_date(start_date) or date(2000, 1, 1),
            end_date=parse_date(end_date) or date.today(),
        )

    typer.echo(
        "Synced Tushare basic data: "
        f"rows_fetched={summary.rows_fetched}, "
        f"rows_upserted={summary.rows_upserted}"
    )


@cli.command()
def quotes(
    start_date: Annotated[
        str | None,
        typer.Option(help="Optional backfill floor date, YYYY-MM-DD."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive quote end date, YYYY-MM-DD."),
    ] = None,
    max_trade_days: Annotated[
        int,
        typer.Option(help="Maximum open trading days to process in this run."),
    ] = 5,
    sleep_seconds: Annotated[
        float,
        typer.Option(help="Delay between Tushare daily API calls."),
    ] = 0,
    normalize: Annotated[
        bool,
        typer.Option(help="Normalize each fetched trade date into app quote tables."),
    ] = True,
) -> None:
    with SessionLocal() as session:
        summaries = TushareMarketDataSyncService(session, normalize=False).sync_quote_data(
            start_date=parse_date(start_date),
            end_date=parse_date(end_date) or date.today(),
            max_trade_days=max_trade_days,
            sleep_seconds=sleep_seconds,
            normalize=normalize,
        )

    typer.echo(
        "Synced Tushare quote backfill batch: "
        f"windows={len(summaries)}, "
        f"rows_fetched={sum(summary.rows_fetched for summary in summaries)}, "
        f"rows_upserted={sum(summary.rows_upserted for summary in summaries)}"
    )


@cli.command("quotes-plan")
def quotes_plan(
    start_date: Annotated[
        str | None,
        typer.Option(help="Optional backfill floor date, YYYY-MM-DD."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive quote end date, YYYY-MM-DD."),
    ] = None,
    max_trade_days: Annotated[
        int,
        typer.Option(help="Maximum open trading days to include in the preview."),
    ] = 5,
) -> None:
    with SessionLocal() as session:
        plan = TushareMarketDataSyncService(session, normalize=False).plan_daily_quote_backfill(
            start_date=parse_date(start_date),
            end_date=parse_date(end_date) or date.today(),
            max_trade_days=max_trade_days,
        )

    typer.echo(
        "Planned Tushare quote backfill batch: "
        f"cursor_date={plan.cursor_date.isoformat()}, "
        f"end_date={plan.end_date.isoformat()}, "
        f"trade_days={len(plan.trade_dates)}, "
        f"next_trade_date={plan.next_trade_date.isoformat() if plan.next_trade_date else 'none'}"
    )


@cli.command("quotes-window")
def quotes_window(
    start_date: Annotated[
        str,
        typer.Option(help="Inclusive quote start date, YYYY-MM-DD."),
    ],
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive quote end date, YYYY-MM-DD."),
    ] = None,
) -> None:
    parsed_start_date = parse_date(start_date)
    if parsed_start_date is None:
        raise typer.BadParameter("start-date is required.")

    with SessionLocal() as session:
        summaries = TushareMarketDataSyncService(session, normalize=False).sync_quote_data_window(
            start_date=parsed_start_date,
            end_date=parse_date(end_date) or parsed_start_date,
        )

    typer.echo(
        "Synced Tushare quote window: "
        f"windows={len(summaries)}, "
        f"rows_fetched={sum(summary.rows_fetched for summary in summaries)}, "
        f"rows_upserted={sum(summary.rows_upserted for summary in summaries)}"
    )


@cli.command("benchmark-indexes")
def benchmark_indexes(
    start_date: Annotated[
        str,
        typer.Option(help="Inclusive index quote start date, YYYY-MM-DD."),
    ] = "2020-01-01",
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive index quote end date, YYYY-MM-DD."),
    ] = None,
    ts_code: Annotated[
        list[str] | None,
        typer.Option(help="Benchmark index code. Repeat for multiple indexes."),
    ] = None,
    normalize: Annotated[
        bool,
        typer.Option(help="Normalize fetched index quotes into app.index_daily_quotes."),
    ] = True,
) -> None:
    parsed_start_date = parse_date(start_date)
    if parsed_start_date is None:
        raise typer.BadParameter("start-date is required.")
    index_codes = tuple(ts_code or DEFAULT_BENCHMARK_INDEX_CODES)

    with SessionLocal() as session:
        summaries = TushareMarketDataSyncService(session, normalize=False).sync_index_daily_window(
            ts_codes=index_codes,
            start_date=parsed_start_date,
            end_date=parse_date(end_date) or date.today(),
            normalize=normalize,
        )

    typer.echo(
        "Synced Tushare benchmark indexes: "
        f"indexes={len(index_codes)}, "
        f"windows={len(summaries)}, "
        f"rows_fetched={sum(summary.rows_fetched for summary in summaries)}, "
        f"rows_upserted={sum(summary.rows_upserted for summary in summaries)}"
    )


@cli.command()
def finance(
    start_date: Annotated[
        str,
        typer.Option(help="Inclusive announcement start date, YYYY-MM-DD."),
    ],
    ts_code: Annotated[
        str,
        typer.Option(help="Tushare stock code for finance APIs, e.g. 000001.SZ."),
    ] = "000001.SZ",
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive announcement end date, YYYY-MM-DD."),
    ] = None,
    sleep_seconds: Annotated[
        float,
        typer.Option(help="Delay between finance API calls. Some VIP APIs allow 1 call/minute."),
    ] = 65,
    api: Annotated[
        list[str] | None,
        typer.Option(help="Finance API to sync. Repeat for multiple APIs."),
    ] = None,
) -> None:
    parsed_start_date = parse_date(start_date)
    if parsed_start_date is None:
        raise typer.BadParameter("start-date is required.")

    with SessionLocal() as session:
        service = TushareMarketDataSyncService(session, normalize=False)
        summaries = service.sync_finance_data_for_stock(
            ts_code=ts_code,
            start_date=parsed_start_date,
            end_date=parse_date(end_date) or date.today(),
            sleep_seconds=sleep_seconds,
            api_names=tuple(api or FINANCE_TABLES),
        )

    typer.echo(
        "Synced Tushare finance data: "
        f"ts_code={ts_code}, "
        f"windows={len(summaries)}, "
        f"rows_fetched={sum(summary.rows_fetched for summary in summaries)}, "
        f"rows_upserted={sum(summary.rows_upserted for summary in summaries)}"
    )


@cli.command("api-probe")
def api_probe(
    api_name: Annotated[
        str,
        typer.Argument(help="Tushare API name registered in the local coverage registry."),
    ],
    trade_date: Annotated[
        str | None,
        typer.Option(help="Trade date, YYYY-MM-DD."),
    ] = None,
    start_date: Annotated[
        str | None,
        typer.Option(help="Window start date, YYYY-MM-DD."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Window end date, YYYY-MM-DD."),
    ] = None,
    ts_code: Annotated[
        str | None,
        typer.Option(help="Tushare stock code, e.g. 000001.SZ."),
    ] = "000001.SZ",
    month: Annotated[
        str | None,
        typer.Option(help="Month value for monthly APIs, YYYYMM."),
    ] = "202605",
) -> None:
    if api_name not in TUSHARE_API_SPECS_BY_NAME:
        raise typer.BadParameter(f"Unsupported Tushare API: {api_name}")

    with SessionLocal() as session:
        summary = TushareMarketDataSyncService(session, normalize=False).sync_registered_api(
            api_name=api_name,
            trade_date=parse_date(trade_date) or default_trade_date(),
            start_date=parse_date(start_date) or date(2026, 5, 1),
            end_date=parse_date(end_date) or date(2026, 5, 24),
            ts_code=ts_code,
            month=month,
        )

    typer.echo(
        "Probed Tushare API: "
        f"api={summary.api_name}, "
        f"rows_fetched={summary.rows_fetched}, "
        f"rows_upserted={summary.rows_upserted}"
    )


@cli.command("api-probe-batch")
def api_probe_batch(
    api: Annotated[
        list[str] | None,
        typer.Option(help="Tushare API to probe. Repeat for multiple APIs. Omit to probe all."),
    ] = None,
    trade_date: Annotated[
        str | None,
        typer.Option(help="Trade date, YYYY-MM-DD."),
    ] = None,
    start_date: Annotated[
        str | None,
        typer.Option(help="Window start date, YYYY-MM-DD."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Window end date, YYYY-MM-DD."),
    ] = None,
    ts_code: Annotated[
        str | None,
        typer.Option(help="Tushare stock code, e.g. 000001.SZ."),
    ] = "000001.SZ",
    month: Annotated[
        str | None,
        typer.Option(help="Month value for monthly APIs, YYYYMM."),
    ] = "202605",
    continue_on_error: Annotated[
        bool,
        typer.Option(help="Continue probing remaining APIs after a failure."),
    ] = True,
) -> None:
    api_names = list(api) if api else [spec.api_name for spec in TUSHARE_API_SPECS]
    unknown_api_names = sorted(set(api_names) - set(TUSHARE_API_SPECS_BY_NAME))
    if unknown_api_names:
        raise typer.BadParameter(f"Unsupported Tushare APIs: {', '.join(unknown_api_names)}")

    parsed_trade_date = parse_date(trade_date) or default_trade_date()
    parsed_start_date = parse_date(start_date) or date(2026, 5, 1)
    parsed_end_date = parse_date(end_date) or date(2026, 5, 24)

    successes = 0
    failures = 0
    with SessionLocal() as session:
        service = TushareMarketDataSyncService(session, normalize=False)
        for api_name in api_names:
            try:
                summary = service.sync_registered_api(
                    api_name=api_name,
                    trade_date=parsed_trade_date,
                    start_date=parsed_start_date,
                    end_date=parsed_end_date,
                    ts_code=ts_code,
                    month=month,
                )
            except Exception as exc:
                failures += 1
                typer.echo(
                    f"FAILED api={api_name}, error={concise_error_message(exc)}",
                    err=True,
                )
                if not continue_on_error:
                    raise
            else:
                successes += 1
                typer.echo(
                    "OK "
                    f"api={summary.api_name}, "
                    f"rows_fetched={summary.rows_fetched}, "
                    f"rows_upserted={summary.rows_upserted}"
                )

    typer.echo(f"Batch probe finished: success={successes}, failed={failures}")


if __name__ == "__main__":
    cli()
