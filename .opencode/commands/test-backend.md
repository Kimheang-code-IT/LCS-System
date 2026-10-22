---
description: Run backend tests (argument = path, file, node id or -k expression)
---

Run from `backend/`:

- No argument: `uv run pytest -q` (whole suite, SQLite in-memory).
- File: `uv run pytest -q tests/test_workflows.py`.
- Single test: `uv run pytest -q tests/test_quotations.py::test_create_quotation`.
- Keyword: `uv run pytest -q -k "posting and balance"`.
- Previous failures only: `uv run pytest -q --lf`.
- With a full traceback and stop-on-first: add `-x --tb=short`.

`$ARGUMENTS`

Notes:

- Tests use in-memory SQLite and real routers through `client`; no PostgreSQL or Docker
  needed. Never point a test at a real database.
- When `uv` is not on PATH, fall back to the documented Docker runner in `AGENTS.md`
  (mount the repo, `uv sync --frozen --extra dev`, then run the same selector).
- Never delete, skip or weaken a failing test to make the suite green.
- Report counts plus the first failure only; the full log stays in the terminal.
