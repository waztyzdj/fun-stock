from datetime import date
from typing import cast

from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.adapters.tushare import TushareInsufficientPointsError
from app.adapters.tushare.registry import TUSHARE_API_SPECS
from app.engines.data_sync.tushare.market_data_sync import TushareMarketDataSyncService
from app.engines.data_sync.tushare.scheduler import (
    TUSHARE_SYNC_PLANS,
    TushareScheduleKind,
    TushareSchedulerRunResult,
    TushareSyncPlan,
    TushareSyncScheduler,
)
from app.models.data_sync import DataSyncJob


class FakeDataSyncRepository:
    def __init__(self, session: Session) -> None:
        self.jobs: dict[str, DataSyncJob] = getattr(session, "jobs", {})

    def get_job(self, *, provider: str, api_name: str) -> DataSyncJob | None:
        del provider
        return self.jobs.get(api_name)


class FakeSession:
    def __init__(self) -> None:
        self.jobs: dict[str, DataSyncJob] = {}


class FakeTushareService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.raw_repository = FakeRawRepository()

    def sync_registered_api(
        self,
        *,
        api_name: str,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        ts_code: str | None = None,
        month: str | None = None,
    ) -> object:
        self.calls.append(
            {
                "api_name": api_name,
                "trade_date": trade_date,
                "start_date": start_date,
                "end_date": end_date,
                "ts_code": ts_code,
                "month": month,
            }
        )
        return type(
            "Summary",
            (),
            {"api_name": api_name, "rows_fetched": 2, "rows_upserted": 1},
        )()


class InsufficientPointsService(FakeTushareService):
    def sync_registered_api(
        self,
        *,
        api_name: str,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        ts_code: str | None = None,
        month: str | None = None,
    ) -> object:
        del api_name, trade_date, start_date, end_date, ts_code, month
        raise TushareInsufficientPointsError("积分不足")


class FakeRawRepository:
    def __init__(self) -> None:
        self.open_trade_dates = [date(2026, 5, 22)]

    def get_open_trade_dates_after(
        self,
        *,
        exchange: str,
        after_date: date,
        end_date: date,
    ) -> list[date]:
        del exchange
        return [
            trade_date
            for trade_date in self.open_trade_dates
            if after_date < trade_date <= end_date
        ]


def test_default_scheduler_plans_cover_every_registered_tushare_api() -> None:
    registered_api_names = {spec.api_name for spec in TUSHARE_API_SPECS}
    planned_api_names = {plan.api_name for plan in TUSHARE_SYNC_PLANS}

    assert planned_api_names == registered_api_names
    assert len(TUSHARE_SYNC_PLANS) == 38


