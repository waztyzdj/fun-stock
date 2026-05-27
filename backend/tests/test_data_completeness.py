from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.services.data_completeness import CoreMarketCompletenessService, build_missing_date_ranges


class FakeSession:
    def __init__(self) -> None:
        self.sql_texts: list[str] = []

    def execute(self, statement: Any, params: dict[str, object]) -> object:
        del params
        sql_text = str(statement)
        self.sql_texts.append(sql_text)
        if "app.trade_calendars" in sql_text:
            return FakeResult([(date(2026, 1, 5),)])
        return FakeResult([])


class FakeResult:
    def __init__(self, rows: list[tuple[date]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[date]]:
        return self.rows


def test_build_missing_date_ranges_groups_calendar_adjacent_dates() -> None:
    ranges = build_missing_date_ranges(
        [
            date(2026, 1, 5),
            date(2026, 1, 6),
            date(2026, 1, 8),
        ]
    )

    assert [(item.start_date, item.end_date, item.days) for item in ranges] == [
        (date(2026, 1, 5), date(2026, 1, 6), 2),
        (date(2026, 1, 8), date(2026, 1, 8), 1),
    ]


def test_build_missing_date_ranges_returns_empty_list_for_complete_data() -> None:
    assert build_missing_date_ranges([]) == []


def test_completeness_scan_uses_app_tables_by_default() -> None:
    session = FakeSession()

    report = CoreMarketCompletenessService(cast(Session, session)).scan(
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 5),
    )

    assert report.layer == "app"
    assert any("app.daily_quotes" in sql_text for sql_text in session.sql_texts)
    assert any("app.daily_indicators" in sql_text for sql_text in session.sql_texts)
    assert any("app.adj_factors" in sql_text for sql_text in session.sql_texts)


def test_completeness_scan_can_use_raw_tables() -> None:
    session = FakeSession()

    report = CoreMarketCompletenessService(cast(Session, session)).scan(
        start_date=date(2026, 1, 5),
        end_date=date(2026, 1, 5),
        layer="raw",
    )

    assert report.layer == "raw"
    assert any("tushare.daily" in sql_text for sql_text in session.sql_texts)
    assert any("tushare.daily_basic" in sql_text for sql_text in session.sql_texts)
    assert any("tushare.adj_factor" in sql_text for sql_text in session.sql_texts)
