from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.models.factor import FactorDefinition
from app.repositories.factor import (
    FactorBuildStatus,
    FactorCoverage,
    FactorQuality,
    FactorRepository,
    FactorValueSnapshot,
    StrategyDetail,
)
from app.services.strategy_screening import (
    StrategyFilter,
    StrategyFilterEvaluation,
    StrategyScreeningService,
    StrategyScreenRequest,
    StrategySort,
    StrategyUniverse,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


class FactorDefinitionResponse(BaseModel):
    code: str
    name: str
    category: str
    unit: str | None
    period_type: str
    source: str
    calculation_method: str
    description: str
    sort_direction: str
    value_count: int
    stock_count: int
    latest_factor_date: date | None
    latest_report_end_date: date | None
    latest_value_count: int


class FactorBuildStatusResponse(BaseModel):
    total_value_count: int
    factor_count: int
    stock_count: int
    latest_factor_date: date | None
    latest_report_end_date: date | None
    latest_updated_at: datetime | None


class FactorBuildRequestBody(BaseModel):
    start_date: date | None = None


class FactorBuildRunResponse(BaseModel):
    rows: int
    start_date: date | None
    status: FactorBuildStatusResponse


class FactorQualityResponse(BaseModel):
    factor_code: str
    factor_name: str
    category: str
    status: str
    value_count: int
    stock_count: int
    latest_factor_date: date | None
    latest_value_count: int
    universe_stock_count: int
    coverage_ratio: Decimal
    missing_stock_count: int
    zero_value_count: int
    negative_value_count: int


class StrategyUniverseRequest(BaseModel):
    exclude_st: bool = True
    min_list_years: int | None = Field(default=3, ge=0, le=30)


class StrategyFilterRequest(BaseModel):
    factor_code: str
    operator: Literal[">=", "<=", ">", "<", "="]
    value: Decimal


class StrategySortRequest(BaseModel):
    factor_code: str
    direction: Literal["asc", "desc"]


class StrategyScreenRequestBody(BaseModel):
    universe: StrategyUniverseRequest = Field(default_factory=StrategyUniverseRequest)
    filters: list[StrategyFilterRequest] = Field(default_factory=list)
    sort: list[StrategySortRequest] = Field(default_factory=list)
    as_of_date: date | None = None
    limit: int = Field(default=50, ge=1, le=200)


class StrategySaveRequestBody(StrategyScreenRequestBody):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)


class FactorValueResponse(BaseModel):
    factor_code: str
    value: Decimal
    factor_date: date
    report_end_date: date | None = None


class StrategyFilterEvaluationResponse(BaseModel):
    factor_code: str
    operator: str
    threshold: Decimal
    value: Decimal | None
    factor_date: date | None
    passed: bool
    distance_ratio: Decimal | None


class StrategyScreenItemResponse(BaseModel):
    ts_code: str
    name: str
    industry: str | None
    market: str | None
    list_date: date | None
    factor_values: list[FactorValueResponse]
    score: Decimal
    filter_evaluations: list[StrategyFilterEvaluationResponse]


class StrategyScreenResponse(BaseModel):
    total: int
    items: list[StrategyScreenItemResponse]
    near_misses: list[StrategyScreenItemResponse]


class StrategyListItemResponse(BaseModel):
    id: int
    name: str
    description: str | None
    status: str


class StrategyDetailResponse(StrategyListItemResponse):
    strategy_json: dict[str, object]


class StrategySaveResponse(BaseModel):
    id: int
    name: str
    status: str


@router.get("/factors", response_model=list[FactorDefinitionResponse])
def list_factor_definitions(
    session: Annotated[Session, Depends(get_db_session)],
) -> list[FactorDefinitionResponse]:
    repository = FactorRepository(session)
    repository.upsert_factor_definitions()
    session.commit()
    coverage_by_code = repository.factor_coverages()
    return [
        _factor_definition_response(item, coverage_by_code.get(item.code))
        for item in repository.list_factor_definitions()
    ]


@router.get("/factors/build-status", response_model=FactorBuildStatusResponse)
def get_factor_build_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> FactorBuildStatusResponse:
    return _factor_build_status_response(FactorRepository(session).factor_build_status())


@router.post("/factors/build", response_model=FactorBuildRunResponse)
def build_factor_values(
    session: Annotated[Session, Depends(get_db_session)],
    request: FactorBuildRequestBody,
) -> FactorBuildRunResponse:
    repository = FactorRepository(session)
    rows = repository.rebuild_factor_values(start_date=request.start_date)
    status = repository.factor_build_status()
    session.commit()
    return FactorBuildRunResponse(
        rows=rows,
        start_date=request.start_date,
        status=_factor_build_status_response(status),
    )


@router.get("/factors/quality", response_model=list[FactorQualityResponse])
def get_factor_quality_report(
    session: Annotated[Session, Depends(get_db_session)],
) -> list[FactorQualityResponse]:
    repository = FactorRepository(session)
    qualities = repository.factor_quality_report()
    session.commit()
    return [_factor_quality_response(item) for item in qualities]


@router.get("", response_model=list[StrategyListItemResponse])
def list_strategies(
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = 20,
) -> list[StrategyListItemResponse]:
    return [
        StrategyListItemResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            status=item.status,
        )
        for item in FactorRepository(session).list_strategies(limit=max(1, min(limit, 100)))
    ]


