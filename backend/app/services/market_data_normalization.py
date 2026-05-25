from datetime import date

from sqlalchemy.orm import Session

from app.repositories.market_data import MarketDataRepository, NormalizationResult


class MarketDataNormalizationService:
    def __init__(self, session: Session) -> None:
        self.repository = MarketDataRepository(session)
        self.session = session

    def normalize_core_market_data(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> NormalizationResult:
        stocks = self.repository.upsert_stocks_from_tushare()
        trade_calendars = self.repository.upsert_trade_calendars_from_tushare()
        daily_quotes = self.repository.upsert_daily_quotes_from_tushare(
            start_date=start_date,
            end_date=end_date,
        )
        self.session.commit()
        return NormalizationResult(
            stocks=stocks,
            trade_calendars=trade_calendars,
            daily_quotes=daily_quotes,
        )

