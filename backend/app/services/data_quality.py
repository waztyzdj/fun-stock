from dataclasses import dataclass
from datetime import date
from typing import Any

from app.adapters.tushare.registry import TUSHARE_API_SPECS_BY_NAME, TushareApiParamMode


class DataQualityStatus:
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class DataQualitySeverity:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class DataQualityCheckResult:
    check_name: str
    status: str
    severity: str
    message: str
    observed_value: str


@dataclass(frozen=True)
class DataQualityContext:
    api_name: str
    table_name: str
    records: list[dict[str, object]]
    rows_upserted: int
    window_start: str | None
    window_end: str | None


class TushareDataQualityService:
    def evaluate(self, context: DataQualityContext) -> list[DataQualityCheckResult]:
        return [
            self._row_count_check(context),
            self._upsert_count_check(context),
            *self._required_field_checks(context),
            *self._trade_date_gap_checks(context),
        ]

    def _row_count_check(self, context: DataQualityContext) -> DataQualityCheckResult:
        if context.records:
            return _passed(
                "row_count",
                "接口返回行数大于 0。",
                str(len(context.records)),
            )
        return _warning(
            "row_count",
            "接口返回 0 行。可能是正常空窗口，也可能是参数、交易日或权限异常，"
            "需要结合接口语义排查。",
            "0",
        )

    def _upsert_count_check(self, context: DataQualityContext) -> DataQualityCheckResult:
        if not context.records:
            return _passed("upsert_count", "无返回数据，无需写入。", "0")
        if context.rows_upserted > 0:
            return _passed(
                "upsert_count",
                "写入行数大于 0。",
                str(context.rows_upserted),
            )
        return _failed(
            "upsert_count",
            "接口返回了数据，但写入行数为 0，可能存在字段过滤、主键或约束问题。",
            "0",
        )

    def _required_field_checks(
        self,
        context: DataQualityContext,
    ) -> list[DataQualityCheckResult]:
        if not context.records:
            return []
        required_fields = _required_fields_for_api(context.api_name)
        results: list[DataQualityCheckResult] = []
        for field_name in required_fields:
            missing_count = sum(
                1 for record in context.records if _is_empty(record.get(field_name))
            )
            if missing_count == 0:
                results.append(
                    _passed(
                        f"required_field:{field_name}",
                        f"关键字段 `{field_name}` 无空值。",
                        "0",
                    )
                )
            else:
                results.append(
                    _failed(
                        f"required_field:{field_name}",
                        f"关键字段 `{field_name}` 存在空值。",
                        str(missing_count),
                    )
                )
        return results

    def _trade_date_gap_checks(
        self,
        context: DataQualityContext,
    ) -> list[DataQualityCheckResult]:
        spec = TUSHARE_API_SPECS_BY_NAME[_base_api_name(context.api_name)]
        if spec.param_mode not in {
            TushareApiParamMode.TRADE_DATE,
            TushareApiParamMode.TRADE_DATE_WITH_MARKET,
        }:
            return []
        if context.window_start is None:
            return []
        trade_dates = {
            _compact_date(record.get("trade_date"))
            for record in context.records
            if record.get("trade_date")
        }
        expected_trade_date = context.window_start
        if not context.records:
            return [
                _warning(
                    "trade_date_gap",
                    f"交易日 `{expected_trade_date}` 返回 0 行。",
                    "0",
                )
            ]
        if trade_dates == {expected_trade_date}:
            return [
                _passed(
                    "trade_date_gap",
                    f"返回数据均属于交易日 `{expected_trade_date}`。",
                    str(len(trade_dates)),
                )
            ]
        return [
            _failed(
                "trade_date_gap",
                f"返回数据交易日与期望交易日 `{expected_trade_date}` 不一致。",
                ",".join(sorted(trade_dates)),
            )
        ]


def _required_fields_for_api(api_name: str) -> tuple[str, ...]:
    spec = TUSHARE_API_SPECS_BY_NAME[_base_api_name(api_name)]
    if spec.param_mode in {
        TushareApiParamMode.TRADE_DATE,
        TushareApiParamMode.TRADE_DATE_WITH_MARKET,
    }:
        return ("ts_code", "trade_date")
    if spec.param_mode is TushareApiParamMode.TS_CODE:
        return ("ts_code",)
    if spec.param_mode is TushareApiParamMode.TS_CODE_WINDOW:
        return ("ts_code",)
    if spec.param_mode is TushareApiParamMode.TS_CODE_END_DATE:
        return ("ts_code", "end_date")
    if spec.param_mode is TushareApiParamMode.MONTH:
        return ("month",)
    if spec.param_mode is TushareApiParamMode.CALENDAR_WINDOW:
        return ("start_date",) if api_name == "new_share" else ()
    if spec.param_mode is TushareApiParamMode.LIST_STATUS:
        return ("ts_code",)
    return ()


def _base_api_name(api_name: str) -> str:
    return api_name.removesuffix("_window")


def _is_empty(value: object) -> bool:
    return value is None or value == ""


def _compact_date(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value)


def _passed(check_name: str, message: str, observed_value: str) -> DataQualityCheckResult:
    return DataQualityCheckResult(
        check_name=check_name,
        status=DataQualityStatus.PASSED,
        severity=DataQualitySeverity.INFO,
        message=message,
        observed_value=observed_value,
    )


def _warning(check_name: str, message: str, observed_value: str) -> DataQualityCheckResult:
    return DataQualityCheckResult(
        check_name=check_name,
        status=DataQualityStatus.WARNING,
        severity=DataQualitySeverity.WARNING,
        message=message,
        observed_value=observed_value,
    )


def _failed(check_name: str, message: str, observed_value: str) -> DataQualityCheckResult:
    return DataQualityCheckResult(
        check_name=check_name,
        status=DataQualityStatus.FAILED,
        severity=DataQualitySeverity.ERROR,
        message=message,
        observed_value=observed_value,
    )
