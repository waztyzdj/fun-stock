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
