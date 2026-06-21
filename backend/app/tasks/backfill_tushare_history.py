from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from time import sleep
from typing import Annotated

import typer
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.tushare import TushareInsufficientPointsError, TushareRateLimitError
from app.adapters.tushare.registry import (
    TUSHARE_API_SPECS_BY_NAME,
    TushareApiParamMode,
    TushareApiSpec,
)
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.engines.data_sync.tushare.market_data_sync import (
    DEFAULT_START_DATE,
    SyncSummary,
    TushareMarketDataSyncService,
)
from app.models.backfill import BackfillBatch
from app.repositories.backfill import BackfillRepository
from app.repositories.data_sync import BLOCKED_INSUFFICIENT_POINTS_STATUS, DataSyncRepository
from app.services.distributed_lock import RedisDistributedLock
from app.tasks.sync_tushare_scheduler import PROVIDER

cli = typer.Typer(help="Run resumable historical backfill for registered Tushare APIs.")

CORE_QUOTE_APIS = frozenset({"daily", "daily_basic", "adj_factor", "index_daily"})
REALTIME_OR_MINUTE_APIS = frozenset({"rt_k", "rt_min", "rt_min_daily", "stk_mins"})
SAFE_FULL_APIS = frozenset({"stock_basic", "stock_company", "stock_st_warning", "bse_mapping"})
WEEKLY_TRADE_DATE_APIS = frozenset({"weekly", "stk_weekly_monthly", "stk_week_month_adj"})
MONTHLY_TRADE_DATE_APIS = frozenset({"monthly"})
API_HISTORY_START_DATES = {
    "ggt_daily": date(2014, 11, 17),
    "ggt_top10": date(2014, 11, 17),
    "hsgt_top10": date(2014, 11, 17),
    "stock_st": date(2007, 1, 1),
    "stk_limit": date(2010, 1, 1),
    "stk_premarket": date(2010, 1, 1),
    "suspend_d": date(2010, 1, 1),
    "weekly": date(2000, 1, 7),
    "monthly": date(2000, 1, 31),
    "stk_weekly_monthly": date(2000, 1, 7),
    "stk_week_month_adj": date(2000, 1, 7),
    "ggt_monthly": date(2014, 11, 1),
}
TS_CODE_APIS = frozenset(
    {
        "namechange",
        "stk_managers",
        "stk_rewards",
        "income",
        "balancesheet",
        "forecast",
        "express",
        "dividend",
        "fina_indicator",
        "fina_audit",
        "fina_mainbz",
        "disclosure_date",
    }
)
DEFERRED_TS_CODE_APIS = frozenset({"disclosure_date", "fina_mainbz"})
CORE_TS_CODE_APIS = TS_CODE_APIS - DEFERRED_TS_CODE_APIS
CORE_TS_CODE_API_ORDER = (
    "income",
    "balancesheet",
    "fina_indicator",
    "fina_audit",
    "forecast",
    "express",
    "dividend",
    "namechange",
    "stk_managers",
    "stk_rewards",
)
DEFERRED_TS_CODE_API_ORDER = ("fina_mainbz", "disclosure_date")
STOCK_LEVEL_END_DATE_APIS = frozenset({"fina_mainbz"})


class BackfillHistoryGroup(StrEnum):
    SAFE = "safe"
    TS_CODE = "ts-code"
    TS_DEFERRED = "ts-deferred"
    ALL = "all"


@dataclass(frozen=True)
class HistoryBackfillWindow:
    api_name: str
    mode: TushareApiParamMode
    trade_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    ts_code: str | None = None
    month: str | None = None
    cursor_value: str | None = None

    @property
    def batch_start_date(self) -> date | None:
        return self.start_date or self.trade_date or self.end_date

    @property
    def batch_end_date(self) -> date | None:
        return self.end_date or self.trade_date or self.start_date


@dataclass(frozen=True)
class ApiBackfillPlan:
    api_name: str
    mode: TushareApiParamMode
    windows: list[HistoryBackfillWindow]
    skipped_reason: str | None = None


@dataclass(frozen=True)
class HistoryBackfillSelection:
    api_names: list[str]
    excluded_api_names: list[str]


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


