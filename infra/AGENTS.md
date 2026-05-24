# AGENTS.md

Infrastructure and database bootstrap files live here. Follow the root `AGENTS.md` and
`docs/coding-standards.md`.

## Rules

- Keep local bootstrap SQL idempotent when possible.
- Prefix ordered SQL init files with a sortable number, for example `001_extensions.sql`.
- Do not put production secrets in this directory.
- Do not modify user-created schema scripts unless explicitly asked.
- Prefer migrations for application schema changes once Alembic is introduced.

## Database Naming

- Tables: plural `snake_case`.
- Columns: `snake_case`.
- Indexes: descriptive `snake_case`, for example `ix_daily_quotes_ts_code_trade_date`.
- Unique constraints: descriptive `snake_case`, for example `uq_daily_quotes_ts_code_trade_date`.

## Validation

```powershell
docker compose config --quiet
```

