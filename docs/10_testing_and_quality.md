# Testing and Quality

## 1. Quality Gates

A change is releasable only when all applicable gates pass:

| Layer | Command (from the stated directory) | What it proves |
|---|---|---|
| Backend tests | `uv run pytest -q` (from `backend/`) | Unit, API, permission, migration, financial and contract behaviour |
| Backend lint | `uv run ruff check .` (from `backend/`) | Imports, unused names, bugbear and upgrade rules |
| Schema reference | `uv run python scripts/generate_schema_docs.py --check --strict` (from `backend/`) | The committed SQL matches the models and every table/column is documented |
| Frontend lint | `pnpm lint` (from `frontend/`) | Vue/TypeScript style and unsafe patterns |
| Frontend types | `pnpm typecheck` (from `frontend/`) | Type contract across pages, stores, repositories and config |
| Frontend tests | `pnpm test` (from `frontend/`) | Validation, permissions, i18n, metadata, formatting, contract constants |
| i18n parity | `pnpm i18n:check` (from `frontend/`) | `en`, `km`, and `zh` bundles have identical keys |
| Docker build | `docker build` in CI | The image still builds from a clean context |

The focused gate is preferred while iterating (for example
`uv run pytest tests/test_party_roles.py -q`); the full gates run before a merge to
`dev` or `main`. The CI workflow runs the frontend gates, backend tests/lint, the
contract test, and a Docker build; it never deploys.

## 2. Backend Test Architecture

- Tests live in `backend/tests/` and use **in-memory SQLite** (`aiosqlite`).
  `conftest.py` overrides `get_session` and creates the schema with
  `Base.metadata.create_all`.
- `tests/seed.py` is test-only. The default login is `admin` / `Passw0rd!`.
  Fixtures provide an authenticated `client` and `login()` headers.
- Because SQLite has no PostgreSQL triggers, the default suite verifies service
  rules, API shape, authorization and state transitions, not trigger behaviour.
  The PostgreSQL guard script is a separate manual gate.
- Tests are organised by risk, not by file count: each module has a test file for
  its workflow, plus cross-cutting files for permissions, validation, migrations,
  schema drift, deletion policy, archive, attachments, reports, and the frontend
  contract.

Important cross-cutting suites:

| Suite | Purpose |
|---|---|
| `test_frontend_api_contract.py` | Statically reads frontend API constants and asserts every referenced `/api/v1/...` path and collection verb exists on the FastAPI app |
| `test_schema_docs.py` | Asserts one SQL file exists, the generated file is current, every table/column has a comment, and the schema matches the models |
| `test_schema_integrity.py` | Checks model metadata, naming conventions, and generated DDL expectations |
| `test_migration_chain.py` | Asserts the Alembic revision chain is linear and the head matches the documented head |
| `test_role_permissions.py` | Covers permission catalog, page-to-source mapping, single active role, protected administrator and delegation rules |
| `test_record_status.py` | Covers the shared status policy, permissions, audit, workflow-command refusal and frontend runner parity |
| `test_party_roles.py` | Covers Party Roles CRUD, duplicate code/name, multi-role assignment, inactive roles, rename propagation and delete blocking |
| `test_place_roles.py` | Covers Place Roles and route-stop validation after the Places removal |
| `test_financial_documents_module.py`, `test_finance_automation.py` | Document types, posting, allocation, reversal, and one create-read-post-balance run per document type |
| `test_posting_rules.py` | Rule selection by type/fee/priority, ambiguity, fallback, posting, reversal, concurrency and protected deletes |
| `test_multi_currency.py`, `test_reporting_values.py` | FX snapshotting, allocation exchange differences, and reconciled financial statements |
| `test_auth_rbac.py`, `test_password_reset.py`, `test_lockout_policy.py`, `test_rate_limit.py` | Authentication, RBAC denial paths, password lifecycle, lockout and throttling |
| `test_archive.py`, `test_attachments.py`, `test_deletion_policy.py` | Soft delete, restore, guarded hard delete, attachment lifecycle and reference-delete guards |

## 3. Frontend Test Architecture

- Plain Vitest, `environment: node`, `import.meta.client = false`, alias
  `~ -> app`. Only `tests/**/*.spec.ts` run; there is no Nuxt runtime and no
  browser suite.
- Tests cover pure logic and static-source contracts rather than rendered pixels:
  validation rules and error paths, notification policy, i18n key parity,
  reference options, form metadata, formatting, page access, permissions,
  route-stop tables, dynamic tabs, print models, and API endpoint constants.
- The static notification-policy spec scans every toast call in `app/` so a
  validation error cannot regress into a toast.
- The i18n spec compares the three bundles structurally and fails on a missing or
  extra key.

## 4. Test Data, Fixtures, and Determinism

- Seed data is created through services, not raw inserts, so constraints and
  defaults are exercised.
