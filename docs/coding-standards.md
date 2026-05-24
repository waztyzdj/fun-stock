# Coding Standards

This document is the project contract for human developers and AI coding agents. Follow it
before adding features, refactoring, or generating code.

## Principles

- Prefer boring, explicit, maintainable code over clever abstractions.
- Keep changes scoped to the requested behavior.
- Do not modify unrelated files or user-owned work in progress.
- Add dependencies only when they clearly reduce complexity or match the project stack.
- Keep generated files, caches, secrets, local databases, and build outputs out of Git.
- Update tests and documentation when behavior or setup changes.

## Repository Layout

```text
fun-stock/
  backend/
    app/
      api/
      core/
      engines/
      models/
      repositories/
      schemas/
      services/
      tasks/
    tests/
  frontend/
    src/
  infra/
    postgres/
      init/
  docs/
  tools/
```

Use these boundaries:

- `backend/app/api`: FastAPI routers only. Keep route handlers thin.
- `backend/app/core`: configuration, logging, database wiring, shared infrastructure.
- `backend/app/models`: SQLAlchemy ORM models.
- `backend/app/schemas`: Pydantic request and response schemas.
- `backend/app/repositories`: database access. No HTTP or UI concerns.
- `backend/app/services`: application use cases and business workflows.
- `backend/app/engines`: domain engines for data sync, factors, strategies, and backtests.
- `backend/app/tasks`: async or scheduled task entrypoints.
- `frontend/src`: React application code.
- `infra`: local infrastructure scripts and database bootstrap SQL.
- `docs`: architecture, operations, standards, and decisions.
- `tools`: developer utilities and one-off scripts.

## Git And Generated Files

Tracked files should be source code, lock files, docs, configuration, migrations, and stable
infrastructure scripts.

Never commit:

- `node_modules/`, `.pnpm-store/`, `dist/`, `.vite/`
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `.env`, `.env.*` except `.env.example`
- logs, temporary files, local DB files, generated data, CSV/TSV/Parquet outputs

Before committing, check:

```powershell
git status --short
git ls-files frontend/.pnpm-store frontend/node_modules frontend/dist backend/.venv
```

The second command should return nothing.

## Backend Standards

### Python

- Use Python 3.13 syntax.
- Follow PEP 8 naming:
  - modules and packages: `snake_case`
  - functions and variables: `snake_case`
  - classes: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`
- Use explicit type annotations for public functions and non-obvious values.
- Avoid `Any`; if it is unavoidable, isolate it at integration boundaries.
- Prefer standard library types such as `list[str]` and `dict[str, int]`.
- Keep imports sorted by Ruff/isort.
- Use double quotes in Python files, matching Ruff format configuration.

### FastAPI

- Define routers in `app/api/routes/<resource>.py`.
- Register routers in `app/api/router.py`.
- Keep route handlers limited to validation, authorization, calling services, and returning
  schemas.
- Do not put SQLAlchemy queries or Pandas-heavy logic in route handlers.
- Use Pydantic schemas for request and response contracts.
- Expose stable API paths under `/api/v1`.

### Services And Repositories

- Services own business workflows.
- Repositories own persistence queries.
- Engines own domain computation and should be easy to test without HTTP.
- A service may call repositories and engines.
- Repositories must not call services.
- Engines should avoid direct HTTP or FastAPI dependencies.

### Database

- Use SQLAlchemy 2 style APIs.
- Use Alembic migrations for schema changes once migrations are introduced.
- Prefer explicit constraints, indexes, and unique keys.
- Use `UTC` timestamps for backend-created timestamps unless a market calendar requires an
  exchange-local date.
- For stock data, keep `trade_date` as a date-like domain field and avoid overloading it as a
  system timestamp.

### Tests

- Put backend tests under `backend/tests`.
- Name test files `test_<subject>.py`.
- Prefer behavior-focused tests over implementation-detail tests.
- Engine and service code should have unit tests.
- Data sync and database code should have integration tests when persistence behavior matters.

Run:

```powershell
docker compose run --rm --no-deps backend uv run pytest
docker compose run --rm --no-deps backend uv run ruff check .
docker compose run --rm --no-deps backend uv run mypy .
```

## Frontend Standards

### TypeScript

- Use strict TypeScript.
- Components use `PascalCase`.
- Hooks use `useCamelCase`.
- Variables and functions use `camelCase`.
- Types and interfaces use `PascalCase`.
- Prefer `interface` for object shapes exported or used as component props.
- Avoid `any`; use `unknown` and narrow it.
- Avoid non-null assertions. Check the value and throw or handle the empty state.

### React

- Use function components.
- Keep components pure: rendering should not cause side effects.
- Use hooks only at the top level of React components or custom hooks.
- Put data loading in hooks or service modules, not deeply inside presentational components.
- Split components when a file becomes hard to scan, not just to reduce line count.
- Avoid global mutable state unless it is managed by an explicit state library.

### Frontend Organization

Use this structure as the application grows:

```text
frontend/src/
  app/
  components/
  features/
    stocks/
    strategies/
    backtests/
  hooks/
  lib/
  services/
  styles/
  types/
