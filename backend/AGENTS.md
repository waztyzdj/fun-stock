# AGENTS.md

后端代码位于本目录。请同时遵循根目录 `AGENTS.md` 和
`docs/coding-standards.md`。

## 范围

- `app/api`：FastAPI 路由和 API 装配。
- `app/core`：配置、日志、数据库会话、共享基础设施。
- `app/models`：SQLAlchemy 模型。
- `app/schemas`：Pydantic 请求和响应模型。
- `app/repositories`：持久化访问。
- `app/services`：业务用例和应用服务。
- `app/engines`：数据同步、因子、策略、回测引擎。
- `app/tasks`：异步任务和调度任务入口。
- `app/core/celery_app.py`：Celery 应用和 beat 计划配置。
- `tests`：后端测试。

## 规则

- 路由处理函数保持轻量。
- 不在 API 路由中直接写数据库查询。
- 不把 FastAPI 依赖放入引擎层。
- 新增持久化代码时使用 SQLAlchemy 2 风格。
- API 边界使用 Pydantic 模型。
- 服务、仓储、引擎的行为变化需要补测试。
- Tushare token 和其它密钥不得进入源码。
- Celery 定时任务必须保持幂等，并通过 Redis 锁避免同类同步并发执行。

## 命名

- Python 模块：`snake_case`。
- 函数和变量：`snake_case`。
- 类、Pydantic 模型、SQLAlchemy 模型：`PascalCase`。
- 常量：`UPPER_SNAKE_CASE`。
- 测试文件：`test_<subject>.py`。

## 校验

```powershell
docker compose run --rm --no-deps backend uv run pytest
docker compose run --rm --no-deps backend uv run ruff check .
docker compose run --rm --no-deps backend uv run mypy .
```
