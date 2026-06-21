from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.strategies import (
    StrategyFilterRequest,
    StrategyScreenRequestBody,
    StrategySortRequest,
    StrategyUniverseRequest,
    _screen_request,
)
from app.core.db import get_db_session
from app.models.backtest import BacktestRun
from app.repositories.backtest import BacktestRepository, BacktestRunSummary
from app.repositories.factor import FactorRepository, StrategyDetail
from app.services.long_term_backtest import (
    BacktestBenchmarkConfig,
    BacktestExecutionConfig,
    LongTermBacktestService,
)
from app.services.strategy_screening import (
    StrategyFilter,
    StrategyScreeningService,
    StrategyScreenRequest,
    StrategySort,
    StrategyUniverse,
)

router = APIRouter(prefix="/backtests", tags=["backtests"])


class LongTermBacktestRequestBody(BaseModel):
    name: str = Field(default="Long-term fundamental backtest", min_length=1, max_length=128)
    strategy_id: int | None = None
    universe: StrategyUniverseRequest = Field(default_factory=StrategyUniverseRequest)
    filters: list[StrategyFilterRequest] = Field(default_factory=list)
    sort: list[StrategySortRequest] = Field(default_factory=list)
    limit: int = Field(default=30, ge=1, le=100)
    start_date: date
    end_date: date
    frequency: Literal["annual", "quarterly"] = "annual"
    initial_cash: Decimal = Field(default=Decimal("1000000"), gt=0)
    commission_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    slippage_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    stamp_tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    use_adjusted_prices: bool = True
    benchmark_kind: Literal["index", "same_universe"] = "index"
    benchmark_ts_code: str = Field(default="000300.SH", max_length=16)
    benchmark_name: str = Field(default="沪深300", max_length=64)


class BacktestHoldingResponse(BaseModel):
    ts_code: str
    name: str
    weight: Decimal
    entry_price: Decimal | None
    exit_price: Decimal | None
    return_ratio: Decimal | None


class BacktestPeriodResponse(BaseModel):
    rebalance_date: date
    exit_date: date
    selected_count: int
    period_return: Decimal
    benchmark_return: Decimal
    excess_return: Decimal
    turnover_rate: Decimal
    portfolio_value: Decimal
    benchmark_value: Decimal
    holdings: list[BacktestHoldingResponse]


class LongTermBacktestResponse(BaseModel):
    id: int | None = None
    name: str | None = None
    strategy_id: int | None = None
    strategy_name: str | None = None
    benchmark_kind: str = "index"
    benchmark_ts_code: str | None = "000300.SH"
    benchmark_name: str = "same universe equal weight"
    start_date: date
    end_date: date
    frequency: str
    initial_cash: Decimal
    commission_rate: Decimal = Decimal("0")
    slippage_rate: Decimal = Decimal("0")
    stamp_tax_rate: Decimal = Decimal("0")
    use_adjusted_prices: bool = True
    final_value: Decimal
    benchmark_final_value: Decimal
    total_return: Decimal
    benchmark_return: Decimal
    excess_return: Decimal
    annualized_return: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    average_turnover: Decimal
    periods: list[BacktestPeriodResponse]


class BacktestRunListItemResponse(BaseModel):
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


@router.get("", response_model=list[BacktestRunListItemResponse])
def list_backtest_runs(
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = 20,
) -> list[BacktestRunListItemResponse]:
    return [
        _run_summary_response(item)
        for item in BacktestRepository(session).list_runs(limit=max(1, min(limit, 100)))
    ]


@router.get("/{run_id}", response_model=LongTermBacktestResponse)
def get_backtest_run(
    session: Annotated[Session, Depends(get_db_session)],
    run_id: int,
) -> LongTermBacktestResponse:
    run = BacktestRepository(session).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest run not found.")
    return _run_response(run)


