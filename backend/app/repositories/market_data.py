from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, bindparam, or_, select, text
from sqlalchemy.orm import Session

from app.models.market import DailyQuote, Stock


@dataclass(frozen=True)
class NormalizationResult:
    stocks: int
    trade_calendars: int
    daily_quotes: int
    index_daily_quotes: int = 0
    daily_indicators: int = 0
    adj_factors: int = 0


@dataclass(frozen=True)
class StockListItem:
    ts_code: str
    symbol: str
    name: str
    area: str | None
    industry: str | None
    market: str | None
    exchange: str | None
    list_status: str | None
    list_date: date | None


@dataclass(frozen=True)
class StockQuotePoint:
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    pct_chg: Decimal | None
    vol: Decimal | None
    amount: Decimal | None


class MarketDataRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_stocks_from_tushare(self) -> int:
        result = self.session.execute(
            text(
                """
                INSERT INTO app.stocks (
                    ts_code,
                    symbol,
                    name,
                    area,
                    industry,
                    market,
                    exchange,
                    list_status,
                    list_date,
                    delist_date,
                    updated_at
                )
                SELECT
                    ts_code,
                    symbol,
                    name,
                    area,
                    industry,
                    market,
                    exchange,
                    list_status,
                    list_date,
                    delist_date,
                    now()
                FROM tushare.stock_basic
                WHERE ts_code IS NOT NULL
                  AND symbol IS NOT NULL
                  AND name IS NOT NULL
                ON CONFLICT (ts_code) DO UPDATE SET
                    symbol = EXCLUDED.symbol,
                    name = EXCLUDED.name,
                    area = EXCLUDED.area,
                    industry = EXCLUDED.industry,
                    market = EXCLUDED.market,
                    exchange = EXCLUDED.exchange,
                    list_status = EXCLUDED.list_status,
                    list_date = EXCLUDED.list_date,
                    delist_date = EXCLUDED.delist_date,
                    updated_at = now()
                RETURNING 1
                """
            )
        )
        return len(result.all())

    def list_stocks(self, *, query: str | None = None, limit: int = 50) -> list[StockListItem]:
        statement = select(Stock).order_by(Stock.ts_code).limit(limit)
        if query:
            keyword = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    Stock.ts_code.ilike(keyword),
                    Stock.symbol.ilike(keyword),
                    Stock.name.ilike(keyword),
                )
            )
        return [
            StockListItem(
                ts_code=stock.ts_code,
                symbol=stock.symbol,
                name=stock.name,
                area=stock.area,
                industry=stock.industry,
                market=stock.market,
                exchange=stock.exchange,
                list_status=stock.list_status,
                list_date=stock.list_date,
            )
            for stock in self.session.scalars(statement)
        ]

    def get_stock(self, ts_code: str) -> StockListItem | None:
        stock = self.session.get(Stock, ts_code)
        if stock is None:
            return None
        return StockListItem(
            ts_code=stock.ts_code,
            symbol=stock.symbol,
            name=stock.name,
            area=stock.area,
            industry=stock.industry,
            market=stock.market,
            exchange=stock.exchange,
            list_status=stock.list_status,
            list_date=stock.list_date,
        )

    def list_stock_quotes(self, *, ts_code: str, limit: int = 60) -> list[StockQuotePoint]:
        statement = (
            select(DailyQuote)
            .where(DailyQuote.ts_code == ts_code)
            .order_by(DailyQuote.trade_date.desc())
            .limit(limit)
        )
        quotes = list(self.session.scalars(statement))
        quotes.reverse()
        return [
            StockQuotePoint(
                trade_date=quote.trade_date,
                open=quote.open,
                high=quote.high,
                low=quote.low,
                close=quote.close,
                pct_chg=quote.pct_chg,
                vol=quote.vol,
                amount=quote.amount,
            )
            for quote in quotes
        ]

    def upsert_trade_calendars_from_tushare(self) -> int:
        result = self.session.execute(
            text(
                """
                INSERT INTO app.trade_calendars (
                    exchange,
                    cal_date,
                    is_open,
                    pretrade_date,
                    updated_at
                )
                SELECT
                    exchange,
                    cal_date,
                    is_open = '1',
                    pretrade_date,
                    now()
                FROM tushare.trade_cal
                WHERE exchange IS NOT NULL
                  AND cal_date IS NOT NULL
                ON CONFLICT (exchange, cal_date) DO UPDATE SET
                    is_open = EXCLUDED.is_open,
                    pretrade_date = EXCLUDED.pretrade_date,
                    updated_at = now()
                RETURNING 1
                """
            )
        )
        return len(result.all())

    def upsert_daily_quotes_from_tushare(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        result = self.session.execute(
            text(
                f"""
                INSERT INTO app.daily_quotes (
                    ts_code,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    pre_close,
                    change,
                    pct_chg,
                    vol,
                    amount,
                    updated_at
                )
                SELECT
                    ts_code,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    pre_close,
                    change,
                    pct_chg,
                    vol,
                    amount,
                    now()
                FROM tushare.daily
                WHERE ts_code IS NOT NULL
                  AND trade_date IS NOT NULL
                  {_date_window_sql()}
                ON CONFLICT (ts_code, trade_date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    pre_close = EXCLUDED.pre_close,
                    change = EXCLUDED.change,
                    pct_chg = EXCLUDED.pct_chg,
                    vol = EXCLUDED.vol,
                    amount = EXCLUDED.amount,
                    updated_at = now()
                RETURNING 1
                """
            ).bindparams(
                bindparam("start_date", type_=Date),
                bindparam("end_date", type_=Date),
            ),
            {"start_date": start_date, "end_date": end_date},
        )
        return len(result.all())

    def upsert_index_daily_quotes_from_tushare(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        result = self.session.execute(
            text(
                f"""
                INSERT INTO app.index_daily_quotes (
                    ts_code,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    pre_close,
                    change,
                    pct_chg,
                    vol,
                    amount,
                    updated_at
                )
                SELECT
                    ts_code,
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    pre_close,
                    change,
                    pct_chg,
                    vol,
                    amount,
                    now()
                FROM tushare.index_daily
                WHERE ts_code IS NOT NULL
                  AND trade_date IS NOT NULL
                  {_date_window_sql()}
                ON CONFLICT (ts_code, trade_date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    pre_close = EXCLUDED.pre_close,
                    change = EXCLUDED.change,
                    pct_chg = EXCLUDED.pct_chg,
                    vol = EXCLUDED.vol,
                    amount = EXCLUDED.amount,
                    updated_at = now()
                RETURNING 1
                """
            ).bindparams(
                bindparam("start_date", type_=Date),
                bindparam("end_date", type_=Date),
            ),
            {"start_date": start_date, "end_date": end_date},
        )
        return len(result.all())

    def upsert_daily_indicators_from_tushare(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        result = self.session.execute(
            text(
                f"""
                INSERT INTO app.daily_indicators (
                    ts_code,
                    trade_date,
                    close,
                    turnover_rate,
                    turnover_rate_f,
                    volume_ratio,
                    pe,
                    pe_ttm,
                    pb,
                    ps,
                    ps_ttm,
                    dv_ratio,
                    dv_ttm,
                    total_share,
                    float_share,
                    free_share,
                    total_mv,
                    circ_mv,
                    updated_at
                )
                SELECT
                    ts_code,
                    trade_date,
                    close,
                    turnover_rate,
                    turnover_rate_f,
                    volume_ratio,
                    pe,
                    pe_ttm,
                    pb,
                    ps,
                    ps_ttm,
                    dv_ratio,
                    dv_ttm,
                    total_share,
                    float_share,
                    free_share,
                    total_mv,
                    circ_mv,
                    now()
                FROM tushare.daily_basic
                WHERE ts_code IS NOT NULL
                  AND trade_date IS NOT NULL
                  {_date_window_sql()}
                ON CONFLICT (ts_code, trade_date) DO UPDATE SET
                    close = EXCLUDED.close,
                    turnover_rate = EXCLUDED.turnover_rate,
                    turnover_rate_f = EXCLUDED.turnover_rate_f,
                    volume_ratio = EXCLUDED.volume_ratio,
                    pe = EXCLUDED.pe,
                    pe_ttm = EXCLUDED.pe_ttm,
                    pb = EXCLUDED.pb,
                    ps = EXCLUDED.ps,
                    ps_ttm = EXCLUDED.ps_ttm,
                    dv_ratio = EXCLUDED.dv_ratio,
                    dv_ttm = EXCLUDED.dv_ttm,
                    total_share = EXCLUDED.total_share,
                    float_share = EXCLUDED.float_share,
                    free_share = EXCLUDED.free_share,
                    total_mv = EXCLUDED.total_mv,
                    circ_mv = EXCLUDED.circ_mv,
                    updated_at = now()
                RETURNING 1
                """
            ).bindparams(
                bindparam("start_date", type_=Date),
                bindparam("end_date", type_=Date),
            ),
            {"start_date": start_date, "end_date": end_date},
        )
        return len(result.all())

    def upsert_adj_factors_from_tushare(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        result = self.session.execute(
            text(
                f"""
                INSERT INTO app.adj_factors (
                    ts_code,
                    trade_date,
                    adj_factor,
                    updated_at
                )
                SELECT
                    ts_code,
                    trade_date,
                    adj_factor,
                    now()
                FROM tushare.adj_factor
                WHERE ts_code IS NOT NULL
                  AND trade_date IS NOT NULL
                  {_date_window_sql()}
                ON CONFLICT (ts_code, trade_date) DO UPDATE SET
                    adj_factor = EXCLUDED.adj_factor,
                    updated_at = now()
                RETURNING 1
                """
            ).bindparams(
                bindparam("start_date", type_=Date),
                bindparam("end_date", type_=Date),
            ),
            {"start_date": start_date, "end_date": end_date},
        )
        return len(result.all())


def _date_window_sql() -> str:
    return """
                  AND trade_date >= COALESCE(:start_date, '-infinity'::date)
                  AND trade_date <= COALESCE(:end_date, 'infinity'::date)
    """
