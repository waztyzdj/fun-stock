from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from time import sleep

from sqlalchemy.orm import Session

from app.adapters.tushare import TushareInsufficientPointsError
from app.adapters.tushare.registry import (
    TUSHARE_API_SPECS,
    TushareApiCategory,
    TushareApiParamMode,
    TushareApiSpec,
)
from app.engines.data_sync.tushare.market_data_sync import (
    PROVIDER,
    TushareMarketDataSyncService,
)
from app.models.data_sync import DataSyncJob
from app.repositories.data_sync import (
    BLOCKED_INSUFFICIENT_POINTS_STATUS,
    DataSyncRepository,
)

DEFAULT_TS_CODE = "000001.SZ"


class TushareScheduleKind(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    MANUAL = "manual"


@dataclass(frozen=True)
class TushareSyncPlan:
    api_name: str
    schedule: TushareScheduleKind
    priority: int
    enabled: bool = True
    max_lag_days: int = 1
    lookback_days: int = 7
    sleep_seconds_after: float = 0
    notes: str = ""


@dataclass(frozen=True)
class TusharePlanWindow:
    api_name: str
    schedule: TushareScheduleKind
    trade_date: date | None
    start_date: date | None
    end_date: date | None
    ts_code: str | None
    month: str | None
    reason: str
    due: bool


@dataclass(frozen=True)
class TushareSchedulerRunItem:
    window: TusharePlanWindow
    status: str
    rows_fetched: int = 0
    rows_upserted: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class TushareSchedulerRunResult:
    items: list[TushareSchedulerRunItem]

    @property
    def successes(self) -> int:
        return sum(1 for item in self.items if item.status == "success")

    @property
    def failures(self) -> int:
        return sum(1 for item in self.items if item.status == "failed")

    @property
    def blocked(self) -> int:
        return sum(1 for item in self.items if item.status == BLOCKED_INSUFFICIENT_POINTS_STATUS)

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.items if item.status == "skipped")

    @property
    def rows_fetched(self) -> int:
        return sum(item.rows_fetched for item in self.items)

    @property
    def rows_upserted(self) -> int:
        return sum(item.rows_upserted for item in self.items)


def build_default_tushare_sync_plans() -> tuple[TushareSyncPlan, ...]:
    plans: list[TushareSyncPlan] = []
    for spec in TUSHARE_API_SPECS:
        plans.append(
            TushareSyncPlan(
                api_name=spec.api_name,
                schedule=_default_schedule_for_spec(spec),
                priority=_default_priority_for_spec(spec),
                enabled=spec.api_name not in _manual_api_names(),
                max_lag_days=_default_max_lag_days_for_spec(spec),
                lookback_days=_default_lookback_days_for_spec(spec),
                sleep_seconds_after=_default_sleep_seconds_for_spec(spec),
                notes=_default_notes_for_spec(spec),
            )
        )
    return tuple(sorted(plans, key=lambda plan: (plan.priority, plan.api_name)))


def _manual_api_names() -> set[str]:
    return {
        "rt_k",
        "stk_mins",
        "rt_min",
        "rt_min_daily",
    }


def _default_schedule_for_spec(spec: TushareApiSpec) -> TushareScheduleKind:
    if spec.api_name in _manual_api_names():
        return TushareScheduleKind.MANUAL
    if spec.param_mode is TushareApiParamMode.MONTH:
        return TushareScheduleKind.MONTHLY
    if spec.category is TushareApiCategory.FINANCE:
        return TushareScheduleKind.WEEKLY
    if spec.api_name in {"stock_basic", "stock_company", "bse_mapping"}:
        return TushareScheduleKind.WEEKLY
    return TushareScheduleKind.DAILY


def _default_priority_for_spec(spec: TushareApiSpec) -> int:
    if spec.api_name in {"stock_basic", "trade_cal"}:
        return 10
    if spec.api_name in {
        "daily",
        "daily_basic",
        "adj_factor",
        "index_daily",
        "stk_limit",
        "suspend_d",
    }:
        return 20
    if spec.category is TushareApiCategory.FINANCE:
        return 40
    if spec.api_name in _manual_api_names():
        return 90
    return 50


