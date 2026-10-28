---
description: Run the full Definition-of-Done verification for the current change set
---

Verify the uncommitted change against `AGENTS.md` → Definition of Done. Classify the
change set first, run only the gates it can affect, and stop reporting as soon as a gate
fails.

1. **Change set** — `git status --porcelain`, `git diff --stat` and `git diff --cached
   --stat`. Confirm it is what you expect and contains no secret, dump, log or throwaway
   file. Derive the changed paths; untracked files count.
2. **Backend** (`backend/**`) — `uv run ruff check .`. Tests: use `/test-fast` when every
   changed path belongs to one module row; run `uv run pytest -q` when the diff touches
   `app/core/**`, `app/api/**`, `models.py`, `alembic/versions/**`, dependency manifests,
   several modules, or a path `/test-fast` does not cover. If no test ran, prove imports
   with `uv run python -c "import app.main"`.
3. **Frontend** (`frontend/**`) — `pnpm lint`, `pnpm typecheck`, `pnpm test`; add
   `pnpm i18n:check` only for `i18n/locales/**` or language constants. A production build
   is `/build-fast`, not this command.
4. **Schema** (`models.py`, `alembic/versions/**`, `backend/scripts/schema_descriptions.py`)
   — from `backend/` run `uv run python scripts/generate_schema_docs.py --check --strict`
   (never hand-edit `docs/06_database_design.sql`) and confirm the revision has a working
   `downgrade()`.
5. **Docs** — apply the `/docs-check` checklist (`.opencode/commands/docs-check.md`):
   generated SQL, status/risk, permissions, architecture, deploy, and dead references.
6. **Authorization and money** — a new endpoint has a permission code and a test proving
   the denial path; a money path has a balanced journal and `Decimal` arithmetic.
7. **Build** only when the diff can break it (see `/build-fast`); Docker only for a
   Dockerfile, dependency manifest, `infrastructure/**` or `infrastructure/docker-compose.prod.yml` change.

Finish with: gates run, their observed results, anything still unverified (say so
explicitly), and the changed files.
