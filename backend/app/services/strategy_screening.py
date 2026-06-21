from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.engines.factor.fundamental_factors import FUNDAMENTAL_FACTOR_SPECS_BY_CODE
from app.repositories.factor import FactorRepository, FactorValueSnapshot

FilterOperator = Literal[">=", "<=", ">", "<", "="]
SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True)
class StrategyFilter:
    factor_code: str
    operator: FilterOperator
    value: Decimal


@dataclass(frozen=True)
class StrategySort:
    factor_code: str
    direction: SortDirection


@dataclass(frozen=True)
class StrategyUniverse:
    exclude_st: bool = True
    min_list_years: int | None = 3


@dataclass(frozen=True)
class StrategyScreenRequest:
    universe: StrategyUniverse
    filters: list[StrategyFilter]
    sort: list[StrategySort]
    as_of_date: date | None = None
    limit: int = 50


@dataclass(frozen=True)
class StrategyFilterEvaluation:
    factor_code: str
    operator: FilterOperator
    threshold: Decimal
    value: Decimal | None
    factor_date: date | None
    passed: bool
    distance_ratio: Decimal | None


@dataclass(frozen=True)
class StrategyScreenResultItem:
    ts_code: str
    name: str
    industry: str | None
    market: str | None
    list_date: date | None
    factor_values: list[FactorValueSnapshot]
    score: Decimal = Decimal("0")
    filter_evaluations: list[StrategyFilterEvaluation] = field(default_factory=list)


@dataclass(frozen=True)
class StrategyScreenResult:
    items: list[StrategyScreenResultItem]
    total: int
    near_misses: list[StrategyScreenResultItem] = field(default_factory=list)


class StrategyScreeningService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.factor_repository = FactorRepository(session)

    def screen(self, request: StrategyScreenRequest) -> StrategyScreenResult:
        factor_codes = _unique_factor_codes(request)
        _validate_factor_codes(factor_codes)
        candidate_rows = self.session.execute(
            text(
                """
                SELECT ts_code, name, industry, market, list_date
                FROM app.stocks
                WHERE (:exclude_st = false OR name NOT ILIKE '%ST%')
                  AND (
                    :min_list_years IS NULL
                    OR list_date <= CURRENT_DATE - (:min_list_years * INTERVAL '1 year')
                  )
                  AND (list_status = 'L' OR list_status IS NULL)
                ORDER BY ts_code
                """
            ),
            {
                "exclude_st": request.universe.exclude_st,
                "min_list_years": request.universe.min_list_years,
            },
        ).all()

        matched_items: list[StrategyScreenResultItem] = []
        near_misses: list[StrategyScreenResultItem] = []
        for row in candidate_rows:
            snapshots = self.factor_repository.latest_factor_snapshots(
                ts_code=row.ts_code,
                factor_codes=factor_codes,
                as_of_date=request.as_of_date,
            )
            snapshot_by_code = {snapshot.factor_code: snapshot for snapshot in snapshots}
            evaluations = _evaluate_filters(request.filters, snapshot_by_code)
            item = StrategyScreenResultItem(
                ts_code=row.ts_code,
                name=row.name,
                industry=row.industry,
                market=row.market,
                list_date=row.list_date,
                factor_values=[
                    snapshot_by_code[code]
                    for code in factor_codes
                    if code in snapshot_by_code
                ],
                score=_score_item(snapshot_by_code=snapshot_by_code, sort_rules=request.sort),
                filter_evaluations=evaluations,
            )
            if all(evaluation.passed for evaluation in evaluations):
                matched_items.append(item)
            elif _is_near_miss(evaluations):
                near_misses.append(item)

        near_misses.sort(
            key=lambda item: min(
                (
                    evaluation.distance_ratio
                    for evaluation in item.filter_evaluations
                    if not evaluation.passed and evaluation.distance_ratio is not None
                ),
                default=Decimal("Infinity"),
            )
        )

        sorted_items = _sort_items(matched_items, request.sort)
        total = len(sorted_items)
        return StrategyScreenResult(
            items=sorted_items[: request.limit],
            total=total,
            near_misses=near_misses[:10],
        )

    def strategy_json_from_request(self, request: StrategyScreenRequest) -> dict[str, object]:
        _validate_factor_codes(_unique_factor_codes(request))
        return {
            "universe": {
                "exclude_st": request.universe.exclude_st,
                "min_list_years": request.universe.min_list_years,
            },
            "filters": [
                {
                    "factor": item.factor_code,
                    "op": item.operator,
                    "value": str(item.value),
                }
                for item in request.filters
            ],
            "sort": [
                {
                    "factor": item.factor_code,
                    "direction": item.direction,
                }
                for item in request.sort
            ],
        }