def _default_max_lag_days_for_spec(spec: TushareApiSpec) -> int:
    if spec.param_mode is TushareApiParamMode.MONTH:
        return 32
    if spec.category is TushareApiCategory.FINANCE:
        return 7
    if spec.api_name in {"stock_basic", "stock_company", "bse_mapping"}:
        return 7
    return 1


def _default_lookback_days_for_spec(spec: TushareApiSpec) -> int:
    if spec.category is TushareApiCategory.FINANCE:
        return 120
    if spec.param_mode is TushareApiParamMode.CALENDAR_WINDOW:
        return 30
    return 7


def _default_sleep_seconds_for_spec(spec: TushareApiSpec) -> float:
    if spec.api_name == "stk_mins":
        return 65
    return 0


def _default_notes_for_spec(spec: TushareApiSpec) -> str:
    if spec.api_name in _manual_api_names():
        return "实时或分钟接口默认不进入自动调度，避免交易时段和限流噪声。"
    return ""


TUSHARE_SYNC_PLANS = build_default_tushare_sync_plans()
TUSHARE_SYNC_PLANS_BY_API = {plan.api_name: plan for plan in TUSHARE_SYNC_PLANS}


class TushareSyncScheduler:
    def __init__(
        self,
        session: Session,
        *,
        plans: tuple[TushareSyncPlan, ...] = TUSHARE_SYNC_PLANS,
        service: TushareMarketDataSyncService | None = None,
        ts_code: str = DEFAULT_TS_CODE,
    ) -> None:
        self.session = session
        self.plans = plans
        self.service = service or TushareMarketDataSyncService(session, normalize=False)
        self.repository = DataSyncRepository(session)
        self.ts_code = ts_code

    def plan_due_windows(
        self,
        *,
        run_date: date,
        include_manual: bool = False,
        api_names: set[str] | None = None,
        force_selected: bool = False,
    ) -> list[TusharePlanWindow]:
        windows: list[TusharePlanWindow] = []
        for plan in self.plans:
            if not plan.enabled and not include_manual:
                continue
            if api_names is not None and plan.api_name not in api_names:
                continue
            window = self._window_for_plan(
                plan,
                run_date=run_date,
                include_manual=include_manual,
                force_due=force_selected and api_names is not None and plan.api_name in api_names,
            )
            if window.due:
                windows.append(window)
        return windows

    def run_once(
        self,
        *,
        run_date: date,
        max_items: int | None = None,
        dry_run: bool = False,
        continue_on_error: bool = True,
        include_manual: bool = False,
        api_names: set[str] | None = None,
        force_selected: bool = False,
    ) -> TushareSchedulerRunResult:
        windows = self.plan_due_windows(
            run_date=run_date,
            include_manual=include_manual,
            api_names=api_names,
            force_selected=force_selected,
        )
        if max_items is not None:
            windows = windows[:max_items]

        items: list[TushareSchedulerRunItem] = []
        blocked_api_names: set[str] = set()
        for window in windows:
            if window.api_name in blocked_api_names:
                items.append(
                    TushareSchedulerRunItem(
                        window=window,
                        status="skipped",
                        error_message="本轮已检测到积分或权限不足，跳过该接口后续调用。",
                    )
                )
                continue
            if dry_run:
                items.append(TushareSchedulerRunItem(window=window, status="skipped"))
                continue
            try:
                summary = self.service.sync_registered_api(
                    api_name=window.api_name,
                    trade_date=window.trade_date,
                    start_date=window.start_date,
                    end_date=window.end_date,
                    ts_code=window.ts_code,
                    month=window.month,
                )
            except TushareInsufficientPointsError as exc:
                blocked_api_names.add(window.api_name)
                items.append(
                    TushareSchedulerRunItem(
                        window=window,
                        status=BLOCKED_INSUFFICIENT_POINTS_STATUS,
                        error_message=_concise_error(exc),
                    )
                )
            except Exception as exc:
                items.append(
                    TushareSchedulerRunItem(
                        window=window,
                        status="failed",
                        error_message=_concise_error(exc),
                    )
                )
                if not continue_on_error:
                    break
            else:
                items.append(
                    TushareSchedulerRunItem(
                        window=window,
                        status="success",
                        rows_fetched=summary.rows_fetched,
                        rows_upserted=summary.rows_upserted,
                    )
                )
                sleep_seconds = self._plans_by_api_name()[window.api_name].sleep_seconds_after
                if sleep_seconds > 0:
                    sleep(sleep_seconds)
        return TushareSchedulerRunResult(items=items)

    def _window_for_plan(
        self,
        plan: TushareSyncPlan,
        *,
        run_date: date,
        include_manual: bool,
        force_due: bool = False,
    ) -> TusharePlanWindow:
        spec = _spec_by_api_name(plan.api_name)
        job = self.repository.get_job(provider=PROVIDER, api_name=plan.api_name)
        cursor_job = self._cursor_job_for_plan(plan, job)
        cursor_date = _parse_cursor_date(cursor_job.cursor_value if cursor_job else None)
        due, reason = _is_plan_due(
            plan=plan,
            job=cursor_job,
            run_date=run_date,
            include_manual=include_manual,
        )
        if force_due and not _is_blocked_job(job) and not _is_blocked_job(cursor_job):
            due = True
            reason = "人工重跑可重试失败项"
        default_start_date = max(
            date(2000, 1, 1),
            run_date - timedelta(days=plan.lookback_days),
        )
        start_date = (
            cursor_date + timedelta(days=1)
            if cursor_date
            else default_start_date
        )

        if spec.param_mode is TushareApiParamMode.NONE:
            return _window(
                plan,
                due=due,
                reason=reason,
            )
        if spec.param_mode is TushareApiParamMode.LIST_STATUS:
            return _window(plan, due=due, reason=reason)
        if spec.param_mode is TushareApiParamMode.CALENDAR_WINDOW:
            return _window(
                plan,
                due=due,
                reason=reason,
                start_date=start_date,
                end_date=run_date,
            )
        if spec.param_mode in {
            TushareApiParamMode.TRADE_DATE,
            TushareApiParamMode.TRADE_DATE_WITH_MARKET,
        }:
            trade_date = self._next_trade_date_for_plan(
                cursor_date=cursor_date,
                run_date=run_date,
                default_start_date=default_start_date,
            )
            if trade_date is None:
                return _window(
                    plan,
                    due=False,
                    reason="交易日历中没有待同步交易日",
                )
            return _window(plan, due=due, reason=reason, trade_date=trade_date)
        if spec.param_mode is TushareApiParamMode.MONTH:
            return _window(
                plan,
                due=due,
                reason=reason,
                month=_month_for_run_date(run_date),
            )
        if spec.param_mode is TushareApiParamMode.TS_CODE:
            return _window(
                plan,
                due=due,
                reason=reason,
                ts_code=self.ts_code,
            )
        if spec.param_mode is TushareApiParamMode.TS_CODE_WINDOW:
            return _window(
                plan,
                due=due,
                reason=reason,
                start_date=start_date,
                end_date=run_date,
                ts_code=self.ts_code,
            )
        if spec.param_mode is TushareApiParamMode.TS_CODE_END_DATE:
            return _window(
                plan,
                due=due,
                reason=reason,
                end_date=_quarter_end_on_or_before(run_date),
                ts_code=self.ts_code,
            )
        msg = f"Unsupported Tushare parameter mode: {spec.param_mode}"
        raise ValueError(msg)

    def _plans_by_api_name(self) -> dict[str, TushareSyncPlan]:
        return {plan.api_name: plan for plan in self.plans}

    def _cursor_job_for_plan(
        self,
        plan: TushareSyncPlan,
        job: DataSyncJob | None,
    ) -> DataSyncJob | None:
        if plan.api_name in {"daily", "daily_basic", "adj_factor", "index_daily"}:
            return self.repository.get_job(provider=PROVIDER, api_name="daily") or job
        return job

    def _next_trade_date_for_plan(
        self,
        *,
        cursor_date: date | None,
        run_date: date,
        default_start_date: date,
    ) -> date | None:
        after_date = cursor_date or default_start_date - timedelta(days=1)
        trade_dates = self.service.raw_repository.get_open_trade_dates_after(
            exchange="SSE",
            after_date=after_date,
            end_date=run_date,
        )
        if trade_dates:
            return trade_dates[0]
        return run_date if run_date.weekday() < 5 and cursor_date is None else None


