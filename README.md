# Fun Stock

Fun Stock is a stock strategy research and backtesting platform. The first milestone focuses
on a reproducible engineering baseline: Dockerized services, API health checks, frontend
bootstrap, and strict code quality defaults.

## Stack

- Backend: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Celery, Redis
- Frontend: React, TypeScript, Vite
- Database: PostgreSQL 17 with TimescaleDB
- Tooling: uv, pnpm, Ruff, mypy, ESLint, Prettier, pytest

## Quick Start

```powershell
docker compose up --build
```

Open:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Backend health: http://localhost:8000/api/v1/health

## Development

See [docs/development.md](docs/development.md).

