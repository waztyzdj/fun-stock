from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy.orm import Session

from app.api.routes.backtests import _screen_request_from_strategy_json
from app.models.backtest import BacktestHolding, BacktestPeriod, BacktestRun
from app.models.factor import StrategyVersion
from app.services.long_term_backtest import (
    BacktestBenchmarkConfig,
    BacktestExecutionConfig,
    LongTermBacktestService,
    _average_turnover,
    _benchmark_display_name,
    _max_drawdown,
    _price_expression,
    _return_ratio,
    _turnover_rate,
    _win_rate,
)
from app.services.long_term_backtest import (
    BacktestPeriod as ServiceBacktestPeriod,
)
from app.services.strategy_screening import StrategyScreenRequest, StrategyUniverse


def test_return_ratio_uses_entry_and_exit_price() -> None:
    assert _return_ratio(entry_price=Decimal("10"), exit_price=Decimal("12")) == Decimal("0.2")


def test_return_ratio_applies_trading_costs() -> None:
    result = _return_ratio(
        entry_price=Decimal("10"),
        exit_price=Decimal("12"),
        execution_config=BacktestExecutionConfig(
            commission_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.001"),
            stamp_tax_rate=Decimal("0.001"),
        ),
    )

    assert result == (Decimal("12") * Decimal("0.997")) / (
        Decimal("10") * Decimal("1.002")
    ) - Decimal("1")


def test_return_ratio_ignores_missing_or_invalid_entry_price() -> None:
    assert _return_ratio(entry_price=None, exit_price=Decimal("12")) is None
    assert _return_ratio(entry_price=Decimal("0"), exit_price=Decimal("12")) is None


def test_price_expression_can_use_adjusted_or_raw_close() -> None:
    assert _price_expression(use_adjusted_prices=True) == "q.close * COALESCE(af.adj_factor, 1)"
    assert _price_expression(use_adjusted_prices=False) == "q.close"


class FakeIndexSession:
    def execute(self, statement: object, params: dict[str, object]) -> object:
        del params
        sql_text = str(statement)
        if "app.index_daily_quotes" not in sql_text:
            raise AssertionError(f"Unexpected SQL: {sql_text}")
        if "ORDER BY q.trade_date DESC" in sql_text:
            return FakeScalarResult(Decimal("3300"))
        return FakeScalarResult(Decimal("3000"))


class FakeScalarResult:
    def __init__(self, value: Decimal | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Decimal | None:
        return self.value


def test_index_benchmark_uses_index_daily_quotes() -> None:
    period_return, fallback_used = LongTermBacktestService(
        cast(Session, FakeIndexSession())
    )._benchmark_period_return(
        screen_request=StrategyScreenRequest(
            universe=StrategyUniverse(),
            filters=[],
            sort=[],
            as_of_date=date(2020, 1, 2),
            limit=30,
        ),
        rebalance_date=date(2020, 1, 2),
        exit_date=date(2020, 12, 31),
        benchmark_config=BacktestBenchmarkConfig(
            kind="index",
            ts_code="000300.SH",
            name="沪深300",
        ),
        execution_config=BacktestExecutionConfig(),
    )

    assert period_return == Decimal("0.1")
    assert fallback_used is False


def test_index_benchmark_name_marks_partial_fallback() -> None:
    assert _benchmark_display_name(
        BacktestBenchmarkConfig(kind="index", ts_code="000300.SH", name="沪深300"),
        fallback_used=True,
    ) == "沪深300（指数行情缺失，部分回退同池等权）"


def test_saved_strategy_json_converts_to_backtest_request() -> None:
    request = _screen_request_from_strategy_json(
        {
            "universe": {"exclude_st": True, "min_list_years": 5},
            "filters": [{"factor": "roe", "op": ">=", "value": "12"}],
            "sort": [{"factor": "pe_ttm", "direction": "asc"}],
        },
        limit=20,
    )

    assert request.universe.exclude_st
    assert request.universe.min_list_years == 5
    assert request.filters[0].factor_code == "roe"
    assert request.sort[0].factor_code == "pe_ttm"
    assert request.limit == 20


def test_backtest_diagnostics_calculate_drawdown_win_rate_and_turnover() -> None:
    first_period = ServiceBacktestPeriod(
        rebalance_date=date(2020, 1, 2),
        exit_date=date(2021, 1, 4),
        selected_count=2,
        period_return=Decimal("0.10"),
        benchmark_return=Decimal("0.03"),
        excess_return=Decimal("0.07"),
        turnover_rate=Decimal("1"),
        portfolio_value=Decimal("110"),
        benchmark_value=Decimal("103"),
    )
    second_period = ServiceBacktestPeriod(
        rebalance_date=date(2021, 1, 4),
        exit_date=date(2022, 1, 4),
        selected_count=2,
        period_return=Decimal("-0.20"),
        benchmark_return=Decimal("-0.10"),
        excess_return=Decimal("-0.10"),
        turnover_rate=Decimal("0.5"),
        portfolio_value=Decimal("88"),
        benchmark_value=Decimal("92.7"),
    )

    assert _max_drawdown([Decimal("100"), Decimal("110"), Decimal("88")]) == Decimal("0.2")
    assert _win_rate([first_period, second_period]) == Decimal("0.5")
    assert _average_turnover([first_period, second_period]) == Decimal("0.5")
    assert _turnover_rate(
        {"000001.SZ": Decimal("0.5"), "000002.SZ": Decimal("0.5")},
        {"000001.SZ": Decimal("0.5"), "000003.SZ": Decimal("0.5")},
    ) == Decimal("0.5")


def test_backtest_report_models_keep_persistent_metrics() -> None:
    run = BacktestRun(
        strategy_version_id=1,
        name="quality strategy",
        status="success",
        start_date=date(2020, 1, 1),
        end_date=date(2025, 12, 31),
        frequency="annual",
        initial_cash=Decimal("1000000"),
        final_value=Decimal("1500000"),
        benchmark_final_value=Decimal("1200000"),
        total_return=Decimal("0.5"),
        benchmark_return=Decimal("0.2"),
        excess_return=Decimal("0.3"),
        annualized_return=Decimal("0.08"),
        max_drawdown=Decimal("0.12"),
        win_rate=Decimal("0.75"),
        average_turnover=Decimal("0.25"),
        params_json={"frequency": "annual"},
    )
    period = BacktestPeriod(
        run_id=1,
        sequence_no=1,
        rebalance_date=date(2020, 1, 2),
        exit_date=date(2021, 1, 4),
        selected_count=30,
        period_return=Decimal("0.1"),
        benchmark_return=Decimal("0.04"),
        excess_return=Decimal("0.06"),
        turnover_rate=Decimal("1"),
        portfolio_value=Decimal("1100000"),
        benchmark_value=Decimal("1040000"),
    )
    holding = BacktestHolding(
        period_id=1,
        ts_code="000001.SZ",
        name="Ping An Bank",
        weight=Decimal("0.1"),
        entry_price=Decimal("10"),
        exit_price=Decimal("12"),
        return_ratio=Decimal("0.2"),
    )
    version = StrategyVersion(
        strategy_id=1,
        version_no=1,
        strategy_json={"filters": []},
    )

    assert run.excess_return == Decimal("0.3")
    assert run.max_drawdown == Decimal("0.12")
    assert period.benchmark_return == Decimal("0.04")
    assert period.turnover_rate == Decimal("1")
    assert holding.return_ratio == Decimal("0.2")
    assert version.version_no == 1