def _window(
    plan: TushareSyncPlan,
    *,
    due: bool,
    reason: str,
    trade_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    ts_code: str | None = None,
    month: str | None = None,
) -> TusharePlanWindow:
    return TusharePlanWindow(
        api_name=plan.api_name,
        schedule=plan.schedule,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
        ts_code=ts_code,
        month=month,
        reason=reason,
        due=due,
    )


def _spec_by_api_name(api_name: str) -> TushareApiSpec:
    for spec in TUSHARE_API_SPECS:
        if spec.api_name == api_name:
            return spec
    msg = f"Unknown Tushare API in sync plan: {api_name}"
    raise ValueError(msg)


def _is_plan_due(
    *,
    plan: TushareSyncPlan,
    job: DataSyncJob | None,
    run_date: date,
    include_manual: bool,
) -> tuple[bool, str]:
    if not plan.enabled and not include_manual:
        return False, "计划未启用"
    if _is_blocked_job(job):
        return False, "接口因积分或权限不足被阻塞，需人工处理后再恢复"
    cursor_date = _effective_job_date(job)
    if cursor_date is None or (include_manual and not plan.enabled):
        return True, "首次同步"
    lag_days = (run_date - cursor_date).days
    if lag_days >= plan.max_lag_days:
        return True, f"游标落后 {lag_days} 天"
    return False, f"游标未达到触发阈值，落后 {lag_days} 天"


