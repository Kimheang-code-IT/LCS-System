---
name: testing-qa
description: Use when adding or running LCS tests: backend unit, API, permission, constraint, migration, transaction and financial-reconciliation tests; frontend component and validation tests; end-to-end workflow verification; and interpreting a failing suite.
---

# Testing and QA

Prove behaviour rather than describing it. A feature is not done because the code
looks right — it is done when the applicable check has actually run and passed.

## When to use

- Adding or changing any feature, rule, or contract.
- A test is failing and you need to find out why.
- Verifying a migration, a financial invariant, or a permission.
- Preparing a release.

## Required inputs

1. What was changed and what could break as a result.
2. The narrowest check that would catch that break.
3. Whether the change affects money, authorization, the schema, or a contract.

## Project references

| Document | Use it for |
|---|---|
| `AGENTS.md` §Commands, §Tests | Canonical commands and the test harness |
| `docs/02_software_requirements_specification.md` | Acceptance criteria to test against |
| `docs/15_migration_and_rollback_guide.md` | Migration verification and reconciliation queries |
| `backend/tests/sql/integrity_guards.sql` | Executable PostgreSQL invariant checks |
| `backend/tests/sql/pre_migration_counts.sql` | Row-count and financial-total reconciliation |
| `docs/17_repository_analysis.md` §Coverage gaps | Known untested areas |

## The two harnesses

**Backend** — `backend/tests/`, in-memory SQLite via `aiosqlite`. `conftest.py`
overrides `get_session` and builds the schema with `Base.metadata.create_all`.
Fixtures: `client` (seeded `AsyncClient`), `login()` for auth headers (default
`admin` / `Passw0rd!`), `login(client, "sales")` for a role that lacks a
permission. `backend/tests/seed.py` is test-only.

Consequences you must design around:

- **A model change is in the test schema automatically; a migration-only change is
  not.** SQLite never runs Alembic.
- **PostgreSQL triggers, views, and JSONB operators do not exist in tests.** A guard
  added in a migration needs a case in `tests/sql/integrity_guards.sql` instead.
- `SELECT … FOR UPDATE` is a no-op on SQLite, so a lock cannot be proven by
  concurrency; prove the property that *depends* on the lock (unique revision
  numbers, no duplicate allocation) instead.
- The test client retains the login cookie. Clear `client.cookies` before asserting
  that an anonymous request is rejected, or the assertion is vacuous.

**Frontend** — `frontend/tests/**/*.spec.ts`, plain Vitest, `environment: node`,
`import.meta.client = false`, alias `~ -> app`. The Nuxt runtime is **not** mounted,
so test pure functions: validators, key mapping, formatters, table arithmetic,
module resolvers. Do not write component-mount tests.

## Workflow

1. **Reproduce first.** For a bug, write the failing test before the fix. Do not
   patch a symptom you cannot reproduce.
2. **Run the narrowest check**, then widen:

   ```bash
   cd backend && uv run python -m pytest tests/<file>::<test> -q --no-header
   cd backend && uv run python -m pytest tests/<file>.py -q --no-header
   cd frontend && pnpm vitest run tests/<file>.spec.ts
   ```

3. **Cover the shape of the change**, not just its happy path:

   | Change | Minimum coverage |
   |---|---|
   | New endpoint | success, each validation failure, permission denial |
   | New rule | accepted case, each rejected case, boundary value |
   | Schema change | `tests/test_migration_chain.py`, `tests/test_schema_integrity.py`, both schema docs, a live upgrade/downgrade |
   | Money logic | balanced ledger, rejected imbalance, reconciliation of the affected report |
   | Error key change | a frontend spec proving the key maps to a field |
   | Contract change | `tests/test_frontend_api_contract.py` |

4. **Run the gates in order.** Frontend `lint -> typecheck -> test`; backend
   `pytest -> ruff`. Then, when the change touches schema or guards, the
   PostgreSQL-side checks.
5. **Record what you ran.** Report the exact command and the observed result. A
   claim with no command behind it is not a verification.

## Full command reference

```bash
# Backend (from backend/)
uv run python -m pytest -q --no-header     # ~12 minutes, 220+ tests
uv run ruff check .

# Schema and PostgreSQL-specific verification
uv run python -m alembic heads
uv run python -m pytest tests/test_migration_chain.py tests/test_schema_integrity.py -q
uv run python scripts/generate_schema_docs.py --check --strict
uv run python scripts/generate_schema_dump.py --check
psql <DISPOSABLE_DB> -f tests/sql/integrity_guards.sql         # truncates everything
psql "$DATABASE_URL" -f tests/sql/pre_migration_counts.sql > post-counts.txt

# Frontend (from frontend/)
pnpm lint && pnpm typecheck && pnpm test && pnpm i18n:check
pnpm generate                              # build-affecting changes only
```

## End-to-end workflow to verify after a cross-cutting change

Create quotation → revise it → accept → convert to a Service Order → enter dynamic
component values → record a charge → issue it → create the financial document →
post it → allocate a payment → confirm the reports reconcile. `tests/test_workflows.py`
and `tests/test_finance_automation.py` cover most of this chain through the API;
extend them rather than writing a parallel suite.

## Rules

- **Never delete, skip, or weaken a failing test to make the suite pass.** A
  failure is either a real defect or a wrong expectation — decide which, fix the
  cause, and say so.
- **Never mark a report "reconciled" without running the reconciliation.** Trial
  balance must net to zero; AR/AP must equal the posted control accounts.
- Do not commit a test that asserts current buggy behaviour without labelling it.
- Do not add a retry or an `xfail` to hide flakiness; find the race.
- When a change cannot be verified without PostgreSQL, say so explicitly instead of
  claiming it passed.

## Acceptance criteria

- Every changed behaviour has at least one test that fails without the change.
- The narrow check, the full backend suite, and `ruff` pass for backend changes.
- The frontend gates pass for frontend changes.
- Schema changes additionally pass the migration-chain, schema-integrity, and
  schema-doc checks on both directions of the migration.
- Financial changes have a reconciliation result recorded, not asserted.
- The exact commands and their results are reported, and anything not run is named
  as unverified.

## Expected outputs

- New or updated tests under `backend/tests/` and `frontend/tests/`.
- New scenarios in `tests/sql/integrity_guards.sql` when a database guard changed.
- A coverage-gap update in `docs/17_repository_analysis.md`.
- A verification record with commands and observed results.
