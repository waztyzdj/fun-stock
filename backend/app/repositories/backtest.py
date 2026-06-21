from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.backtest import BacktestHolding, BacktestPeriod, BacktestRun
from app.models.factor import StrategyDefinition, StrategyVersion
from app.services.long_term_backtest import LongTermBacktestResult


@dataclass(frozen=True)
class BacktestRunSummary:
    id: int
    name: str
    status: str
    start_date: date
    end_date: date
    frequency: str
    final_value: Decimal
    total_return: Decimal
    benchmark_return: Decimal
    excess_return: Decimal
    annualized_return: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    average_turnover: Decimal
    created_at: datetime


class BacktestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_long_term_run(
        self,
        *,
        name: str,
        strategy_json: dict[str, object],
        params_json: dict[str, object],
        result: LongTermBacktestResult,
        strategy_id: int | None = None,
    ) -> BacktestRun:
        if strategy_id is None:
            strategy = StrategyDefinition(
                name=name,
                description="Auto-created from a long-term backtest run.",
                strategy_json=strategy_json,
                status="active",
            )
            self.session.add(strategy)
            self.session.flush()
            version_no = 1
        else:
            existing_strategy = self.session.get(StrategyDefinition, strategy_id)
            if existing_strategy is None:
                raise ValueError(f"Strategy not found: {strategy_id}")
            strategy = existing_strategy
            version_no = self._next_strategy_version_no(strategy_id)
        version = StrategyVersion(
            strategy_id=strategy.id,
            version_no=version_no,
            strategy_json=strategy_json,
            notes="Backtest snapshot.",
        )
        self.session.add(version)
        self.session.flush()
        run = BacktestRun(
            strategy_version_id=version.id,
            name=name,
            status="success",
            start_date=result.start_date,
            end_date=result.end_date,
            frequency=result.frequency,
            initial_cash=result.initial_cash,
            final_value=result.final_value,
            benchmark_final_value=result.benchmark_final_value,
            total_return=result.total_return,
            benchmark_return=result.benchmark_return,
            excess_return=result.excess_return,
            annualized_return=result.annualized_return,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            average_turnover=result.average_turnover,
            params_json=params_json,
        )
        self.session.add(run)
        self.session.flush()
        for period_index, period in enumerate(result.periods, start=1):
            period_model = BacktestPeriod(
                run_id=run.id,
                sequence_no=period_index,
                rebalance_date=period.rebalance_date,
                exit_date=period.exit_date,
                selected_count=period.selected_count,
                period_return=period.period_return,
                benchmark_return=period.benchmark_return,
                excess_return=period.excess_return,
                turnover_rate=period.turnover_rate,
                portfolio_value=period.portfolio_value,
                benchmark_value=period.benchmark_value,
            )
            self.session.add(period_model)
            self.session.flush()
            self.session.add_all(
                [
                    BacktestHolding(
                        period_id=period_model.id,
                        ts_code=holding.ts_code,
                        name=holding.name,
                        weight=holding.weight,
                        entry_price=holding.entry_price,
                        exit_price=holding.exit_price,
                        return_ratio=holding.return_ratio,
                    )
                    for holding in period.holdings
                ]
            )
        self.session.flush()
        return run

    def _next_strategy_version_no(self, strategy_id: int) -> int:
        current_max = self.session.scalar(
            select(func.max(StrategyVersion.version_no)).where(
                StrategyVersion.strategy_id == strategy_id
            )
        )
        return int(current_max or 0) + 1

    def list_runs(self, *, limit: int = 20) -> list[BacktestRunSummary]:
        runs = self.session.scalars(
            select(BacktestRun)
            .order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
            .limit(limit)
        )
        return [
            BacktestRunSummary(
                id=run.id,
                name=run.name,
                status=run.status,
                start_date=run.start_date,
                end_date=run.end_date,
                frequency=run.frequency,
                final_value=run.final_value,
                total_return=run.total_return,
                benchmark_return=run.benchmark_return,
                excess_return=run.excess_return,
                annualized_return=run.annualized_return,
                max_drawdown=run.max_drawdown,
                win_rate=run.win_rate,
                average_turnover=run.average_turnover,
                created_at=run.created_at,
            )
            for run in runs
        ]

    def get_run(self, run_id: int) -> BacktestRun | None:
        return self.session.scalar(
            select(BacktestRun)
            .where(BacktestRun.id == run_id)
            .options(selectinload(BacktestRun.periods).selectinload(BacktestPeriod.holdings))
        )
