from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backfill import BackfillBatch
from app.repositories.backfill import (
    BACKFILL_FAILED_STATUS,
    BACKFILL_RUNNING_STATUS,
    BACKFILL_SUCCESS_STATUS,
)
from app.services.data_completeness import CoreMarketCompletenessService
from app.services.market_data_normalization import MarketDataNormalizationService


@dataclass(frozen=True)
class DataRepairPlan:
    start_date: date
    end_date: date
    missing_trade_days: int
    repair_ranges: list[tuple[date, date, int]]


@dataclass(frozen=True)
class DataRepairResult:
    plan: DataRepairPlan
    executed: bool
    daily_quotes: int = 0
    daily_indicators: int = 0
    adj_factors: int = 0


@dataclass(frozen=True)
class BackfillBatchFixResult:
    scanned_batches: int
    fixed_batches: int
    still_failed_batches: int
    stale_running_batches: int


@dataclass(frozen=True)
class CoreMarketRepairSummary:
    data_repair: DataRepairResult
    batch_fix: BackfillBatchFixResult


class CoreMarketDataRepairService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def plan(self, *, start_date: date, end_date: date) -> DataRepairPlan:
        report = CoreMarketCompletenessService(self.session).scan(
            start_date=start_date,
            end_date=end_date,
            layer="app",
            missing_limit=200,
        )
        ranges_by_key = {
            (repair_range.start_date, repair_range.end_date): repair_range.days
            for table in report.tables
            for repair_range in table.repair_ranges
        }
        return DataRepairPlan(
            start_date=start_date,
            end_date=end_date,
            missing_trade_days=report.total_missing_trade_days,
            repair_ranges=[
                (range_start, range_end, days)
                for (range_start, range_end), days in sorted(ranges_by_key.items())
            ],
        )

    def repair(self, *, start_date: date, end_date: date, dry_run: bool = True) -> DataRepairResult:
        plan = self.plan(start_date=start_date, end_date=end_date)
        if dry_run:
            return DataRepairResult(plan=plan, executed=False)

        result = MarketDataNormalizationService(self.session).normalize_daily_market_data(
            start_date=start_date,
            end_date=end_date,
        )
        return DataRepairResult(
            plan=plan,
            executed=True,
            daily_quotes=result.daily_quotes,
            daily_indicators=result.daily_indicators,
            adj_factors=result.adj_factors,
        )

    def repair_and_fix_batches(
        self,
        *,
        start_date: date,
        end_date: date,
        dry_run: bool = True,
        stale_after_minutes: int = 180,
    ) -> CoreMarketRepairSummary:
        data_repair = self.repair(start_date=start_date, end_date=end_date, dry_run=dry_run)
        batch_fix = self.fix_backfill_batches(
            start_date=start_date,
            end_date=end_date,
            dry_run=dry_run,
            stale_after_minutes=stale_after_minutes,
        )
        return CoreMarketRepairSummary(data_repair=data_repair, batch_fix=batch_fix)

    def fix_backfill_batches(
        self,
        *,
        start_date: date,
        end_date: date,
        dry_run: bool = True,
        stale_after_minutes: int = 180,
    ) -> BackfillBatchFixResult:
        batches = self._repairable_batches(
            start_date=start_date,
            end_date=end_date,
            stale_after_minutes=stale_after_minutes,
        )
        fixed_batches = 0
        still_failed_batches = 0
        stale_running_batches = 0
        for batch in batches:
            if batch.status == BACKFILL_RUNNING_STATUS:
                stale_running_batches += 1
            if self._app_data_complete(start_date=batch.start_date, end_date=batch.end_date):
                fixed_batches += 1
                if not dry_run:
                    batch.status = BACKFILL_SUCCESS_STATUS
                    batch.error_message = None
                    batch.finished_at = datetime.now(UTC)
            else:
                still_failed_batches += 1
                if not dry_run and batch.status == BACKFILL_RUNNING_STATUS:
                    batch.status = BACKFILL_FAILED_STATUS
                    batch.error_message = "批次已超时，但归一化数据仍不完整。"
                    batch.finished_at = datetime.now(UTC)

        if not dry_run:
            self.session.commit()

        return BackfillBatchFixResult(
            scanned_batches=len(batches),
            fixed_batches=fixed_batches,
            still_failed_batches=still_failed_batches,
            stale_running_batches=stale_running_batches,
        )

    def _repairable_batches(
        self,
        *,
        start_date: date,
        end_date: date,
        stale_after_minutes: int,
    ) -> list[BackfillBatch]:
        stale_before = datetime.now(UTC) - timedelta(minutes=stale_after_minutes)
        return list(
            self.session.scalars(
                select(BackfillBatch)
                .where(
                    BackfillBatch.start_date.is_not(None),
                    BackfillBatch.end_date.is_not(None),
                    BackfillBatch.start_date >= start_date,
                    BackfillBatch.end_date <= end_date,
                    (
                        (BackfillBatch.status == BACKFILL_FAILED_STATUS)
                        | (
                            (BackfillBatch.status == BACKFILL_RUNNING_STATUS)
                            & (BackfillBatch.started_at < stale_before)
                        )
                    ),
                )
                .order_by(BackfillBatch.started_at.desc(), BackfillBatch.id.desc())
            )
        )

    def _app_data_complete(self, *, start_date: date | None, end_date: date | None) -> bool:
        if start_date is None or end_date is None:
            return False
        report = CoreMarketCompletenessService(self.session).scan(
            start_date=start_date,
            end_date=end_date,
            layer="app",
            missing_limit=1,
        )
        return report.total_missing_trade_days == 0
