# 开发指南

## 前置条件

默认开发流程使用 Docker Desktop。本机安装 Python 和 Node.js 不是必需条件。

## 启动平台

```powershell
docker compose up --build
```

服务地址：

- 前端：http://localhost:5175
- 后端 API 文档：http://localhost:8000/docs
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6380`

如需同时启动 Tushare 定时同步，使用：

```powershell
docker compose up --build backend frontend celery-worker celery-beat
```

定时同步由 `celery-worker` 执行，`celery-beat` 负责编排计划。默认只启用小范围接口：

```text
stock_basic,trade_cal,daily,daily_basic,adj_factor
```

可以通过 `.env` 中的 `TUSHARE_SCHEDULER_API_NAMES`、`TUSHARE_SCHEDULER_MAX_ITEMS` 调整范围和单次规模。
Tushare 每分钟访问频率受账号积分影响时，可以通过 `TUSHARE_RATE_LIMIT_SLEEP_SECONDS` 和
`TUSHARE_RATE_LIMIT_MAX_RETRIES` 控制自动休眠重试。
Tushare DNS 或连接类瞬时网络错误可以通过 `TUSHARE_NETWORK_RETRY_SLEEP_SECONDS` 和
`TUSHARE_NETWORK_MAX_RETRIES` 控制自动休眠重试。

本地开发数据库连接信息：

```text
database: fun_stock
username: fun_stock
password: fun_stock
```

## 后端命令

```powershell
docker compose run --rm backend uv run pytest
docker compose run --rm backend uv run ruff check .
docker compose run --rm backend uv run mypy .
docker compose run --rm backend uv run alembic upgrade head
docker compose run --rm --no-deps backend uv run python -m app.tasks.normalize_market_data
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler plan
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler run-once --dry-run --max-items 5
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler alerts --limit 10
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler retry-failed --dry-run --max-items 5
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler completeness --layer app
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler completeness --layer raw
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler repair-core --start-date 2020-01-01 --end-date 2020-01-31
docker compose run --rm backend uv run python -m app.tasks.sync_tushare_scheduler fix-backfill-batches --start-date 2020-01-01 --end-date 2020-01-31
```

`repair-core` 默认 dry-run，只从 `tushare.daily`、`tushare.daily_basic`、`tushare.adj_factor`
归一化修复到 `app.daily_quotes`、`app.daily_indicators`、`app.adj_factors`，不会重新调用
Tushare。需要实际写入时加 `--no-dry-run`。`fix-backfill-batches` 用于修正 failed 或超时
running 的回填批次状态，前提是对应应用层数据已经完整。

## 前端命令

```powershell
docker compose run --rm --no-deps -e CI=true frontend pnpm install --frozen-lockfile
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```

前端页面按业务模块放在 `frontend/src/features`：

- `data-sync`：Tushare 同步状态和历史回填任务控制台。
- `data-quality`：应用层和原始层完整性巡检、归一化修复、回填批次状态修正。
- `stocks`：股票列表、搜索、基础信息和日行情概览。
- `strategies`、`backtests`：策略和回测模块占位，后续逐步填充。

## 开发规范

- 业务逻辑不要放在路由处理函数里。
- 用 service 承载应用用例。
- 用 repository 处理数据库访问。
- 行为变化要补测试，尤其是 engines 和 services。
- 生成数据、缓存文件和本地密钥不得进入 Git。
