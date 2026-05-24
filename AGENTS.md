# AGENTS.md

This repository is a stock strategy research and backtesting platform.

Before making changes, read and follow:

- `docs/coding-standards.md`
- `docs/architecture.md`
- `docs/development.md`

## Required Workflow

1. Run `git status --short` before editing.
2. Do not modify unrelated user changes.
3. Do not edit generated files, caches, build outputs, dependency folders, or local secrets.
4. Keep changes scoped and consistent with the existing architecture.
5. Update tests and docs when behavior or setup changes.
6. Run relevant checks before finishing.

## Never Commit

- `node_modules/`
- `.pnpm-store/`
- `dist/`
- `.vite/`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.env` or `.env.*` except `.env.example`
- local database files, logs, coverage output, generated market data, CSV/TSV/Parquet outputs

## Validation

Backend changes:

```powershell
docker compose run --rm --no-deps backend uv run pytest
docker compose run --rm --no-deps backend uv run ruff check .
docker compose run --rm --no-deps backend uv run mypy .
```

Frontend changes:

```powershell
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```

Project configuration changes:

```powershell
docker compose config --quiet
```

## Notes For AI Agents

- Prefer small, reviewable edits.
- Use existing patterns before introducing new abstractions.
- Do not add dependencies without a clear need.
- Do not rewrite user-created work in `tools/` or `infra/` unless explicitly asked.
- If generated or cache files appear in `git status`, fix ignore rules before committing.

