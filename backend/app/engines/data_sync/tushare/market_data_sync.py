from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from time import sleep

from sqlalchemy.orm import Session

from app.adapters.tushare import (
    TushareClient,
    TushareDataClient,
    TushareInsufficientPointsError,
)
from app.adapters.tushare.registry import TUSHARE_API_SPECS_BY_NAME
from app.models.data_sync import DataSyncJob
from app.repositories.data_sync import DataSyncRepository
from app.repositories.tushare_raw import TushareRawRepository
from app.services.data_quality import DataQualityContext, TushareDataQualityService
from app.services.market_data_normalization import MarketDataNormalizationService

PROVIDER = "tushare"
DEFAULT_START_DATE = date(2000, 1, 1)
TRADE_CALENDAR_EXCHANGE = "SSE"
QUOTE_DAILY_TABLES = ("daily", "daily_basic", "adj_factor")
FINANCE_TABLES = ("income", "balancesheet", "cashflow_vip", "fina_indicator")


@dataclass(frozen=True)
class SyncSummary:
    api_name: str
    rows_fetched: int
    rows_upserted: int


@dataclass(frozen=True)
class TushareMarketDataSyncResult:
    summaries: list[SyncSummary]

    @property
    def rows_fetched(self) -> int:
        return sum(summary.rows_fetched for summary in self.summaries)

    @property
    def rows_upserted(self) -> int:
        return sum(summary.rows_upserted for summary in self.summaries)


@dataclass(frozen=True)
class DailyQuoteBackfillPlan:
    cursor_date: date
    end_date: date
    trade_dates: list[date]

    @property
    def next_trade_date(self) -> date | None:
        if not self.trade_dates:
            return None
        return self.trade_dates[0]


@dataclass(frozen=True)
class QuoteApiPayload:
    api_name: str
    table_name: str
    records: list[dict[str, object]]


