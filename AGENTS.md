# AGENTS.md

本仓库是一个股票策略研究与回测平台。

修改代码前，必须先阅读并遵循：

- `docs/coding-standards.md`
- `docs/architecture.md`
- `docs/development.md`

## 必要工作流程

1. 编辑前运行 `git status --short`。
2. 不修改与当前任务无关的用户改动。
3. 不编辑生成文件、缓存、构建产物、依赖目录或本地密钥。
4. 保持改动范围清晰，并与现有架构一致。
5. 行为或环境变更时，同步更新测试和文档。
6. 结束前运行相关检查。

## 禁止提交

- `node_modules/`
- `.pnpm-store/`
- `dist/`
- `.vite/`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.env` 或 `.env.*`，但 `.env.example` 例外
- 本地数据库文件、日志、覆盖率产物、生成的行情数据、CSV/TSV/Parquet 输出

## 校验命令

后端改动：

```powershell
docker compose run --rm --no-deps backend uv run pytest
docker compose run --rm --no-deps backend uv run ruff check .
docker compose run --rm --no-deps backend uv run mypy .
```

前端改动：

```powershell
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```

项目配置改动：

```powershell
docker compose config --quiet
```

## AI 代理注意事项

- 优先做小而可审查的改动。
- 引入新抽象前，先复用现有模式。
- 没有明确必要时不要新增依赖。
- 不要重写 `tools/` 或 `infra/` 中用户创建的内容，除非用户明确要求。
- 如果 `git status` 中出现生成文件或缓存文件，先修正忽略规则再提交。
