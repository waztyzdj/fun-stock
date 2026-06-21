from datetime import date
from typing import cast

from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.services.data_repair import CoreMarketDataRepairService


class FakeCompletenessService:
    def __init__(self, session: object) -> None:
        del session

    def scan(
        self,
        *,
        start_date: date,
        end_date: date,
        layer: str,
        missing_limit: int,
    ) -> object:
        del layer, missing_limit
        range_item = type(
            "Range",
            (),
            {"start_date": start_date, "end_date": end_date, "days": 2},
        )()
        table = type(
            "Table",
            (),
            {"repair_ranges": [range_item], "missing_trade_days": 2},
        )()
        return type("Report", (), {"tables": [table], "total_missing_trade_days": 2})()


class FakeNormalizationService:
    called = False

    def __init__(self, session: object) -> None:
        del session

    def normalize_daily_market_data(self, *, start_date: date, end_date: date) -> object:
        FakeNormalizationService.called = True
        del start_date, end_date
        return type(
            "Result",
            (),
            {
                "daily_quotes": 1,
                "index_daily_quotes": 4,
                "daily_indicators": 2,
                "adj_factors": 3,
            },
        )()


class FakeBatch:
    def __init__(self, *, status: str, start_date: date, end_date: date) -> None:
        self.status = status
        self.start_date = start_date
        self.end_date = end_date
        self.error_message: str | None = "failed"
        self.finished_at = None


class FakeBatchSession:
    committed = False

    def __init__(self, batches: list[FakeBatch]) -> None:
        self.batches = batches

    def scalars(self, statement: object) -> object:
        del statement
        return self.batches

    def commit(self) -> None:
        self.committed = True


def test_repair_dry_run_only_returns_plan(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.data_repair.CoreMarketCompletenessService",
        FakeCompletenessService,
    )
    monkeypatch.setattr(
        "app.services.data_repair.MarketDataNormalizationService",
        FakeNormalizationService,
    )
    FakeNormalizationService.called = False

    result = CoreMarketDataRepairService(cast(Session, object())).repair(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        dry_run=True,
    )

    assert result.executed is False
    assert result.plan.missing_trade_days == 2
    assert FakeNormalizationService.called is False


def test_repair_executes_daily_normalization(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.data_repair.CoreMarketCompletenessService",
        FakeCompletenessService,
    )
    monkeypatch.setattr(
        "app.services.data_repair.MarketDataNormalizationService",
        FakeNormalizationService,
    )
    FakeNormalizationService.called = False

    result = CoreMarketDataRepairService(cast(Session, object())).repair(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        dry_run=False,
    )

    assert result.executed is True
    assert result.daily_quotes == 1
    assert result.index_daily_quotes == 4
    assert result.daily_indicators == 2
    assert result.adj_factors == 3
    assert FakeNormalizationService.called is True


def test_fix_backfill_batches_marks_complete_failed_batch_success(
    monkeypatch: MonkeyPatch,
) -> None:
    batch = FakeBatch(
        status="failed",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
    )
    session = FakeBatchSession([batch])
    monkeypatch.setattr(
        CoreMarketDataRepairService,
        "_app_data_complete",
        lambda self, start_date, end_date: True,
    )

    result = CoreMarketDataRepairService(cast(Session, session)).fix_backfill_batches(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        dry_run=False,
    )

    assert result.scanned_batches == 1
    assert result.fixed_batches == 1
    assert result.still_failed_batches == 0
    assert batch.status == "success"
    assert batch.error_message is None
    assert session.committed is True
