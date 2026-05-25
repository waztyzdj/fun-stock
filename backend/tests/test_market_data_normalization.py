from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.services.market_data_normalization import MarketDataNormalizationService


class FakeRepository:
    def __init__(self) -> None:
        self.daily_quote_start_date: date | None = None
        self.daily_quote_end_date: date | None = None

    def upsert_stocks_from_tushare(self) -> int:
        return 2

    def upsert_trade_calendars_from_tushare(self) -> int:
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


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


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
