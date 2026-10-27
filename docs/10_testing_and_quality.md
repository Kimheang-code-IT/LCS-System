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
- In-memory SQLite serialises writers, so it cannot prove that two simultaneous
  conversions create one service order. `tests/test_quotation_postgres.py` covers
  that on a disposable PostgreSQL database and is skipped unless
  `LCS_TEST_PG_HOST`, `LCS_TEST_PG_USER`, `LCS_TEST_PG_PASSWORD` and
  `LCS_TEST_PG_DB` are set. It also proves the `ON DELETE SET NULL` behaviour of
  `quotations.source_service_order_id`.
- `test_postgres_places_migration.py` is the PostgreSQL data-preservation
  rehearsal. It is skipped unless `LCS_TEST_POSTGRES_URL` points at a disposable
  server; it creates and drops randomly named databases, migrates to the head,
  asserts Places rows/links/foreign keys survive, and proves the guard aborts on
  a database that already lost Places.
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
| `test_migration_chain.py` | Asserts the Alembic revision chain is linear, the head matches the documented head, and the Places revisions never drop the legacy table/columns |
| `test_postgres_places_migration.py` | PostgreSQL-only rehearsal: Places rows, role links, foreign keys and financial totals survive upgrade; the destructive-c3d4 guard aborts; downgrade is non-destructive |
| `test_role_permissions.py` | Covers permission catalog, page-to-source mapping, single active role, protected administrator and delegation rules |
| `test_record_status.py` | Covers the shared status policy, permissions, audit, workflow-command refusal and frontend runner parity |
| `test_party_roles.py` | Covers Party Roles CRUD, duplicate code/name, multi-role assignment, inactive roles, rename propagation and delete blocking |
| `test_place_roles.py` | Covers Place Roles and the route-stop validation/lifecycle; legacy column preservation is covered by the PostgreSQL test |
| `test_financial_documents_module.py`, `test_finance_automation.py` | Document types, posting, allocation, reversal, and one create-read-post-balance run per document type |
| `test_posting_rules.py` | Rule selection by type/fee/priority, ambiguity, fallback, posting, reversal, concurrency and protected deletes |
| `test_multi_currency.py`, `test_reporting_values.py` | FX snapshotting, allocation exchange differences, and reconciled financial statements |
| `test_auth_rbac.py`, `test_password_reset.py`, `test_lockout_policy.py`, `test_rate_limit.py` | Authentication, RBAC denial paths, password lifecycle, lockout and throttling |
| `test_archive.py`, `test_attachments.py`, `test_deletion_policy.py` | Soft delete, restore, guarded hard delete, attachment lifecycle and reference-delete guards |

## 3. Frontend Test Architecture

- Plain Vitest, `environment: node`, `import.meta.client = false`, alias
  `~ -> app`. Only `tests/**/*.spec.ts` run; there is no Nuxt runtime.
- **Browser layer:** Playwright Test, `frontend/e2e/**/*.spec.ts`, configured by
  `frontend/playwright.config.ts` and run with `pnpm test:e2e`. It targets the compose
  stack at `http://localhost` by default (`E2E_BASE_URL` overrides). The checked-in specs
  are read-only — startup, the anonymous auth guard, and login-form validation — and the
  authenticated navigation/sign-out journey is skipped unless `E2E_USERNAME` and
  `E2E_PASSWORD` name a dedicated non-production account. No spec creates, edits or
  deletes a record.
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

# Disposable PostgreSQL rehearsal for the Places migration (creates/drops a
# randomly named database; never touches the database named in the URL)
cd backend
LCS_TEST_POSTGRES_URL=postgresql://user:password@host:5432/postgres \
  uv run pytest tests/test_postgres_places_migration.py -q
