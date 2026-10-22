---
description: Run the full Definition-of-Done verification for the current change set
---

Verify the uncommitted change against `AGENTS.md` → Definition of Done. Run only what
the diff can affect, in this order, and stop reporting as soon as a gate fails.

1. `git status --porcelain` and `git diff --stat` — confirm the change set is what you
   expect and contains no secret, dump, log or throwaway file.
2. Backend: from `backend/` `uv run pytest -q` and `uv run ruff check .`.
3. Frontend: from `frontend/` `pnpm lint && pnpm typecheck && pnpm test && pnpm i18n:check`.
4. Schema changed: from `backend/` run `uv run python scripts/generate_schema_docs.py`
   (never hand-edit `docs/06_database_design.sql`), and confirm the Alembic revision has
   a working `downgrade()`.
5. Authorization: the endpoint has a permission code and a test proves the denial path.
6. Docs: `docs/10_testing_and_quality.md` reflects the new status;
   `docs/09_roles_and_permissions.md` is updated for a new code;
   `docs/07_api_documentation.md`, `docs/08_frontend_and_ui_design.md`, and
   `docs/11_deployment_and_security.md` change when their contract, UI, or deployment
   surface changed.
7. Build only if the change can break it (see `/build-fast`).

Finish with: gates run, their observed results, anything still unverified (say so
explicitly), and the changed files.
