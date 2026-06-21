# 长线基本面策略模块

本模块面向长期基本面投资，优先支持“好公司 + 合理估值”的选股流程。
第一版聚焦于因子字典、历史因子值和选股向导，不直接进入回测中心。

## 第一版范围

- 因子字典：统一维护因子代码、中文名、分类、单位、数据来源、计算口径和排序方向。
- 因子值：从 Tushare 原始表和应用层每日指标表计算并落地到 `app.factor_values`，保留公告可用时间。
- 策略定义：使用 JSON 保存选股范围、过滤条件和排序规则。
- 策略筛选：基于最新因子快照筛选股票，返回入选股票和关键因子值。

## 因子分类

- 盈利能力：ROE、加权 ROE、ROA、毛利率、净利率。
- 成长能力：营业收入增速、净利润增速、扣非净利润增速、经营现金流增速。
- 现金流质量：经营现金流 / 净利润、经营现金流 / 营业收入、公司自由现金流。
- 财务安全：资产负债率、流动比率、速动比率、利息保障倍数。
- 估值分红：PE TTM、PB、PS TTM、股息率 TTM。

## 构建命令

```powershell
docker compose run --rm backend uv run alembic upgrade head
docker compose run --rm backend uv run python -m app.tasks.build_fundamental_factors
```

可以按起始日期增量重建：

```powershell
docker compose run --rm backend uv run python -m app.tasks.build_fundamental_factors --start-date 2020-01-01
```

## 策略 JSON 契约

```json
{
  "universe": {
    "exclude_st": true,
    "min_list_years": 3
  },
  "filters": [
    {"factor": "roe", "op": ">=", "value": "12"},
    {"factor": "ocf_to_profit", "op": ">=", "value": "80"},
    {"factor": "debt_to_assets", "op": "<=", "value": "60"}
  ],
  "sort": [
    {"factor": "roe", "direction": "desc"},
    {"factor": "pe_ttm", "direction": "asc"}
  ]
}
```

策略保存后可以在回测中心直接选择并运行。回测会把策略 JSON 重新解析为筛选条件、
排序规则和股票池约束，生成本次回测绑定的策略版本快照。

## 策略版本与回测持久化

回测不再只作为临时计算结果返回。系统会把一次回测拆成以下持久化对象：

- `app.strategy_versions`：保存策略定义在某一时点的不可变快照，回测绑定到具体版本，保证后续可复盘。
- `app.backtest_runs`：保存一次回测任务的参数、状态和核心绩效指标。
- `app.backtest_periods`：保存每个年度或季度调仓区间的策略收益、基准收益、超额收益和组合资产。
- `app.backtest_holdings`：保存每个调仓区间的持仓股票、权重、进出价格和区间收益。

当前长线回测基线使用等权持有和年度/季度调仓。回测默认使用 `app.index_daily_quotes`
中的沪深300作为真实指数基准，也可以选择中证500、中证1000、中证全指或同一股票池等权收益。
如果某个调仓区间缺少指数行情，系统会对该区间回退到同池等权基准，并在基准名称中标记。
收益计算默认使用 `app.daily_quotes.close * app.adj_factors.adj_factor` 的复权价格口径；回测请求可以关闭复权，也可以配置佣金率、滑点率和卖出印花税率。成本会按买入端
`commission_rate + slippage_rate`、卖出端 `commission_rate + slippage_rate + stamp_tax_rate` 计入区间收益。

## 回测诊断指标

回测报告除收益指标外，还会持久化以下诊断指标：

- 最大回撤：基于期初资产和每个调仓区间期末组合资产计算，保存为正数比例。
- 胜率：策略区间收益大于 0 的调仓区间占比。
- 区间换手率：等权组合使用 `sum(abs(current_weight - previous_weight)) / 2` 计算；首期建仓记为 100%。
- 平均换手率：多个调仓区间时排除首期建仓，只统计后续调仓换手；单区间时保留首期建仓。

前端回测中心会展示最大回撤、胜率、平均换手率，并按退出日期所属年度汇总年度收益和换手情况。
