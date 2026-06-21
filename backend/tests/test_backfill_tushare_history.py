from datetime import date
from typing import cast

from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.adapters.tushare import TushareRateLimitError
from app.adapters.tushare.registry import TUSHARE_API_SPECS_BY_NAME, TushareApiParamMode
from app.engines.data_sync.tushare.market_data_sync import SyncSummary
from app.tasks.backfill_tushare_history import (
    BackfillHistoryGroup,
    HistoryBackfillWindow,
    _history_backfill_lock_names,
    _pending_stock_quarters,
    _period_end_trade_dates,
    _select_api_names,
    _stock_level_cursor,
    _sync_window_with_rate_limit_retry,
    _windows_for_spec,
)


class FakeSession:
    pass


def fake_session() -> Session:
    return cast(Session, FakeSession())


def test_history_backfill_default_selection_excludes_core_and_realtime_apis() -> None:
    selection = _select_api_names(group=BackfillHistoryGroup.ALL, api_names=set())

    assert "daily" not in selection.api_names
    assert "daily_basic" not in selection.api_names
    assert "adj_factor" not in selection.api_names
    assert "stk_mins" not in selection.api_names
    assert "income" in selection.api_names
    assert "fina_mainbz" not in selection.api_names
    assert "disclosure_date" not in selection.api_names
    assert "weekly" in selection.api_names


def test_ts_code_selection_uses_core_finance_priority_without_deferred_apis() -> None:
    selection = _select_api_names(group=BackfillHistoryGroup.TS_CODE, api_names=set())

    assert selection.api_names[:4] == [
        "income",
        "balancesheet",
        "fina_indicator",
        "fina_audit",
    ]
    assert "fina_mainbz" not in selection.api_names
    assert "disclosure_date" not in selection.api_names


def test_deferred_ts_code_selection_only_contains_low_priority_large_window_apis() -> None:
    selection = _select_api_names(group=BackfillHistoryGroup.TS_DEFERRED, api_names=set())

    assert selection.api_names == ["fina_mainbz", "disclosure_date"]


def test_history_backfill_locks_are_scoped_by_api() -> None:
    safe_selection = _select_api_names(group=BackfillHistoryGroup.SAFE, api_names=set())
    finance_lock_names = set(_history_backfill_lock_names(["fina_indicator"]))
    safe_lock_names = set(_history_backfill_lock_names(safe_selection.api_names))

    assert finance_lock_names == {"tushare-history-backfill:fina_indicator"}
    assert finance_lock_names.isdisjoint(safe_lock_names)


