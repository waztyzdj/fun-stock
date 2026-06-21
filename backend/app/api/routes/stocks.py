from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.repositories.factor import FactorRepository
from app.repositories.market_data import MarketDataRepository

router = APIRouter(prefix="/stocks", tags=["stocks"])

CORE_STOCK_FACTOR_CODES = [
    "roe",
    "grossprofit_margin",
    "netprofit_margin",
    "debt_to_assets",
    "ocf_to_profit",
    "or_yoy",
    "netprofit_yoy",
    "pe_ttm",
    "pb",
    "dv_ttm",
]


class StockListItemResponse(BaseModel):
    ts_code: str
    symbol: str
    name: str
    area: str | None
    industry: str | None
    market: str | None
    exchange: str | None
    list_status: str | None
    list_date: date | None


class StockQuotePointResponse(BaseModel):
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    pct_chg: Decimal | None
    vol: Decimal | None
    amount: Decimal | None


class StockFactorSnapshotResponse(BaseModel):
    factor_code: str
    value: Decimal
    factor_date: date
    report_end_date: date | None


class StockFactorHistoryPointResponse(BaseModel):
    factor_code: str
    value: Decimal
    factor_date: date
    report_end_date: date | None


class StockDetailResponse(BaseModel):
    stock: StockListItemResponse
    quotes: list[StockQuotePointResponse]
    factors: list[StockFactorSnapshotResponse]
    factor_history: list[StockFactorHistoryPointResponse]


@router.get("", response_model=list[StockListItemResponse])
def list_stocks(
    session: Annotated[Session, Depends(get_db_session)],
    q: str | None = None,
    limit: int = 50,
) -> list[StockListItemResponse]:
    safe_limit = max(1, min(limit, 100))
    stocks = MarketDataRepository(session).list_stocks(query=q, limit=safe_limit)
    return [
        StockListItemResponse(
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
        for stock in stocks
    ]


@router.get("/{ts_code}", response_model=StockDetailResponse)
def get_stock_detail(
    session: Annotated[Session, Depends(get_db_session)],
    ts_code: str,
    quote_limit: int = 60,
) -> StockDetailResponse:
    repository = MarketDataRepository(session)
    factor_repository = FactorRepository(session)
    stock = repository.get_stock(ts_code)
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found.")
    quotes = repository.list_stock_quotes(ts_code=ts_code, limit=max(1, min(quote_limit, 240)))
    factor_snapshots = factor_repository.latest_factor_snapshots(
        ts_code=ts_code,
        factor_codes=CORE_STOCK_FACTOR_CODES,
    )
    factor_history = factor_repository.factor_value_history(
        ts_code=ts_code,
        factor_codes=CORE_STOCK_FACTOR_CODES,
        limit_per_factor=12,
    )
    return StockDetailResponse(
        stock=StockListItemResponse(
            ts_code=stock.ts_code,
            symbol=stock.symbol,
            name=stock.name,
            area=stock.area,
            industry=stock.industry,
            market=stock.market,
            exchange=stock.exchange,
            list_status=stock.list_status,
            list_date=stock.list_date,
        ),
        quotes=[
            StockQuotePointResponse(
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
        ],
        factors=[
            StockFactorSnapshotResponse(
                factor_code=factor.factor_code,
                value=factor.value,
                factor_date=factor.factor_date,
                report_end_date=factor.report_end_date,
            )
            for factor in factor_snapshots
        ],
        factor_history=[
            StockFactorHistoryPointResponse(
                factor_code=factor.factor_code,
                value=factor.value,
                factor_date=factor.factor_date,
                report_end_date=factor.report_end_date,
            )
            for factor in factor_history
        ],
    )
