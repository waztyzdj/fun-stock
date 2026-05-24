# AGENTS.md

Backend code lives here. Follow the root `AGENTS.md` and `docs/coding-standards.md`.

## Scope

- `app/api`: FastAPI routers and API wiring.
- `app/core`: configuration, logging, database/session setup, shared infrastructure.
- `app/models`: SQLAlchemy models.
- `app/schemas`: Pydantic request/response schemas.
- `app/repositories`: persistence access.
- `app/services`: business workflows.
- `app/engines`: data sync, factor, strategy, and backtest engines.
- `app/tasks`: async and scheduled task entrypoints.
- `tests`: backend tests.

## Rules

- Keep route handlers thin.
- Do not place database queries in API routes.
- Do not place FastAPI dependencies inside engines.
- Use SQLAlchemy 2 style when adding persistence code.
- Use Pydantic schemas at API boundaries.
- Add tests for services, repositories, and engines when behavior changes.
- Keep Tushare tokens and secrets out of source code.

## Naming

- Python modules: `snake_case`.
- Functions and variables: `snake_case`.
- Classes and Pydantic/SQLAlchemy models: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Test files: `test_<subject>.py`.

## Validation

```powershell
docker compose run --rm --no-deps backend uv run pytest
docker compose run --rm --no-deps backend uv run ruff check .
docker compose run --rm --no-deps backend uv run mypy .
```