@router.post("/long-term", response_model=LongTermBacktestResponse)
def run_long_term_backtest(
    session: Annotated[Session, Depends(get_db_session)],
    request: LongTermBacktestRequestBody,
) -> LongTermBacktestResponse:
    strategy: StrategyDetail | None = None
    if request.strategy_id is None:
        screen_request = _screen_request(
            StrategyScreenRequestBody(
                universe=request.universe,
                filters=request.filters,
                sort=request.sort,
                as_of_date=None,
                limit=request.limit,
            )
        )
    else:
        strategy = FactorRepository(session).get_strategy(request.strategy_id)
        if strategy is None:
            raise HTTPException(status_code=404, detail="Strategy not found.")
        screen_request = _screen_request_from_strategy_json(
            strategy.strategy_json,
            limit=request.limit,
        )
    try:
        strategy_json = StrategyScreeningService(session).strategy_json_from_request(screen_request)
        result = LongTermBacktestService(session).run(
            screen_request=screen_request,
            start_date=request.start_date,
            end_date=request.end_date,
            frequency=request.frequency,
            initial_cash=request.initial_cash,
            execution_config=BacktestExecutionConfig(
                commission_rate=request.commission_rate,
                slippage_rate=request.slippage_rate,
                stamp_tax_rate=request.stamp_tax_rate,
                use_adjusted_prices=request.use_adjusted_prices,
            ),
            benchmark_config=BacktestBenchmarkConfig(
                kind=request.benchmark_kind,
                ts_code=request.benchmark_ts_code,
                name=request.benchmark_name,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run = BacktestRepository(session).save_long_term_run(
        name=request.name,
        strategy_json=strategy_json,
        params_json={
            "benchmark_kind": request.benchmark_kind,
            "benchmark_name": result.benchmark_name,
            "benchmark_ts_code": request.benchmark_ts_code,
            "commission_rate": str(request.commission_rate),
            "frequency": request.frequency,
            "initial_cash": str(request.initial_cash),
            "limit": request.limit,
            "slippage_rate": str(request.slippage_rate),
            "stamp_tax_rate": str(request.stamp_tax_rate),
            "start_date": request.start_date.isoformat(),
            "strategy_id": request.strategy_id,
            "strategy_name": strategy.name if strategy else None,
            "end_date": request.end_date.isoformat(),
            "use_adjusted_prices": request.use_adjusted_prices,
        },
        result=result,
        strategy_id=request.strategy_id,
    )
    session.commit()
    return LongTermBacktestResponse(
        id=run.id,
        name=run.name,
        strategy_id=request.strategy_id,
        strategy_name=strategy.name if strategy else None,
        benchmark_kind=request.benchmark_kind,
        benchmark_ts_code=request.benchmark_ts_code,
        benchmark_name=result.benchmark_name,
        start_date=result.start_date,
        end_date=result.end_date,
        frequency=result.frequency,
        initial_cash=result.initial_cash,
        commission_rate=request.commission_rate,
        slippage_rate=request.slippage_rate,
        stamp_tax_rate=request.stamp_tax_rate,
        use_adjusted_prices=request.use_adjusted_prices,
        final_value=result.final_value,
        benchmark_final_value=result.benchmark_final_value,
        total_return=result.total_return,
        benchmark_return=result.benchmark_return,
        excess_return=result.excess_return,
        annualized_return=result.annualized_return,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        average_turnover=result.average_turnover,
        periods=[
            BacktestPeriodResponse(
                rebalance_date=period.rebalance_date,
                exit_date=period.exit_date,
                selected_count=period.selected_count,
                period_return=period.period_return,
                benchmark_return=period.benchmark_return,
                excess_return=period.excess_return,
                turnover_rate=period.turnover_rate,
                portfolio_value=period.portfolio_value,
                benchmark_value=period.benchmark_value,
                holdings=[
                    BacktestHoldingResponse(
                        ts_code=holding.ts_code,
                        name=holding.name,
                        weight=holding.weight,
                        entry_price=holding.entry_price,
                        exit_price=holding.exit_price,
                        return_ratio=holding.return_ratio,
                    )
                    for holding in period.holdings
                ],
            )
            for period in result.periods
        ],
    )


def _run_summary_response(item: BacktestRunSummary) -> BacktestRunListItemResponse:
    return BacktestRunListItemResponse(
        id=item.id,
        name=item.name,
        status=item.status,
        start_date=item.start_date,
        end_date=item.end_date,
        frequency=item.frequency,
        final_value=item.final_value,
        total_return=item.total_return,
        benchmark_return=item.benchmark_return,
        excess_return=item.excess_return,
        annualized_return=item.annualized_return,
        max_drawdown=item.max_drawdown,
        win_rate=item.win_rate,
        average_turnover=item.average_turnover,
        created_at=item.created_at,
    )


def _run_response(run: BacktestRun) -> LongTermBacktestResponse:
    sorted_periods = sorted(run.periods, key=lambda item: item.sequence_no)
    params_json = run.params_json
    return LongTermBacktestResponse(
        id=run.id,
        name=run.name,
        strategy_id=_int_param(params_json.get("strategy_id")),
        strategy_name=_str_param(params_json.get("strategy_name")),
        benchmark_kind=_str_param(params_json.get("benchmark_kind")) or "same_universe",
        benchmark_ts_code=_str_param(params_json.get("benchmark_ts_code")),
        benchmark_name=(
            _str_param(params_json.get("benchmark_name")) or "same universe equal weight"
        ),
        start_date=run.start_date,
        end_date=run.end_date,
        frequency=run.frequency,
        initial_cash=run.initial_cash,
        commission_rate=_decimal_param(params_json.get("commission_rate")),
        slippage_rate=_decimal_param(params_json.get("slippage_rate")),
        stamp_tax_rate=_decimal_param(params_json.get("stamp_tax_rate")),
        use_adjusted_prices=_bool_param(params_json.get("use_adjusted_prices"), default=True),
        final_value=run.final_value,
        benchmark_final_value=run.benchmark_final_value,
        total_return=run.total_return,
        benchmark_return=run.benchmark_return,
        excess_return=run.excess_return,
        annualized_return=run.annualized_return,
        max_drawdown=run.max_drawdown,
        win_rate=run.win_rate,
        average_turnover=run.average_turnover,
        periods=[
            BacktestPeriodResponse(
                rebalance_date=period.rebalance_date,
                exit_date=period.exit_date,
                selected_count=period.selected_count,
                period_return=period.period_return,
                benchmark_return=period.benchmark_return,
                excess_return=period.excess_return,
                turnover_rate=period.turnover_rate,
                portfolio_value=period.portfolio_value,
                benchmark_value=period.benchmark_value,
                holdings=[
                    BacktestHoldingResponse(
                        ts_code=holding.ts_code,
                        name=holding.name,
                        weight=holding.weight,
                        entry_price=holding.entry_price,
                        exit_price=holding.exit_price,
                        return_ratio=holding.return_ratio,
                    )
                    for holding in sorted(period.holdings, key=lambda item: item.ts_code)
                ],
            )
            for period in sorted_periods
        ],
    )


def _screen_request_from_strategy_json(
    strategy_json: dict[str, object],
    *,
    limit: int,
) -> StrategyScreenRequest:
    universe_json = _dict_param(strategy_json.get("universe"))
    filters_json = _list_param(strategy_json.get("filters"))
    sort_json = _list_param(strategy_json.get("sort"))
    return StrategyScreenRequest(
        universe=StrategyUniverse(
            exclude_st=_bool_param(universe_json.get("exclude_st"), default=True),
            min_list_years=_int_param(universe_json.get("min_list_years")),
        ),
        filters=[
            StrategyFilter(
                factor_code=_required_str(item, "factor"),
                operator=_required_operator(item, "op"),
                value=Decimal(_required_str(item, "value")),
            )
            for item in filters_json
        ],
        sort=[
            StrategySort(
                factor_code=_required_str(item, "factor"),
                direction=_required_direction(item, "direction"),
            )
            for item in sort_json
        ],
        as_of_date=None,
        limit=limit,
    )


def _dict_param(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list_param(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _required_str(item: dict[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"Invalid strategy JSON: missing {key}")
    return value


def _required_operator(
    item: dict[str, object],
    key: str,
) -> Literal[">=", "<=", ">", "<", "="]:
    value = _required_str(item, key)
    if value not in {">=", "<=", ">", "<", "="}:
        raise ValueError(f"Invalid strategy JSON operator: {value}")
    return cast(Literal[">=", "<=", ">", "<", "="], value)


def _required_direction(item: dict[str, object], key: str) -> Literal["asc", "desc"]:
    value = _required_str(item, key)
    if value not in {"asc", "desc"}:
        raise ValueError(f"Invalid strategy JSON direction: {value}")
    return cast(Literal["asc", "desc"], value)


def _int_param(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _str_param(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _decimal_param(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        return Decimal(str(value))
    return Decimal("0")


def _bool_param(value: object, *, default: bool) -> bool:
    return value if isinstance(value, bool) else default