@cli.command("plan")
def plan(
    start_date: Annotated[
        str,
        typer.Option(help="Inclusive backfill start date, YYYY-MM-DD."),
    ] = DEFAULT_START_DATE.isoformat(),
    end_date: Annotated[
        str,
        typer.Option(help="Inclusive backfill end date, YYYY-MM-DD."),
    ] = date.today().isoformat(),
    group: Annotated[
        BackfillHistoryGroup,
        typer.Option(help="Backfill group: safe, ts-code, ts-deferred, or all."),
    ] = BackfillHistoryGroup.ALL,
    api: Annotated[
        list[str] | None,
        typer.Option(help="Only plan selected API. Repeat for multiple APIs."),
    ] = None,
    batch_trade_days: Annotated[
        int,
        typer.Option(help="Maximum trade-date windows per API execution."),
    ] = 20,
    batch_calendar_days: Annotated[
        int,
        typer.Option(help="Maximum calendar days per window execution."),
    ] = 180,
    batch_months: Annotated[
        int,
        typer.Option(help="Maximum months per API execution."),
    ] = 12,
    max_stocks_per_api: Annotated[
        int | None,
        typer.Option(help="Maximum stock codes per ts-code API execution."),
    ] = None,
    max_windows_per_api: Annotated[
        int,
        typer.Option(help="Maximum pending windows per API execution."),
    ] = 200,
) -> None:
    parsed_start_date = parse_date(start_date)
    parsed_end_date = parse_date(end_date)
    selection = _select_api_names(group=group, api_names=set(api or []))
    with SessionLocal() as session:
        plans = _build_plans(
            session=session,
            api_names=selection.api_names,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            batch_trade_days=batch_trade_days,
            batch_calendar_days=batch_calendar_days,
            batch_months=batch_months,
            max_stocks_per_api=max_stocks_per_api,
            max_windows_per_api=max_windows_per_api,
        )

    typer.echo(
        "HISTORY_BACKFILL_PLAN "
        f"group={group} "
        f"start_date={parsed_start_date} "
        f"end_date={parsed_end_date} "
        f"apis={len(selection.api_names)} "
        f"excluded={','.join(selection.excluded_api_names) or '-'}"
    )
    for item in plans:
        if item.skipped_reason:
            typer.echo(f"SKIP api={item.api_name} reason={item.skipped_reason}")
            continue
        typer.echo(
            "PLAN "
            f"api={item.api_name} "
            f"mode={item.mode} "
            f"windows={len(item.windows)} "
            f"first={_format_window(item.windows[0]) if item.windows else '-'}"
        )


@cli.command("run")
def run(
    start_date: Annotated[
        str,
        typer.Option(help="Inclusive backfill start date, YYYY-MM-DD."),
    ] = DEFAULT_START_DATE.isoformat(),
    end_date: Annotated[
        str,
        typer.Option(help="Inclusive backfill end date, YYYY-MM-DD."),
    ] = date.today().isoformat(),
    group: Annotated[
        BackfillHistoryGroup,
        typer.Option(help="Backfill group: safe, ts-code, ts-deferred, or all."),
    ] = BackfillHistoryGroup.ALL,
    api: Annotated[
        list[str] | None,
        typer.Option(help="Only run selected API. Repeat for multiple APIs."),
    ] = None,
    batch_trade_days: Annotated[
        int,
        typer.Option(help="Maximum trade-date windows per API execution."),
    ] = 20,
    batch_calendar_days: Annotated[
        int,
        typer.Option(help="Maximum calendar days per window execution."),
    ] = 180,
    batch_months: Annotated[
        int,
        typer.Option(help="Maximum months per API execution."),
    ] = 12,
    max_stocks_per_api: Annotated[
        int | None,
        typer.Option(help="Maximum stock codes per ts-code API execution."),
    ] = None,
    max_windows_per_api: Annotated[
        int,
        typer.Option(help="Maximum pending windows per API execution."),
    ] = 200,
    sleep_seconds: Annotated[
        float,
        typer.Option(help="Sleep seconds between API windows."),
    ] = 3,
    dry_run: Annotated[
        bool,
        typer.Option(help="Preview execution without calling Tushare or writing batches."),
    ] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option(help="Continue remaining APIs after retryable failures."),
    ] = True,
    until_complete: Annotated[
        bool,
        typer.Option(help="Keep planning and running batches until no pending windows remain."),
    ] = False,
    max_rounds: Annotated[
        int,
        typer.Option(help="Maximum planning rounds when --until-complete is enabled."),
    ] = 1000,
    rate_limit_retry_sleep_seconds: Annotated[
        float,
        typer.Option(help="Sleep seconds before retrying a Tushare rate-limited window."),
    ] = 0,
    rate_limit_max_retries: Annotated[
        int,
        typer.Option(help="Maximum batch-level retries for Tushare rate-limited windows."),
    ] = 0,
) -> None:
    parsed_start_date = parse_date(start_date)
    parsed_end_date = parse_date(end_date)
    selection = _select_api_names(group=group, api_names=set(api or []))
    if dry_run:
        _echo_dry_run(
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            group=group,
            selection=selection,
            batch_trade_days=batch_trade_days,
            batch_calendar_days=batch_calendar_days,
            batch_months=batch_months,
            max_stocks_per_api=max_stocks_per_api,
            max_windows_per_api=max_windows_per_api,
        )
        return

    settings = get_settings()
    lock = RedisDistributedLock(Redis.from_url(settings.redis_url, decode_responses=True))
    with _acquire_history_backfill_locks(lock, selection.api_names) as (acquired, blocked_api_name):
        if not acquired:
            typer.echo(
                "SKIPPED another Tushare history backfill task is already running "
                f"for api={blocked_api_name}."
            )
            raise typer.Exit(code=0)
        _run_backfill(
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            selection=selection,
            group=group,
            batch_trade_days=batch_trade_days,
            batch_calendar_days=batch_calendar_days,
            batch_months=batch_months,
            max_stocks_per_api=max_stocks_per_api,
            max_windows_per_api=max_windows_per_api,
            sleep_seconds=sleep_seconds,
            continue_on_error=continue_on_error,
            until_complete=until_complete,
            max_rounds=max_rounds,
            rate_limit_retry_sleep_seconds=rate_limit_retry_sleep_seconds,
            rate_limit_max_retries=rate_limit_max_retries,
        )