def test_trade_date_windows_are_limited_by_batch_trade_days(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tasks.backfill_tushare_history._history_cursor",
        lambda session, api_name: None,
    )

    windows = _windows_for_spec(
        session=fake_session(),
        spec=TUSHARE_API_SPECS_BY_NAME["weekly"],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        open_trade_dates=[date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        stock_codes=[],
        batch_trade_days=2,
        batch_calendar_days=30,
        batch_months=12,
        max_windows_per_api=100,
    )

    assert [window.trade_date for window in windows] == [date(2026, 1, 2), date(2026, 1, 6)]
    assert [window.cursor_value for window in windows] == ["20260102", "20260106"]


def test_ts_code_window_backfill_limits_stock_windows(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tasks.backfill_tushare_history._history_cursor",
        lambda session, api_name: None,
    )

    windows = _windows_for_spec(
        session=fake_session(),
        spec=TUSHARE_API_SPECS_BY_NAME["income"],
        start_date=date(2020, 1, 1),
        end_date=date(2026, 5, 27),
        open_trade_dates=[],
        stock_codes=["000001.SZ", "000002.SZ", "000004.SZ"],
        batch_trade_days=20,
        batch_calendar_days=180,
        batch_months=12,
        max_windows_per_api=2,
    )

    assert [window.ts_code for window in windows] == ["000001.SZ", "000002.SZ"]
    assert {window.mode for window in windows} == {TushareApiParamMode.TS_CODE_WINDOW}
    assert {window.cursor_value for window in windows} == {"000001.SZ", "000002.SZ"}


def test_stock_level_end_date_backfill_uses_one_window_per_stock(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.backfill_tushare_history._history_cursor",
        lambda session, api_name: None,
    )

    windows = _windows_for_spec(
        session=fake_session(),
        spec=TUSHARE_API_SPECS_BY_NAME["fina_mainbz"],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        open_trade_dates=[],
        stock_codes=["000001.SZ", "000002.SZ"],
        batch_trade_days=20,
        batch_calendar_days=180,
        batch_months=12,
        max_windows_per_api=3,
    )

    assert [(window.ts_code, window.end_date) for window in windows] == [
        ("000001.SZ", date(2026, 6, 30)),
        ("000002.SZ", date(2026, 6, 30)),
    ]
    assert windows[-1].cursor_value == "000002.SZ"


def test_ts_code_end_date_backfill_uses_composite_cursor_order_for_disclosure_date(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.backfill_tushare_history._history_cursor",
        lambda session, api_name: None,
    )

    windows = _windows_for_spec(
        session=fake_session(),
        spec=TUSHARE_API_SPECS_BY_NAME["disclosure_date"],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        open_trade_dates=[],
        stock_codes=["000001.SZ", "000002.SZ"],
        batch_trade_days=20,
        batch_calendar_days=180,
        batch_months=12,
        max_windows_per_api=3,
    )

    assert [(window.ts_code, window.end_date) for window in windows] == [
        ("000001.SZ", date(2026, 3, 31)),
        ("000001.SZ", date(2026, 6, 30)),
        ("000002.SZ", date(2026, 3, 31)),
    ]
    assert windows[-1].cursor_value == "000002.SZ:20260331"


def test_pending_stock_quarters_resumes_after_composite_cursor(monkeypatch: MonkeyPatch) -> None:
    del monkeypatch

    pending = _pending_stock_quarters(
        stock_codes=["000001.SZ", "000002.SZ"],
        quarter_ends=[date(2026, 3, 31), date(2026, 6, 30)],
        cursor="000001.SZ:20260331",
    )

    assert pending == [
        ("000001.SZ", date(2026, 6, 30)),
        ("000002.SZ", date(2026, 3, 31)),
        ("000002.SZ", date(2026, 6, 30)),
    ]


def test_stock_level_cursor_resumes_after_legacy_composite_cursor() -> None:
    assert _stock_level_cursor("000001.SZ:20260331") == "000001.SZ"
    assert _stock_level_cursor("000001.SZ") == "000001.SZ"
    assert _stock_level_cursor(None) is None


def test_period_end_trade_dates_keep_last_open_day_for_week_and_month() -> None:
    trade_dates = [
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 30),
        date(2026, 2, 2),
    ]

    assert _period_end_trade_dates(trade_dates, period="week") == [
        date(2026, 1, 2),
        date(2026, 1, 6),
        date(2026, 1, 30),
        date(2026, 2, 2),
    ]
    assert _period_end_trade_dates(trade_dates, period="month") == [
        date(2026, 1, 30),
        date(2026, 2, 2),
    ]


def test_sync_window_retries_after_rate_limit(monkeypatch: MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    def fake_sync_window(window: HistoryBackfillWindow) -> SyncSummary:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TushareRateLimitError("rate limit")
        return SyncSummary(api_name=window.api_name, rows_fetched=1, rows_upserted=1)

    monkeypatch.setattr("app.tasks.backfill_tushare_history._sync_window", fake_sync_window)
    monkeypatch.setattr("app.tasks.backfill_tushare_history.sleep", sleeps.append)

    summary = _sync_window_with_rate_limit_retry(
        HistoryBackfillWindow(
            api_name="income",
            mode=TushareApiParamMode.TS_CODE_WINDOW,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            ts_code="000001.SZ",
            cursor_value="000001.SZ",
        ),
        retry_sleep_seconds=3600,
        max_retries=1,
    )

    assert summary == SyncSummary(api_name="income", rows_fetched=1, rows_upserted=1)
    assert calls == 2
    assert sleeps == [3600]
