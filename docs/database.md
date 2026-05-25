# 数据库设计

## 命名

本地和应用运行时使用一个项目数据库：

```text
database: fun_stock
```

正常应用开发中不要单独创建名为 `tushare` 的数据库。Tushare 是数据来源，不是产品边界。
与来源强相关的原始表应放在 `fun_stock` 数据库内的 `tushare` schema。

推荐 schema 布局：

```text
fun_stock
  app        -- 应用自有的归一化业务表
  tushare    -- 映射 Tushare API 的原始或轻类型表
  factor     -- 后续计算因子表
  backtest   -- 后续回测任务、交易、持仓和权益曲线
```

这样可以简化跨 schema 查询，让一个事务同时访问原始数据和归一化数据，并让 Alembic
清晰管理应用自有 schema。

## 迁移归属

- Alembic 管理应用表，当前从 `app` schema 开始。
- 生成的 Tushare DDL 作为原始数据接入的初始化和参考材料。
- 不手工修改生成的 Tushare DDL，除非生成器有误且变更已记录。
- 数据接入稳定后，raw schema 的调整应通过受控迁移或生成器输出审查完成。

## 当前核心表

第一组 Alembic 迁移创建：

- `app.stocks`：归一化股票身份和上市信息。
- `app.trade_calendars`：交易所交易日历。
- `app.daily_quotes`：日线 OHLCV 行情。
- `app.data_sync_jobs`：按数据来源和 API 记录持久化同步游标。
- `app.data_sync_runs`：每个同步窗口的执行日志。
- `app.data_quality_checks`：每个同步窗口的数据质量检查结果。

生成的 Tushare 脚本会在以下 schema 下创建原始表：

```text
tushare.*
```

这些表用作数据接入落地表或来源参考。业务 API 默认读取 `app.*` 表，除非接口明确暴露
原始 Tushare 数据。

## 原始数据到应用表归一化

当前归一化服务会复制并 upsert：

```text
tushare.stock_basic -> app.stocks
tushare.trade_cal   -> app.trade_calendars
tushare.daily       -> app.daily_quotes
tushare.daily_basic -> app.daily_indicators
tushare.adj_factor  -> app.adj_factors
```

raw 表有数据后手动执行：

```powershell
docker compose run --rm --no-deps backend uv run python -m app.tasks.normalize_market_data
```

按日行情窗口归一化：

```powershell
docker compose run --rm --no-deps backend uv run python -m app.tasks.normalize_market_data --start-date 2026-01-01 --end-date 2026-01-31
```

## Tushare 同步

真实拉取数据前，需要在本地 `.env` 中设置 `TUSHARE_TOKEN`。

Tushare 接入层会先把来源数据写入 `tushare.*`，再把同步进度记录到
`app.data_sync_jobs`，把每个窗口的执行情况记录到 `app.data_sync_runs`，最后将已支持的
raw 表归一化到 `app.*`。

运行当前已支持的全部同步：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_market_data all
```

按统一计划预览本次应执行的同步：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler plan
```

按统一计划执行一次同步：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler run-once
```

先预演前 5 个待执行计划，不调用 Tushare：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler run-once --dry-run --max-items 5
```

