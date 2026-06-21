from datetime import date
from decimal import Decimal

from app.repositories.factor import FactorValueSnapshot
from app.services.strategy_screening import (
    StrategyFilter,
    StrategyFilterEvaluation,
    StrategyScreeningService,
    StrategyScreenResultItem,
    StrategySort,
    StrategyUniverse,
    _distance_ratio,
    _evaluate_filters,
    _is_near_miss,
    _matches_filters,
    _sort_items,
)


def test_strategy_filter_matches_thresholds() -> None:
    snapshots = {
        "roe": FactorValueSnapshot(
            factor_code="roe",
            value=Decimal("18.5"),
            factor_date=date(2025, 12, 31),
        ),
        "debt_to_assets": FactorValueSnapshot(
            factor_code="debt_to_assets",
            value=Decimal("42"),
            factor_date=date(2025, 12, 31),
        ),
    }

    assert _matches_filters(
        [
            StrategyFilter(factor_code="roe", operator=">=", value=Decimal("15")),
            StrategyFilter(factor_code="debt_to_assets", operator="<=", value=Decimal("60")),
        ],
        snapshots,
    )
    assert not _matches_filters(
        [StrategyFilter(factor_code="roe", operator=">=", value=Decimal("20"))],
        snapshots,
    )


def test_strategy_sort_uses_factor_values() -> None:
    first = StrategyScreenResultItem(
        ts_code="000001.SZ",
        name="A",
        industry=None,
        market=None,
        list_date=None,
        factor_values=[
            FactorValueSnapshot("roe", Decimal("12"), date(2025, 12, 31)),
        ],
    )
    second = StrategyScreenResultItem(
        ts_code="000002.SZ",
        name="B",
        industry=None,
        market=None,
        list_date=None,
        factor_values=[
            FactorValueSnapshot("roe", Decimal("20"), date(2025, 12, 31)),
        ],
    )

    result = _sort_items(
        [first, second],
        [StrategySort(factor_code="roe", direction="desc")],
    )

    assert [item.ts_code for item in result] == ["000002.SZ", "000001.SZ"]


def test_strategy_filter_evaluation_explains_passed_and_missing_values() -> None:
    snapshots = {
        "roe": FactorValueSnapshot(
            factor_code="roe",
            value=Decimal("18.5"),
            factor_date=date(2025, 12, 31),
        )
    }

    evaluations = _evaluate_filters(
        [
            StrategyFilter(factor_code="roe", operator=">=", value=Decimal("15")),
            StrategyFilter(factor_code="debt_to_assets", operator="<=", value=Decimal("60")),
        ],
        snapshots,
    )

    assert evaluations[0].passed
    assert evaluations[0].value == Decimal("18.5")
    assert not evaluations[1].passed
    assert evaluations[1].value is None


def test_strategy_near_miss_allows_one_close_failed_filter() -> None:
    evaluations = [
        StrategyFilterEvaluation(
            factor_code="roe",
            operator=">=",
            threshold=Decimal("12"),
            value=Decimal("11"),
            factor_date=date(2025, 12, 31),
            passed=False,
            distance_ratio=Decimal("0.083333"),
        )
    ]

    assert _is_near_miss(evaluations)
    distance = _distance_ratio(value=Decimal("11"), operator=">=", threshold=Decimal("12"))
    assert distance is not None
    assert distance > 0


def test_strategy_json_from_request_uses_stable_contract() -> None:
    service = StrategyScreeningService.__new__(StrategyScreeningService)
    strategy_json = service.strategy_json_from_request(
        request=type(
            "Request",
            (),
            {
                "universe": StrategyUniverse(exclude_st=True, min_list_years=3),
                "filters": [
                    StrategyFilter(factor_code="roe", operator=">=", value=Decimal("12")),
                ],
                "sort": [StrategySort(factor_code="roe", direction="desc")],
            },
        )()
    )

    assert strategy_json == {
        "universe": {"exclude_st": True, "min_list_years": 3},
        "filters": [{"factor": "roe", "op": ">=", "value": "12"}],
        "sort": [{"factor": "roe", "direction": "desc"}],
    }