```

Guidelines:

- `components`: reusable UI pieces with no domain ownership.
- `features/<name>`: domain-specific screens, components, hooks, and helpers.
- `services`: HTTP clients and API adapters.
- `lib`: framework-neutral utilities.
- `types`: shared TypeScript types when they do not belong to one feature.

### Styling

- Keep CSS class names descriptive and stable.
- Avoid inline styles except for dynamic values that truly require them.
- Do not let text overflow buttons, cards, tables, or panels.
- Prefer accessible semantic HTML and labels.
- Use existing design conventions before introducing new visual patterns.

Run:

```powershell
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```

## Naming

- Database tables: plural snake case, for example `stocks`, `daily_quotes`.
- Database columns: snake case.
- API routes: plural nouns, for example `/api/v1/stocks`.
- Python modules: snake case.
- React components: PascalCase file names when component-specific, for example
  `StockTable.tsx`.
- General TypeScript utilities: camel or kebab file names are allowed; choose one within a
  folder and stay consistent.
- Test files mirror the subject name.

## Error Handling

- Raise typed domain exceptions in services and engines when useful.
- Convert domain errors to HTTP errors at the API boundary.
- Do not swallow exceptions silently.
- Log unexpected errors with context, but never log secrets or Tushare tokens.
- Frontend API errors should produce clear UI states: loading, empty, error, success.

## Configuration And Secrets

- Keep runtime configuration in environment variables.
- Commit `.env.example`, never real `.env` files.
- Do not hardcode tokens, database passwords for production, or local absolute paths in source
  code.
- Docker Compose local credentials are acceptable only for local development.

## Documentation

Update docs when:

- setup commands change
- architecture boundaries change
- new major dependencies are introduced
- database schema or migration workflow changes
- a new engine or strategy contract is added

## AI Agent Rules

When an AI agent edits this repository:

1. Inspect existing files before changing code.
2. Check `git status --short` and avoid unrelated user changes.
3. Do not modify generated or ignored directories.
4. Use the existing module boundaries.
5. Prefer small, reviewable changes.
6. Add or update tests for behavior changes.
7. Run the relevant quality checks.
8. Report exactly what changed and what was verified.

For frontend changes, run lint and build. For backend changes, run pytest, Ruff, and mypy.

## References

- PEP 8: https://peps.python.org/pep-0008/
- FastAPI bigger applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- React Rules of React: https://react.dev/reference/rules
- typescript-eslint typed linting: https://typescript-eslint.io/getting-started/typed-linting/
- GitHub ignoring files: https://docs.github.com/en/get-started/git-basics/ignoring-files
- Prettier ignore files: https://prettier.io/docs/ignore

