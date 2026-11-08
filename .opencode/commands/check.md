---
description: Run scoped lint/type checks for task-owned changed code
---

Identify the current task-owned delta using status/diff, untracked files and timestamps;
exclude unrelated preexisting work. Read docs/03-development/testing-guide.md for risk.

- Documentation/instructions only: structural checks via /docs-check; no runtime gates.
- Backend code: from backend/ run uv run --no-sync ruff check <changed paths>.
- Frontend code: from frontend/ run pnpm exec eslint <changed files>; pnpm typecheck when
  types/components/contracts can be affected. Locale changes add pnpm i18n:check.
- Schema changes alone add the existing generated-schema check from backend/.

Commands are selectors, not literal angle-bracket paths. Report exact commands/results and
unverified checks. No build/full suite or unrelated fix.
