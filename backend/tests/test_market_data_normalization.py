from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.services.market_data_normalization import MarketDataNormalizationService


class FakeRepository:
    def __init__(self) -> None:
        self.daily_quote_start_date: date | None = None
        self.daily_quote_end_date: date | None = None
        self.stock_upserts = 0
        self.trade_calendar_upserts = 0

    def upsert_stocks_from_tushare(self) -> int:
        self.stock_upserts += 1
        return 2

    def upsert_trade_calendars_from_tushare(self) -> int:
        self.trade_calendar_upserts += 1
        return 3

    def upsert_daily_quotes_from_tushare(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        self.daily_quote_start_date = start_date
        self.daily_quote_end_date = end_date
        return 5

    def upsert_daily_indicators_from_tushare(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        del start_date, end_date
        return 7

    def upsert_adj_factors_from_tushare(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        del start_date, end_date
        return 11


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.commit_count = 0

    def commit(self) -> None:
        self.committed = True
        self.commit_count += 1


def test_normalize_core_market_data_commits_and_returns_counts(monkeypatch: Any) -> None:
    fake_repository = FakeRepository()
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.services.market_data_normalization.MarketDataRepository",
        lambda session: fake_repository,
    )

    service = MarketDataNormalizationService(cast(Session, fake_session))

    result = service.normalize_core_market_data(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert fake_session.committed is True
    assert fake_repository.daily_quote_start_date == date(2026, 1, 1)
    assert fake_repository.daily_quote_end_date == date(2026, 1, 31)
    assert result.stocks == 2
    assert result.trade_calendars == 3
    assert result.daily_quotes == 5
    assert result.daily_indicators == 7
    assert result.adj_factors == 11


def test_normalize_daily_market_data_skips_dimension_tables(monkeypatch: Any) -> None:
    fake_repository = FakeRepository()
    fake_session = FakeSession()

    monkeypatch.setattr(
        "app.services.market_data_normalization.MarketDataRepository",
        lambda session: fake_repository,
    )

    service = MarketDataNormalizationService(cast(Session, fake_session))

    result = service.normalize_daily_market_data(
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 5),
    )

    assert fake_repository.stock_upserts == 0
    assert fake_repository.trade_calendar_upserts == 0
    assert fake_repository.daily_quote_start_date == date(2026, 1, 5)
    assert fake_repository.daily_quote_end_date == date(2026, 1, 5)
    assert fake_session.commit_count == 3
    assert result.stocks == 0
    assert result.trade_calendars == 0
    assert result.daily_quotes == 5
    assert result.daily_indicators == 7
    assert result.adj_factors == 11
