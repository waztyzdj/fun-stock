from datetime import date
from types import SimpleNamespace

from pytest import MonkeyPatch

from app.engines.data_sync.tushare.scheduler import (
    TusharePlanWindow,
    TushareScheduleKind,
    TushareSchedulerRunItem,
    TushareSchedulerRunResult,
)
from app.tasks.tushare_celery import (
    RETRY_FAILED_TASK_NAME,
    SYNC_DUE_TASK_NAME,
    _configured_api_names,
    _scheduler_result_payload,
    enqueue_tushare_startup_catchup,
)


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


def test_startup_catchup_enqueues_due_and_retry_tasks(monkeypatch: MonkeyPatch) -> None:
    sent_tasks: list[str] = []
    monkeypatch.setattr(
        "app.tasks.tushare_celery.get_settings",
        lambda: SimpleNamespace(
            tushare_startup_catchup_enabled=True,
            tushare_startup_retry_failed_enabled=True,
        ),
    )
    monkeypatch.setattr(
        "app.tasks.tushare_celery.celery_app.send_task",
        sent_tasks.append,
    )

    enqueue_tushare_startup_catchup()

    assert sent_tasks == [SYNC_DUE_TASK_NAME, RETRY_FAILED_TASK_NAME]


def test_startup_catchup_can_be_disabled(monkeypatch: MonkeyPatch) -> None:
    sent_tasks: list[str] = []
    monkeypatch.setattr(
        "app.tasks.tushare_celery.get_settings",
        lambda: SimpleNamespace(
            tushare_startup_catchup_enabled=False,
            tushare_startup_retry_failed_enabled=True,
        ),
    )
    monkeypatch.setattr(
        "app.tasks.tushare_celery.celery_app.send_task",
        sent_tasks.append,
    )

    enqueue_tushare_startup_catchup()

    assert sent_tasks == []


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