class TushareMarketDataSyncService:
    def __init__(
        self,
        session: Session,
        *,
        client: TushareDataClient | None = None,
        normalize: bool = True,
    ) -> None:
        self.session = session
        self.client = client or TushareClient()
        self.normalize = normalize
        self.sync_repository = DataSyncRepository(session)
        self.raw_repository = TushareRawRepository(session)
        self.quality_service = TushareDataQualityService()

    def sync_registered_api(
        self,
        *,
        api_name: str,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        ts_code: str | None = None,
        month: str | None = None,
    ) -> SyncSummary:
        spec = TUSHARE_API_SPECS_BY_NAME[api_name]
        self.raw_repository.ensure_tables_exist([spec.table_name])
        window_start = self._window_value(start_date or trade_date, month)
        window_end = self._window_value(end_date or trade_date, month)
        cursor_value = self._window_value(end_date or trade_date, month)
        try:
            records = self.client.query_api(
                api_name,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                ts_code=ts_code,
                month=month,
            )
        except TushareInsufficientPointsError as exc:
            self._mark_prefetch_blocked(
                api_name=api_name,
                window_start=window_start,
                window_end=window_end,
                error_message=str(exc),
                sync_mode="manual_probe",
            )
            raise
        except Exception as exc:
            self._mark_prefetch_failure(
                api_name=api_name,
                window_start=window_start,
                window_end=window_end,
                error_message=str(exc),
                sync_mode="manual_probe",
            )
            raise
        return self._sync_window_table(
            api_name=api_name,
            table_name=spec.table_name,
            records=records,
            window_start=window_start,
            window_end=window_end,
            cursor_value=cursor_value,
            sync_mode="manual_probe",
        )

    def _mark_prefetch_blocked(
        self,
        *,
        api_name: str,
        window_start: str | None,
        window_end: str | None,
        error_message: str,
        sync_mode: str,
    ) -> None:
        job = self.sync_repository.get_or_create_job(
            provider=PROVIDER,
            api_name=api_name,
            sync_mode=sync_mode,
        )
        run = self.sync_repository.start_run(
            job,
            window_start=window_start,
            window_end=window_end,
        )
        self.sync_repository.mark_blocked(job, run, error_message=error_message)
        self.session.commit()

    def _mark_prefetch_failure(
        self,
        *,
        api_name: str,
        window_start: str | None,
        window_end: str | None,
        error_message: str,
        sync_mode: str,
    ) -> None:
        job = self.sync_repository.get_or_create_job(
            provider=PROVIDER,
            api_name=api_name,
            sync_mode=sync_mode,
        )
        run = self.sync_repository.start_run(
            job,
            window_start=window_start,
            window_end=window_end,
        )
        self.sync_repository.mark_failure(job, run, error_message=error_message)
        self.session.commit()

    def sync_all(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        finance_lookback_days: int = 90,
    ) -> TushareMarketDataSyncResult:
        effective_end_date = end_date or date.today()
        summaries = [
            self.sync_basic_data(
                start_date=start_date or DEFAULT_START_DATE,
                end_date=effective_end_date,
            ),
            *self.sync_quote_data(end_date=effective_end_date),
            *self.sync_finance_data(
                start_date=start_date or effective_end_date - timedelta(days=finance_lookback_days),
                end_date=effective_end_date,
            ),
        ]
        if self.normalize:
            MarketDataNormalizationService(self.session).normalize_core_market_data(
                start_date=start_date,
                end_date=effective_end_date,
            )
        return TushareMarketDataSyncResult(summaries=summaries)

    def sync_basic_data(self, *, start_date: date, end_date: date) -> SyncSummary:
        self.raw_repository.ensure_tables_exist(["stock_basic", "trade_cal"])
        stock_summary = self._sync_full_table(
            api_name="stock_basic",
            table_name="stock_basic",
            records=self.client.stock_basic(),
        )
        trade_cal_summary = self._sync_window_table(
            api_name="trade_cal",
            table_name="trade_cal",
            records=self.client.trade_cal(
                start_date=start_date,
                end_date=end_date,
                exchange=TRADE_CALENDAR_EXCHANGE,
            ),
            window_start=self._format_date(start_date),
            window_end=self._format_date(end_date),
            cursor_value=self._format_date(end_date),
        )
        return SyncSummary(
            api_name="basic_data",
            rows_fetched=stock_summary.rows_fetched + trade_cal_summary.rows_fetched,
            rows_upserted=stock_summary.rows_upserted + trade_cal_summary.rows_upserted,
        )

    def plan_daily_quote_backfill(
        self,
        *,
        end_date: date,
        max_trade_days: int,
        start_date: date | None = None,
    ) -> DailyQuoteBackfillPlan:
        if max_trade_days <= 0:
            msg = "max_trade_days must be greater than 0."
            raise ValueError(msg)
        job = self.sync_repository.get_or_create_job(
            provider=PROVIDER,
            api_name="daily",
            sync_mode="by_trade_date",
            default_cursor_value=self._format_date(start_date or DEFAULT_START_DATE),
        )
        cursor_date = self._parse_cursor_date(job.cursor_value) or DEFAULT_START_DATE
        if start_date is not None and cursor_date < start_date:
            cursor_date = start_date - timedelta(days=1)
        trade_dates = self.raw_repository.get_open_trade_dates_after(
            exchange=TRADE_CALENDAR_EXCHANGE,
            after_date=cursor_date,
            end_date=end_date,
        )
        return DailyQuoteBackfillPlan(
            cursor_date=cursor_date,
            end_date=end_date,
            trade_dates=trade_dates[:max_trade_days],
        )

    def sync_quote_data(
        self,
        *,
        end_date: date,
        max_trade_days: int = 5,
        start_date: date | None = None,
        sleep_seconds: float = 0,
        normalize: bool = True,
    ) -> list[SyncSummary]:
        self.raw_repository.ensure_tables_exist(list(QUOTE_DAILY_TABLES))
        plan = self.plan_daily_quote_backfill(
            end_date=end_date,
            max_trade_days=max_trade_days,
            start_date=start_date,
        )
        summaries: list[SyncSummary] = []
        for trade_date in plan.trade_dates:
            summaries.extend(self._sync_quote_trade_date_batch(trade_date=trade_date))
            if normalize:
                MarketDataNormalizationService(self.session).normalize_core_market_data(
                    start_date=trade_date,
                    end_date=trade_date,
                )
            if sleep_seconds > 0:
                sleep(sleep_seconds)
        return summaries

    def sync_quote_data_window(self, *, start_date: date, end_date: date) -> list[SyncSummary]:
        self.raw_repository.ensure_tables_exist(list(QUOTE_DAILY_TABLES))
        trade_dates = self.raw_repository.get_open_trade_dates_after(
            exchange=TRADE_CALENDAR_EXCHANGE,
            after_date=start_date - timedelta(days=1),
            end_date=end_date,
        )
        summaries: list[SyncSummary] = []
        for trade_date in trade_dates:
            summaries.extend(self.sync_quote_trade_date_all(trade_date=trade_date))
        return summaries

    def sync_quote_trade_date(self, *, trade_date: date) -> SyncSummary:
        return self.sync_quote_trade_date_all(trade_date=trade_date)[0]

    def sync_quote_trade_date_all(self, *, trade_date: date) -> list[SyncSummary]:
        self.raw_repository.ensure_tables_exist(list(QUOTE_DAILY_TABLES))
        return [
            self._sync_window_table(
                api_name="daily_window",
                table_name="daily",
                records=self.client.daily(trade_date=trade_date),
                window_start=self._format_date(trade_date),
                window_end=self._format_date(trade_date),
                cursor_value=self._format_date(trade_date),
                sync_mode="by_trade_date_window",
            ),
            self._sync_window_table(
                api_name="daily_basic_window",
                table_name="daily_basic",
                records=self.client.daily_basic(trade_date=trade_date),
                window_start=self._format_date(trade_date),
                window_end=self._format_date(trade_date),
                cursor_value=self._format_date(trade_date),
                sync_mode="by_trade_date_window",
            ),
            self._sync_window_table(
                api_name="adj_factor_window",
                table_name="adj_factor",
                records=self.client.adj_factor(trade_date=trade_date),
                window_start=self._format_date(trade_date),
                window_end=self._format_date(trade_date),
                cursor_value=self._format_date(trade_date),
                sync_mode="by_trade_date_window",
            ),
        ]

    def _sync_quote_trade_date_batch(self, *, trade_date: date) -> list[SyncSummary]:
        window = self._format_date(trade_date)
        payloads = [
            QuoteApiPayload("daily", "daily", self.client.daily(trade_date=trade_date)),
            QuoteApiPayload(
                "daily_basic",
                "daily_basic",
                self.client.daily_basic(trade_date=trade_date),
            ),
            QuoteApiPayload(
                "adj_factor",
                "adj_factor",
                self.client.adj_factor(trade_date=trade_date),
            ),
        ]
        jobs_and_runs = [
            (
                self.sync_repository.get_or_create_job(
                    provider=PROVIDER,
                    api_name=payload.api_name,
                    sync_mode="by_trade_date",
                    default_cursor_value=window,
                ),
                payload,
            )
            for payload in payloads
        ]
        runs = [
            (
                job,
                payload,
                self.sync_repository.start_run(job, window_start=window, window_end=window),
            )
            for job, payload in jobs_and_runs
        ]
        try:
            summaries: list[SyncSummary] = []
            for job, payload, run in runs:
                rows_upserted = self.raw_repository.upsert(payload.table_name, payload.records)
                self.sync_repository.mark_success(
                    job,
                    run,
                    rows_fetched=len(payload.records),
                    rows_upserted=rows_upserted,
                    cursor_value=window,
                )
                summaries.append(
                    SyncSummary(
                        api_name=job.api_name,
                        rows_fetched=len(payload.records),
                        rows_upserted=rows_upserted,
                    )
                )
            self.session.commit()
            return summaries
        except Exception as exc:
            self.session.rollback()
            for job, _payload in jobs_and_runs:
                failure_run = self.sync_repository.start_run(
                    job,
                    window_start=window,
                    window_end=window,
                )
                self.sync_repository.mark_failure(job, failure_run, error_message=str(exc))
            self.session.commit()
            raise

    def sync_finance_data(
        self,
        *,
        start_date: date,
        end_date: date,
        sleep_seconds: float = 65,
    ) -> list[SyncSummary]:
        return self.sync_finance_data_for_stock(
            ts_code="000001.SZ",
            start_date=start_date,
            end_date=end_date,
            sleep_seconds=sleep_seconds,
        )

    def sync_finance_data_for_stock(
        self,
        *,
        ts_code: str,
        start_date: date,
        end_date: date,
        sleep_seconds: float = 65,
        api_names: tuple[str, ...] = FINANCE_TABLES,
    ) -> list[SyncSummary]:
        self.raw_repository.ensure_tables_exist(list(FINANCE_TABLES))
        unknown_api_names = set(api_names) - set(FINANCE_TABLES)
        if unknown_api_names:
            msg = f"Unsupported finance APIs: {', '.join(sorted(unknown_api_names))}"
            raise ValueError(msg)
        finance_fetchers: list[tuple[str, str, Callable[[], list[dict[str, object]]]]] = [
            (
                "income",
                "income",
                lambda: self.client.income(
                    start_date=start_date,
                    end_date=end_date,
                    ts_code=ts_code,
                ),
            ),
            (
                "balancesheet",
                "balancesheet",
                lambda: self.client.balancesheet(
                    start_date=start_date,
                    end_date=end_date,
                    ts_code=ts_code,
                ),
            ),
            (
                "cashflow_vip",
                "cashflow_vip",
                lambda: self.client.cashflow_vip(
                    start_date=start_date,
                    end_date=end_date,
                    ts_code=ts_code,
                ),
            ),
            (
                "fina_indicator",
                "fina_indicator",
                lambda: self.client.fina_indicator(
                    start_date=start_date,
                    end_date=end_date,
                    ts_code=ts_code,
                ),
            ),
        ]
        finance_fetchers = [
            (api_name, table_name, fetch)
            for api_name, table_name, fetch in finance_fetchers
            if api_name in api_names
        ]
        summaries: list[SyncSummary] = []
        for index, (api_name, table_name, fetch) in enumerate(finance_fetchers):
            summaries.append(
                self._sync_window_table(
                    api_name=api_name,
                    table_name=table_name,
                    records=fetch(),
                    window_start=self._format_date(start_date),
                    window_end=self._format_date(end_date),
                    cursor_value=self._format_date(end_date),
                )
            )
            if sleep_seconds > 0 and index < len(finance_fetchers) - 1:
                sleep(sleep_seconds)
        return summaries

    def _sync_full_table(
        self,
        *,
        api_name: str,
        table_name: str,
            records: list[dict[str, object]],
    ) -> SyncSummary:
        return self._sync_window_table(
            api_name=api_name,
            table_name=table_name,
            records=records,
            window_start=None,
            window_end=None,
            cursor_value="full",
            sync_mode="full",
        )

    def _sync_window_table(
        self,
        *,
        api_name: str,
        table_name: str,
        records: list[dict[str, object]],
        window_start: str | None,
        window_end: str | None,
        cursor_value: str | None,
        sync_mode: str = "window",
    ) -> SyncSummary:
        job = self.sync_repository.get_or_create_job(
            provider=PROVIDER,
            api_name=api_name,
            sync_mode=sync_mode,
        )
        return self._sync_existing_job_window(
            job=job,
            table_name=table_name,
            records=records,
            window_start=window_start,
            window_end=window_end,
            cursor_value=cursor_value,
        )

    def _sync_existing_job_window(
        self,
        *,
        job: DataSyncJob,
        table_name: str,
        records: list[dict[str, object]],
        window_start: str | None,
        window_end: str | None,
        cursor_value: str | None,
    ) -> SyncSummary:
        run = self.sync_repository.start_run(
            job,
            window_start=window_start,
            window_end=window_end,
        )
        try:
            rows_upserted = self.raw_repository.upsert(table_name, records)
            quality_results = self.quality_service.evaluate(
                DataQualityContext(
                    api_name=job.api_name,
                    table_name=table_name,
                    records=records,
                    rows_upserted=rows_upserted,
                    window_start=window_start,
                    window_end=window_end,
                )
            )
            for result in quality_results:
                self.sync_repository.add_quality_check(
                    run,
                    check_name=result.check_name,
                    status=result.status,
                    severity=result.severity,
                    message=result.message,
                    observed_value=result.observed_value,
                )
            self.sync_repository.mark_success(
                job,
                run,
                rows_fetched=len(records),
                rows_upserted=rows_upserted,
                cursor_value=cursor_value,
            )
            self.session.commit()
            return SyncSummary(
                api_name=job.api_name,
                rows_fetched=len(records),
                rows_upserted=rows_upserted,
            )
        except TushareInsufficientPointsError as exc:
            self.session.rollback()
            blocked_job = self.sync_repository.get_or_create_job(
                provider=PROVIDER,
                api_name=job.api_name,
                sync_mode=job.sync_mode,
            )
            blocked_run = self.sync_repository.start_run(
                blocked_job,
                window_start=window_start,
                window_end=window_end,
            )
            self.sync_repository.mark_blocked(blocked_job, blocked_run, error_message=str(exc))
            self.session.commit()
            raise
        except Exception as exc:
            self.session.rollback()
            failure_job = self.sync_repository.get_or_create_job(
                provider=PROVIDER,
                api_name=job.api_name,
                sync_mode=job.sync_mode,
            )
            failure_run = self.sync_repository.start_run(
                failure_job,
                window_start=window_start,
                window_end=window_end,
            )
            self.sync_repository.mark_failure(failure_job, failure_run, error_message=str(exc))
            self.session.commit()
            raise

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%Y%m%d")

    @staticmethod
    def _window_value(value: date | None, month: str | None) -> str | None:
        if value is not None:
            return value.strftime("%Y%m%d")
        return month

    @staticmethod
    def _parse_cursor_date(value: str | None) -> date | None:
        if not value or value == "full":
            return None
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
