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
| `AGENTS.md`, `docs/11-testing-and-quality.md` | Agent rules, canonical commands and test harness |
| `docs/09-design-brief.md#legacy-requirement-traceability` | Acceptance criteria to test against |
| `docs/11_deployment_and_security.md` §8, §12 | Migration verification and the backup/restore drill |
| `backend/tests/sql/integrity_guards.sql` | Executable PostgreSQL invariant checks |
| `backend/tests/sql/pre_migration_counts.sql` | Row-count and financial-total reconciliation |
| `docs/10_testing_and_quality.md` §7 | Known untested areas and open risks |

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

## Backend test map — pick the narrowest file

Flat directory on purpose (node IDs are referenced by `docs/10`); select by file or
`-k`, not by moving files. Fastest selective run: the file, or `-k "<word>"`.
The `/test-fast` command holds the diff→tests matrix; `/test-backend` holds run modes.

| Module area | Test files |
|---|---|
| Auth & authorization | `test_auth_rbac.py`, `test_auth_sessions.py`, `test_auth_remember_me.py`, `test_lockout_policy.py`, `test_password_policy.py`, `test_password_reset.py`, `test_rate_limit.py`, `test_security_hardening.py`, `test_setup.py` |
| Authorization decisions | `test_role_permissions.py`, `test_single_role_rbac.py`, `test_access_enforcement.py`, `test_route_authorization.py`, `test_authorization_wildcard.py`, `test_audit_logs.py` |
| Finance & accounting | `test_posting_rules.py`, `test_financial_documents_module.py`, `test_finance_automation.py`, `test_job_finance_entries.py`, `test_charge_tax_round_trip.py` |
| Quotations | `test_quotations.py`, `test_quotation_versions.py`, `test_quotation_postgres.py` |
| Service orders & operations | `test_workflows.py`, `test_component_attributes.py`, `test_component_layouts.py`, `test_movements_and_milestones.py`, `test_transport_assets.py`, `test_record_status.py`, `test_archive.py` |
| Master data | `test_container_types.py`, `test_currencies_and_fx.py`, `test_document_types.py`, `test_party_roles.py`, `test_place_roles.py`, `test_deletion_policy.py`, `test_created_by.py` |
| System configuration | `test_config_versions.py`, `test_config_compare.py`, `test_config_version_lifecycle.py`, `test_settings_validation.py`, `test_localization_settings.py`, `test_validation_schema.py` |
| Reporting | `test_report_accounting.py`, `test_report_generation.py`, `test_report_export.py`, `test_reports_dashboard.py`, `test_reporting_values.py` |
| Integrations | `test_excel_import_export.py`, `test_attachments.py`, `test_upload_policy.py`, `test_backup.py`, `test_telegram.py`, `test_telegram_client.py`, `test_telegram_monitor.py`, `test_telegram_outbox.py`, `test_telegram_recovery.py`, `test_redis_integration.py` |
| Database & migrations | `test_migration_chain.py`, `test_schema_integrity.py`, `test_schema_docs.py`, `test_auth_postgres.py`, `test_postgres_places_migration.py`, `test_telegram_postgres.py`, `test_quotation_postgres.py` |
| Cross-module workflows | `test_workflows.py`, `test_multi_currency.py`, `test_request_schemas.py`, `test_api_completeness.py`, `test_frontend_api_contract.py`, `test_page_api_integration.py`, `test_write_validation.py`, `test_sorting.py`, `test_repository_queries.py` |

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
uv run python -m pytest -q --no-header     # full suite: minutes, SQLite in-memory
uv run ruff check .

# Schema and PostgreSQL-specific verification
uv run python -m alembic heads
uv run python -m pytest tests/test_migration_chain.py tests/test_schema_integrity.py -q
uv run python scripts/generate_schema_docs.py --check --strict
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
- A coverage-gap update in `docs/10_testing_and_quality.md`.
- A verification record with commands and observed results.
