from datetime import date

from app.adapters.tushare.client import TushareClient
from app.adapters.tushare.registry import (
    TUSHARE_API_SPECS,
    TUSHARE_API_SPECS_BY_NAME,
    TushareApiParamMode,
)


def test_registry_has_unique_api_names_and_tables() -> None:
    api_names = [spec.api_name for spec in TUSHARE_API_SPECS]
    table_names = [spec.table_name for spec in TUSHARE_API_SPECS]

    assert len(api_names) == len(set(api_names)) == 41
    assert len(table_names) == len(set(table_names)) == 41
    assert set(TUSHARE_API_SPECS_BY_NAME) == set(api_names)


def test_stock_st_warning_uses_actual_tushare_api_name_and_field_alias() -> None:
    spec = TUSHARE_API_SPECS_BY_NAME["stock_st_warning"]

    assert spec.query_api_name == "st"
    assert spec.table_name == "stock_st_warning"
    assert spec.field_aliases == {"st_type": "st_tpye"}


def test_registered_api_params_include_default_params() -> None:
    params = TushareClient._params_for_spec(
        mode=TushareApiParamMode.TS_CODE_WINDOW,
        trade_date=None,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 24),
        ts_code="000001.SZ",
        month=None,
        extra_params={"freq": "1min"},
    )

    assert params == {
        "freq": "1min",
        "ts_code": "000001.SZ",
        "start_date": "20260501",
        "end_date": "20260524",
    }


def test_rename_fields_preserves_existing_target_value() -> None:
    record = {"ts_code": "000001.SZ", "st_type": "S", "st_tpye": "existing"}

    result = TushareClient._rename_fields(record, field_aliases={"st_type": "st_tpye"})

    assert result == {"ts_code": "000001.SZ", "st_type": "S", "st_tpye": "existing"}