@contextmanager
def _acquire_history_backfill_locks(
    lock: RedisDistributedLock,
    api_names: list[str],
) -> Iterator[tuple[bool, str | None]]:
    with ExitStack() as stack:
        for lock_name in _history_backfill_lock_names(api_names):
            acquired = stack.enter_context(lock.acquire(lock_name, ttl_seconds=24 * 60 * 60))
            if not acquired:
                yield False, _api_name_from_lock_name(lock_name)
                return
        yield True, None


def _history_backfill_lock_names(api_names: list[str]) -> tuple[str, ...]:
    return tuple(f"tushare-history-backfill:{api_name}" for api_name in sorted(api_names))


def _api_name_from_lock_name(lock_name: str) -> str:
    return lock_name.rsplit(":", maxsplit=1)[-1]


def _echo_dry_run(
    *,
    start_date: date,
    end_date: date,
    group: BackfillHistoryGroup,
    selection: HistoryBackfillSelection,
    batch_trade_days: int,
    batch_calendar_days: int,
    batch_months: int,
    max_stocks_per_api: int | None,
    max_windows_per_api: int,
) -> None:
    with SessionLocal() as session:
        plans = _build_plans(
            session=session,
            api_names=selection.api_names,
            start_date=start_date,
            end_date=end_date,
            batch_trade_days=batch_trade_days,
            batch_calendar_days=batch_calendar_days,
            batch_months=batch_months,
            max_stocks_per_api=max_stocks_per_api,
            max_windows_per_api=max_windows_per_api,
        )
    typer.echo(
        "DRY_RUN "
        f"group={group} "
        f"apis={len(selection.api_names)} "
        f"windows={sum(len(item.windows) for item in plans)} "
        f"excluded={','.join(selection.excluded_api_names) or '-'}"
    )
    for item in plans:
        if item.skipped_reason:
            typer.echo(f"SKIP api={item.api_name} reason={item.skipped_reason}")
        else:
            typer.echo(f"PLAN api={item.api_name} windows={len(item.windows)}")


