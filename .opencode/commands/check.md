---
description: Run the lint and type checks that apply to the changed files
---

Check only the stack that changed, then report failures without fixing unrelated ones.
If the diff and untracked files match none of the paths below, report `no changed stack`
and stop.

1. Backend changed (`backend/**`): from `backend/` run `uv run ruff check .`.
2. Frontend changed (`frontend/**`): from `frontend/` run `pnpm lint`, then `pnpm typecheck`.
3. Locale bundles changed (`frontend/i18n/locales/**`): from `frontend/` run `pnpm i18n:check`.
4. Model or `schema_descriptions.py` changed: from `backend/` run
   `uv run python scripts/generate_schema_docs.py --check --strict`.
5. Docs changed: apply the `/docs-check` checklist (`.opencode/commands/docs-check.md`)
   for status, permissions, architecture, deploy and dead references.

Report a one-line verdict per gate and the exact failing lines. Do not run the frontend
production build here — that is `/build-fast`.
