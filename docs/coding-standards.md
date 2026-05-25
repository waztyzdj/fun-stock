# 编码规范

本文档是项目对人工开发者和 AI 编码代理的共同约定。新增功能、重构或生成代码前，都
必须遵循本规范。

## 基本原则

- 优先写朴素、明确、可维护的代码，不追求炫技式抽象。
- 改动范围只覆盖当前请求的行为。
- 不修改无关文件或用户正在进行的工作。
- 只有依赖能明显降低复杂度，或与项目技术栈一致时才新增依赖。
- 生成文件、缓存、密钥、本地数据库和构建产物不得进入 Git。
- 行为或环境变化时，同步更新测试和文档。

## 仓库结构

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

边界说明：

- `backend/app/api`：仅放 FastAPI 路由，路由处理函数保持轻量。
- `backend/app/core`：配置、日志、数据库连接和共享基础设施。
- `backend/app/models`：SQLAlchemy ORM 模型。
- `backend/app/schemas`：Pydantic 请求和响应模型。
- `backend/app/repositories`：数据库访问，不包含 HTTP 或 UI 关注点。
- `backend/app/services`：应用用例和业务流程。
- `backend/app/engines`：数据同步、因子、策略和回测等领域引擎。
- `backend/app/tasks`：异步任务或调度任务入口。
- `frontend/src`：React 应用代码。
- `infra`：本地基础设施脚本和数据库初始化 SQL。
- `docs`：架构、运维、规范和决策文档。
- `tools`：开发工具和一次性脚本。

## Git 与生成文件

应该提交的内容包括源码、锁文件、文档、配置、迁移和稳定的基础设施脚本。

禁止提交：

- `node_modules/`、`.pnpm-store/`、`dist/`、`.vite/`
- `.venv/`、`__pycache__/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`
- `.env`、`.env.*`，但 `.env.example` 例外
- 日志、临时文件、本地数据库文件、生成数据、CSV/TSV/Parquet 输出

提交前检查：

```powershell
git status --short
git ls-files frontend/.pnpm-store frontend/node_modules frontend/dist backend/.venv
```

第二条命令应无输出。

## 后端规范

### Python

- 使用 Python 3.13 语法。
- 遵循 PEP 8 命名：
  - 模块和包：`snake_case`
  - 函数和变量：`snake_case`
  - 类：`PascalCase`
  - 常量：`UPPER_SNAKE_CASE`
- 公共函数和不明显的值必须写显式类型注解。
- 避免使用 `Any`；如不可避免，应隔离在集成边界。
- 优先使用标准库泛型，例如 `list[str]` 和 `dict[str, int]`。
- 导入顺序交给 Ruff/isort 统一管理。
- Python 文件使用双引号，与 Ruff 格式化配置保持一致。

### FastAPI

- 路由定义在 `app/api/routes/<resource>.py`。
- 路由统一注册到 `app/api/router.py`。
- 路由处理函数只负责校验、鉴权、调用服务和返回 schema。
- 不在路由处理函数中写 SQLAlchemy 查询或 Pandas 重逻辑。
- 请求和响应契约使用 Pydantic 模型。
- 稳定 API 路径放在 `/api/v1` 下。

### 服务与仓储

- Services 负责业务流程。
- Repositories 负责持久化查询。
- Engines 负责领域计算，并且应易于脱离 HTTP 测试。
- Service 可以调用 repositories 和 engines。
- Repository 不调用 service。
- Engine 避免直接依赖 HTTP 或 FastAPI。

### 数据库

- 使用 SQLAlchemy 2 风格 API。
- 引入迁移后，schema 变更使用 Alembic migration。
- 优先定义明确的约束、索引和唯一键。
- 后端创建的系统时间戳使用 UTC，除非市场日历明确要求交易所本地日期。
- 股票数据中，`trade_date` 是领域日期字段，不要把它当作系统时间戳滥用。

### 测试

- 后端测试放在 `backend/tests`。
- 测试文件命名为 `test_<subject>.py`。
- 优先写面向行为的测试，少测实现细节。
- Engine 和 service 代码应有单元测试。
- 数据同步和数据库代码在持久化行为重要时应有集成测试。