def _is_blocked_job(job: DataSyncJob | None) -> bool:
    return job is not None and job.status == BLOCKED_INSUFFICIENT_POINTS_STATUS


def _effective_job_date(job: DataSyncJob | None) -> date | None:
    if job is None:
        return None
    cursor_date = _parse_cursor_date(job.cursor_value)
    if cursor_date is not None:
        return cursor_date
    if job.last_success_at is not None:
        return job.last_success_at.date()
    return None


def _parse_cursor_date(value: str | None) -> date | None:
    if not value or value == "full":
        return None
    if len(value) == 6:
        return date(int(value[0:4]), int(value[4:6]), 1)
    if len(value) != 8:
        return None
    return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))


def _month_for_run_date(run_date: date) -> str:
    return run_date.strftime("%Y%m")


def _quarter_end_on_or_before(run_date: date) -> date:
    quarter_month = ((run_date.month - 1) // 3) * 3 + 3
    quarter_end = _last_day_of_month(date(run_date.year, quarter_month, 1))
    if quarter_end <= run_date:
        return quarter_end
    previous_quarter_month = quarter_month - 3
    year = run_date.year
    if previous_quarter_month <= 0:
        year -= 1
        previous_quarter_month += 12
    return _last_day_of_month(date(year, previous_quarter_month, 1))


def _last_day_of_month(month_date: date) -> date:
    if month_date.month == 12:
        next_month = date(month_date.year + 1, 1, 1)
    else:
        next_month = date(month_date.year, month_date.month + 1, 1)
    return next_month - timedelta(days=1)


def _concise_error(exc: Exception) -> str:
    original_error = getattr(exc, "orig", None)
    message = str(original_error or exc).strip()
    return message.splitlines()[0] if message else exc.__class__.__name__
