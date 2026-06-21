from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

CompletenessLayer = Literal["app", "raw"]

CORE_MARKET_TABLES: dict[CompletenessLayer, dict[str, str]] = {
    "app": {
        "daily": "app.daily_quotes",
        "index_daily": "app.index_daily_quotes",
        "daily_basic": "app.daily_indicators",
        "adj_factor": "app.adj_factors",
    },
    "raw": {
        "daily": "tushare.daily",
        "index_daily": "tushare.index_daily",
        "daily_basic": "tushare.daily_basic",
        "adj_factor": "tushare.adj_factor",
    },
}


@dataclass(frozen=True)
class MissingDateRange:
    start_date: date
    end_date: date
    days: int


@dataclass(frozen=True)
class TableCompletenessResult:
    api_name: str
    table_name: str
    expected_trade_days: int
    present_trade_days: int
    missing_trade_days: int
    latest_present_date: date | None
    missing_dates: list[date]
    repair_ranges: list[MissingDateRange]

    @property
    def completeness_ratio(self) -> float:
        if self.expected_trade_days == 0:
            return 1.0
        return (self.expected_trade_days - self.missing_trade_days) / self.expected_trade_days


@dataclass(frozen=True)
class CoreMarketCompletenessReport:
    layer: CompletenessLayer
    exchange: str
    start_date: date
    end_date: date
    tables: list[TableCompletenessResult]

    @property
    def total_missing_trade_days(self) -> int:
        return sum(table.missing_trade_days for table in self.tables)


class CoreMarketCompletenessService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def scan(
        self,
        *,
        start_date: date,
        end_date: date,
        exchange: str = "SSE",
        layer: CompletenessLayer = "app",
        api_names: list[str] | None = None,
        missing_limit: int = 30,
    ) -> CoreMarketCompletenessReport:
        if start_date > end_date:
            msg = "start_date must be less than or equal to end_date."
            raise ValueError(msg)

        table_mapping = _table_mapping(layer)
        selected_api_names = api_names or list(table_mapping)
        unknown_api_names = sorted(set(selected_api_names) - set(table_mapping))
        if unknown_api_names:
            msg = f"Unsupported completeness APIs: {', '.join(unknown_api_names)}"
            raise ValueError(msg)

        expected_dates = self._open_trade_dates(
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
        )
        tables = [
            self._scan_table(
                api_name=api_name,
                table_name=table_mapping[api_name],
                expected_dates=expected_dates,
                start_date=start_date,
                end_date=end_date,
                missing_limit=missing_limit,
            )
            for api_name in selected_api_names
        ]
        return CoreMarketCompletenessReport(
            layer=layer,
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            tables=tables,
        )

    def _open_trade_dates(
        self,
        *,
        exchange: str,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        result = self.session.execute(
            text(
                """
                SELECT cal_date
                FROM app.trade_calendars
                WHERE exchange = :exchange
                  AND is_open = true
                  AND cal_date BETWEEN :start_date AND :end_date
                ORDER BY cal_date
                """
            ),
            {"exchange": exchange, "start_date": start_date, "end_date": end_date},
        )
        return [row[0] for row in result.all()]

    def _scan_table(
        self,
        *,
        api_name: str,
        table_name: str,
        expected_dates: list[date],
        start_date: date,
        end_date: date,
        missing_limit: int,
    ) -> TableCompletenessResult:
        present_dates = self._present_dates(
            table_name=table_name,
            start_date=start_date,
            end_date=end_date,
        )
        missing_dates = [
            trade_date for trade_date in expected_dates if trade_date not in present_dates
        ]
        return TableCompletenessResult(
            api_name=api_name,
            table_name=table_name,
            expected_trade_days=len(expected_dates),
            present_trade_days=len(present_dates),
            missing_trade_days=len(missing_dates),
            latest_present_date=max(present_dates) if present_dates else None,
            missing_dates=missing_dates[:missing_limit],
            repair_ranges=build_missing_date_ranges(missing_dates),
        )

    def _present_dates(
        self,
        *,
        table_name: str,
        start_date: date,
        end_date: date,
    ) -> set[date]:
        result = self.session.execute(
            text(
                f"""
                SELECT trade_date
                FROM {table_name}
                WHERE trade_date BETWEEN :start_date AND :end_date
                GROUP BY trade_date
                ORDER BY trade_date
                """
            ),
            {"start_date": start_date, "end_date": end_date},
        )
        return {row[0] for row in result.all()}


def _table_mapping(layer: CompletenessLayer) -> dict[str, str]:
    try:
        return CORE_MARKET_TABLES[layer]
    except KeyError as exc:
        msg = f"Unsupported completeness layer: {layer}"
        raise ValueError(msg) from exc


def build_missing_date_ranges(missing_dates: list[date]) -> list[MissingDateRange]:
    if not missing_dates:
        return []

    ranges: list[MissingDateRange] = []
    range_start = missing_dates[0]
    previous_date = missing_dates[0]
    days = 1
    for missing_date in missing_dates[1:]:
        if (missing_date - previous_date).days == 1:
            days += 1
            previous_date = missing_date
            continue
        ranges.append(MissingDateRange(range_start, previous_date, days))
        range_start = missing_date
        previous_date = missing_date
        days = 1
    ranges.append(MissingDateRange(range_start, previous_date, days))
    return ranges
