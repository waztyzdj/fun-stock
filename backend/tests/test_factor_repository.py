from datetime import date
from decimal import Decimal

from app.engines.factor.fundamental_factors import FUNDAMENTAL_FACTOR_SPECS
from app.models.factor import FactorDefinition
from app.repositories.factor import _factor_quality_status


class DummySession:
    def __init__(self) -> None:
        self.objects: dict[str, FactorDefinition] = {}
        self.flushed = 0

    def get(self, model: type[FactorDefinition], key: str) -> FactorDefinition | None:
        del model
        return self.objects.get(key)

    def add(self, item: FactorDefinition) -> None:
        self.objects[item.code] = item

    def flush(self) -> None:
        self.flushed += 1


def test_factor_spec_dictionary_includes_calculation_methods() -> None:
    assert len(FUNDAMENTAL_FACTOR_SPECS) == 20
    assert all(spec.calculation_method for spec in FUNDAMENTAL_FACTOR_SPECS)


def test_factor_definition_fields_cover_long_term_metadata() -> None:
    definition = FactorDefinition(
        code="roe",
        name="净资产收益率",
        category="profitability",
        unit="%",
        period_type="report",
        source="tushare.fina_indicator.roe",
        calculation_method="直接采用财报指标",
        description="衡量股东权益创造利润的能力",
        sort_direction="desc",
        is_active=True,
    )

    assert definition.calculation_method == "直接采用财报指标"
    assert definition.period_type == "report"


def test_factor_value_metadata_fields_are_usable() -> None:
    from app.models.factor import FactorValue

    value = FactorValue(
        factor_code="roe",
        ts_code="000001.SZ",
        factor_date=date(2025, 12, 31),
        report_end_date=date(2025, 12, 31),
        value=Decimal("12.5"),
        period_type="report",
        ann_date=date(2026, 3, 31),
        source_table="tushare.fina_indicator",
    )

    assert value.report_end_date == date(2025, 12, 31)


def test_factor_quality_status_marks_empty_warning_and_ready() -> None:
    assert (
        _factor_quality_status(
            stock_count=0,
            coverage_ratio=Decimal("0"),
            latest_factor_date=None,
        )
        == "empty"
    )
    assert (
        _factor_quality_status(
            stock_count=100,
            coverage_ratio=Decimal("0.49"),
            latest_factor_date=date(2026, 5, 31),
        )
        == "warning"
    )
    assert (
        _factor_quality_status(
            stock_count=100,
            coverage_ratio=Decimal("0.80"),
            latest_factor_date=date(2026, 5, 31),
        )
        == "ready"
    )
