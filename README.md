# Fun Stock

Fun Stock 是一个股票策略研究与回测平台。当前阶段优先建设可复现的工程基线：
Docker 化服务、API 健康检查、前端脚手架、数据库迁移、Tushare 数据接入，以及严格的
代码质量检查。

## 技术栈

- 后端：Python 3.13、FastAPI、SQLAlchemy 2、Alembic、Celery、Redis
- 前端：React、TypeScript、Vite
- 数据库：PostgreSQL 17、TimescaleDB
- 工具链：uv、pnpm、Ruff、mypy、ESLint、Prettier、pytest

## 快速启动

```powershell
docker compose up --build
```

启动后访问：

- 前端：http://localhost:5173
- 后端接口文档：http://localhost:8000/docs
- 后端健康检查：http://localhost:8000/api/v1/health

## 开发说明

开发环境和常用命令见 [docs/development.md](docs/development.md)。

数据库设计说明见 [docs/database.md](docs/database.md)。

## 编码规范

所有人工编写和 AI 生成的改动都必须遵循
[docs/coding-standards.md](docs/coding-standards.md)。

AI 编码代理应先阅读 [AGENTS.md](AGENTS.md)，再阅读正在编辑目录下的局部
`AGENTS.md`。
