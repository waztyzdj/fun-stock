# Tushare 接口覆盖台账

本文档用于统一记录沪深股票相关 Tushare 接口的接入状态。接口清单以
`infra/postgres/init/010_tushare_stock_schema.sql` 中已生成的 raw schema 为基准，覆盖
基础数据、行情数据和财务数据三类。

状态含义：

- raw 表：是否已经有 `tushare.*` 落地表。
- 客户端获取：是否已在 `backend/app/adapters/tushare/registry.py` 登记，并可通过
  `TushareClient.query_api()` 调用。
- 同步服务：是否已通过 `TushareMarketDataSyncService.sync_registered_api()` 接入落库流程。
- 小批量验证：是否已经用真实 Tushare API 做过小范围调用和落库验证。

## 总览

```text
已纳入 raw schema 的接口数：41
已实现客户端获取：41
已接入同步服务：41
已完成有数据小批量验证：35
已完成空结果小批量验证：5
受 Tushare 限流影响待复验：1
尚未实现数据获取：0
```

最近复查：2026-05-24。已确认 `registry.py`、raw schema 和本文档矩阵均覆盖 41 个接口，
没有发现遗漏接口。`stk_mins` 已完成接口登记和同步接入，但本次复验仍触发 Tushare
`1次/小时` 限流，因此保持“待复验”状态。

实现方式说明：

- `stock_basic`、`trade_cal`、`daily`、`daily_basic`、`adj_factor` 和核心财务接口保留显式方法，供正式增量同步复用。
- 其余接口统一通过 `TUSHARE_API_SPECS` 注册表声明接口名、raw 表、参数模式、默认参数和字段别名。
- `stock_st_warning` 的本地 API 名保持业务语义，实际调用 Tushare `st`，并将返回字段 `st_type` 映射到当前 raw 表字段 `st_tpye`。
- raw 写入层会按落地表字段过滤返回数据，并统一处理 Tushare 日期占位值 `0`、`00000000`。

## 接口覆盖矩阵

