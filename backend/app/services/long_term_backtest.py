from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.strategy_screening import StrategyScreeningService, StrategyScreenRequest

RebalanceFrequency = Literal["annual", "quarterly"]
BenchmarkKind = Literal["index", "same_universe"]


@dataclass(frozen=True)
class BacktestBenchmarkConfig:
    kind: BenchmarkKind = "index"
    ts_code: str = "000300.SH"
    name: str = "沪深300"


@dataclass(frozen=True)
class BacktestHolding:
    ts_code: str
    name: str
    weight: Decimal
    entry_price: Decimal | None
    exit_price: Decimal | None
    return_ratio: Decimal | None


@dataclass(frozen=True)
class BacktestExecutionConfig:
    commission_rate: Decimal = Decimal("0")
    slippage_rate: Decimal = Decimal("0")
    stamp_tax_rate: Decimal = Decimal("0")
    use_adjusted_prices: bool = True


@dataclass(frozen=True)
class BacktestPeriod:
    rebalance_date: date
    exit_date: date
    selected_count: int
    period_return: Decimal
    benchmark_return: Decimal
    excess_return: Decimal
    turnover_rate: Decimal
    portfolio_value: Decimal
    benchmark_value: Decimal
    holdings: list[BacktestHolding] = field(default_factory=list)


@dataclass(frozen=True)
class LongTermBacktestResult:
    start_date: date
    end_date: date
    frequency: RebalanceFrequency
    initial_cash: Decimal
    final_value: Decimal
    benchmark_final_value: Decimal
    total_return: Decimal
    benchmark_return: Decimal
    excess_return: Decimal
    annualized_return: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    average_turnover: Decimal
    periods: list[BacktestPeriod]
    benchmark_name: str = "same universe equal weight"


