from dataclasses import dataclass
from datetime import date

from sqlalchemy import Date, bindparam, text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class NormalizationResult:
    stocks: int
    trade_calendars: int
    daily_quotes: int
    daily_indicators: int = 0
    adj_factors: int = 0


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
                """
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
                  AND (:start_date IS NULL OR trade_date >= :start_date)
                  AND (:end_date IS NULL OR trade_date <= :end_date)
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
                """
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
                  AND (:start_date IS NULL OR trade_date >= :start_date)
                  AND (:end_date IS NULL OR trade_date <= :end_date)
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
                """
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
                  AND (:start_date IS NULL OR trade_date >= :start_date)
                  AND (:end_date IS NULL OR trade_date <= :end_date)
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