def _run_backfill(
    *,
    start_date: date,
    end_date: date,
    selection: HistoryBackfillSelection,
    group: BackfillHistoryGroup,
    batch_trade_days: int,
    batch_calendar_days: int,
    batch_months: int,
    max_stocks_per_api: int | None,
    max_windows_per_api: int,
    sleep_seconds: float,
    continue_on_error: bool,
    until_complete: bool,
    max_rounds: int,
    rate_limit_retry_sleep_seconds: float,
    rate_limit_max_retries: int,
) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.create_job(
            provider=PROVIDER,
            task_type="tushare_history",
            name=f"Tushare 其他接口历史回填 {start_date.isoformat()} 至 {end_date.isoformat()}",
            start_date=start_date,
            end_date=end_date,
            cursor_date=None,
        )
        session.commit()
        job_id = job.id

    total_success = 0
    total_failed = 0
    total_blocked = 0
    batch_index = 0
    rounds = max_rounds if until_complete else 1
    stopped_api_names: set[str] = set()
    for round_index in range(1, rounds + 1):
        round_executed = 0
        typer.echo(f"ROUND index={round_index}")
        for api_name in selection.api_names:
            if api_name in stopped_api_names:
                typer.echo(f"SKIP api={api_name} reason=stopped_after_failure")
                continue
            with SessionLocal() as session:
                plans = _build_plans(
                    session=session,
                    api_names=[api_name],
                    start_date=start_date,
                    end_date=end_date,
                    batch_trade_days=batch_trade_days,
                    batch_calendar_days=batch_calendar_days,
                    batch_months=batch_months,
                    max_stocks_per_api=max_stocks_per_api,
                    max_windows_per_api=max_windows_per_api,
                )
                api_plan = plans[0]
            if api_plan.skipped_reason:
                typer.echo(f"SKIP api={api_name} reason={api_plan.skipped_reason}")
                continue
            if not api_plan.windows:
                typer.echo(f"SKIP api={api_name} reason=no_pending_windows")
                continue
            for window in api_plan.windows:
                batch_index += 1
                round_executed += 1
                batch_id = _start_batch(job_id=job_id, batch_index=batch_index, window=window)
                typer.echo(f"START batch={batch_index} {_format_window(window)}")
                try:
                    summary = _sync_window_with_rate_limit_retry(
                        window,
                        retry_sleep_seconds=rate_limit_retry_sleep_seconds,
                        max_retries=rate_limit_max_retries,
                    )
                except TushareInsufficientPointsError as exc:
                    total_blocked += 1
                    error_message = _single_line(str(exc))
                    _mark_batch_failure(
                        job_id=job_id,
                        batch_id=batch_id,
                        error_message=error_message,
                        blocked=True,
                    )
                    typer.echo(f"BLOCKED api={api_name} error={error_message}")
                    stopped_api_names.add(api_name)
                    break
                except Exception as exc:
                    total_failed += 1
                    error_message = _single_line(str(exc))
                    _mark_batch_failure(
                        job_id=job_id,
                        batch_id=batch_id,
                        error_message=error_message,
                    )
                    typer.echo(f"FAILED api={api_name} error={error_message}")
                    if not continue_on_error:
                        _mark_job_failure(job_id=job_id, error_message=error_message)
                        raise
                    stopped_api_names.add(api_name)
                    break
                else:
                    total_success += 1
                    _mark_batch_success(
                        job_id=job_id,
                        batch_id=batch_id,
                        window=window,
                        rows_fetched=summary.rows_fetched,
                        rows_upserted=summary.rows_upserted,
                    )
                    typer.echo(
                        "SUCCESS "
                        f"api={api_name} "
                        f"rows_fetched={summary.rows_fetched} "
                        f"rows_upserted={summary.rows_upserted}"
                    )
                    if sleep_seconds > 0:
                        sleep(sleep_seconds)
        if round_executed == 0:
            break

    if total_failed > 0:
        _mark_job_failure(job_id=job_id, error_message=f"failed_batches={total_failed}")
    elif total_blocked > 0:
        _mark_job_failure(
            job_id=job_id,
            error_message=f"blocked_batches={total_blocked}",
            blocked=True,
        )
    else:
        _mark_job_success(job_id=job_id)
    typer.echo(
        "DONE "
        f"job_id={job_id} "
        f"success={total_success} "
        f"failed={total_failed} "
        f"blocked={total_blocked}"
    )


