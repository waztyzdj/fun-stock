# AGENTS.md

Frontend code lives here. Follow the root `AGENTS.md` and `docs/coding-standards.md`.

## Scope

Current app code is under `src/`. As the UI grows, prefer:

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

## Rules

- Use strict TypeScript.
- Use function components.
- Keep rendering pure and move side effects to hooks.
- Do not use `any`; use `unknown` and narrow it.
- Avoid non-null assertions.
- Prefer `interface` for props and exported object shapes.
- Keep API calls in service modules or hooks, not deeply nested UI components.
- Do not commit `node_modules`, `.pnpm-store`, `dist`, `.vite`, or coverage output.

## Naming

- Components: `PascalCase`.
- Hooks: `useCamelCase`.
- Variables and functions: `camelCase`.
- Interfaces and type names: `PascalCase`.
- Component-specific files: `PascalCase.tsx`.

## Validation

```powershell
docker compose run --rm --no-deps frontend pnpm lint
docker compose run --rm --no-deps frontend pnpm build
```

