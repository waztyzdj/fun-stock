# AGENTS.md

前端代码位于本目录。请同时遵循根目录 `AGENTS.md` 和
`docs/coding-standards.md`。

## 范围

当前应用代码位于 `src/`。随着界面增长，优先采用以下结构：

```text
src/
  app/
  components/
  features/
  hooks/
  lib/
  services/
  styles/
  types/
```

## 规则

- 使用严格 TypeScript。
- 使用函数组件。
- 保持渲染逻辑纯净，把副作用放入 hooks。
- 不使用 `any`；使用 `unknown` 后再收窄类型。
- 避免非空断言。
- 组件 props 和导出的对象结构优先使用 `interface`。
- API 调用放在 service 模块或 hooks 中，不要深埋在 UI 组件里。
- 不提交 `node_modules`、`.pnpm-store`、`dist`、`.vite` 或覆盖率产物。

## 命名

- 组件：`PascalCase`。
- Hooks：`useCamelCase`。
- 变量和函数：`camelCase`。
- 接口和类型名：`PascalCase`。
- 组件专属文件：`PascalCase.tsx`。

## 校验

```powershell
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```
