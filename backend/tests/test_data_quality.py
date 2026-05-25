from datetime import date

from app.services.data_quality import (
    DataQualityContext,
    DataQualityStatus,
    TushareDataQualityService,
)


def test_quality_service_warns_for_zero_rows() -> None:
    results = TushareDataQualityService().evaluate(
        DataQualityContext(
            api_name="daily",
            table_name="daily",
            records=[],
            rows_upserted=0,
            window_start="20260522",
            window_end="20260522",
        )
    )

    assert ("row_count", DataQualityStatus.WARNING) in {
        (result.check_name, result.status) for result in results
    }
    assert ("trade_date_gap", DataQualityStatus.WARNING) in {
        (result.check_name, result.status) for result in results
    }


def test_quality_service_fails_for_missing_required_field() -> None:
    results = TushareDataQualityService().evaluate(
        DataQualityContext(
            api_name="daily",
            table_name="daily",
            records=[{"ts_code": None, "trade_date": date(2026, 5, 22)}],
            rows_upserted=1,
            window_start="20260522",
            window_end="20260522",
        )
    )

    assert ("required_field:ts_code", DataQualityStatus.FAILED) in {
        (result.check_name, result.status) for result in results
    }


def test_quality_service_fails_for_trade_date_mismatch() -> None:
    results = TushareDataQualityService().evaluate(
        DataQualityContext(
            api_name="daily",
            table_name="daily",
            records=[{"ts_code": "000001.SZ", "trade_date": date(2026, 5, 21)}],
            rows_upserted=1,
            window_start="20260522",
            window_end="20260522",
        )
    )

    assert ("trade_date_gap", DataQualityStatus.FAILED) in {
        (result.check_name, result.status) for result in results
    }


def test_quality_service_allows_empty_finance_windows() -> None:
    results = TushareDataQualityService().evaluate(
        DataQualityContext(
            api_name="income",
            table_name="income",
            records=[],
            rows_upserted=0,
            window_start="20260501",
            window_end="20260525",
        )
    )

    assert ("row_count", DataQualityStatus.PASSED) in {
        (result.check_name, result.status) for result in results
    }


def test_quality_service_uses_ts_code_as_new_share_required_field() -> None:
    results = TushareDataQualityService().evaluate(
        DataQualityContext(
            api_name="new_share",
            table_name="new_share",
            records=[{"ts_code": "001001.SZ", "start_date": None}],
            rows_upserted=1,
            window_start="20260525",
            window_end="20260525",
        )
    )

    assert ("required_field:ts_code", DataQualityStatus.PASSED) in {
        (result.check_name, result.status) for result in results
    }
