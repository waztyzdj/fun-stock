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
        daily_indicators = self.repository.upsert_daily_indicators_from_tushare(
            start_date=start_date,
            end_date=end_date,
        )
        adj_factors = self.repository.upsert_adj_factors_from_tushare(
            start_date=start_date,
            end_date=end_date,
        )
        self.session.commit()
        return NormalizationResult(
            stocks=stocks,
            trade_calendars=trade_calendars,
            daily_quotes=daily_quotes,
            daily_indicators=daily_indicators,
            adj_factors=adj_factors,
        )

    def normalize_daily_market_data(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> NormalizationResult:
        daily_quotes = self.repository.upsert_daily_quotes_from_tushare(
            start_date=start_date,
            end_date=end_date,
        )
        self.session.commit()

        daily_indicators = self.repository.upsert_daily_indicators_from_tushare(
            start_date=start_date,
            end_date=end_date,
        )
        self.session.commit()

        adj_factors = self.repository.upsert_adj_factors_from_tushare(
            start_date=start_date,
            end_date=end_date,
        )
        self.session.commit()

        return NormalizationResult(
            stocks=0,
            trade_calendars=0,
            daily_quotes=daily_quotes,
            daily_indicators=daily_indicators,
            adj_factors=adj_factors,
        )
