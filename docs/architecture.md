# 架构说明

## 架构方向

Fun Stock 当前采用模块化单体架构。代码库会为数据同步、因子、策略和回测保留清晰的
模块边界，同时避免过早拆分为多个服务。

## 模块划分

- `api`：HTTP 路由和请求/响应契约。
- `core`：配置、数据库连接、日志和共享基础设施。
- `models`：数据库模型。
- `schemas`：Pydantic 模型。
- `repositories`：持久化访问模式。
- `services`：应用用例。
- `tasks`：异步任务和调度任务入口。
- `engines.data_sync`：行情数据接入和归一化。
- `engines.factor`：可复用因子计算。
- `engines.strategy`：策略定义和策略评估。
- `engines.backtest`：回测执行和报表。

## 运行时

```text
React 前端
    |
FastAPI 后端
    |
PostgreSQL + TimescaleDB
Redis
Celery workers
```

当前基线包含 API、前端、PostgreSQL 和 Redis 容器。等第一个异步数据同步任务稳定后，
再加入 worker 进程。

## 数据库布局

本地数据库名为 `fun_stock`。Tushare 原始数据表放在 `tushare` schema 中，应用自有
归一化表放在 `app` schema 中，并由 Alembic 管理。
