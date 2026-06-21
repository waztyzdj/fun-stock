from dataclasses import dataclass
from enum import StrEnum


class FactorCategory(StrEnum):
    PROFITABILITY = "profitability"
    GROWTH = "growth"
    CASH_FLOW = "cash_flow"
    SAFETY = "safety"
    VALUATION = "valuation"


@dataclass(frozen=True)
class FundamentalFactorSpec:
    code: str
    name: str
    category: FactorCategory
    unit: str | None
    source_table: str
    source_column: str
    calculation_method: str
    description: str
    sort_direction: str = "desc"
    period_type: str = "report"


FUNDAMENTAL_FACTOR_SPECS: tuple[FundamentalFactorSpec, ...] = (
    FundamentalFactorSpec(
        code="roe",
        name="净资产收益率",
        category=FactorCategory.PROFITABILITY,
        unit="%",
        source_table="fina_indicator",
        source_column="roe",
        calculation_method=(
            "直接采用 tushare.fina_indicator.roe，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="衡量股东权益创造利润的能力，长期投资中用于观察公司质量。",
    ),
    FundamentalFactorSpec(
        code="roe_waa",
        name="加权平均 ROE",
        category=FactorCategory.PROFITABILITY,
        unit="%",
        source_table="fina_indicator",
        source_column="roe_waa",
        calculation_method=(
            "直接采用 tushare.fina_indicator.roe_waa，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="按加权平均净资产计算的净资产收益率。",
    ),
    FundamentalFactorSpec(
        code="roa",
        name="总资产收益率",
        category=FactorCategory.PROFITABILITY,
        unit="%",
        source_table="fina_indicator",
        source_column="roa",
        calculation_method=(
            "直接采用 tushare.fina_indicator.roa，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="衡量公司总资产产生利润的效率。",
    ),
    FundamentalFactorSpec(
        code="grossprofit_margin",
        name="毛利率",
        category=FactorCategory.PROFITABILITY,
        unit="%",
        source_table="fina_indicator",
        source_column="grossprofit_margin",
        calculation_method=(
            "直接采用 tushare.fina_indicator.grossprofit_margin，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="反映产品或服务的基础盈利空间。",
    ),
    FundamentalFactorSpec(
        code="netprofit_margin",
        name="净利率",
        category=FactorCategory.PROFITABILITY,
        unit="%",
        source_table="fina_indicator",
        source_column="netprofit_margin",
        calculation_method=(
            "直接采用 tushare.fina_indicator.netprofit_margin，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="反映收入最终转化为净利润的能力。",
    ),
    FundamentalFactorSpec(
        code="or_yoy",
        name="营业收入同比增速",
        category=FactorCategory.GROWTH,
        unit="%",
        source_table="fina_indicator",
        source_column="or_yoy",
        calculation_method=(
            "直接采用 tushare.fina_indicator.or_yoy，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="营业收入相较上年同期的增长速度。",
    ),
    FundamentalFactorSpec(
        code="netprofit_yoy",
        name="净利润同比增速",
        category=FactorCategory.GROWTH,
        unit="%",
        source_table="fina_indicator",
        source_column="netprofit_yoy",
        calculation_method=(
            "直接采用 tushare.fina_indicator.netprofit_yoy，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="净利润相较上年同期的增长速度。",
    ),
    FundamentalFactorSpec(
        code="dt_netprofit_yoy",
        name="扣非净利润同比增速",
        category=FactorCategory.GROWTH,
        unit="%",
        source_table="fina_indicator",
        source_column="dt_netprofit_yoy",
        calculation_method=(
            "直接采用 tushare.fina_indicator.dt_netprofit_yoy，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="扣除非经常性损益后净利润的同比增长速度。",
    ),
    FundamentalFactorSpec(
        code="ocf_yoy",
        name="经营现金流同比增速",
        category=FactorCategory.GROWTH,
        unit="%",
        source_table="fina_indicator",
        source_column="ocf_yoy",
        calculation_method=(
            "直接采用 tushare.fina_indicator.ocf_yoy，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="经营活动现金流相较上年同期的增长速度。",
    ),
    FundamentalFactorSpec(
        code="ocf_to_profit",
        name="经营现金流 / 净利润",
        category=FactorCategory.CASH_FLOW,
        unit="%",
        source_table="fina_indicator",
        source_column="ocf_to_profit",
        calculation_method=(
            "直接采用 tushare.fina_indicator.ocf_to_profit，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="衡量净利润的现金含量，越高通常代表利润质量越好。",
    ),
    FundamentalFactorSpec(
        code="ocf_to_or",
        name="经营现金流 / 营业收入",
        category=FactorCategory.CASH_FLOW,
        unit="%",
        source_table="fina_indicator",
        source_column="ocf_to_or",
        calculation_method=(
            "直接采用 tushare.fina_indicator.ocf_to_or，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="衡量收入转化为经营现金流的能力。",
    ),
    FundamentalFactorSpec(
        code="fcff",
        name="公司自由现金流",
        category=FactorCategory.CASH_FLOW,
        unit="元",
        source_table="fina_indicator",
        source_column="fcff",
        calculation_method=(
            "直接采用 tushare.fina_indicator.fcff，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="公司层面的自由现金流。",
    ),
    FundamentalFactorSpec(
        code="debt_to_assets",
        name="资产负债率",
        category=FactorCategory.SAFETY,
        unit="%",
        source_table="fina_indicator",
        source_column="debt_to_assets",
        calculation_method=(
            "直接采用 tushare.fina_indicator.debt_to_assets，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="衡量资产中由负债融资的比例，长线投资中用于控制财务风险。",
        sort_direction="asc",
    ),
    FundamentalFactorSpec(
        code="current_ratio",
        name="流动比率",
        category=FactorCategory.SAFETY,
        unit="倍",
        source_table="fina_indicator",
        source_column="current_ratio",
        calculation_method=(
            "直接采用 tushare.fina_indicator.current_ratio，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="衡量短期偿债能力。",
    ),
    FundamentalFactorSpec(
        code="quick_ratio",
        name="速动比率",
        category=FactorCategory.SAFETY,
        unit="倍",
        source_table="fina_indicator",
        source_column="quick_ratio",
        calculation_method=(
            "直接采用 tushare.fina_indicator.quick_ratio，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="剔除存货后的短期偿债能力。",
    ),
    FundamentalFactorSpec(
        code="ebit_to_interest",
        name="利息保障倍数",
        category=FactorCategory.SAFETY,
        unit="倍",
        source_table="fina_indicator",
        source_column="ebit_to_interest",
        calculation_method=(
            "直接采用 tushare.fina_indicator.ebit_to_interest，"
            "factor_date 取公告日，"
            "若公告日为空则回退到报告期。"
        ),
        description="衡量经营利润覆盖利息支出的能力。",
    ),
    FundamentalFactorSpec(
        code="pe_ttm",
        name="滚动市盈率",
        category=FactorCategory.VALUATION,
        unit="倍",
        source_table="daily_basic",
        source_column="pe_ttm",
        calculation_method="直接采用 app.daily_indicators.pe_ttm 的交易日快照。",
        description="基于最近交易日每日指标的滚动市盈率。",
        sort_direction="asc",
        period_type="daily",
    ),
    FundamentalFactorSpec(
        code="pb",
        name="市净率",
        category=FactorCategory.VALUATION,
        unit="倍",
        source_table="daily_basic",
        source_column="pb",
        calculation_method="直接采用 app.daily_indicators.pb 的交易日快照。",
        description="基于最近交易日每日指标的市净率。",
        sort_direction="asc",
        period_type="daily",
    ),
    FundamentalFactorSpec(
        code="ps_ttm",
        name="滚动市销率",
        category=FactorCategory.VALUATION,
        unit="倍",
        source_table="daily_basic",
        source_column="ps_ttm",
        calculation_method="直接采用 app.daily_indicators.ps_ttm 的交易日快照。",
        description="基于最近交易日每日指标的滚动市销率。",
        sort_direction="asc",
        period_type="daily",
    ),
    FundamentalFactorSpec(
        code="dv_ttm",
        name="股息率 TTM",
        category=FactorCategory.VALUATION,
        unit="%",
        source_table="daily_basic",
        source_column="dv_ttm",
        calculation_method="直接采用 app.daily_indicators.dv_ttm 的交易日快照。",
        description="基于最近交易日每日指标的滚动股息率。",
    ),
)

FUNDAMENTAL_FACTOR_SPECS_BY_CODE = {spec.code: spec for spec in FUNDAMENTAL_FACTOR_SPECS}