```

- `integrity_guards.sql` exercises the immutability, balance, period, posting and
  allocation triggers.
- `pre_migration_counts.sql` records row counts before a migration so a rollback
  can verify that no data was lost.
- A live smoke test posts, reverses, re-balances and checks the trial balance
  against the running container.
- Restore drills use a real `pg_dump`/base backup and the isolated
  `/opt/lcs/restore-db.sh` helper, not the Google Sheets mirror.

### Verified on 2026-10-22 (local disposable databases only)

- `uv run pytest -q`: **486 passed, 2 skipped** in 13m33s. The two skips are
  the PostgreSQL rehearsal below when `LCS_TEST_POSTGRES_URL` is unset.
- `uv run ruff check .`: **passed**.
- `uv run python scripts/generate_schema_docs.py --check --strict`: **passed**
  (67 tables documented, SQL up to date).
- `uv run pytest tests/test_migration_chain.py tests/test_schema_docs.py -q`:
  **27 passed**.
- `LCS_TEST_POSTGRES_URL=<disposable local PostgreSQL> uv run pytest
  tests/test_postgres_places_migration.py -q`: **2 passed**. This migrated a
  fresh database to the base revision, inserted two representative Places rows
  (one linked to a Place Role, one unreferenced), route stops and movements with
  one blank and one manual snapshot, and a balanced draft journal (debit and
  credit both 100), upgraded to `d4e5f6a7b8c9`, and verified the rows, role link,
  four legacy columns, five foreign keys, business row counts, financial totals,
  and a non-destructive downgrade. It also verified that `c3d4e5f6a7b8` fills
  blank route-stop/movement snapshots from Places without overwriting manual
  text. The second test simulated a database that had already lost Places and
  confirmed the guard raises instead of continuing.
- Backend image build (`docker build -t lcs-pr35-backend:test backend`)
  succeeded; `docker run --rm lcs-pr35-backend:test alembic heads` reports
  `d4e5f6a7b8c9 (head)`, and the image CMD is Uvicorn only (no startup
  migration).
- Restore drill: `deploy/restore-db.sh` restored a custom-format dump into a new
  isolated database; `SELECT count(*) ...` returned `2` and both codes were
  present. The helper refused an existing target (exit 2) and refused the
  production-named database (exit 2). The disposable source/target databases were
  then dropped.
- Frontend gates were not rerun because no frontend file changed in this
  release-safety change.
- No production database or AWS host was available, so an actual production
  restore and the workflow's host-side rollback were **not** executed.

## 7. Coverage Gaps and Open Risks

| Gap / risk | Impact | Status |
|---|---|---|
| No browser E2E of blur/focus, tab reveal and responsive layout | Startup, the anonymous guard and login validation are covered by `frontend/e2e`; real DOM interaction for the rest is still manual | Partial |
| No authenticated browser journey in CI | `pnpm test:e2e` runs locally against the compose stack; the suite is not a CI gate, so a login or navigation regression can reach `dev` | Open |
| PostgreSQL guard SQL is not in CI | A trigger regression can pass the SQLite suite; this already caused a posting outage once | Open (highest-value CI addition) |
| No unsaved-changes guard on document navigation | A user can lose a dirty form | Open |
| Computed line-table cells cannot show inline errors | Non-editable cells are skipped; the focus target still exists | Accepted |
| Movements/milestones editor has no UI | APIs are tested; the itinerary is unreachable from the UI | Open |
| `customer_customs_accounts` has no API or UI | The table and `customs_credential.retrieve` permission are unused; customer customs fields live on the encrypted customer module record | Open |
| Quotation revision comparison has no side-by-side UI | API supports compare; users cannot see it | Open |
| `vw_general_ledger` is not exposed as an endpoint | The view exists; `ledger-lines` covers the same rows | Queued, low value |
| User deletion fails for audited accounts | `audit_events.actor_user_id` has `NO ACTION`; deactivate until an additive `ON DELETE SET NULL` migration lands | Open |
| No monitoring or alerting | A failed posting, lockout or backup produces no signal | Open |
| Off-host PostgreSQL backup/WAL archiving is only partially automated | Pre-deployment dumps can be uploaded with SSE-KMS, but no WAL/PITR and no scheduled off-host job; Google Sheets is not a database backup | Partial |
| Places migration is verified on disposable PostgreSQL only | No production-size copy or live host rehearsal was available | Manual gate; run the env-gated test and a restore drill before release |
| Reconciliation queries are manual | F6 remains open | Open |
| A private key sits in `docs/lcssystem.pem` | Untracked and gitignored, but inside the working tree; owner decision required | Open (**S1**) |

## 8. Implementation Status Summary

Verified against the current code and focused tests:

| Area | Status |
|---|---|
| Master data, Party Roles, Place Roles, legacy Places retention, route stops, currencies | Implemented and tested |
| Transport Assets: DB-driven identity-type vocabulary filtered by transport type, optional asset name, capacity value + unit as a paired optional value, MAINTENANCE status, business-party owner/operator | Implemented and tested (`test_transport_assets.py`, `frontend/tests/transport-assets.spec.ts`; vocabulary managed at /master-data/asset-identity-types). Capacity units are master data at /master-data/capacity-units; the optional capacity is clearable (blank stays null, not 0). Identity patterns are compile- and nested-quantifier-checked on save; the vocabulary form has a client-side Test Pattern row, while the backend `re` full match stays the authority, a stored pattern that no longer compiles behaves as no pattern so an old row never blocks an asset save, and a vocabulary row renamed or archived after an asset was saved keeps that asset editable |
| Places migration preservation and destructive-revision guard | Implemented; PostgreSQL rehearsal passed on disposable databases |
| Quotations, revisions, accept/convert, service orders, dynamic tabs, Transport Type pricing lines | Implemented and tested |
| Re-quotation from a service order: new draft quotation copied from the order's customer, direction, route, containers and priced lines, linked by `source_service_order_id`; the order is never modified | Implemented and tested (`test_quotations.py::test_requotation_*`, `quotation-actions.spec.ts`) |
| Conversion idempotency: `Idempotency-Key` replay returns the original service order; a concurrent duplicate rolls back to `409 DUPLICATE_CONVERSION`, and a same-key retry returns the original order | Implemented and tested (`test_quotations.py::test_conversion_replays_the_same_idempotency_key`; `test_quotation_postgres.py`: two concurrent conversions → one order and one 409, two same-key retries → one order) |
| Quotation container requirements persist to `quotation_revision_containers` and survive the API round trip | Implemented and tested (`test_quotations.py::test_container_requirements_are_persisted_and_returned`) |
| Conversion prepares one pending `service_order_containers` row per required unit (no fake number), numbering updates the prepared row in place, a payment-referenced container cannot be deleted, and container payments expand per actual container from a pricing line's `containerType` while shipment charges stay single | Implemented and tested (`test_workflows.py::test_conversion_prepares_pending_actual_containers`, `job-containers.spec.ts`, `workspace-tables.spec.ts`). `service_order_containers.container_number` is nullable (`d8f9a0b1c2d3`); the unique constraint still covers real numbers |
| Quotation Overview/Route/Pricing/Files/Revisions: required party/direction, date ordering, active master-data options, role+location route validation, Fee Type/Charge Basis/optional container, authoritative 2dp totals, attachment upload/link, re-quote action | Implemented and tested (`test_quotations.py`, `test_place_roles.py`, `test_attachments.py`, `document-calculations.spec.ts`, `document-form-validation.spec.ts`, `document-tabs.spec.ts`, `quotation-company-field.spec.ts`). Direction-specific *role* requirements are not a stored configuration; the form validates the role and location of every stop. Upload progress is an indeterminate spinner, not a percentage |
| Revision history grid: revision (`R01`), status, grand total, creator, created, actions; newest first; short revision column; read-only with no add row; View opens the revision | Implemented and tested (`quotation-revisions.spec.ts`) |
| Attachment note: a Note column edited directly in the cell, saved on leave through `PATCH /attachments/{id}` (max 1000 characters, `attachment.upload`); no note input in the tab header | Implemented and tested (`test_attachments.py` (8), `attachment-note.spec.ts`); Alembic `e9a0b1c2d3e4` |
| Per-line discount and tax: **Additional Details** in the row menu of quotation pricing, container payments, service charges and fee lines; server derives the tax from the rate, and sheet totals switch to line sums when a line carries an adjustment | Implemented and tested (`line-details.spec.ts`, `test_quotations.py::test_a_line_tax_rate_derives_the_quotation_tax_and_is_validated`, existing charge tax round trip) |
| Fee-line printing: one fee line by stable id, whole charge, and the order-wide combined statement; drafts keep the watermark and never become an issued invoice | Implemented and tested (`charge-print.spec.ts` (5)); printing is read-only |
| Service Order Finance tab: manual entries only (financial documents linked by `serviceOrderId`), six entry types, posting-rule warning, draft edit/post/reverse/delete and receipt/payment allocation through the existing finance services; no charge/estimate import | Implemented and tested (`test_job_finance_entries.py` (4), `finance-tab.spec.ts`); backend validation covers order/party/lines/positive total |
| Shared Excel Import & Export engine (Phase A/B: Master Data): backend-driven templates, upload validate + preview (per-row/column errors, workbook duplicates, references, business rules), durable single-use session in PostgreSQL bound to user/checksum/mode/expiry, atomic commit with revalidation, XLSX error report, authorized export, `import_jobs` history | Implemented and tested (`test_excel_import_export.py` (35), `tests/excel-io.spec.ts` (7)). PostgreSQL transactions, constraints and the migration chain verified on an isolated PostgreSQL 16 database with `scripts/verify_excel_postgres.py` (2026-10-24). Archive expansion is capped by uncompressed size and entry count, and the Data sheet is streamed, so a crafted workbook cannot exhaust the 4 GB server. Browser journey verified on the compose stack (2026-10-24): template download, validate/preview, commit, list refresh, export download, invalid-workbook field errors with no toast, discard confirmation |
| Component attribute catalog: explicit unique code, all supported data types (including `integer`), static/dynamic select sources, validation rules, catalog reorder, published-snapshot delete guard | Implemented and tested (`test_component_attributes.py`, `frontend/tests/component-attribute-{inline,validation}.spec.ts`, `component-config-tables.spec.ts`). Catalog reorder is not yet exposed as a keyboard-only alternative to the move buttons |
| Service charges, finance invoice draft, financial documents, posting rules | Implemented and tested |
| Double-entry posting, reversals, periods, allocation, multi-currency | Implemented and tested |
| RBAC, one active role, protected administrator, audit | Implemented and tested |
| Stable PostgreSQL sessions, opaque refresh rotation/history, idle and absolute limits, immediate access revocation, silent frontend renewal | Implemented; focused API, PostgreSQL and browser verification recorded below. Production HTTPS deployment remains unverified |
| Archive, attachments, record status, validation, success-only toasts | Implemented and tested |
| Financial and operational reports (server-side) | Implemented and tested |
| Google Sheets backup scheduler | Implemented and tested |
| Off-host PostgreSQL backup/WAL | Partial (optional pre-deployment S3 SSE-KMS upload; no WAL/PITR) |
| Monitoring/alerting | Missing |
| Movements/milestones UI, quotation comparison UI | Missing |
| Browser E2E | Partial: normal `frontend/e2e` smoke coverage stays read-only. `auth-renewal.spec.ts` additionally writes only to an explicitly opted-in disposable stack (`LCS_AUTH_E2E_ISOLATED=1`); these journeys are not a CI gate |
| CI PostgreSQL guard run | Missing |

### Authentication renewal verification — 2026-10-24

Root causes were per-rotation session rows, access JWTs without a session ID,
navigation clearing auth before renewal, refresh network failures treated as
logout, and refresh credentials returned to JavaScript/storage. The upgrade
reuses the auth module, settings policy and existing cookies/RBAC. API changes
are confined to login/refresh metadata, cookie-only refresh, session-aware
logout/protected-request validation and the expected-account header; no new
authentication endpoint or permission is introduced.

Changed implementation files: `backend/app/core/{config,security,deps,exceptions,bootstrap}.py`,
`backend/app/main.py`, `backend/app/modules/auth/{models,schemas,service,router}.py`,
`backend/app/modules/settings/service.py`, `backend/scripts/schema_descriptions.py`,
the additive `24ac57ef90bd_stable_auth_sessions.py` migration and the unpublished
import-jobs revision identity; `frontend/app/stores/auth.ts`,
`composables/useApi.ts`, `composables/auth/useAuth.ts`, `middleware/auth.global.ts`,
`utils/auth/renewal.ts`, `components/common/AppSessionStatus.vue`, `app.vue`,
security settings schema/types/form rules, all three locale bundles, and the
development/production compose environment defaults. Existing unrelated edits
were retained. The schema reference was regenerated.

Observed verification (commands run from their owning toolchain directory):

- `uv run pytest tests/test_auth_sessions.py tests/test_auth_remember_me.py -q --disable-warnings`:
  **26 passed**, including one-minute idle activity, legacy production-cookie
  exchange, account mismatch refusal, issuer/audience, expiry, CSRF, disable,
  logout and background refresh not extending idle time.
- `uv run pytest tests/test_auth_sessions.py tests/test_auth_remember_me.py tests/test_security_hardening.py tests/test_access_enforcement.py tests/test_password_reset.py tests/test_migration_chain.py tests/test_schema_docs.py tests/test_frontend_api_contract.py -q`:
  **83 passed** during implementation; later auth-specific cases are in the
  26-test run above.
- `uv run pytest tests/test_redis_integration.py tests/test_auth_sessions.py -q --disable-warnings`:
  **27 passed, 1 skipped**. The initial full run exposed three query-budget
  regressions; a joined user/session lookup fixed them without relaxing tests.
- With `LCS_AUTH_TEST_DATABASE_URL` naming the disposable PostgreSQL instance,
  `uv run pytest tests/test_auth_postgres.py -q --disable-warnings`: **1 passed**.
  Proves one refresh winner/one overlap rejection, later replay revocation,
  migrated auth column/type/nullability agreement, downgrade/re-upgrade,
  activity backfill, and unchanged existing-table counts.
- `uv run alembic upgrade head` applied the whole chain on empty disposable
  PostgreSQL. A `pg_dump --format=custom` / `pg_restore --exit-on-error` drill
  restored 71 tables; business, user and permission row counts matched. Test
  sessions/audit rows changed concurrently and were accounted for separately.
- `pnpm vitest run tests/auth-api.spec.ts tests/auth-renewal.spec.ts`: **17 passed**,
  including single flight, retry once, short-token scheduling, unattended tabs,
  delayed logout, temporary failures, CSRF/permission refusals, body replay
  safety, and blocking unverified shared-cookie identities.
- `pnpm lint`, `pnpm typecheck`, `pnpm i18n:check`, and `uv run ruff check .`:
  passed after fixes. Temporary unrelated Excel-import lint/type errors from
  concurrent work were resolved by that work before the final gate run.
- `uv run pytest -q --disable-warnings`: **606 passed, 4 skipped**. Optional
  PostgreSQL/externally configured cases are skipped by the default harness;
  the auth PostgreSQL case was separately executed above. The latest added
  account-header denial is additionally covered by the 26-test focused run.
- `pnpm test`: **681 passed in 88 files**. An attempted `--reporter=basic`
  invocation failed before collection because this Vitest version has no such
  reporter; the standard command subsequently passed.
- `uv run python scripts/generate_schema_docs.py --check --strict`: **passed**,
  70 model tables documented (including concurrent module additions).

The isolated browser journey has verified an unsaved Service Order remark,
expired access JWT, one silent refresh, successful save, reload restoration and
sibling-tab logout without losing the open draft. Additional browser checks
exercise a held concurrent rotation, delayed refresh/logout, identity-check
failure/recovery, deferred identity/logout settlement, and real PostgreSQL idle
expiry refusing Save while keeping the draft. Run from `frontend/`:
`pnpm exec playwright test e2e/auth-renewal.spec.ts --workers=1 --reporter=list`
with `LCS_AUTH_E2E_ISOLATED=1`, `E2E_BASE_URL=http://localhost:3001`,
`LCS_AUTH_E2E_API=http://localhost:8008`, `LCS_AUTH_E2E_DATABASE_URL` pointing
to the local disposable database, and `LCS_AUTH_E2E_EXPIRED_ACCESS` holding a
signed expired access JWT from that same isolated backend. The API used
`AUTH_RETURN_TOKENS=false`, as production does. Initial browser failures from
an old server process retaining the earlier CORS header list were resolved by
restarting that isolated API; business-page code was unchanged.
The final command result was **4 passed (32.5 seconds)**, including the deferred
identity response arriving after sibling logout. The temporary servers and
disposable PostgreSQL container were removed after verification.

Final review: no blocking issues after fixing short-token wake scheduling,
fail-closed identity checks, stale identity/logout cleanup, cross-account
permission refresh, and the immediate local logout lock.
HTTPS proxy cookie delivery, production deployment and a
production-data restore rehearsal remain release checks; none was performed
against the live installation.

## 9. Reporting a Test Result

Report the exact command, the directory it ran from, and the observed result. A
focused pass is not a full-suite pass; say which one was run. A skipped or
weakened test is a failure of the definition of done, not a workaround. If a
PostgreSQL-only check was not run, say so explicitly.
