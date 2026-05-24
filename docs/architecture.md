# Architecture

## Direction

Fun Stock starts as a modular monolith. The codebase keeps clear module boundaries for data
sync, factors, strategies, and backtesting, while avoiding premature service decomposition.

## Modules

- `api`: HTTP routes and request/response contracts.
- `core`: configuration, database wiring, logging, and shared infrastructure.
- `models`: database models.
- `schemas`: Pydantic schemas.
- `repositories`: persistence access patterns.
- `services`: application use cases.
- `tasks`: asynchronous and scheduled jobs.
- `engines.data_sync`: market data ingestion and normalization.
- `engines.factor`: reusable factor calculations.
- `engines.strategy`: strategy definition and evaluation.
- `engines.backtest`: backtesting execution and reports.

## Runtime

```text
React frontend
    |
FastAPI backend
    |
PostgreSQL + TimescaleDB
Redis
Celery workers
```

The current baseline only includes the API, frontend, PostgreSQL, and Redis containers. Worker
processes will be added when the first asynchronous data-sync task is implemented.