- Money and quantities use `Decimal`; tests never compare with binary floats.
- Time-dependent tests freeze or inject the relevant date/period; the seeded
  current-year document sequences make number allocation deterministic.
- Permission-denial tests use a user without the required code and assert the
  exact `403`/`ACCESS_DENIED` response, not just the UI hiding a button.
- The contract test reads the checked-in frontend source; it does not start the
  frontend or a browser.

## 5. Financial Integrity Verification

The following invariants are tested, and must stay tested:

- Every posted journal balances; an unbalanced draft is rejected with
  `JOURNAL_UNBALANCED`.
- Posting is atomic: journal, lines, posting link and document status commit
  together or not at all.
- A posted document cannot be edited or deleted; corrections use
  `reverse_document`.
- Closed accounting periods reject new postings.
- A document cannot be posted twice; `financial_document_postings` is unique.
- Allocation cannot exceed the payment or target balance and requires matching
  party and currency.
- Each posting snapshots its own exchange rate and base-currency amounts; a newer
  rate never rewrites a posted amount.
- Reports read posted data only; trial balance nets to zero, and AR/AP reconcile
  to their control accounts.
- Charge tax is read from `taxRate` (with `tax` fallback) and survives the trip
  from service charge to finance invoice.

## 6. PostgreSQL-Only and Manual Checks

These are not covered by the default SQLite suite and must be run on the real
stack before a production release:

```bash
# From a machine with psql access to the target database
psql "$DATABASE_URL" -f backend/tests/sql/integrity_guards.sql
psql "$DATABASE_URL" -f backend/tests/sql/pre_migration_counts.sql
```

- `integrity_guards.sql` exercises the immutability, balance, period, posting and
  allocation triggers.
- `pre_migration_counts.sql` records row counts before a migration so a rollback
  can verify that no data was lost.
- A live smoke test posts, reverses, re-balances and checks the trial balance
  against the running container.
- Restore drills use a real `pg_dump`/base backup, not the Google Sheets mirror.

## 7. Coverage Gaps and Open Risks

| Gap / risk | Impact | Status |
|---|---|---|
| No browser E2E of blur/focus, tab reveal and responsive layout | The validation pipeline is tested in units and static source; real DOM interaction is manual | Open |
| PostgreSQL guard SQL is not in CI | A trigger regression can pass the SQLite suite; this already caused a posting outage once | Open (highest-value CI addition) |
| No unsaved-changes guard on document navigation | A user can lose a dirty form | Open |
| Computed line-table cells cannot show inline errors | Non-editable cells are skipped; the focus target still exists | Accepted |
| Movements/milestones editor has no UI | APIs are tested; the itinerary is unreachable from the UI | Open |
| `customer_customs_accounts` has no API or UI | The table and `customs_credential.retrieve` permission are unused; customer customs fields live on the encrypted customer module record | Open |
| Quotation revision comparison has no side-by-side UI | API supports compare; users cannot see it | Open |
| `vw_general_ledger` is not exposed as an endpoint | The view exists; `ledger-lines` covers the same rows | Queued, low value |
| User deletion fails for audited accounts | `audit_events.actor_user_id` has `NO ACTION`; deactivate until an additive `ON DELETE SET NULL` migration lands | Open |
| No monitoring or alerting | A failed posting, lockout or backup produces no signal | Open |
| Off-host PostgreSQL backup/WAL archiving is documented, not automated | Google Sheets is not a database backup | Partial |
| Reconciliation queries are manual | F6 remains open | Open |
| A private key sits in `docs/lcssystem.pem` | Untracked and gitignored, but inside the working tree; owner decision required | Open (**S1**) |

## 8. Implementation Status Summary

Verified against the current code and focused tests:

| Area | Status |
|---|---|
| Master data, Party Roles, Place Roles, route stops, currencies | Implemented and tested |
| Quotations, revisions, accept/convert, service orders, dynamic tabs, Transport Type pricing lines | Implemented and tested |
| Service charges, finance invoice draft, financial documents, posting rules | Implemented and tested |
| Double-entry posting, reversals, periods, allocation, multi-currency | Implemented and tested |
| RBAC, one active role, protected administrator, audit | Implemented and tested |
| Archive, attachments, record status, validation, success-only toasts | Implemented and tested |
| Financial and operational reports (server-side) | Implemented and tested |
| Google Sheets backup scheduler | Implemented and tested |
| Off-host PostgreSQL backup/WAL | Partial (documented, not automated) |
| Monitoring/alerting | Missing |
| Movements/milestones UI, quotation comparison UI | Missing |
| Browser E2E and CI PostgreSQL guard run | Missing |

## 9. Reporting a Test Result

Report the exact command, the directory it ran from, and the observed result. A
focused pass is not a full-suite pass; say which one was run. A skipped or
weakened test is a failure of the definition of done, not a workaround. If a
PostgreSQL-only check was not run, say so explicitly.
