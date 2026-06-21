from collections.abc import Mapping, Sequence
from datetime import date
from time import sleep
from typing import Any, Protocol

import pandas as pd

import tushare as ts
from app.adapters.tushare.registry import (
    TUSHARE_API_SPECS_BY_NAME,
    TushareApiParamMode,
    yyyymmdd,
)
from app.core.config import get_settings

TushareRecord = dict[str, Any]


class TushareTokenMissingError(RuntimeError):
    pass


class TushareInsufficientPointsError(RuntimeError):
    pass


class TushareRateLimitError(RuntimeError):
    pass


class TushareTransientNetworkError(RuntimeError):
    pass


class TushareDataClient(Protocol):
    def stock_basic(self) -> list[TushareRecord]:
        raise NotImplementedError

    def trade_cal(self, *, start_date: date, end_date: date, exchange: str) -> list[TushareRecord]:
        raise NotImplementedError

    def daily(self, *, trade_date: date) -> list[TushareRecord]:
        raise NotImplementedError

    def index_daily(self, *, trade_date: date) -> list[TushareRecord]:
        raise NotImplementedError

    def index_daily_window(
        self,
        *,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> list[TushareRecord]:
        raise NotImplementedError

    def daily_basic(self, *, trade_date: date) -> list[TushareRecord]:
        raise NotImplementedError

    def adj_factor(self, *, trade_date: date) -> list[TushareRecord]:
        raise NotImplementedError

    def income(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[TushareRecord]:
        raise NotImplementedError

    def balancesheet(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[TushareRecord]:
        raise NotImplementedError

    def fina_indicator(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[TushareRecord]:
        raise NotImplementedError

    def query_api(
        self,
        api_name: str,
        *,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        ts_code: str | None = None,
        month: str | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> list[TushareRecord]:
        raise NotImplementedError


class TushareClient:
    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self.token = token or settings.tushare_token
        if not self.token:
            raise TushareTokenMissingError("TUSHARE_TOKEN is required to fetch Tushare data.")
        self._pro = ts.pro_api(self.token)
        self.rate_limit_sleep_seconds = settings.tushare_rate_limit_sleep_seconds
        self.rate_limit_max_retries = settings.tushare_rate_limit_max_retries
        self.network_retry_sleep_seconds = settings.tushare_network_retry_sleep_seconds
        self.network_max_retries = settings.tushare_network_max_retries

    def stock_basic(self) -> list[TushareRecord]:
        fields = [
            "ts_code",
            "symbol",
            "name",
            "area",
            "industry",
            "fullname",
            "enname",
            "cnspell",
            "market",
            "exchange",
            "curr_type",
            "list_status",
            "list_date",
            "delist_date",
            "is_hs",
            "act_name",
            "act_ent_type",
        ]
        records: list[TushareRecord] = []
        for list_status in ["L", "D", "P"]:
            records.extend(
                self._call(
                    "stock_basic",
                    params={"list_status": list_status},
                    fields=fields,
                )
            )
        return records

    def trade_cal(
        self,
        *,
        start_date: date,
        end_date: date,
        exchange: str = "",
    ) -> list[TushareRecord]:
        return self._call(
            "trade_cal",
            params={
                "exchange": exchange,
                "start_date": self._format_date(start_date),
                "end_date": self._format_date(end_date),
            },
            fields=["exchange", "cal_date", "is_open", "pretrade_date"],
        )

    def daily(self, *, trade_date: date) -> list[TushareRecord]:
        return self._call(
            "daily",
            params={"trade_date": self._format_date(trade_date)},
            fields=[
                "ts_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "change",
                "pct_chg",
                "vol",
                "amount",
            ],
        )

    def index_daily(self, *, trade_date: date) -> list[TushareRecord]:
        return self._call(
            "index_daily",
            params={"trade_date": self._format_date(trade_date)},
            fields=[
                "ts_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "change",
                "pct_chg",
                "vol",
                "amount",
            ],
        )

    def index_daily_window(
        self,
        *,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> list[TushareRecord]:
        return self._call(
            "index_daily",
            params={
                "ts_code": ts_code,
                "start_date": self._format_date(start_date),
                "end_date": self._format_date(end_date),
            },
            fields=[
                "ts_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "change",
                "pct_chg",
                "vol",
                "amount",
            ],
        )

    def daily_basic(self, *, trade_date: date) -> list[TushareRecord]:
        return self._call(
            "daily_basic",
            params={"trade_date": self._format_date(trade_date)},
            fields=[
                "ts_code",
                "trade_date",
                "close",
                "turnover_rate",
                "turnover_rate_f",
                "volume_ratio",
                "pe",
                "pe_ttm",
                "pb",
                "ps",
                "ps_ttm",
                "dv_ratio",
                "dv_ttm",
                "total_share",
                "float_share",
                "free_share",
                "total_mv",
                "circ_mv",
            ],
        )

    def adj_factor(self, *, trade_date: date) -> list[TushareRecord]:
        return self._call(
            "adj_factor",
            params={"trade_date": self._format_date(trade_date)},
            fields=["ts_code", "trade_date", "adj_factor"],
        )

    def income(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[TushareRecord]:
        return self._finance_call(
            "income",
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
        )

    def balancesheet(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[TushareRecord]:
        return self._finance_call(
            "balancesheet",
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
        )

    def fina_indicator(
        self,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[TushareRecord]:
        return self._finance_call(
            "fina_indicator",
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
        )

    def query_api(
        self,
        api_name: str,
        *,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        ts_code: str | None = None,
        month: str | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> list[TushareRecord]:
        spec = TUSHARE_API_SPECS_BY_NAME[api_name]
        params = self._params_for_spec(
            mode=spec.param_mode,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            ts_code=ts_code,
            month=month,
            extra_params={**(spec.default_params or {}), **dict(extra_params or {})},
        )
        if spec.param_mode is TushareApiParamMode.LIST_STATUS:
            records: list[TushareRecord] = []
            for list_status in ["L", "D", "P"]:
                records.extend(
                    self._call(
                        spec.query_api_name,
                        params={**params, "list_status": list_status},
                        field_aliases=spec.field_aliases,
                    )
                )
            return records
        return self._call(
            spec.query_api_name,
            params=params,
            field_aliases=spec.field_aliases,
        )

    def _finance_call(
        self,
        api_name: str,
        *,
        start_date: date,
        end_date: date,
        ts_code: str | None = None,
    ) -> list[TushareRecord]:
        params: dict[str, Any] = {
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        if ts_code is not None:
            params["ts_code"] = ts_code
        return self._call(
            api_name,
            params=params,
        )

    def _call(
        self,
        api_name: str,
        *,
        params: Mapping[str, Any] | None = None,
        fields: Sequence[str] | None = None,
        field_aliases: Mapping[str, str] | None = None,
    ) -> list[TushareRecord]:
        dataframe: pd.DataFrame | None = None
        max_attempts = max(self.rate_limit_max_retries, self.network_max_retries) + 1
        for attempt in range(max_attempts):
            try:
                dataframe = self._pro.query(
                    api_name,
                    **dict(params or {}),
                    fields=",".join(fields) if fields else None,
                )
            except Exception as exc:
                message = str(exc)
                if _is_insufficient_points_message(message):
                    raise TushareInsufficientPointsError(message) from exc
                if _is_rate_limit_message(message):
                    if attempt < self.rate_limit_max_retries:
                        sleep(self.rate_limit_sleep_seconds)
                        continue
                    raise TushareRateLimitError(message) from exc
                if _is_transient_network_message(message):
                    if attempt < self.network_max_retries:
                        sleep(self.network_retry_sleep_seconds)
                        continue
                    raise TushareTransientNetworkError(message) from exc
                raise
            break
        else:
            raise TushareRateLimitError(f"Tushare API {api_name} exceeded rate limit retries.")
        if dataframe is None:
            raise TushareRateLimitError(f"Tushare API {api_name} did not return a dataframe.")
        records = self._records_from_dataframe(dataframe)
        if field_aliases is None:
            return records
        return [self._rename_fields(record, field_aliases=field_aliases) for record in records]

    @staticmethod
    def _params_for_spec(
        *,
        mode: TushareApiParamMode,
        trade_date: date | None,
        start_date: date | None,
        end_date: date | None,
        ts_code: str | None,
        month: str | None,
        extra_params: Mapping[str, Any],
    ) -> dict[str, Any]:
        params = dict(extra_params)
        if mode is TushareApiParamMode.NONE:
            return params
        if mode is TushareApiParamMode.LIST_STATUS:
            return params
        if mode is TushareApiParamMode.CALENDAR_WINDOW:
            if start_date is None or end_date is None:
                raise ValueError("start_date and end_date are required.")
            return {**params, "start_date": yyyymmdd(start_date), "end_date": yyyymmdd(end_date)}
        if mode in {TushareApiParamMode.TRADE_DATE, TushareApiParamMode.TRADE_DATE_WITH_MARKET}:
            if trade_date is None:
                raise ValueError("trade_date is required.")
            return {**params, "trade_date": yyyymmdd(trade_date)}
        if mode is TushareApiParamMode.MONTH:
            if month is None:
                raise ValueError("month is required.")
            return {**params, "month": month}
        if mode is TushareApiParamMode.TS_CODE:
            if ts_code is None:
                raise ValueError("ts_code is required.")
            return {**params, "ts_code": ts_code}
        if mode is TushareApiParamMode.TS_CODE_WINDOW:
            if ts_code is None or start_date is None or end_date is None:
                raise ValueError("ts_code, start_date, and end_date are required.")
            return {
                **params,
                "ts_code": ts_code,
                "start_date": yyyymmdd(start_date),
                "end_date": yyyymmdd(end_date),
            }
        if mode is TushareApiParamMode.TS_CODE_END_DATE:
            if ts_code is None or end_date is None:
                raise ValueError("ts_code and end_date are required.")
            return {**params, "ts_code": ts_code, "end_date": yyyymmdd(end_date)}
        raise ValueError(f"Unsupported Tushare parameter mode: {mode}")

    @staticmethod
    def _records_from_dataframe(dataframe: pd.DataFrame) -> list[TushareRecord]:
        if dataframe.empty:
            return []
        normalized = dataframe.astype(object).where(pd.notnull(dataframe), None)
        return list(normalized.to_dict(orient="records"))

    @staticmethod
    def _rename_fields(
        record: TushareRecord,
        *,
        field_aliases: Mapping[str, str],
    ) -> TushareRecord:
        renamed = dict(record)
        for source, target in field_aliases.items():
            if source in renamed and target not in renamed:
                renamed[target] = renamed.pop(source)
        return renamed

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%Y%m%d")


def _is_insufficient_points_message(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            "积分不足",
            "积分不够",
            "权限不足",
            "没有访问权限",
            "没有权限",
            "开通权限",
        )
    )


def _is_rate_limit_message(message: str) -> bool:
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in (
            "每分钟",
            "访问频次",
            "访问次数",
            "超过限制",
            "超过每分钟",
            "频率",
            "限流",
            "too many requests",
            "rate limit",
            "try again later",
        )
    )


def _is_transient_network_message(message: str) -> bool:
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in (
            "failed to resolve",
            "name or service not known",
            "temporary failure in name resolution",
            "nameresolutionerror",
            "connectionerror",
            "max retries exceeded",
            "connection timed out",
            "read timed out",
            "connection aborted",
            "remote end closed connection",
        )
    )