| 分类 | API | 接口名称 | 文档 ID | raw 表 | 客户端获取 | 同步服务 | 小批量验证 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 基础数据 | `stock_basic` | 股票基础信息 | 25 | `tushare.stock_basic` | 已实现 | 已接入 | 已通过 | 参数：`list_status=L/D/P`；已归一化到 `app.stocks` |
| 基础数据 | `stk_premarket` | 股本情况（盘前） | 329 | `tushare.stk_premarket` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 5504 行 |
| 基础数据 | `trade_cal` | 交易日历 | 26 | `tushare.trade_cal` | 已实现 | 已接入 | 已通过 | 参数：`exchange=SSE`, `start_date`, `end_date`；已归一化到 `app.trade_calendars` |
| 基础数据 | `stock_st` | ST 股票列表 | 397 | `tushare.stock_st` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 255 行 |
| 基础数据 | `stock_st_warning` | ST 预警数据 | 423 | `tushare.stock_st_warning` | 已实现 | 已接入 | 已通过 | 实际调用 Tushare `st`；获取 1000 行，按 `ts_code` 幂等写入 523 行 |
| 基础数据 | `stock_hsgt` | 沪深港通股票列表 | 398 | `tushare.stock_hsgt` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取 2000 行，写入 1729 行 |
| 基础数据 | `namechange` | 股票曾用名 | 100 | `tushare.namechange` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`，获取 8 行，写入 4 行 |
| 基础数据 | `stock_company` | 上市公司基本信息 | 112 | `tushare.stock_company` | 已实现 | 已接入 | 已通过 | 获取/写入 6271 行 |
| 基础数据 | `stk_managers` | 上市公司管理层 | 193 | `tushare.stk_managers` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`，获取 193 行，写入 88 行 |
| 基础数据 | `stk_rewards` | 管理层薪酬和持股 | 194 | `tushare.stk_rewards` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`，获取 3667 行，写入 1428 行；已修正 nullable `title` 主键问题 |
| 基础数据 | `bse_mapping` | 北交所新旧代码对照表 | 375 | `tushare.bse_mapping` | 已实现 | 已接入 | 已通过 | 获取/写入 248 行；已补充 `(o_code, n_code)` 主键 |
| 基础数据 | `new_share` | IPO 新股列表 | 123 | `tushare.new_share` | 已实现 | 已接入 | 已通过 | `2026-05-01` 至 `2026-05-24`，获取/写入 9 行 |
| 基础数据 | `bak_basic` | 股票历史列表 | 262 | `tushare.bak_basic` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 5525 行 |
| 行情数据 | `daily` | A 股日线行情 | 27 | `tushare.daily` | 已实现 | 已接入 | 已通过 | `trade_date`；已归一化到 `app.daily_quotes` |
| 行情数据 | `rt_k` | A 股实时日线 | 372 | `tushare.rt_k` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`，获取/写入 1 行 |
| 行情数据 | `stk_mins` | 股票历史分钟行情 | 370 | `tushare.stk_mins` | 已实现 | 已接入 | 待复验 | 当前 Tushare 限流；此前已取到 3133 行，已修正 raw 主键为 `(ts_code, trade_time)`，需限流窗口恢复后复验写入 |
| 行情数据 | `rt_min` | A 股实时分钟 | 374 | `tushare.rt_min` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`, `freq=1MIN`，获取/写入 1 行 |
| 行情数据 | `rt_min_daily` | 实时分钟日内数据 | 457 | `tushare.rt_min_daily` | 已实现 | 已接入 | 空结果通过 | `ts_code=000001.SZ`, `freq=1MIN`，调用成功，返回 0 行 |
| 行情数据 | `weekly` | 周线行情 | 144 | `tushare.weekly` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 5583 行 |
| 行情数据 | `monthly` | 月线行情 | 145 | `tushare.monthly` | 已实现 | 已接入 | 已通过 | `trade_date=2026-04-30`，获取/写入 5593 行 |
| 行情数据 | `stk_weekly_monthly` | 股票周/月线行情 | 336 | `tushare.stk_weekly_monthly` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`, `freq=week`，获取/写入 5502 行 |
| 行情数据 | `stk_week_month_adj` | 股票周/月复权行情 | 365 | `tushare.stk_week_month_adj` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`, `freq=week`，获取/写入 5502 行 |
| 行情数据 | `adj_factor` | 复权因子 | 28 | `tushare.adj_factor` | 已实现 | 已接入 | 已通过 | `trade_date`；暂未归一化 |
| 行情数据 | `daily_basic` | 每日指标 | 32 | `tushare.daily_basic` | 已实现 | 已接入 | 已通过 | `trade_date`；暂未归一化 |
| 行情数据 | `stk_limit` | 每日涨跌停价格 | 183 | `tushare.stk_limit` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 7613 行 |
| 行情数据 | `suspend_d` | 每日停复牌信息 | 214 | `tushare.suspend_d` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 25 行 |
| 行情数据 | `hsgt_top10` | 沪深股通十大成交股 | 48 | `tushare.hsgt_top10` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`, `market_type=1`，获取/写入 10 行 |
| 行情数据 | `ggt_top10` | 港股通十大成交股 | 49 | `tushare.ggt_top10` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取 20 行，写入 14 行 |
| 行情数据 | `ggt_daily` | 港股通每日成交统计 | 196 | `tushare.ggt_daily` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 1 行 |
| 行情数据 | `ggt_monthly` | 港股通每月成交统计 | 197 | `tushare.ggt_monthly` | 已实现 | 已接入 | 空结果通过 | `month=202604`，调用成功，返回 0 行 |
| 行情数据 | `bak_daily` | 备用行情 | 255 | `tushare.bak_daily` | 已实现 | 已接入 | 已通过 | `trade_date=2026-05-22`，获取/写入 5525 行 |
| 财务数据 | `income` | 利润表 | 33 | `tushare.income` | 已实现 | 已接入 | 已通过 | `ts_code`, `start_date`, `end_date`；暂未归一化 |
| 财务数据 | `balancesheet` | 资产负债表 | 36 | `tushare.balancesheet` | 已实现 | 已接入 | 已通过 | `ts_code`, `start_date`, `end_date`；已处理同批重复主键 |
| 财务数据 | `cashflow_vip` | 现金流量表 | 44 | `tushare.cashflow_vip` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`，获取 7 行，写入 6 行 |
| 财务数据 | `forecast` | 业绩预告 | 45 | `tushare.forecast` | 已实现 | 已接入 | 空结果通过 | `ts_code=000001.SZ`, `2025-01-01` 至 `2026-04-30`，调用成功，返回 0 行 |
| 财务数据 | `express` | 业绩快报 | 46 | `tushare.express` | 已实现 | 已接入 | 空结果通过 | `ts_code=000001.SZ`, `2025-01-01` 至 `2026-04-30`，调用成功，返回 0 行 |
| 财务数据 | `dividend` | 分红送股 | 103 | `tushare.dividend` | 已实现 | 已接入 | 空结果通过 | `ts_code=000001.SZ`, `2020-01-01` 至 `2026-04-30`，调用成功，返回 0 行 |
| 财务数据 | `fina_indicator` | 财务指标数据 | 79 | `tushare.fina_indicator` | 已实现 | 已接入 | 已通过 | `ts_code`, `start_date`, `end_date`；暂未归一化 |
| 财务数据 | `fina_audit` | 财务审计意见 | 80 | `tushare.fina_audit` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`，获取/写入 2 行 |
| 财务数据 | `fina_mainbz` | 主营业务构成 | 81 | `tushare.fina_mainbz` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`, `end_date=2026-04-30`，获取/写入 150 行 |
| 财务数据 | `disclosure_date` | 财报披露计划 | 162 | `tushare.disclosure_date` | 已实现 | 已接入 | 已通过 | `ts_code=000001.SZ`, `end_date=2025-12-31`，获取/写入 1 行 |

## 批量探测命令

可以用以下命令探测全部注册接口：

```powershell
docker compose run --rm --no-deps backend uv run python -m app.tasks.sync_tushare_market_data api-probe-batch
```

也可以重复传入 `--api` 只探测指定接口：

```powershell
docker compose run --rm --no-deps backend uv run python -m app.tasks.sync_tushare_market_data api-probe-batch --api stk_limit --api suspend_d
```

`api-probe-batch` 默认使用：

```text
trade_date=2026-05-22
start_date=2026-05-01
end_date=2026-05-24
ts_code=000001.SZ
month=202605
```

部分接口需要更贴近业务的数据窗口，例如：

```powershell
docker compose run --rm --no-deps backend uv run python -m app.tasks.sync_tushare_market_data api-probe monthly --trade-date 2026-04-30
docker compose run --rm --no-deps backend uv run python -m app.tasks.sync_tushare_market_data api-probe disclosure_date --ts-code 000001.SZ --end-date 2025-12-31
```

## 已修正的 raw schema 问题

- `bse_mapping` 原始表缺少主键，已补充 `(o_code, n_code)`。
- `stk_rewards.title` 真实数据可能为空，已将主键从 `(ts_code, ann_date, name, title)` 调整为 `(ts_code, ann_date, name)`。
- `stk_mins`、`rt_min`、`rt_min_daily` 原主键只包含 `ts_code`，会覆盖分钟历史数据；已分别调整为 `(ts_code, trade_time)`、`(ts_code, time)`、`(ts_code, freq, time)`。
- Tushare 日期字段可能返回 `0` 或 `00000000`，raw 写入层已统一转为 `NULL`。
