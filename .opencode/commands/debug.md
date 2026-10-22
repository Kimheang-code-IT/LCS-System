---
description: Investigate an error and apply the smallest correct fix
---

Target: `$ARGUMENTS`

Work in this order and stop at the first step that identifies the cause.

1. **Reproduce.** Get the exact symptom: failing test, HTTP status + body, browser
   console error, backend traceback. Failing test or API call beats guessing.
2. **Localize with context, not with rereads.** `ctx_compose` for the owning module, then
   `ctx_read` on the symbol's line range. Trace the failure from the router inward:
   `router.py` → `service.py` → `repository.py` / `models.py`.
3. Check the repo's usual suspects before deep debugging:
   - `uv run pytest -q --lf`, then one file with `-x --tb=long`.
   - `docker compose -f infrastructure/docker-compose.yml logs --tail=80 backend`.
   - `uv run ruff check .` (an import or name error is often a lint error first).
   - `uv run python scripts/generate_schema_docs.py --check` (model/doc drift).
   - `pnpm typecheck` (auto-import, prop or composable mismatch).
   - `tests/test_frontend_api_contract.py` when a frontend call 404s.
4. **Fix the cause, not the symptom.** Keep the smallest correct diff; no surrounding
   refactor, no swallowed exception, no commented-out assertion, no widened permission.
5. **Prove it.** Re-run the failing selector, then `/test-fast` for the neighbouring
   suites. State whether data or posts were touched.
6. If the root cause is outside this change (environment, missing service, credentials),
   say so and stop — do not paper over it in code.
