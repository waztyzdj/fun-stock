from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = (
        Index("ix_stocks_symbol", "symbol"),
        Index("ix_stocks_exchange", "exchange"),
        {"schema": "app"},
    )

    ts_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    area: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128))
    market: Mapped[str | None] = mapped_column(String(32))
    exchange: Mapped[str | None] = mapped_column(String(16))
    list_status: Mapped[str | None] = mapped_column(String(8))
    list_date: Mapped[date | None] = mapped_column(Date)
    delist_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TradeCalendar(Base):
    __tablename__ = "trade_calendars"
    __table_args__ = (
        Index("ix_trade_calendars_cal_date", "cal_date"),
        {"schema": "app"},
    )

    exchange: Mapped[str] = mapped_column(String(16), primary_key=True)
    cal_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_open: Mapped[bool] = mapped_column(nullable=False)
    pretrade_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DailyQuote(Base):
    __tablename__ = "daily_quotes"
    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_daily_quotes_ts_code_trade_date"),
        Index("ix_daily_quotes_trade_date", "trade_date"),
        Index("ix_daily_quotes_ts_code", "ts_code"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    change: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IndexDailyQuote(Base):
    __tablename__ = "index_daily_quotes"
    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_index_daily_quotes_ts_code_trade_date"),
        Index("ix_index_daily_quotes_trade_date", "trade_date"),
        Index("ix_index_daily_quotes_ts_code", "ts_code"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    change: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    vol: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DailyIndicator(Base):
    __tablename__ = "daily_indicators"
    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_daily_indicators_ts_code_trade_date"),
        Index("ix_daily_indicators_trade_date", "trade_date"),
        Index("ix_daily_indicators_ts_code", "ts_code"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    turnover_rate_f: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pe: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pb: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ps: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ps_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    dv_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    dv_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    total_share: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    float_share: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    free_share: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    circ_mv: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AdjFactor(Base):
    __tablename__ = "adj_factors"
    __table_args__ = (
        UniqueConstraint("ts_code", "trade_date", name="uq_adj_factors_ts_code_trade_date"),
        Index("ix_adj_factors_trade_date", "trade_date"),
        Index("ix_adj_factors_ts_code", "ts_code"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    adj_factor: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
