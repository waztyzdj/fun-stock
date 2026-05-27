from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.adapters.tushare import TushareInsufficientPointsError
from app.engines.data_sync.tushare.market_data_sync import TushareMarketDataSyncService
from app.models.data_sync import DataSyncJob, DataSyncRun


class FakeTushareClient:
    def __init__(self) -> None:
        self.daily_trade_dates: list[date] = []
        self.daily_basic_trade_dates: list[date] = []
        self.adj_factor_trade_dates: list[date] = []
        self.finance_windows: list[tuple[date, date]] = []

    def stock_basic(self) -> list[dict[str, object]]:
        return [{"ts_code": "000001.SZ", "symbol": "000001", "name": "Ping An Bank"}]

    def trade_cal(
        self,
        *,
        start_date: date,
        end_date: date,
        exchange: str,
    ) -> list[dict[str, object]]:
        return [
            {
                "exchange": exchange,
                "cal_date": start_date,
                "is_open": "1",
                "pretrade_date": None,
            },
            {
                "exchange": exchange,
                "cal_date": end_date,
                "is_open": "1",
                "pretrade_date": start_date,
            },
        ]

    def daily(self, *, trade_date: date) -> list[dict[str, object]]:
        self.daily_trade_dates.append(trade_date)
        return [{"ts_code": "000001.SZ", "trade_date": trade_date, "close": 10}]

    def daily_basic(self, *, trade_date: date) -> list[dict[str, object]]:
        self.daily_basic_trade_dates.append(trade_date)
        return [{"ts_code": "000001.SZ", "trade_date": trade_date, "pe": 8}]

    def adj_factor(self, *, trade_date: date) -> list[dict[str, object]]:
        self.adj_factor_trade_dates.append(trade_date)
        return [{"ts_code": "000001.SZ", "trade_date": trade_date, "adj_factor": 1}]

    def income(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[dict[str, object]]:
        del ts_code
        self.finance_windows.append((start_date, end_date))
        return [{"ts_code": "000001.SZ", "ann_date": start_date, "end_date": end_date}]

    def balancesheet(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[dict[str, object]]:
        del ts_code
        return [{"ts_code": "000001.SZ", "ann_date": start_date, "end_date": end_date}]

    def cashflow_vip(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[dict[str, object]]:
        del ts_code
        return [{"ts_code": "000001.SZ", "ann_date": start_date, "end_date": end_date}]

    def fina_indicator(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[dict[str, object]]:
        del ts_code
        return [{"ts_code": "000001.SZ", "ann_date": start_date, "end_date": end_date}]

    def query_api(
        self,
        api_name: str,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        del kwargs
        return [{"api_name": api_name, "ts_code": "000001.SZ"}]


class InsufficientPointsTushareClient(FakeTushareClient):
    def query_api(
        self,
        api_name: str,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        del api_name, kwargs
        raise TushareInsufficientPointsError("积分不足")


class FakeDataSyncRepository:
    def __init__(self, session: Session) -> None:
        self.jobs: dict[str, DataSyncJob] = {}
        self.quality_checks: list[tuple[str, str]] = []

    def get_or_create_job(
        self,
        *,
        provider: str,
        api_name: str,
        sync_mode: str,
        default_cursor_value: str | None = None,
    ) -> DataSyncJob:
        del provider
        job = self.jobs.get(api_name)
        if job is None:
            job = DataSyncJob(
                id=len(self.jobs) + 1,
                provider="tushare",
                api_name=api_name,
                sync_mode=sync_mode,
                cursor_value=default_cursor_value,
                status="idle",
            )
            self.jobs[api_name] = job
        return job

    def start_run(
        self,
        job: DataSyncJob,
        *,
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> DataSyncRun:
        return DataSyncRun(
            id=1,
            job_id=job.id,
            status="running",
            window_start=window_start,
            window_end=window_end,
            rows_fetched=0,
            rows_upserted=0,
        )

    def mark_success(
        self,
        job: DataSyncJob,
        run: DataSyncRun,
        *,
        rows_fetched: int,
        rows_upserted: int,
        cursor_value: str | None = None,
    ) -> None:
        del run, rows_fetched, rows_upserted
        job.status = "success"
        if cursor_value is not None:
            job.cursor_value = cursor_value

    def mark_failure(self, job: DataSyncJob, run: DataSyncRun, *, error_message: str) -> None:
        del run
        job.status = "failed"
        job.error_message = error_message

    def mark_blocked(self, job: DataSyncJob, run: DataSyncRun, *, error_message: str) -> None:
        del run
        job.status = "blocked_insufficient_points"
        job.error_message = error_message

    def add_quality_check(
        self,
        run: DataSyncRun,
        *,
        check_name: str,
        status: str,
        severity: str,
        message: str | None = None,
        observed_value: str | None = None,
    ) -> object:
        del run, severity, message, observed_value
        self.quality_checks.append((check_name, status))
        return object()


class FakeRawRepository:
    def __init__(self, session: Session) -> None:
        self.upserts: list[tuple[str, int]] = []
        self.open_trade_dates = [date(2026, 1, 2), date(2026, 1, 5)]

    def ensure_tables_exist(self, table_names: list[str]) -> None:
        del table_names

    def upsert(self, table_name: str, records: list[dict[str, Any]]) -> int:
        self.upserts.append((table_name, len(records)))
        return len(records)

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


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeNormalizationService:
    normalized_windows: list[tuple[date | None, date | None]] = []

    def __init__(self, session: Session) -> None:
        del session

    def normalize_core_market_data(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> None:
        self.normalized_windows.append((start_date, end_date))

    def normalize_daily_market_data(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> None:
        self.normalized_windows.append((start_date, end_date))


def test_sync_quote_data_resumes_from_last_daily_cursor(monkeypatch: Any) -> None:
    fake_client = FakeTushareClient()
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.DataSyncRepository",
        FakeDataSyncRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.TushareRawRepository",
        FakeRawRepository,
    )

    service = TushareMarketDataSyncService(
        cast(Session, fake_session),
        client=fake_client,
        normalize=False,
    )
    sync_repository = cast(FakeDataSyncRepository, service.sync_repository)
    sync_repository.get_or_create_job(
        provider="tushare",
        api_name="daily",
        sync_mode="by_trade_date",
        default_cursor_value="20260102",
    )

    summaries = service.sync_quote_data(
        end_date=date(2026, 1, 5),
        max_trade_days=5,
        normalize=False,
    )

    assert [summary.api_name for summary in summaries] == ["daily", "daily_basic", "adj_factor"]
    assert fake_client.daily_trade_dates == [date(2026, 1, 5)]
    assert fake_client.daily_basic_trade_dates == [date(2026, 1, 5)]
    assert fake_client.adj_factor_trade_dates == [date(2026, 1, 5)]
    assert sync_repository.jobs["daily"].cursor_value == "20260105"
    assert sync_repository.jobs["daily_basic"].cursor_value == "20260105"
    assert sync_repository.jobs["adj_factor"].cursor_value == "20260105"
    assert fake_session.commits == 1


def test_sync_quote_data_limits_batch_and_normalizes_each_trade_date(monkeypatch: Any) -> None:
    fake_client = FakeTushareClient()
    fake_session = FakeSession()
    FakeNormalizationService.normalized_windows = []

    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.DataSyncRepository",
        FakeDataSyncRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.TushareRawRepository",
        FakeRawRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.MarketDataNormalizationService",
        FakeNormalizationService,
    )

    service = TushareMarketDataSyncService(
        cast(Session, fake_session),
        client=fake_client,
        normalize=False,
    )

    summaries = service.sync_quote_data(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        max_trade_days=1,
        normalize=True,
    )
    sync_repository = cast(FakeDataSyncRepository, service.sync_repository)

    assert [summary.api_name for summary in summaries] == ["daily", "daily_basic", "adj_factor"]
    assert fake_client.daily_trade_dates == [date(2026, 1, 2)]
    assert fake_client.daily_basic_trade_dates == [date(2026, 1, 2)]
    assert fake_client.adj_factor_trade_dates == [date(2026, 1, 2)]
    assert FakeNormalizationService.normalized_windows == [
        (date(2026, 1, 2), date(2026, 1, 2))
    ]
    assert sync_repository.jobs["daily"].cursor_value == "20260102"
    assert sync_repository.jobs["daily_basic"].cursor_value == "20260102"
    assert sync_repository.jobs["adj_factor"].cursor_value == "20260102"


def test_plan_daily_quote_backfill_returns_next_limited_trade_dates(monkeypatch: Any) -> None:
    fake_client = FakeTushareClient()
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.DataSyncRepository",
        FakeDataSyncRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.TushareRawRepository",
        FakeRawRepository,
    )

    service = TushareMarketDataSyncService(
        cast(Session, fake_session),
        client=fake_client,
        normalize=False,
    )

    plan = service.plan_daily_quote_backfill(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        max_trade_days=1,
    )

    assert plan.cursor_date == date(2026, 1, 1)
    assert plan.end_date == date(2026, 1, 5)
    assert plan.trade_dates == [date(2026, 1, 2)]
    assert plan.next_trade_date == date(2026, 1, 2)


def test_sync_finance_data_uses_announcement_window(monkeypatch: Any) -> None:
    fake_client = FakeTushareClient()
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.DataSyncRepository",
        FakeDataSyncRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.TushareRawRepository",
        FakeRawRepository,
    )

    service = TushareMarketDataSyncService(
        cast(Session, fake_session),
        client=fake_client,
        normalize=False,
    )

    summaries = service.sync_finance_data(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        sleep_seconds=0,
    )

    assert [summary.api_name for summary in summaries] == [
        "income",
        "balancesheet",
        "cashflow_vip",
        "fina_indicator",
    ]
    assert fake_client.finance_windows == [(date(2026, 1, 1), date(2026, 3, 31))]
    assert fake_session.commits == 4


def test_sync_quote_data_window_does_not_advance_incremental_daily_cursor(
    monkeypatch: Any,
) -> None:
    fake_client = FakeTushareClient()
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.DataSyncRepository",
        FakeDataSyncRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.TushareRawRepository",
        FakeRawRepository,
    )

    service = TushareMarketDataSyncService(
        cast(Session, fake_session),
        client=fake_client,
        normalize=False,
    )

    summaries = service.sync_quote_data_window(
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 5),
    )
    sync_repository = cast(FakeDataSyncRepository, service.sync_repository)

    assert [summary.api_name for summary in summaries] == [
        "daily_window",
        "daily_basic_window",
        "adj_factor_window",
        "daily_window",
        "daily_basic_window",
        "adj_factor_window",
    ]
    assert fake_client.daily_trade_dates == [date(2026, 1, 2), date(2026, 1, 5)]
    assert fake_client.daily_basic_trade_dates == [date(2026, 1, 2), date(2026, 1, 5)]
    assert fake_client.adj_factor_trade_dates == [date(2026, 1, 2), date(2026, 1, 5)]
    assert "daily" not in sync_repository.jobs
    assert sync_repository.jobs["daily_window"].cursor_value == "20260105"
    assert sync_repository.jobs["daily_basic_window"].cursor_value == "20260105"
    assert sync_repository.jobs["adj_factor_window"].cursor_value == "20260105"


def test_sync_registered_api_records_quality_checks(monkeypatch: Any) -> None:
    fake_client = FakeTushareClient()
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.DataSyncRepository",
        FakeDataSyncRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.TushareRawRepository",
        FakeRawRepository,
    )

    service = TushareMarketDataSyncService(
        cast(Session, fake_session),
        client=fake_client,
        normalize=False,
    )
    service.sync_registered_api(api_name="daily", trade_date=date(2026, 1, 2))
    sync_repository = cast(FakeDataSyncRepository, service.sync_repository)

    assert ("row_count", "passed") in sync_repository.quality_checks
    assert ("upsert_count", "passed") in sync_repository.quality_checks


def test_sync_registered_api_marks_insufficient_points_without_retry(monkeypatch: Any) -> None:
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.DataSyncRepository",
        FakeDataSyncRepository,
    )
    monkeypatch.setattr(
        "app.engines.data_sync.tushare.market_data_sync.TushareRawRepository",
        FakeRawRepository,
    )

    service = TushareMarketDataSyncService(
        cast(Session, fake_session),
        client=InsufficientPointsTushareClient(),
        normalize=False,
    )

    try:
        service.sync_registered_api(api_name="daily", trade_date=date(2026, 1, 2))
    except TushareInsufficientPointsError:
        pass
    else:
        raise AssertionError("Expected TushareInsufficientPointsError")

    sync_repository = cast(FakeDataSyncRepository, service.sync_repository)
    assert sync_repository.jobs["daily"].status == "blocked_insufficient_points"
    assert fake_session.commits == 1
