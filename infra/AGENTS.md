# AGENTS.md

基础设施和数据库初始化文件位于本目录。请同时遵循根目录 `AGENTS.md` 和
`docs/coding-standards.md`。

## 规则

- 本地初始化 SQL 尽量保持幂等。
- 有顺序要求的 SQL 初始化文件使用可排序数字前缀，例如 `001_extensions.sql`。
- 不在本目录放置生产密钥。
- 不修改用户创建的 schema 脚本，除非用户明确要求。
- 引入 Alembic 后，应用自有 schema 的变更优先通过迁移管理。

## 数据库命名

- 表名：复数 `snake_case`。
- 字段名：`snake_case`。
- 索引名：描述性 `snake_case`，例如 `ix_daily_quotes_ts_code_trade_date`。
- 唯一约束名：描述性 `snake_case`，例如 `uq_daily_quotes_ts_code_trade_date`。

## 校验

```powershell
docker compose config --quiet
```