def test_scheduler_plan_due_windows_skips_manual_apis_by_default(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    scheduler = TushareSyncScheduler(
        cast(Session, FakeSession()),
        service=cast(TushareMarketDataSyncService, FakeTushareService()),
    )

    windows = scheduler.plan_due_windows(run_date=date(2026, 5, 24))
    api_names = {window.api_name for window in windows}

    assert "rt_min" not in api_names
    assert "stk_mins" not in api_names
    assert "daily" in api_names


def test_scheduler_dry_run_does_not_call_sync_service(monkeypatch: MonkeyPatch) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    fake_service = FakeTushareService()
    plans = (
        TushareSyncPlan(api_name="daily", schedule=TushareScheduleKind.DAILY, priority=1),
        TushareSyncPlan(
            api_name="stock_basic",
            schedule=TushareScheduleKind.WEEKLY,
            priority=2,
        ),
    )

    scheduler = TushareSyncScheduler(
        cast(Session, FakeSession()),
        plans=plans,
        service=cast(TushareMarketDataSyncService, fake_service),
    )
    result = scheduler.run_once(
        run_date=date(2026, 5, 24),
        dry_run=True,
    )

    assert isinstance(result, TushareSchedulerRunResult)
    assert result.skipped == 2
    assert fake_service.calls == []


def test_scheduler_run_once_passes_params_by_api_mode(monkeypatch: MonkeyPatch) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    fake_service = FakeTushareService()
    plans = (
        TushareSyncPlan(api_name="daily", schedule=TushareScheduleKind.DAILY, priority=1),
        TushareSyncPlan(
            api_name="income",
            schedule=TushareScheduleKind.WEEKLY,
            priority=2,
            lookback_days=120,
        ),
        TushareSyncPlan(
            api_name="ggt_monthly",
            schedule=TushareScheduleKind.MONTHLY,
            priority=3,
        ),
    )

    scheduler = TushareSyncScheduler(
        cast(Session, FakeSession()),
        plans=plans,
        service=cast(TushareMarketDataSyncService, fake_service),
        ts_code="000001.SZ",
    )
    result = scheduler.run_once(run_date=date(2026, 5, 24))

    assert result.successes == 3
    assert fake_service.calls == [
        {
            "api_name": "daily",
            "trade_date": date(2026, 5, 22),
            "start_date": None,
            "end_date": None,
            "ts_code": None,
            "month": None,
        },
        {
            "api_name": "income",
            "trade_date": None,
            "start_date": date(2026, 1, 24),
            "end_date": date(2026, 5, 24),
            "ts_code": "000001.SZ",
            "month": None,
        },
        {
            "api_name": "ggt_monthly",
            "trade_date": None,
            "start_date": None,
            "end_date": None,
            "ts_code": None,
            "month": "202605",
        },
    ]


def test_scheduler_uses_latest_open_trade_date_before_weekend(monkeypatch: MonkeyPatch) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    fake_service = FakeTushareService()
    plans = (TushareSyncPlan(api_name="daily", schedule=TushareScheduleKind.DAILY, priority=1),)

    scheduler = TushareSyncScheduler(
        cast(Session, FakeSession()),
        plans=plans,
        service=cast(TushareMarketDataSyncService, fake_service),
    )

    windows = scheduler.plan_due_windows(run_date=date(2026, 5, 24))

    assert windows[0].trade_date == date(2026, 5, 22)


def test_core_daily_tables_share_daily_cursor(monkeypatch: MonkeyPatch) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    fake_session = FakeSession()
    fake_session.jobs["daily"] = DataSyncJob(
        id=1,
        provider="tushare",
        api_name="daily",
        sync_mode="by_trade_date",
        cursor_value="20260520",
        status="success",
    )
    fake_service = FakeTushareService()
    fake_service.raw_repository.open_trade_dates = [date(2026, 5, 21), date(2026, 5, 22)]
    plans = (
        TushareSyncPlan(api_name="daily", schedule=TushareScheduleKind.DAILY, priority=1),
        TushareSyncPlan(api_name="daily_basic", schedule=TushareScheduleKind.DAILY, priority=2),
        TushareSyncPlan(api_name="adj_factor", schedule=TushareScheduleKind.DAILY, priority=3),
        TushareSyncPlan(api_name="index_daily", schedule=TushareScheduleKind.DAILY, priority=4),
    )

    scheduler = TushareSyncScheduler(
        cast(Session, fake_session),
        plans=plans,
        service=cast(TushareMarketDataSyncService, fake_service),
    )

    windows = scheduler.plan_due_windows(run_date=date(2026, 5, 24))

    assert [window.api_name for window in windows] == [
        "daily",
        "daily_basic",
        "adj_factor",
        "index_daily",
    ]
    assert {window.trade_date for window in windows} == {date(2026, 5, 21)}


def test_scheduler_marks_insufficient_points_as_blocked(monkeypatch: MonkeyPatch) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    plans = (TushareSyncPlan(api_name="income", schedule=TushareScheduleKind.WEEKLY, priority=1),)
    scheduler = TushareSyncScheduler(
        cast(Session, FakeSession()),
        plans=plans,
        service=cast(TushareMarketDataSyncService, InsufficientPointsService()),
    )

    result = scheduler.run_once(run_date=date(2026, 5, 24))

    assert result.blocked == 1
    assert result.failures == 0
    assert result.items[0].status == "blocked_insufficient_points"


def test_scheduler_skips_blocked_jobs_until_manual_recovery(monkeypatch: MonkeyPatch) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    fake_session = FakeSession()
    fake_session.jobs["income"] = DataSyncJob(
        id=1,
        provider="tushare",
        api_name="income",
        sync_mode="by_ts_code_window",
        cursor_value=None,
        status="blocked_insufficient_points",
    )
    fake_service = FakeTushareService()
    plans = (TushareSyncPlan(api_name="income", schedule=TushareScheduleKind.WEEKLY, priority=1),)
    scheduler = TushareSyncScheduler(
        cast(Session, fake_session),
        plans=plans,
        service=cast(TushareMarketDataSyncService, fake_service),
    )

    result = scheduler.run_once(
        run_date=date(2026, 5, 24),
        api_names={"income"},
        force_selected=True,
    )

    assert result.items == []
    assert fake_service.calls == []


def test_scheduler_force_selected_retries_failed_job_even_when_not_due(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.engines.data_sync.tushare import scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "DataSyncRepository", FakeDataSyncRepository)
    fake_session = FakeSession()
    fake_session.jobs["income"] = DataSyncJob(
        id=1,
        provider="tushare",
        api_name="income",
        sync_mode="by_ts_code_window",
        cursor_value="20260524",
        status="failed",
    )
    fake_service = FakeTushareService()
    plans = (TushareSyncPlan(api_name="income", schedule=TushareScheduleKind.WEEKLY, priority=1),)
    scheduler = TushareSyncScheduler(
        cast(Session, fake_session),
        plans=plans,
        service=cast(TushareMarketDataSyncService, fake_service),
    )

    result = scheduler.run_once(
        run_date=date(2026, 5, 24),
        api_names={"income"},
        force_selected=True,
    )

    assert result.successes == 1
    assert fake_service.calls[0]["api_name"] == "income"
