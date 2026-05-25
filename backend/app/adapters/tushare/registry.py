from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any


class TushareApiCategory(StrEnum):
    BASIC = "基础数据"
    QUOTE = "行情数据"
    FINANCE = "财务数据"


class TushareApiParamMode(StrEnum):
    NONE = "none"
    LIST_STATUS = "list_status"
    CALENDAR_WINDOW = "calendar_window"
    TRADE_DATE = "trade_date"
    TRADE_DATE_WITH_MARKET = "trade_date_with_market"
    MONTH = "month"
    TS_CODE = "ts_code"
    TS_CODE_WINDOW = "ts_code_window"
    TS_CODE_END_DATE = "ts_code_end_date"


@dataclass(frozen=True)
class TushareApiSpec:
    api_name: str
    table_name: str
    category: TushareApiCategory
    display_name: str
    doc_id: int
    param_mode: TushareApiParamMode
    default_params: dict[str, Any] | None = None
    tushare_api_name: str | None = None
    field_aliases: dict[str, str] | None = None

    @property
    def query_api_name(self) -> str:
        return self.tushare_api_name or self.api_name


def yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


TUSHARE_API_SPECS: tuple[TushareApiSpec, ...] = (
    TushareApiSpec(
        "stock_basic",
        "stock_basic",
        TushareApiCategory.BASIC,
        "股票基础信息",
        25,
        TushareApiParamMode.LIST_STATUS,
    ),
    TushareApiSpec(
        "stk_premarket",
        "stk_premarket",
        TushareApiCategory.BASIC,
        "股本情况（盘前）",
        329,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "trade_cal",
        "trade_cal",
        TushareApiCategory.BASIC,
        "交易日历",
        26,
        TushareApiParamMode.CALENDAR_WINDOW,
        {"exchange": "SSE"},
    ),
    TushareApiSpec(
        "stock_st",
        "stock_st",
        TushareApiCategory.BASIC,
        "ST 股票列表",
        397,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "stock_st_warning",
        "stock_st_warning",
        TushareApiCategory.BASIC,
        "ST 预警数据",
        423,
        TushareApiParamMode.NONE,
        tushare_api_name="st",
        field_aliases={"st_type": "st_tpye"},
    ),
    TushareApiSpec(
        "stock_hsgt",
        "stock_hsgt",
        TushareApiCategory.BASIC,
        "沪深港通股票列表",
        398,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "namechange",
        "namechange",
        TushareApiCategory.BASIC,
        "股票曾用名",
        100,
        TushareApiParamMode.TS_CODE,
    ),
    TushareApiSpec(
        "stock_company",
        "stock_company",
        TushareApiCategory.BASIC,
        "上市公司基本信息",
        112,
        TushareApiParamMode.NONE,
    ),
    TushareApiSpec(
        "stk_managers",
        "stk_managers",
        TushareApiCategory.BASIC,
        "上市公司管理层",
        193,
        TushareApiParamMode.TS_CODE,
    ),
    TushareApiSpec(
        "stk_rewards",
        "stk_rewards",
        TushareApiCategory.BASIC,
        "管理层薪酬和持股",
        194,
        TushareApiParamMode.TS_CODE,
    ),
    TushareApiSpec(
        "bse_mapping",
        "bse_mapping",
        TushareApiCategory.BASIC,
        "北交所新旧代码对照表",
        375,
        TushareApiParamMode.NONE,
    ),
    TushareApiSpec(
        "new_share",
        "new_share",
        TushareApiCategory.BASIC,
        "IPO 新股列表",
        123,
        TushareApiParamMode.CALENDAR_WINDOW,
    ),
    TushareApiSpec(
        "bak_basic",
        "bak_basic",
        TushareApiCategory.BASIC,
        "股票历史列表",
        262,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "daily",
        "daily",
        TushareApiCategory.QUOTE,
        "A 股日线行情",
        27,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "rt_k",
        "rt_k",
        TushareApiCategory.QUOTE,
        "A 股实时日线",
        372,
        TushareApiParamMode.TS_CODE,
    ),
    TushareApiSpec(
        "stk_mins",
        "stk_mins",
        TushareApiCategory.QUOTE,
        "股票历史分钟行情",
        370,
        TushareApiParamMode.TS_CODE_WINDOW,
        {"freq": "1min"},
    ),
    TushareApiSpec(
        "rt_min",
        "rt_min",
        TushareApiCategory.QUOTE,
        "A 股实时分钟",
        374,
        TushareApiParamMode.TS_CODE,
        {"freq": "1MIN"},
    ),
    TushareApiSpec(
        "rt_min_daily",
        "rt_min_daily",
        TushareApiCategory.QUOTE,
        "实时分钟日内数据",
        457,
        TushareApiParamMode.TS_CODE,
        {"freq": "1MIN"},
    ),
    TushareApiSpec(
        "weekly",
        "weekly",
        TushareApiCategory.QUOTE,
        "周线行情",
        144,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "monthly",
        "monthly",
        TushareApiCategory.QUOTE,
        "月线行情",
        145,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "stk_weekly_monthly",
        "stk_weekly_monthly",
        TushareApiCategory.QUOTE,
        "股票周/月线行情",
        336,
        TushareApiParamMode.TRADE_DATE,
        {"freq": "week"},
    ),
    TushareApiSpec(
        "stk_week_month_adj",
        "stk_week_month_adj",
        TushareApiCategory.QUOTE,
        "股票周/月复权行情",
        365,
        TushareApiParamMode.TRADE_DATE,
        {"freq": "week"},
    ),
    TushareApiSpec(
        "adj_factor",
        "adj_factor",
        TushareApiCategory.QUOTE,
        "复权因子",
        28,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "daily_basic",
        "daily_basic",
        TushareApiCategory.QUOTE,
        "每日指标",
        32,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "stk_limit",
        "stk_limit",
        TushareApiCategory.QUOTE,
        "每日涨跌停价格",
        183,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "suspend_d",
        "suspend_d",
        TushareApiCategory.QUOTE,
        "每日停复牌信息",
        214,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "hsgt_top10",
        "hsgt_top10",
        TushareApiCategory.QUOTE,
        "沪深股通十大成交股",
        48,
        TushareApiParamMode.TRADE_DATE_WITH_MARKET,
        {"market_type": "1"},
    ),
    TushareApiSpec(
        "ggt_top10",
        "ggt_top10",
        TushareApiCategory.QUOTE,
        "港股通十大成交股",
        49,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "ggt_daily",
        "ggt_daily",
        TushareApiCategory.QUOTE,
        "港股通每日成交统计",
        196,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "ggt_monthly",
        "ggt_monthly",
        TushareApiCategory.QUOTE,
        "港股通每月成交统计",
        197,
        TushareApiParamMode.MONTH,
    ),
    TushareApiSpec(
        "bak_daily",
        "bak_daily",
        TushareApiCategory.QUOTE,
        "备用行情",
        255,
        TushareApiParamMode.TRADE_DATE,
    ),
    TushareApiSpec(
        "income",
        "income",
        TushareApiCategory.FINANCE,
        "利润表",
        33,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "balancesheet",
        "balancesheet",
        TushareApiCategory.FINANCE,
        "资产负债表",
        36,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "cashflow_vip",
        "cashflow_vip",
        TushareApiCategory.FINANCE,
        "现金流量表",
        44,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "forecast",
        "forecast",
        TushareApiCategory.FINANCE,
        "业绩预告",
        45,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "express",
        "express",
        TushareApiCategory.FINANCE,
        "业绩快报",
        46,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "dividend",
        "dividend",
        TushareApiCategory.FINANCE,
        "分红送股",
        103,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "fina_indicator",
        "fina_indicator",
        TushareApiCategory.FINANCE,
        "财务指标数据",
        79,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "fina_audit",
        "fina_audit",
        TushareApiCategory.FINANCE,
        "财务审计意见",
        80,
        TushareApiParamMode.TS_CODE_WINDOW,
    ),
    TushareApiSpec(
        "fina_mainbz",
        "fina_mainbz",
        TushareApiCategory.FINANCE,
        "主营业务构成",
        81,
        TushareApiParamMode.TS_CODE_END_DATE,
    ),
    TushareApiSpec(
        "disclosure_date",
        "disclosure_date",
        TushareApiCategory.FINANCE,
        "财报披露计划",
        162,
        TushareApiParamMode.TS_CODE_END_DATE,
    ),
)

TUSHARE_API_SPECS_BY_NAME = {spec.api_name: spec for spec in TUSHARE_API_SPECS}