按范围运行：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_market_data basic
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_market_data quotes-plan
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_market_data quotes --max-trade-days 5 --sleep-seconds 0.2
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_market_data quotes-window --start-date 2026-05-22 --end-date 2026-05-22
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_market_data finance --start-date 2026-01-01
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_market_data finance --start-date 2026-01-01 --ts-code 000001.SZ --api income
```

日行情同步会读取最近一次成功的 `daily` 游标，并补齐游标之后的开市交易日。如果服务停
了一段时间，下次运行会从第一个缺失交易日继续。长时间补拉前先用 `quotes-plan` 预览
下一批；用 `--max-trade-days` 控制单次运行规模；用 `--sleep-seconds` 降低触发上游限流
的概率。临时验证使用 `quotes-window`，它写入独立的 `daily_window` 游标，不会推进正式
历史补拉的 `daily` 游标。

完整接口排查台账见 [Tushare 接口覆盖台账](tushare-interface-coverage.md)。该台账记录
raw 表、客户端获取、同步服务和小批量验证状态。

正式 `quotes` 补拉会对每个交易日同步 `daily`、`daily_basic` 和 `adj_factor`。这三张
日频行情表被视为同一个交易日批次，只有三份 API 数据都成功写入后，才推进对应游标。

统一计划调度同样会让 `daily`、`daily_basic` 和 `adj_factor` 共用 `daily` 的补拉游标，
避免三张核心日频表错开交易日。对按 `trade_date` 同步的接口，调度器会根据
`tushare.trade_cal` 选择下一个开市交易日，不会在周末或节假日直接推进行情游标。

财务 API 按 `ts_code` 同步。部分 VIP 财务接口有严格频率限制。验证或恢复失败任务时，
可重复使用 `--api` 参数只同步指定子集。

实时和分钟接口默认不进入统一计划自动调度，包括 `rt_k`、`stk_mins`、`rt_min` 和
`rt_min_daily`。这些接口受交易时段、频率限制和实时性影响更大，需要时使用
`--include-manual` 显式纳入预览或执行。

## Tushare 接口映射

当前代码已将 raw schema 中的 41 个 Tushare 接口全部纳入统一注册表：

```text
backend/app/adapters/tushare/registry.py
```

注册表负责声明 API 名称、raw 落地表、分类、文档 ID、参数模式、默认参数和必要字段别名。
除少数正式增量同步路径保留显式方法外，其余接口统一通过 `TushareClient.query_api()` 调用，
并通过 `TushareMarketDataSyncService.sync_registered_api()` 写入对应 `tushare.*` 表。

完整接口、请求参数、落库表和小批量验证结果见
[Tushare 接口覆盖台账](tushare-interface-coverage.md)。

同步状态统一记录在：

```text
app.data_sync_jobs
app.data_sync_runs
app.data_quality_checks
```

其中正式历史日行情补拉使用 `daily`、`daily_basic`、`adj_factor` 三个同步任务名；临时窗口
验证使用 `daily_window`、`daily_basic_window`、`adj_factor_window`，避免污染正式补拉游标。

## 数据质量检查

每个同步窗口成功写入 raw 表后，会将数据质量检查结果写入 `app.data_quality_checks`，
并通过 `run_id` 关联到本次 `app.data_sync_runs`。

当前检查项包括：

- `row_count`：接口返回行数。返回 0 行会记录为 warning，避免无声推进。
- `upsert_count`：写入行数。接口返回有数据但写入 0 行会记录为 failed。
- `required_field:*`：关键字段空值检查，例如 `ts_code`、`trade_date`、`end_date`、`month`。
- `trade_date_gap`：按交易日同步的接口必须返回目标交易日数据；交易日不一致会记录为 failed。

质量检查不会直接替代同步失败判定：Tushare 调用失败、数据库写入失败仍会让
`app.data_sync_runs.status` 变为失败；质量检查用于标记“同步成功但数据值得复核”的情况。

## 积分和权限不足

Tushare 部分接口需要积分。客户端会识别常见的积分或权限不足错误，例如“积分不足”、
“权限不足”、“没有访问权限”、“开通权限”等，并抛出专用错误。

调度器遇到这类错误时：

- 将当前 run 标记为 `blocked_insufficient_points`。
- 将对应 job 标记为 `blocked_insufficient_points`。
- 本轮不再重复尝试同一个接口，避免浪费请求次数。
- 不把积分不足当作普通可重试失败处理。

如果 Tushare 返回的是每分钟访问频次限制，而不是积分或权限不足，客户端会按
`TUSHARE_RATE_LIMIT_SLEEP_SECONDS` 休眠后重试，最多重试
`TUSHARE_RATE_LIMIT_MAX_RETRIES` 次。这样可以处理“积分等级对应每分钟请求次数较低”的情况，
同时不会把真正的积分不足误判为可自动恢复。

## 失败恢复和告警查看

同步告警统一从三张应用表读取：

```text
app.data_sync_jobs
app.data_sync_runs
app.data_quality_checks
```

查看最近失败、阻塞和数据质量告警：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler alerts --limit 10
```

只预览可自动重跑的失败接口：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler retry-failed --dry-run --max-items 5
```

实际重跑可重试失败项：

```powershell
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler retry-failed --max-items 5
```

恢复策略：

- `failed`：视为可重试失败，可由 `retry-failed` 选择并重跑。
- `blocked_insufficient_points`：积分或权限不足，需要人工处理，不会被 `retry-failed` 自动重跑。
- `warning` 或质量检查 `failed`：表示本次同步成功但数据需要复核，先进入告警视图，不直接触发自动重跑。
- `retry-failed --api <name>` 可以限制只重跑指定接口；接口名称必须已经登记在 Tushare 注册表中。

## 定时同步

定时同步使用 `Celery + Redis + Celery Beat`：

- `celery-worker`：执行实际同步任务。
- `celery-beat`：按北京时间触发计划。
- Redis：作为 Celery broker、结果后端和分布式锁存储。

默认计划：

- 每天 20:00：执行 Tushare 小范围同步。
- 每周六 21:00：再执行一次小范围同步，用于基础信息和周频数据补齐。
- 每天 20:40：只重跑 `failed` 状态的可重试接口。
- 每天 21:20：输出失败、blocked、质量告警快照到 worker 日志。

默认小范围接口由环境变量控制：

```text
TUSHARE_SCHEDULER_API_NAMES=stock_basic,trade_cal,daily,daily_basic,adj_factor
TUSHARE_SCHEDULER_MAX_ITEMS=5
```

定时任务会使用 Redis 分布式锁，避免同一类 Tushare 同步任务并发执行。`blocked_insufficient_points`
不会被自动重试；处理积分或权限后，需要人工确认状态，再恢复对应接口同步。

## Tushare 脚本审查说明

生成脚本有价值，但应视为 raw DDL，而不是业务模型。

优点：

- 使用 `CREATE SCHEMA IF NOT EXISTS`。
- 使用 `CREATE TABLE IF NOT EXISTS`。
- 将 Tushare 表隔离在 `tushare` schema。
- 为许多表添加了主键和索引。
- 带有 API 和文档元数据注释。

风险：

- 部分主键来自文档推断，可能与真实唯一性不完全一致。
- 部分实时或分钟级表使用 `ts_code` 作为唯一主键，可能不适合追加式行情数据。
- 生成注释依赖正确的来源编码，读取文件时应使用 UTF-8。
- 脚本范围较广，目前包含 41 张 raw 表。初期应用只需要股票基础信息、交易日历、日线
  行情、复权因子、每日指标、停复牌、涨跌停等核心表。
- raw schema 的变更应能由生成器复现，或通过正式迁移固化。