def _build_plans(
    *,
    session: Session,
    api_names: list[str],
    start_date: date,
    end_date: date,
    batch_trade_days: int,
    batch_calendar_days: int,
    batch_months: int,
    max_stocks_per_api: int | None,
    max_windows_per_api: int,
) -> list[ApiBackfillPlan]:
    open_trade_dates = _open_trade_dates(session, start_date=start_date, end_date=end_date)
    stock_codes = _stock_codes(session, limit=max_stocks_per_api)
    plans: list[ApiBackfillPlan] = []
    for api_name in api_names:
        spec = TUSHARE_API_SPECS_BY_NAME[api_name]
        plans.append(
            ApiBackfillPlan(
                api_name=api_name,
                mode=spec.param_mode,
                windows=_windows_for_spec(
                    session=session,
                    spec=spec,
                    start_date=start_date,
                    end_date=end_date,
                    open_trade_dates=open_trade_dates,
                    stock_codes=stock_codes,
                    batch_trade_days=batch_trade_days,
                    batch_calendar_days=batch_calendar_days,
                    batch_months=batch_months,
                    max_windows_per_api=max_windows_per_api,
                ),
                skipped_reason=_skip_reason(session, spec, stock_codes=stock_codes),
            )
        )
    return plans


def _windows_for_spec(
    *,
    session: Session,
    spec: TushareApiSpec,
    start_date: date,
    end_date: date,
    open_trade_dates: list[date],
    stock_codes: list[str],
    batch_trade_days: int,
    batch_calendar_days: int,
    batch_months: int,
    max_windows_per_api: int,
) -> list[HistoryBackfillWindow]:
    history_cursor = _history_cursor(session, api_name=spec.api_name)
    effective_start_date = max(start_date, API_HISTORY_START_DATES.get(spec.api_name, start_date))
    effective_trade_dates = [item for item in open_trade_dates if item >= effective_start_date]
    if spec.param_mode in {TushareApiParamMode.NONE, TushareApiParamMode.LIST_STATUS}:
        if history_cursor == "full":
            return []
        return [HistoryBackfillWindow(api_name=spec.api_name, mode=spec.param_mode)]
    if spec.param_mode in {
        TushareApiParamMode.TRADE_DATE,
        TushareApiParamMode.TRADE_DATE_WITH_MARKET,
    }:
        trade_dates = _trade_dates_for_api(
            api_name=spec.api_name,
            open_trade_dates=effective_trade_dates,
        )
        pending = _pending_trade_dates(
            trade_dates=trade_dates,
            cursor=history_cursor,
            limit=batch_trade_days,
        )
        return [
            HistoryBackfillWindow(
                api_name=spec.api_name,
                mode=spec.param_mode,
                trade_date=trade_date,
                cursor_value=_format_date(trade_date),
            )
            for trade_date in pending
        ]
    if spec.param_mode is TushareApiParamMode.CALENDAR_WINDOW:
        cursor_date = _parse_date_cursor(history_cursor)
        window_start_date = (
            max(effective_start_date, cursor_date + timedelta(days=1))
            if cursor_date
            else effective_start_date
        )
        return [
            HistoryBackfillWindow(
                api_name=spec.api_name,
                mode=spec.param_mode,
                start_date=window_start,
                end_date=window_end,
                cursor_value=_format_date(window_end),
            )
            for window_start, window_end in _date_windows(
                start_date=window_start_date,
                end_date=end_date,
                days=batch_calendar_days,
            )
        ]
    if spec.param_mode is TushareApiParamMode.MONTH:
        return [
            HistoryBackfillWindow(
                api_name=spec.api_name,
                mode=spec.param_mode,
                month=month,
                cursor_value=month,
            )
            for month in _pending_months(
                months=_months(start_date=effective_start_date, end_date=end_date),
                cursor=history_cursor,
                limit=batch_months,
            )
        ]
    if spec.param_mode in {TushareApiParamMode.TS_CODE, TushareApiParamMode.TS_CODE_WINDOW}:
        return [
            HistoryBackfillWindow(
                api_name=spec.api_name,
                mode=spec.param_mode,
                start_date=(
                    start_date if spec.param_mode is TushareApiParamMode.TS_CODE_WINDOW else None
                ),
                end_date=(
                    end_date if spec.param_mode is TushareApiParamMode.TS_CODE_WINDOW else None
                ),
                ts_code=ts_code,
                cursor_value=ts_code,
            )
            for ts_code in _pending_stock_codes(stock_codes=stock_codes, cursor=history_cursor)
        ][:max_windows_per_api]
    if spec.param_mode is TushareApiParamMode.TS_CODE_END_DATE:
        if spec.api_name in STOCK_LEVEL_END_DATE_APIS:
            return [
                HistoryBackfillWindow(
                    api_name=spec.api_name,
                    mode=spec.param_mode,
                    end_date=end_date,
                    ts_code=ts_code,
                    cursor_value=ts_code,
                )
                for ts_code in _pending_stock_codes(
                    stock_codes=stock_codes,
                    cursor=_stock_level_cursor(history_cursor),
                )
            ][:max_windows_per_api]
        return [
            HistoryBackfillWindow(
                api_name=spec.api_name,
                mode=spec.param_mode,
                end_date=quarter_end,
                ts_code=ts_code,
                cursor_value=f"{ts_code}:{_format_date(quarter_end)}",
            )
            for ts_code, quarter_end in _pending_stock_quarters(
                stock_codes=stock_codes,
                quarter_ends=_quarter_ends(start_date=start_date, end_date=end_date),
                cursor=history_cursor,
            )
        ][:max_windows_per_api]
    return []