运行：

```powershell
docker compose run --rm --no-deps backend uv run pytest
docker compose run --rm --no-deps backend uv run ruff check .
docker compose run --rm --no-deps backend uv run mypy .
```

## 前端规范

### TypeScript

- 使用严格 TypeScript。
- 组件使用 `PascalCase`。
- Hooks 使用 `useCamelCase`。
- 变量和函数使用 `camelCase`。
- 类型和接口使用 `PascalCase`。
- 组件 props 或导出的对象结构优先使用 `interface`。
- 避免 `any`；使用 `unknown` 并收窄类型。
- 避免非空断言。应检查值并抛错，或处理空状态。

### React

- 使用函数组件。
- 组件保持纯净：渲染不产生副作用。
- Hooks 只在 React 组件或自定义 hooks 顶层使用。
- 数据加载放在 hooks 或 service 模块中，不要深埋在展示组件里。
- 文件难以扫描时再拆组件，不只为了减少行数而拆。
- 避免全局可变状态，除非由明确的状态库管理。

### 前端组织

应用增长后采用以下结构：

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

约定：

- `components`：无领域归属的可复用 UI 组件。
- `features/<name>`：领域相关页面、组件、hooks 和辅助函数。
- `services`：HTTP 客户端和 API adapter。
- `lib`：与框架无关的工具函数。
- `types`：不属于单一 feature 的共享 TypeScript 类型。

### 样式

- CSS class 名应清晰、稳定。
- 避免内联样式，除非确实需要动态值。
- 不允许文本溢出按钮、卡片、表格或面板。
- 优先使用可访问的语义化 HTML 和 label。
- 引入新视觉模式前，先复用现有设计约定。

运行：

```powershell
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```

## 命名

- 数据库表：复数 snake case，例如 `stocks`、`daily_quotes`。
- 数据库字段：snake case。
- API 路由：复数名词，例如 `/api/v1/stocks`。
- Python 模块：snake case。
- React 组件专属文件使用 PascalCase，例如 `StockTable.tsx`。
- 通用 TypeScript 工具文件可使用 camel case 或 kebab case；同一目录内保持一致。
- 测试文件名称应对应被测主题。

## 错误处理

- 服务和引擎中有必要时抛出类型化领域异常。
- 在 API 边界把领域错误转换为 HTTP 错误。
- 不要静默吞异常。
- 记录意外错误时带上上下文，但绝不记录密钥或 Tushare token。
- 前端 API 错误应呈现清晰状态：加载、空、错误、成功。

## 配置与密钥

- 运行时配置使用环境变量。
- 提交 `.env.example`，不提交真实 `.env` 文件。
- 不在源码中硬编码 token、生产数据库密码或本地绝对路径。
- Docker Compose 中的本地账号密码只允许用于本地开发。

## 文档

以下情况需要更新文档：

- 启动或开发命令变化
- 架构边界变化
- 引入重要新依赖
- 数据库 schema 或迁移流程变化
- 增加新的引擎或策略契约

## AI 代理规则

AI 代理编辑本仓库时：

1. 修改前先阅读现有文件。
2. 检查 `git status --short`，避开无关用户改动。
3. 不修改生成目录或已忽略目录。
4. 使用现有模块边界。
5. 优先做小而可审查的改动。
6. 行为变化时添加或更新测试。
7. 运行相关质量检查。
8. 准确说明改了什么、验证了什么。

前端改动运行 lint 和 build。后端改动运行 pytest、Ruff 和 mypy。

## 参考资料

- PEP 8：https://peps.python.org/pep-0008/
- FastAPI 大型应用：https://fastapi.tiangolo.com/tutorial/bigger-applications/
- React 规则：https://react.dev/reference/rules
- typescript-eslint 类型化 lint：https://typescript-eslint.io/getting-started/typed-linting/
- GitHub 忽略文件：https://docs.github.com/en/get-started/git-basics/ignoring-files
- Prettier ignore 文件：https://prettier.io/docs/ignore