class LongTermBacktestService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        *,
        screen_request: StrategyScreenRequest,
        start_date: date,
        end_date: date,
        frequency: RebalanceFrequency,
        initial_cash: Decimal = Decimal("1000000"),
        execution_config: BacktestExecutionConfig | None = None,
        benchmark_config: BacktestBenchmarkConfig | None = None,
    ) -> LongTermBacktestResult:
        if start_date >= end_date:
            raise ValueError("start_date must be earlier than end_date.")
        execution_config = execution_config or BacktestExecutionConfig()
        benchmark_config = benchmark_config or BacktestBenchmarkConfig()
        if benchmark_config.kind == "index" and benchmark_config.ts_code.strip() == "":
            raise ValueError("benchmark_ts_code is required for index benchmark.")
        rebalance_dates = self._rebalance_dates(
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
        )
        portfolio_value = initial_cash
        benchmark_value = initial_cash
        periods: list[BacktestPeriod] = []
        previous_weights: dict[str, Decimal] | None = None
        benchmark_fallback_used = False

        for index, rebalance_date in enumerate(rebalance_dates):
            exit_date = rebalance_dates[index + 1] if index + 1 < len(rebalance_dates) else end_date
            request = StrategyScreenRequest(
                universe=screen_request.universe,
                filters=screen_request.filters,
                sort=screen_request.sort,
                as_of_date=rebalance_date,
                limit=screen_request.limit,
            )
            screen_result = StrategyScreeningService(self.session).screen(request)
            holdings = self._period_holdings(
                ts_codes=[item.ts_code for item in screen_result.items],
                names={item.ts_code: item.name for item in screen_result.items},
                entry_date=rebalance_date,
                exit_date=exit_date,
                execution_config=execution_config,
            )
            valid_returns = [
                holding.return_ratio for holding in holdings if holding.return_ratio is not None
            ]
            period_return = (
                sum(valid_returns, Decimal("0")) / Decimal(len(valid_returns))
                if valid_returns
                else Decimal("0")
            )
            benchmark_period_return, used_fallback = self._benchmark_period_return(
                screen_request=screen_request,
                rebalance_date=rebalance_date,
                exit_date=exit_date,
                benchmark_config=benchmark_config,
                execution_config=execution_config,
            )
            benchmark_fallback_used = benchmark_fallback_used or used_fallback
            current_weights = {holding.ts_code: holding.weight for holding in holdings}
            turnover_rate = _turnover_rate(previous_weights, current_weights)
            previous_weights = current_weights
            portfolio_value *= Decimal("1") + period_return
            benchmark_value *= Decimal("1") + benchmark_period_return
            periods.append(
                BacktestPeriod(
                    rebalance_date=rebalance_date,
                    exit_date=exit_date,
                    selected_count=len(screen_result.items),
                    period_return=period_return,
                    benchmark_return=benchmark_period_return,
                    excess_return=period_return - benchmark_period_return,
                    turnover_rate=turnover_rate,
                    portfolio_value=portfolio_value,
                    benchmark_value=benchmark_value,
                    holdings=holdings,
                )
            )

        total_return = (
            (portfolio_value / initial_cash) - Decimal("1") if initial_cash > 0 else Decimal("0")
        )
        years = max(Decimal((end_date - start_date).days) / Decimal("365"), Decimal("0.01"))
        annualized_return = Decimal(
            str(float(portfolio_value / initial_cash) ** (1 / float(years)) - 1)
        )
        benchmark_total_return = (benchmark_value / initial_cash) - Decimal("1")
        return LongTermBacktestResult(
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            initial_cash=initial_cash,
            final_value=portfolio_value,
            benchmark_final_value=benchmark_value,
            total_return=total_return,
            benchmark_return=benchmark_total_return,
            excess_return=total_return - benchmark_total_return,
            annualized_return=annualized_return,
            max_drawdown=_max_drawdown(
                [initial_cash, *(period.portfolio_value for period in periods)]
            ),
            win_rate=_win_rate(periods),
            average_turnover=_average_turnover(periods),
            periods=periods,
            benchmark_name=_benchmark_display_name(
                benchmark_config,
                fallback_used=benchmark_fallback_used,
            ),
        )

    def _benchmark_period_return(
        self,
        *,
        screen_request: StrategyScreenRequest,
        rebalance_date: date,
        exit_date: date,
        benchmark_config: BacktestBenchmarkConfig,
        execution_config: BacktestExecutionConfig,
    ) -> tuple[Decimal, bool]:
        if benchmark_config.kind == "same_universe":
            return self._same_universe_benchmark_period_return(
                screen_request=screen_request,
                rebalance_date=rebalance_date,
                exit_date=exit_date,
                execution_config=execution_config,
            ), False

        index_return = _return_ratio(
            entry_price=self._index_close_on_or_after(benchmark_config.ts_code, rebalance_date),
            exit_price=self._index_close_on_or_before(benchmark_config.ts_code, exit_date),
        )
        if index_return is not None:
            return index_return, False
        return self._same_universe_benchmark_period_return(
            screen_request=screen_request,
            rebalance_date=rebalance_date,
            exit_date=exit_date,
            execution_config=execution_config,
        ), True

    def _same_universe_benchmark_period_return(
        self,
        *,
        screen_request: StrategyScreenRequest,
        rebalance_date: date,
        exit_date: date,
        execution_config: BacktestExecutionConfig,
    ) -> Decimal:
        benchmark_result = StrategyScreeningService(self.session).screen(
            StrategyScreenRequest(
                universe=screen_request.universe,
                filters=[],
                sort=[],
                as_of_date=rebalance_date,
                limit=5000,
            )
        )
        benchmark_holdings = self._period_holdings(
            ts_codes=[item.ts_code for item in benchmark_result.items],
            names={item.ts_code: item.name for item in benchmark_result.items},
            entry_date=rebalance_date,
            exit_date=exit_date,
            execution_config=execution_config,
        )
        benchmark_returns = [
            holding.return_ratio
            for holding in benchmark_holdings
            if holding.return_ratio is not None
        ]
        if not benchmark_returns:
            return Decimal("0")
        return sum(benchmark_returns, Decimal("0")) / Decimal(len(benchmark_returns))

    def _rebalance_dates(
        self,
        *,
        start_date: date,
        end_date: date,
        frequency: RebalanceFrequency,
    ) -> list[date]:
        months = [1] if frequency == "annual" else [1, 4, 7, 10]
        targets = [
            date(year, month, 1)
            for year in range(start_date.year, end_date.year + 1)
            for month in months
            if start_date <= date(year, month, 1) <= end_date
        ]
        dates = [self._next_trade_date(target) for target in targets]
        unique_dates = sorted({item for item in dates if item <= end_date})
        return unique_dates or [start_date]

    def _next_trade_date(self, target: date) -> date:
        value = self.session.execute(
            text(
                """
                SELECT min(cal_date)
                FROM app.trade_calendars
                WHERE is_open = true
                  AND cal_date >= :target
                """
            ),
            {"target": target},
        ).scalar_one_or_none()
        return value or target

    def _period_holdings(
        self,
        *,
        ts_codes: list[str],
        names: dict[str, str],
        entry_date: date,
        exit_date: date,
        execution_config: BacktestExecutionConfig,
    ) -> list[BacktestHolding]:
        if not ts_codes:
            return []
        weight = Decimal("1") / Decimal(len(ts_codes))
        return [
            BacktestHolding(
                ts_code=ts_code,
                name=names.get(ts_code, ts_code),
                weight=weight,
                entry_price=(
                    entry_price := self._close_on_or_after(
                        ts_code,
                        entry_date,
                        use_adjusted_prices=execution_config.use_adjusted_prices,
                    )
                ),
                exit_price=(
                    exit_price := self._close_on_or_before(
                        ts_code,
                        exit_date,
                        use_adjusted_prices=execution_config.use_adjusted_prices,
                    )
                ),
                return_ratio=_return_ratio(
                    entry_price=entry_price,
                    exit_price=exit_price,
                    execution_config=execution_config,
                ),
            )
            for ts_code in ts_codes
        ]

    def _close_on_or_after(
        self,
        ts_code: str,
        target: date,
        *,
        use_adjusted_prices: bool,
    ) -> Decimal | None:
        price_expression = _price_expression(use_adjusted_prices)
        return self.session.execute(
            text(
                f"""
                SELECT {price_expression}
                FROM app.daily_quotes q
                LEFT JOIN app.adj_factors af
                  ON af.ts_code = q.ts_code
                 AND af.trade_date = q.trade_date
                WHERE q.ts_code = :ts_code
                  AND q.trade_date >= :target
                  AND q.close IS NOT NULL
                ORDER BY q.trade_date
                LIMIT 1
                """
            ),
            {"ts_code": ts_code, "target": target},
        ).scalar_one_or_none()

    def _close_on_or_before(
        self,
        ts_code: str,
        target: date,
        *,
        use_adjusted_prices: bool,
    ) -> Decimal | None:
        price_expression = _price_expression(use_adjusted_prices)
        return self.session.execute(
            text(
                f"""
                SELECT {price_expression}
                FROM app.daily_quotes q
                LEFT JOIN app.adj_factors af
                  ON af.ts_code = q.ts_code
                 AND af.trade_date = q.trade_date
                WHERE q.ts_code = :ts_code
                  AND q.trade_date <= :target
                  AND q.close IS NOT NULL
                ORDER BY q.trade_date DESC
                LIMIT 1
                """
            ),
            {"ts_code": ts_code, "target": target},
        ).scalar_one_or_none()

    def _index_close_on_or_after(self, ts_code: str, target: date) -> Decimal | None:
        return self.session.execute(
            text(
                """
                SELECT q.close
                FROM app.index_daily_quotes q
                WHERE q.ts_code = :ts_code
                  AND q.trade_date >= :target
                  AND q.close IS NOT NULL
                ORDER BY q.trade_date
                LIMIT 1
                """
            ),
            {"ts_code": ts_code, "target": target},
        ).scalar_one_or_none()

    def _index_close_on_or_before(self, ts_code: str, target: date) -> Decimal | None:
        return self.session.execute(
            text(
                """
                SELECT q.close
                FROM app.index_daily_quotes q
                WHERE q.ts_code = :ts_code
                  AND q.trade_date <= :target
                  AND q.close IS NOT NULL
                ORDER BY q.trade_date DESC
                LIMIT 1
                """
            ),
            {"ts_code": ts_code, "target": target},
        ).scalar_one_or_none()