def _unique_factor_codes(request: StrategyScreenRequest) -> list[str]:
    codes: list[str] = []
    for code in [
        *[item.factor_code for item in request.filters],
        *[item.factor_code for item in request.sort],
    ]:
        if code not in codes:
            codes.append(code)
    return codes


def _validate_factor_codes(factor_codes: list[str]) -> None:
    unknown_codes = sorted(set(factor_codes) - set(FUNDAMENTAL_FACTOR_SPECS_BY_CODE))
    if unknown_codes:
        raise ValueError(f"Unsupported factor codes: {', '.join(unknown_codes)}")


def _matches_filters(
    filters: list[StrategyFilter],
    snapshot_by_code: dict[str, FactorValueSnapshot],
) -> bool:
    for item in filters:
        snapshot = snapshot_by_code.get(item.factor_code)
        if snapshot is None or not _compare(snapshot.value, item.operator, item.value):
            return False
    return True


def _evaluate_filters(
    filters: list[StrategyFilter],
    snapshot_by_code: dict[str, FactorValueSnapshot],
) -> list[StrategyFilterEvaluation]:
    evaluations: list[StrategyFilterEvaluation] = []
    for item in filters:
        snapshot = snapshot_by_code.get(item.factor_code)
        passed = snapshot is not None and _compare(snapshot.value, item.operator, item.value)
        evaluations.append(
            StrategyFilterEvaluation(
                factor_code=item.factor_code,
                operator=item.operator,
                threshold=item.value,
                value=snapshot.value if snapshot else None,
                factor_date=snapshot.factor_date if snapshot else None,
                passed=passed,
                distance_ratio=_distance_ratio(
                    value=snapshot.value if snapshot else None,
                    operator=item.operator,
                    threshold=item.value,
                ),
            )
        )
    return evaluations


def _compare(value: Decimal, operator: FilterOperator, threshold: Decimal) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    return value == threshold


def _sort_items(
    items: list[StrategyScreenResultItem],
    sort_rules: list[StrategySort],
) -> list[StrategyScreenResultItem]:
    sorted_items = list(items)
    for rule in reversed(sort_rules):
        sorted_items.sort(
            key=lambda item: _factor_sort_value(item, rule.factor_code),
            reverse=rule.direction == "desc",
        )
    return sorted_items


def _score_item(
    *,
    snapshot_by_code: dict[str, FactorValueSnapshot],
    sort_rules: list[StrategySort],
) -> Decimal:
    score = Decimal("0")
    for rule in sort_rules:
        snapshot = snapshot_by_code.get(rule.factor_code)
        if snapshot is None:
            continue
        score += snapshot.value if rule.direction == "desc" else -snapshot.value
    return score


def _factor_sort_value(item: StrategyScreenResultItem, factor_code: str) -> Decimal:
    for snapshot in item.factor_values:
        if snapshot.factor_code == factor_code:
            return snapshot.value
    return Decimal("-Infinity")


def _is_near_miss(evaluations: list[StrategyFilterEvaluation]) -> bool:
    failed = [evaluation for evaluation in evaluations if not evaluation.passed]
    if len(failed) != 1:
        return False
    distance = failed[0].distance_ratio
    return distance is not None and distance <= Decimal("0.15")


def _distance_ratio(
    *,
    value: Decimal | None,
    operator: FilterOperator,
    threshold: Decimal,
) -> Decimal | None:
    if value is None or threshold == 0:
        return None
    if _compare(value, operator, threshold):
        return Decimal("0")
    if operator in (">=", ">"):
        return max((threshold - value) / abs(threshold), Decimal("0"))
    if operator in ("<=", "<"):
        return max((value - threshold) / abs(threshold), Decimal("0"))
    return abs(value - threshold) / abs(threshold)