def _sync_window(window: HistoryBackfillWindow) -> SyncSummary:
    with SessionLocal() as session:
        service = TushareMarketDataSyncService(session, normalize=False)
        return service.sync_registered_api(
            api_name=window.api_name,
            trade_date=window.trade_date,
            start_date=window.start_date,
            end_date=window.end_date,
            ts_code=window.ts_code,
            month=window.month,
            cursor_value=window.cursor_value,
            sync_mode="history_backfill",
        )


def _sync_window_with_rate_limit_retry(
    window: HistoryBackfillWindow,
    *,
    retry_sleep_seconds: float,
    max_retries: int,
) -> SyncSummary:
    attempt = 0
    while True:
        try:
            return _sync_window(window)
        except TushareRateLimitError:
            if attempt >= max_retries:
                raise
            attempt += 1
            if retry_sleep_seconds > 0:
                typer.echo(
                    "RATE_LIMIT_SLEEP "
                    f"api={window.api_name} "
                    f"attempt={attempt} "
                    f"sleep_seconds={retry_sleep_seconds}"
                )
                sleep(retry_sleep_seconds)


def _select_api_names(
    *,
    group: BackfillHistoryGroup,
    api_names: set[str],
) -> HistoryBackfillSelection:
    unknown_api_names = sorted(api_names - set(TUSHARE_API_SPECS_BY_NAME))
    if unknown_api_names:
        raise typer.BadParameter(f"Unsupported Tushare APIs: {', '.join(unknown_api_names)}")
    if api_names:
        selected = sorted(api_names)
    elif group is BackfillHistoryGroup.SAFE:
        selected = sorted(_safe_history_api_names())
    elif group is BackfillHistoryGroup.TS_CODE:
        selected = _ordered_api_names(CORE_TS_CODE_API_ORDER, CORE_TS_CODE_APIS)
    elif group is BackfillHistoryGroup.TS_DEFERRED:
        selected = _ordered_api_names(DEFERRED_TS_CODE_API_ORDER, DEFERRED_TS_CODE_APIS)
    else:
        selected = [
            *sorted(_safe_history_api_names()),
            *_ordered_api_names(CORE_TS_CODE_API_ORDER, CORE_TS_CODE_APIS),
        ]
    excluded = sorted(CORE_QUOTE_APIS | REALTIME_OR_MINUTE_APIS)
    return HistoryBackfillSelection(api_names=selected, excluded_api_names=excluded)


def _ordered_api_names(priority_order: tuple[str, ...], api_names: frozenset[str]) -> list[str]:
    ordered = [api_name for api_name in priority_order if api_name in api_names]
    ordered.extend(sorted(api_names - set(ordered)))
    return ordered


def _safe_history_api_names() -> set[str]:
    result: set[str] = set(SAFE_FULL_APIS)
    for api_name, spec in TUSHARE_API_SPECS_BY_NAME.items():
        if api_name in CORE_QUOTE_APIS or api_name in REALTIME_OR_MINUTE_APIS:
            continue
        if spec.param_mode in {
            TushareApiParamMode.TRADE_DATE,
            TushareApiParamMode.TRADE_DATE_WITH_MARKET,
            TushareApiParamMode.CALENDAR_WINDOW,
            TushareApiParamMode.MONTH,
        }:
            result.add(api_name)
    return result


def _skip_reason(session: Session, spec: TushareApiSpec, *, stock_codes: list[str]) -> str | None:
    if spec.api_name in CORE_QUOTE_APIS:
        return "核心日行情接口已由 market_quote_history 回填任务负责。"
    if spec.api_name in REALTIME_OR_MINUTE_APIS:
        return "实时或分钟接口不纳入全量历史回填。"
    if _is_blocked_api(session, api_name=spec.api_name):
        return "接口因积分或权限不足处于阻塞状态，保持人工处理。"
    if spec.param_mode in {
        TushareApiParamMode.TS_CODE,
        TushareApiParamMode.TS_CODE_WINDOW,
        TushareApiParamMode.TS_CODE_END_DATE,
    } and not stock_codes:
        return "缺少股票代码列表，请先同步 stock_basic 并归一化 app.stocks。"
    return None


