from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_status", "status"),
        Index("ix_backtest_runs_strategy_version_id", "strategy_version_id"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("app.strategy_versions.id")
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    final_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    benchmark_final_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    total_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    benchmark_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    excess_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    annualized_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    average_turnover: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    params_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    periods: Mapped[list["BacktestPeriod"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class BacktestPeriod(Base):
    __tablename__ = "backtest_periods"
    __table_args__ = (
        Index("ix_backtest_periods_run_id", "run_id"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("app.backtest_runs.id"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    rebalance_date: Mapped[date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[date] = mapped_column(Date, nullable=False)
    selected_count: Mapped[int] = mapped_column(nullable=False)
    period_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    benchmark_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    excess_return: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    turnover_rate: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    portfolio_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    benchmark_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)

    run: Mapped[BacktestRun] = relationship(back_populates="periods")
    holdings: Mapped[list["BacktestHolding"]] = relationship(
        back_populates="period",
        cascade="all, delete-orphan",
    )


class BacktestHolding(Base):
    __tablename__ = "backtest_holdings"
    __table_args__ = (
        Index("ix_backtest_holdings_period_id", "period_id"),
        Index("ix_backtest_holdings_ts_code", "ts_code"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("app.backtest_periods.id"), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    return_ratio: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))

    period: Mapped[BacktestPeriod] = relationship(back_populates="holdings")