def _return_ratio(
    *,
    entry_price: Decimal | None,
    exit_price: Decimal | None,
    execution_config: BacktestExecutionConfig | None = None,
) -> Decimal | None:
    if entry_price is None or exit_price is None or entry_price <= 0:
        return None
    execution_config = execution_config or BacktestExecutionConfig(
        use_adjusted_prices=False,
    )
    buy_cost_rate = execution_config.commission_rate + execution_config.slippage_rate
    sell_cost_rate = (
        execution_config.commission_rate
        + execution_config.slippage_rate
        + execution_config.stamp_tax_rate
    )
    return (exit_price * (Decimal("1") - sell_cost_rate)) / (
        entry_price * (Decimal("1") + buy_cost_rate)
    ) - Decimal("1")


def _price_expression(use_adjusted_prices: bool) -> str:
    if not use_adjusted_prices:
        return "q.close"
    return "q.close * COALESCE(af.adj_factor, 1)"


def _benchmark_display_name(
    benchmark_config: BacktestBenchmarkConfig,
    *,
    fallback_used: bool,
) -> str:
    if benchmark_config.kind == "same_universe":
        return "same universe equal weight"
    if fallback_used:
        return f"{benchmark_config.name}（指数行情缺失，部分回退同池等权）"
    return benchmark_config.name


def _turnover_rate(
    previous_weights: dict[str, Decimal] | None,
    current_weights: dict[str, Decimal],
) -> Decimal:
    if previous_weights is None:
        return Decimal("1") if current_weights else Decimal("0")
    ts_codes = set(previous_weights) | set(current_weights)
    gross_changed_weight = sum(
        abs(
            current_weights.get(ts_code, Decimal("0"))
            - previous_weights.get(ts_code, Decimal("0"))
        )
        for ts_code in ts_codes
    )
    return gross_changed_weight / Decimal("2")


def _max_drawdown(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    peak = values[0]
    max_drawdown = Decimal("0")
    for value in values:
        if value > peak:
            peak = value
        if peak <= 0:
            continue
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def _win_rate(periods: list[BacktestPeriod]) -> Decimal:
    if not periods:
        return Decimal("0")
    wins = sum(1 for period in periods if period.period_return > 0)
    return Decimal(wins) / Decimal(len(periods))


def _average_turnover(periods: list[BacktestPeriod]) -> Decimal:
    if not periods:
        return Decimal("0")
    measured_periods = periods[1:] if len(periods) > 1 else periods
    return sum(
        (period.turnover_rate for period in measured_periods),
        Decimal("0"),
    ) / Decimal(len(measured_periods))