@router.post("/screen", response_model=StrategyScreenResponse)
def screen_strategy(
    session: Annotated[Session, Depends(get_db_session)],
    request: StrategyScreenRequestBody,
) -> StrategyScreenResponse:
    try:
        result = StrategyScreeningService(session).screen(_screen_request(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StrategyScreenResponse(
        total=result.total,
        items=[
            StrategyScreenItemResponse(
                ts_code=item.ts_code,
                name=item.name,
                industry=item.industry,
                market=item.market,
                list_date=item.list_date,
                factor_values=_factor_value_responses(item.factor_values),
                score=item.score,
                filter_evaluations=_filter_evaluation_responses(item.filter_evaluations),
            )
            for item in result.items
        ],
        near_misses=[
            StrategyScreenItemResponse(
                ts_code=item.ts_code,
                name=item.name,
                industry=item.industry,
                market=item.market,
                list_date=item.list_date,
                factor_values=_factor_value_responses(item.factor_values),
                score=item.score,
                filter_evaluations=_filter_evaluation_responses(item.filter_evaluations),
            )
            for item in result.near_misses
        ],
    )


@router.post("", response_model=StrategySaveResponse)
def save_strategy(
    session: Annotated[Session, Depends(get_db_session)],
    request: StrategySaveRequestBody,
) -> StrategySaveResponse:
    service = StrategyScreeningService(session)
    screen_request = _screen_request(request)
    try:
        strategy_json = service.strategy_json_from_request(screen_request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    strategy = FactorRepository(session).save_strategy(
        name=request.name,
        description=request.description,
        strategy_json=strategy_json,
    )
    session.commit()
    return StrategySaveResponse(id=strategy.id, name=strategy.name, status=strategy.status)


@router.get("/{strategy_id}", response_model=StrategyDetailResponse)
def get_strategy(
    session: Annotated[Session, Depends(get_db_session)],
    strategy_id: int,
) -> StrategyDetailResponse:
    strategy = FactorRepository(session).get_strategy(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found.")
    return _strategy_detail_response(strategy)


def _factor_definition_response(
    item: FactorDefinition,
    coverage: FactorCoverage | None,
) -> FactorDefinitionResponse:
    return FactorDefinitionResponse(
        code=item.code,
        name=item.name,
        category=item.category,
        unit=item.unit,
        period_type=item.period_type,
        source=item.source,
        calculation_method=item.calculation_method,
        description=item.description,
        sort_direction=item.sort_direction,
        value_count=coverage.value_count if coverage else 0,
        stock_count=coverage.stock_count if coverage else 0,
        latest_factor_date=coverage.latest_factor_date if coverage else None,
        latest_report_end_date=coverage.latest_report_end_date if coverage else None,
        latest_value_count=coverage.latest_value_count if coverage else 0,
    )


def _factor_build_status_response(status: FactorBuildStatus) -> FactorBuildStatusResponse:
    return FactorBuildStatusResponse(
        total_value_count=status.total_value_count,
        factor_count=status.factor_count,
        stock_count=status.stock_count,
        latest_factor_date=status.latest_factor_date,
        latest_report_end_date=status.latest_report_end_date,
        latest_updated_at=status.latest_updated_at,
    )


def _factor_quality_response(item: FactorQuality) -> FactorQualityResponse:
    return FactorQualityResponse(
        factor_code=item.factor_code,
        factor_name=item.factor_name,
        category=item.category,
        status=item.status,
        value_count=item.value_count,
        stock_count=item.stock_count,
        latest_factor_date=item.latest_factor_date,
        latest_value_count=item.latest_value_count,
        universe_stock_count=item.universe_stock_count,
        coverage_ratio=item.coverage_ratio,
        missing_stock_count=item.missing_stock_count,
        zero_value_count=item.zero_value_count,
        negative_value_count=item.negative_value_count,
    )


def _strategy_detail_response(item: StrategyDetail) -> StrategyDetailResponse:
    return StrategyDetailResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        status=item.status,
        strategy_json=item.strategy_json,
    )


def _screen_request(request: StrategyScreenRequestBody) -> StrategyScreenRequest:
    return StrategyScreenRequest(
        universe=StrategyUniverse(
            exclude_st=request.universe.exclude_st,
            min_list_years=request.universe.min_list_years,
        ),
        as_of_date=request.as_of_date,
        filters=[
            StrategyFilter(
                factor_code=item.factor_code,
                operator=item.operator,
                value=item.value,
            )
            for item in request.filters
        ],
        sort=[
            StrategySort(
                factor_code=item.factor_code,
                direction=item.direction,
            )
            for item in request.sort
        ],
        limit=request.limit,
    )


def _factor_value_responses(
    factor_values: list[FactorValueSnapshot],
) -> list[FactorValueResponse]:
    return [
        FactorValueResponse(
            factor_code=factor.factor_code,
            value=factor.value,
            factor_date=factor.factor_date,
            report_end_date=factor.report_end_date,
        )
        for factor in factor_values
    ]


def _filter_evaluation_responses(
    evaluations: list[StrategyFilterEvaluation],
) -> list[StrategyFilterEvaluationResponse]:
    return [
        StrategyFilterEvaluationResponse(
            factor_code=evaluation.factor_code,
            operator=evaluation.operator,
            threshold=evaluation.threshold,
            value=evaluation.value,
            factor_date=evaluation.factor_date,
            passed=evaluation.passed,
            distance_ratio=evaluation.distance_ratio,
        )
        for evaluation in evaluations
    ]
