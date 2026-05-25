from datetime import date

from app.engines.data_sync.tushare.scheduler import (
    TusharePlanWindow,
    TushareScheduleKind,
    TushareSchedulerRunItem,
    TushareSchedulerRunResult,
)
from app.tasks.tushare_celery import _configured_api_names, _scheduler_result_payload


def test_configured_api_names_ignores_empty_values() -> None:
    assert _configured_api_names("daily, daily_basic,, adj_factor ") == {
        "daily",
        "daily_basic",
        "adj_factor",
    }


def test_scheduler_result_payload_is_json_serializable_summary() -> None:
    result = TushareSchedulerRunResult(
        items=[
            TushareSchedulerRunItem(window=_fake_window("daily"), status="success", rows_fetched=2),
            TushareSchedulerRunItem(window=_fake_window("income"), status="failed"),
        ]
    )

    assert _scheduler_result_payload(result) == {
        "status": "success",
        "success": 1,
        "failed": 1,
        "blocked": 0,
        "skipped": 0,
        "rows_fetched": 2,
        "rows_upserted": 0,
    }


def _fake_window(api_name: str) -> TusharePlanWindow:
    return TusharePlanWindow(
        api_name=api_name,
        schedule=TushareScheduleKind.DAILY,
        trade_date=date(2026, 5, 22),
        start_date=None,
        end_date=None,
        ts_code=None,
        month=None,
        reason="test",
        due=True,
    )
