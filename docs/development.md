# Development Guide

## Prerequisites

Use Docker Desktop for the default workflow. Local Python and Node installations are optional.

## Start The Platform

```powershell
docker compose up --build
```

Services:

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

PostgreSQL credentials for local development:

```text
database: fun_stock
username: fun_stock
password: fun_stock
```

## Backend Commands

```powershell
docker compose run --rm backend uv run pytest
docker compose run --rm backend uv run ruff check .
docker compose run --rm backend uv run mypy .
```

## Frontend Commands

```powershell
docker compose run --rm --no-deps -e CI=true frontend pnpm install --frozen-lockfile
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```

## Standards

- Keep business logic out of route handlers.
- Use service classes/functions for use cases.
- Use repositories for database access.
- Add tests for behavior, especially engines and services.
- Keep generated data, cache files, and local secrets out of git.