def _open_trade_dates(session: Session, *, start_date: date, end_date: date) -> list[date]:
    rows = session.execute(
        text(
            """
            SELECT cal_date
            FROM app.trade_calendars
            WHERE exchange = 'SSE'
              AND is_open = true
              AND cal_date >= :start_date
              AND cal_date <= :end_date
            ORDER BY cal_date
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).all()
    return [row[0] for row in rows]


def _trade_dates_for_api(*, api_name: str, open_trade_dates: list[date]) -> list[date]:
    if api_name in WEEKLY_TRADE_DATE_APIS:
        return _period_end_trade_dates(open_trade_dates, period="week")
    if api_name in MONTHLY_TRADE_DATE_APIS:
        return _period_end_trade_dates(open_trade_dates, period="month")
    return open_trade_dates


def _period_end_trade_dates(open_trade_dates: list[date], *, period: str) -> list[date]:
    grouped: dict[tuple[int, int], date] = {}
    for trade_date in open_trade_dates:
        if period == "week":
            year, week, _weekday = trade_date.isocalendar()
            key = (year, week)
        elif period == "month":
            key = (trade_date.year, trade_date.month)
        else:
            raise ValueError(f"Unsupported period: {period}")
        grouped[key] = trade_date
    return list(grouped.values())


def _stock_codes(session: Session, *, limit: int | None) -> list[str]:
    statement = """
        SELECT ts_code
        FROM app.stocks
        WHERE list_status = 'L' OR list_status IS NULL
        ORDER BY ts_code
    """
    params: dict[str, int] = {}
    if limit is not None:
        statement += "\nLIMIT :limit"
        params["limit"] = limit
    rows = session.execute(text(statement), params).all()
    return [row[0] for row in rows]


def _pending_trade_dates(*, trade_dates: list[date], cursor: str | None, limit: int) -> list[date]:
    cursor_date = _parse_date_cursor(cursor)
    pending = [item for item in trade_dates if cursor_date is None or item > cursor_date]
    return pending[:limit]


def _pending_months(*, months: list[str], cursor: str | None, limit: int) -> list[str]:
    pending = [item for item in months if cursor is None or item > cursor]
    return pending[:limit]


def _pending_stock_codes(*, stock_codes: list[str], cursor: str | None) -> list[str]:
    if cursor is None or ":" in cursor or cursor.isdigit():
        return stock_codes
    return [item for item in stock_codes if item > cursor]


def _stock_level_cursor(cursor: str | None) -> str | None:
    if cursor is None or ":" not in cursor:
        return cursor
    return cursor.split(":", maxsplit=1)[0]


def _pending_stock_quarters(
    *,
    stock_codes: list[str],
    quarter_ends: list[date],
    cursor: str | None,
) -> list[tuple[str, date]]:
    pairs = [(ts_code, quarter_end) for ts_code in stock_codes for quarter_end in quarter_ends]
    if cursor is None:
        return pairs
    return [
        (ts_code, quarter_end)
        for ts_code, quarter_end in pairs
        if f"{ts_code}:{_format_date(quarter_end)}" > cursor
    ]


def _job_cursor(*, api_name: str) -> str | None:
    with SessionLocal() as session:
        job = DataSyncRepository(session).get_job(provider=PROVIDER, api_name=api_name)
        if job is None or job.status == BLOCKED_INSUFFICIENT_POINTS_STATUS:
            return None
        return job.cursor_value


def _history_cursor(session: Session, *, api_name: str) -> str | None:
    spec = TUSHARE_API_SPECS_BY_NAME[api_name]
    if spec.param_mode in {TushareApiParamMode.NONE, TushareApiParamMode.LIST_STATUS}:
        row_count = session.execute(
            text(f"SELECT count(*) FROM tushare.{spec.table_name}")
        ).scalar_one()
        return "full" if int(row_count) > 0 else None
    cursor = session.execute(
        text(
            """
            SELECT b.cursor_value
            FROM app.backfill_batches b
            JOIN app.backfill_jobs j ON j.id = b.job_id
            WHERE j.provider = :provider
              AND j.task_type = 'tushare_history'
              AND b.api_name = :api_name
              AND b.status = 'success'
              AND b.cursor_value IS NOT NULL
            ORDER BY b.id DESC
            LIMIT 1
            """
        ),
        {"provider": PROVIDER, "api_name": api_name},
    ).scalar_one_or_none()
    return str(cursor) if cursor else None


def _is_blocked_api(session: Session, *, api_name: str) -> bool:
    job = DataSyncRepository(session).get_job(provider=PROVIDER, api_name=api_name)
    return job is not None and job.status == BLOCKED_INSUFFICIENT_POINTS_STATUS


def _date_windows(*, start_date: date, end_date: date, days: int) -> list[tuple[date, date]]:
    windows: list[tuple[date, date]] = []
    current = start_date
    while current <= end_date:
        window_end = min(end_date, current + timedelta(days=days - 1))
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)
    return windows


def _months(*, start_date: date, end_date: date) -> list[str]:
    months: list[str] = []
    current = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while current <= end_month:
        months.append(current.strftime("%Y%m"))
        current = _first_day_of_next_month(current)
    return months


def _quarter_ends(*, start_date: date, end_date: date) -> list[date]:
    quarter_ends: list[date] = []
    current = date(start_date.year, 3, 31)
    while current < start_date:
        current = _next_quarter_end(current)
    while current <= end_date:
        quarter_ends.append(current)
        current = _next_quarter_end(current)
    return quarter_ends


def _start_batch(*, job_id: int, batch_index: int, window: HistoryBackfillWindow) -> int:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Backfill job {job_id} not found.")
        trade_dates = list(
            dict.fromkeys(
                value for value in [window.batch_start_date, window.batch_end_date] if value
            )
        )
        batch = repository.start_batch(
            job,
            batch_index=batch_index,
            cursor_date=window.batch_end_date,
            trade_dates=trade_dates,
            api_name=window.api_name,
            cursor_value=window.cursor_value,
        )
        session.commit()
        return batch.id


def _mark_batch_success(
    *,
    job_id: int,
    batch_id: int,
    window: HistoryBackfillWindow,
    rows_fetched: int,
    rows_upserted: int,
) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        batch = session.get(BackfillBatch, batch_id)
        if job is None or batch is None:
            raise RuntimeError(f"Backfill job {job_id} or batch {batch_id} not found.")
        repository.mark_batch_success(
            job,
            batch,
            windows=1,
            rows_fetched=rows_fetched,
            rows_upserted=rows_upserted,
            cursor_date=window.batch_end_date,
        )
        batch.cursor_value = window.cursor_value
        session.commit()


def _mark_batch_failure(
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
            raise RuntimeError(f"Backfill job {job_id} or batch {batch_id} not found.")
        repository.mark_batch_failure(job, batch, error_message=error_message, blocked=blocked)
        session.commit()


def _mark_job_success(job_id: int) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Backfill job {job_id} not found.")
        repository.mark_job_success(job)
        session.commit()


def _mark_job_failure(
    *,
    job_id: int,
    error_message: str,
    blocked: bool = False,
) -> None:
    with SessionLocal() as session:
        repository = BackfillRepository(session)
        job = repository.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Backfill job {job_id} not found.")
        repository.mark_job_failure(job, error_message=error_message, blocked=blocked)
        session.commit()


def _first_day_of_next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _next_quarter_end(value: date) -> date:
    next_month = value.month + 3
    year = value.year
    if next_month > 12:
        year += 1
        next_month -= 12
    return _last_day_of_month(date(year, next_month, 1))


def _last_day_of_month(value: date) -> date:
    return _first_day_of_next_month(value) - timedelta(days=1)


def _parse_date_cursor(value: str | None) -> date | None:
    if value is None or value == "full" or len(value) != 8:
        return None
    return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))


def _format_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _format_window(window: HistoryBackfillWindow) -> str:
    return (
        f"api={window.api_name} "
        f"mode={window.mode} "
        f"trade_date={window.trade_date} "
        f"start_date={window.start_date} "
        f"end_date={window.end_date} "
        f"ts_code={window.ts_code} "
        f"month={window.month} "
        f"cursor={window.cursor_value}"
    )


def _single_line(value: str) -> str:
    stripped = value.strip()
    return stripped.splitlines()[0] if stripped else "Unknown error"


if __name__ == "__main__":
    cli()
