# Solution Architecture

## 1. Architecture Decision

The platform is a **modular monolith**: one FastAPI application with clearly
separated modules, a statically generated Nuxt SPA served by nginx, and the
datastores. There is no separate background worker; the only background job is
an in-process asyncio scheduler for the optional Google Sheets backup.

```text
Nuxt 4 Static SPA (nuxt generate) ── served by nginx
          │  /api/ reverse proxy (same origin)
          ▼
FastAPI application  (async SQLAlchemy 2.x)
 ├── auth         users, credentials, sessions, roles, permissions, first-run setup
 ├── master_data  reference data + generic module records + SO tab config
 ├── quotations   quotations, revisions, children, conversion
 ├── operations   service orders, containers, components, charges, attachments
 ├── finance      CoA, financial accounts, periods, sequences, posting, journals
 ├── reports      read-only dashboard and report endpoints
 ├── settings     app info/config, global search, reset-data
 ├── backup       Google Sheets mirror + scheduler
 └── audit        audit event log
          │
          ├── PostgreSQL  (asyncpg; source of truth)
          ├── Redis       (optional; disables gracefully)
          └── Object storage (local filesystem or MinIO / S3)
```

Organizations and branches were removed from the design; the runtime is
single-tenant and access is governed entirely by users, roles and permissions.

## 2. Bounded Contexts (backend modules)

Each context is a folder under `backend/app/modules/<name>/` with `router.py`,
`service.py`, and (where it owns tables) `models.py`.

### Identity and authorization — `auth`

Owns users, credentials, sessions, roles, permissions, role assignments,
password-reset tokens, and the login/refresh/logout and profile flows. It also
owns the users/roles/permissions administration endpoints. It does not own
business records.

### Reference data — `master_data`

Owns places, trade directions, container types, transport types, transport
assets, fee types, business parties, customer customs accounts, the reusable
component attribute/group catalogue, component tabs (each bound to one trade
direction), and the generic `module_records` JSON store. Component
configuration is served by `component_config.py`; service-order tab rendering by
`component_tabs.py`.

### Quotations — `quotations`

Owns quotation aggregates, immutable revisions, revision places/containers/lines,
and the quotation→service-order conversion ledger. Lifecycle:
`DRAFT → SENT → ACCEPTED → CONVERTED`.

### Operations — `operations`

Owns service orders, their places, container requirements, actual containers,
pricing snapshots, dynamic component rows, movements, milestones, service
charges and charge lines, and attachment metadata. Configurable tab rendering
and row persistence are served by `component_tabs.py`.

### Finance — `finance`

Owns the chart of accounts, financial accounts, accounting periods, document
sequences, posting rules, reusable financial documents (invoices, bills,
receipts, payments, income, expenses, transfers, adjustments), allocation,
journals, and the double-entry posting/reversal engine.

### Reporting — `reports`

Read-only dashboard and report endpoints (service orders, quotation performance,
receivables, payables, income, expenses, profitability, financial summary). It
owns no tables.

### Settings — `settings`

Owns app info (branding) and app config (general/localization/email/telegram/
notifications/security/system/backup), stored as `module_records`. Also provides
global search / Ask, email and Telegram test endpoints, and reset-data. It owns no
tables.

### First-run setup (in `auth`)

Served by the `auth` module: the public `/api/v1/auth/setup/status` and
`/api/v1/auth/setup/initialize` endpoints. Setup is accepted only while no user
exists.

### Backup — `backup`

Owns the Google Sheets append-only mirror, its run/log/record tables, and the
in-process scheduler toggled by `BACKUP_SCHEDULER_ENABLED`.

### Audit — `audit`

Owns the append-only audit event log and its read endpoint. High-risk actions
(financial post/reverse/allocate, period close, journal post) write events;
quotation and service-order mutations are not audited.

## 3. Dependency Rules

Allowed dependency direction:

```text
API layer (router.py)
   ↓
Application services (service.py)
   ↓
Module repository/query component (repository.py)
   ↓
Models / async SQLAlchemy session
   ↓
PostgreSQL
```

Rules:

- Cross-module work goes through application services, not direct table access.
- Repositories own query construction, persistence lookups, filtering, sorting,
  pagination, and aggregate loading. They never authorize requests or commit a
  multi-step workflow.
- Services own business rules and transaction boundaries. One service call may
  compose multiple repositories over the same `AsyncSession`.
- Finance consumes an issued service-charge snapshot automatically and creates one idempotent draft customer invoice. The explicit conversion endpoint retrieves or repairs that draft; ledger posting remains a separate authorized command.
- Reporting reads read-only queries.
- Authorization (`get_current_context`, `require_permission`) runs before
  repository access.
- No UI rule is treated as a security rule.

## 4. Repository Structure (actual)

```text
backend/
  app/
    main.py               FastAPI app, lifespan, exception handlers, middleware
    create_admin.py       headless provisioning CLI
    api/v1/router.py      aggregates all module routers under /api/v1
    core/
      bootstrap.py        provisioning + full data reset
      config.py           pydantic-settings
      context.py          request context
      crypto.py           Fernet field encryption (retrievable secrets)
      database.py         engine, session, Base, mixins, naming convention
      deps.py             auth/permission dependencies
      exceptions.py       domain error hierarchy
      pagination.py       page params + envelope helpers
      permissions.py      permission catalog + role definitions
      redis.py            lazy Redis + safe_* helpers
      security.py         Argon2 hashing, JWT, reset codes
      sequences.py        document-number allocation
      serialization.py    camel/snake + model serialization
      storage.py          LocalStorage / S3Storage
      types.py            JSONType (JSONB on PostgreSQL)
    modules/
      audit/ auth/ backup/ finance/ master_data/ operations/
      quotations/ reports/ settings/
  alembic/versions/       versioned migrations (schema source of truth)
  tests/                  pytest (in-memory SQLite)
frontend/
  app/
    pages/                file-based routes (see §16)
    components/           common, configuration, dashboard, document,
                          freight, layout, print, settings, table
    composables/          auth, common, freight, layout, lcs, print, search,
                          settings + useApi/usePageSeo/...
    config/               freight-modules, lcs-reference-modules,
                          settings-schemas, freight-options, freight-reports,
                          job-workspace-forms, print-templates
    repositories/         contracts/ + http/ + index.ts factories
    stores/               auth, freight, preferences (Pinia)
    utils/                api, auth, constants, export, filter, format,
                          freight, layout, lcs, role, search, security,
                          storage, table, text
    middleware/           auth.global.ts, report-area-auth.ts
    layouts/              default.vue, auth.vue, print.vue
    plugins/              01.auth-hydrate.client.ts
  i18n/locales/           en.json, km.json
infrastructure/
  docker-compose.yml      local stack
  nginx/                  default.conf (SPA + /api proxy), production.conf
deploy/
  compose.yml             production runtime bundle copied to /opt/lcs
docs/                     this documentation set
```

## 5. Backend Module Anatomy

Most modules follow this shape:

```text
modules/<name>/
  router.py     FastAPI routes + permission dependencies
  service.py    business rules, workflow and transaction coordination
  repository.py SQLAlchemy queries and aggregate persistence (DB-heavy modules)
  models.py     SQLAlchemy models (only modules that own tables)
  schemas.py    Pydantic bodies (currently only auth)
  <name>_tabs.py  dynamic tab/column helpers (master_data, operations)
```

Repositories are implemented for `auth`, `master_data`, `quotations`,
`operations`, and `finance`. Backup history has a dedicated read repository.
Reports remain a dedicated read/query service because they are projections,
not aggregate persistence; archive and audit keep their append/archive services
until their query surface grows enough to justify another layer.

## 6. Request Flow

```text
HTTP request
  → optional Redis-backed rate limiting / helpers
  → authentication (JWT bearer or HttpOnly cookie)
  → permission dependency (require_permission / guard)
  → request validation
  → application service
  → module repository/query component
  → async SQLAlchemy transaction
  → audit event (high-risk actions only)
  → {"data": ...} envelope (or {code, message, request_id, field_errors})
```

## 7. API Conventions

- Base path `/api/v1`; routers are aggregated in `app/api/v1/router.py`.
- Success payloads are wrapped as `{"data": ...}`. List endpoints return
  `{"data": {"items": [...], "meta": {page, page_size, total}}}`.
- Errors return `{code, message, request_id, field_errors}`.
- Auth tokens are sent as `Authorization: Bearer` or HttpOnly cookies; a CSRF
  cookie/header pair is used for cookie-authenticated mutations.
- The endpoint permission catalog (`app/core/permissions.py`) is documented in
  `docs/11_permissions_matrix.md`; the counts live there.
- Several finance paths register both kebab-case and camelCase aliases to the
  same handler.
- Master-data reference collections are registered dynamically from
  `service.SPECS`; generic collections resolve to `module_records`
  (`service.GENERIC_COLLECTIONS`). Component configuration (attributes, groups,
  tabs) uses dedicated `/component-*` endpoints:
  - relational: businessParties, places, tradeDirections, containerTypes,
    transportTypes, transportAssets, feeTypes
  - generic (`module_records`): companies, shipments, customs, documents,
    deliveries, customerPayments, supplierCosts, supplierPayments, currencies

## 8. Transaction Boundaries

One database transaction is used for:

- quotation conversion;
- revision creation where children are copied;
- service-charge-to-invoice conversion;
- financial-document posting;
- manual journal posting;
- payment allocation;
- reversal;
- period closure;
- document-number allocation.

The request dependency creates one `AsyncSession`; repositories do not create
sessions and do not commit. Services commit after all invariant checks and
mutations succeed. `get_session` rolls back any uncaught exception. Redis cache
generation bumps happen only after successful commits, and PostgreSQL remains
authoritative.

Bounded-query loaders replace list N+1 patterns for users/roles,
roles/permissions, quotation/latest-revision, financial documents/lines, and
financial accounts/balances. `tests/test_repository_queries.py` measures both
the previous per-row query shape and the bounded repository query count.

## 9. Finance Posting Architecture

```text
Financial document
        │
        ▼
post_document  (transaction owner)
        ├── validate document state
        ├── reject an existing posting link      → DUPLICATE_POSTING
        ├── resolve period; refuse if CLOSED     → PERIOD_CLOSED
        │
        ├─ PostingRuleResolver ─────── "which accounts?"
        │      ├── most specific tier: document type + fee type
        │      ├── document default:   document type, fee type IS NULL
        │      └── within a tier: highest priority wins
        │
        ├─ AccountingPostingService ── "what journal?"
        │      ├── per document type, a named strategy in STRATEGIES
        │      └── returns a balanced JournalDraft or raises
        │
        ├── persist journal + lines + posting link + status atomically
        └── history is immutable from here: reverse_document, never edit
```

The journal is the source of truth for posted accounting balances. Financial
documents are source/business records.

### 9.1 The two units, and why they are separate

`PostingRuleResolver` (`app/modules/finance/posting_rules.py`) answers *which
accounts* and nothing else. `AccountingPostingService`
(`app/modules/finance/posting.py`) answers *what journal* and delegates every
account question back to the resolver. Keeping them apart is what lets a new
document type reuse account resolution without inheriting the customer-invoice
line logic, and what makes rule selection testable without a posting flow around
it.

No account id appears in either file. Every account comes from a `posting_rules`
row, so changing where a document posts is a data change an administrator makes.

### 9.2 Rule selection

Resolution walks two tiers, most specific first, and takes the highest `priority`
within the tier:

1. `document_type` **and** `fee_type_id` — a rule narrowed to one fee type;
2. `document_type` with `fee_type_id IS NULL` — the document default.

A partial unique index over
`(document_type, COALESCE(fee_type_id, 0), priority)` for `status = 'ACTIVE'`
makes "one active rule per scope *and* priority" a database guarantee, so a
concurrent pair of writes leaves one winner rather than two. Two active rules
sharing a priority are an `AMBIGUOUS_POSTING_RULE` conflict in the resolver —
never an arbitrary winner — which covers a database restored without its indexes.

With no rule at all, `DEFAULT_ACCOUNTS` in `finance/service.py` is a last-resort
fallback for an install that has not configured rules yet. The resolved
`PostingRuleAccounts.source` (`EXACT`, `DOCUMENT_DEFAULT`, `LEGACY_DEFAULT`)
records which path was taken, and a document type with neither a rule nor a
fallback is refused with a field-level error rather than guessed.

### 9.3 Journal shapes per document type

The accounting meaning of each type is one table, `STRATEGIES` in `posting.py`:

| Document type | Control side | Detail side |
|---|---|---|
| `CUSTOMER_INVOICE` | Dr receivable | Cr revenue per fee line, tax to the rule's tax account |
| `CREDIT_NOTE` | Cr receivable | Dr revenue per fee line — mirrors its invoice |
| `SUPPLIER_BILL` | Cr payable | Dr expense per fee line, tax to the rule's tax account |
| `SUPPLIER_CREDIT_NOTE` | Dr payable | Cr expense per fee line — mirrors its bill |
| `CUSTOMER_RECEIPT` / `SUPPLIER_PAYMENT` | Dr cash / Dr payable | Cr receivable / Cr cash, two lines |
| `OTHER_INCOME`, `OTHER_EXPENSE`, `TRANSFER`, `ADJUSTMENT` | the rule's debit and credit account | two lines |

A line may override the rule with an account chosen on the document itself, which
is how a one-off revenue or expense is booked without a dedicated rule.

### 9.4 What the ledger guarantees

A `JournalDraft` is only produced when debits equal credits, so the caller never
receives a half-built entry to commit; `post_document` re-checks before persisting.
The database enforces the rest independently of the service: posted journals and
their lines are immutable (`fn_guard_journal_entry`, `fn_guard_journal_line`),
entries must fall inside an `OPEN` period (`fn_validate_journal_post`), and one
document may have only one posting link. A rule change never rewrites posted
history — the journal carries its own account ids, amounts **and the rule that
resolved them** (`journal_entries.posting_rule_id`), so a correction is a
reversal.

One ordering detail is load-bearing: the lines are flushed while the journal
header is still `DRAFT`, and only then is the header promoted to `POSTED`.
`fn_guard_journal_line` is an immediate trigger, and SQLAlchemy emits a mapper's
pending UPDATE before another mapper's pending INSERT when both are queued
together — so promoting the status in the same flush as the line inserts makes
the trigger observe `POSTED` and reject every posting on PostgreSQL. The SQLite
test database has no triggers and would not catch it;
`tests/test_posting_rules.py::test_lines_are_written_before_the_journal_is_marked_posted`
pins the ordering, and `integrity_guards.sql` remains the manual check.

### 9.5 Audit attribution

A journal entry keeps the `posting_rule_id` it was posted under, and a reversal
carries its originating entry's rule, so the rule a posting came from is always
recoverable from `journal_entries`; `audit_events` is excluded from the deletion
reference scan, so the history of a rule outlives the rule.

Deleting a rule that posted something is refused, because the foreign key from
`journal_entries` would otherwise lose the attribution. The rule is deactivated
instead, which is what superseding a rule means everywhere else in the system.

The rule History tab, the standalone Posting Rule History screen and their
endpoints (`/posting-rules/history`, `/posting-rules/{id}/history`,
`/posting-rules/{id}/usage`) were removed by owner request —
`docs/18_implementation_checklist.md` §6 records that and says not to re-add the
screens.

### 9.6 Multi-currency

One base currency per installation (System Settings → Localization → Currency),
one stored rate per document, and one implementation of the conversion:

- **The base currency is the company currency.** Organizations and branches were
  removed from the product, so the installation *is* the company: the localization
  `currency` setting, read through `get_default_currency()`, is seeded onto every
  new document as `baseCurrency`.
- **The rate store** is `currency_rates`: a row reads "1 FROM = rate TO", is
  versioned by `effective_date`, and only an APPROVED row is ever applied. It is
  maintained through the `currencyRates` master-data API (`/api/v1/currencyRates`)
  and deliberately has no sidebar page.
  `master_data/currency_rates.py` resolves the newest approved row for the pair —
  in either direction, inverting it when only the inverse exists — and reports
  `None` rather than 1 when nothing covers the pair.
- **A document snapshots its own rate.** `financial_documents.exchange_rate` means
  "base units per one document unit", so `base = amount * exchange_rate`, which is
  the arithmetic every posting already used. A document already in the base
  currency always stores 1, whatever a client sends; another currency must resolve
  a rate from the store or take the operator's, and a missing, zero, negative,
  non-finite or absurd rate is refused at the API boundary (`app/core/fx.py`).
- **The converted amounts are stored** (`base_subtotal_amount`,
  `base_discount_amount`, `base_tax_amount`, `base_total_amount`), rounded with the
  document currency's own precision (`currencies.decimal_places`, so KHR and JPY
  are not given cents), and re-derived when the document posts — the document and
  the journal it writes cannot disagree. `journal_entry_lines` keeps its own
  `exchange_rate` and `base_debit_amount`/`base_credit_amount`, which is what makes
  a posted amount explainable after the rate store changes. Posted documents cannot
  be edited at all, so a later rate never reaches one.
- **Journals balance twice.** `fn_validate_journal_post` compares the own-currency
  sums, so a journal's lines must agree in their own amounts; the service
  additionally requires the base amounts to balance, which the trigger cannot see.
  A journal is therefore effectively single-currency by design, and a document in
  another currency posts one journal through its own rate.
- **An allocation values each side at its own rate.** `allocate_payment` reports
  `paymentBaseAmount`, `targetBaseAmount` and the `exchangeDifference` between
  them — the exchange gain or loss a settlement realises — and the same figures are
  visible from either document. Posting that difference through a configured
  account pair is not wired yet; the checklist carries it.
- **An invoice generated from a charge** keeps the charge's currency, resolves its
  own approved rate at its own date, and never rewrites the source charge.

## 10. Events and Background Jobs

The application is synchronous: no outbox table and no external worker. The
optional Google Sheets backup runs from an in-process asyncio scheduler
(`BACKUP_SCHEDULER_ENABLED`, tick `BACKUP_SCHEDULER_TICK_SECONDS`). Records are
stored locally first and retried if a Google API write fails.

A future release may add an outbox and workers for document rendering,
email/Telegram notifications, OCR, external customs integration, report refresh,
and antivirus processing. Asynchronous jobs must not be used for operations that
require immediate transactional consistency (posting, allocation).

## 11. Storage Architecture

PostgreSQL stores metadata and business references; object storage stores file
contents. Provider is `STORAGE_PROVIDER` (`local` default, or `s3`); S3 works
with MinIO (`S3_ENDPOINT_URL`, public endpoint `S3_PUBLIC_ENDPOINT_URL`) or AWS.

Upload flow:

1. Authorize attachment creation (`attachment.upload`).
2. Optionally request a pre-signed upload URL (`POST /attachments/presign`).
3. Client uploads the file.
4. API verifies completion, size, MIME type, and checksum.
5. Attachment metadata and links are recorded.
6. Downloads stream through `GET /attachments/file/{storage_key}` (or a
   same-origin presigned URL) and are permission-checked.

## 12. Security Architecture

- TLS for all external traffic (nginx + certbot).
- Argon2id password hashing.
- JWT access token (default 24h) + rotating refresh token (default 30 days).
- Fernet encryption for retrievable secrets (customs passwords); sensitive
  columns are excluded from the backup mirror.
- RBAC enforced at API boundaries; the UI never substitutes for API checks.
- No secrets in logs, responses, seed data, or audit payloads.
- **Passwords are one-way hashed and can never be read back.** `user_credentials`
  stores an Argon2id digest; there is no plaintext and no reversible encryption,
  so no screen can offer a "show password". An administrator who sets a password
  on another account (`POST /users/{id}/password`, gated on `user.manage`) gets no
  access to it either — the request is hashed on arrival and the response carries
  only the account.
- **A password an administrator set must be replaced before anything else.**
  Setting one flags `user_credentials.must_change_password`, revokes every session
  and puts a `pwd` claim on the next access token. `get_current_context` then
  answers `403 ACCESS_DENIED` for every route except
  `auth/change-password`, `auth/logout`, `auth/refresh` and `auth/me` — so
  refreshing is not an escape. `change_password` clears the flag, and the SPA
  routes the session to `/auth/change-password` meanwhile.

## 13. Database and Consistency

- PostgreSQL is the transactional source of truth.
- Migrations are versioned and reviewed (`backend/alembic/versions/`).
- Number allocation uses row locks (`with_for_update`) plus unique constraints.
- Positive/negative invariants not expressible as constraints are enforced in
  services (e.g., journal balance before posting).
- 63 tables; see `docs/06_database_design.sql` for the raw DDL, the annotated
  companion `docs/06b_database_design_annotated.sql`, and
  `docs/07_entity_relationship_diagram.mmd` for the relationships.
  `docs/14_47_table_migration_analysis.md` records how the schema maps to the
  47-table reference proposal and which of its tables were deliberately not
  adopted. PostgreSQL integrity triggers and reporting views are installed by
  `alembic/versions/e6f7a8b9c0d1_reporting_views_and_integrity.py`; they are not
  part of the SQLAlchemy models, so they do not appear in the files above.

## 14. Reporting

Reports are served by the backend `/reports/*` API (dashboard, receivables,
payables, income, expenses, profitability, financial summary) and the
frontend report catalogue (`FREIGHT_REPORTS`, 12 reports). Accounting reports read
posted journal lines only.

## 15. Deployment Environments

```text
local → dev → main (production)
```

- `dev` is the integration branch (validated by Dev CI, never deploys).
- `main` is protected; merging triggers `production.yml`, which builds immutable
  `sha-<short>` images, pushes to GHCR, backs up PostgreSQL, and recreates the
  stack on the EC2 runtime host.
- Each environment has separate database, object-storage bucket, secrets, and
  integration credentials. See `docs/12_deployment_runbook.md`.

## 16. Frontend Architecture

Nuxt 4 with `ssr: false`, generated with `nuxt generate` and served by nginx;
nginx reverse-proxies `/api/` so the browser is same-origin. UI is `@nuxt/ui`
with Tailwind; state is Pinia; i18n is `@nuxtjs/i18n` with `en` and `km`.

### Pages (routes)

- Auth/setup (public): `/auth/setup`, `/auth/login`, `/auth/forget-password`,
  `/auth/verify-code`, `/auth/reset-password`.
- Dashboard: `/`.
- Sales/operations/finance: `/quotations`, `/service-orders`,
  `/service-charges`, `/finance/documents`, `/finance/chart-of-accounts`,
  `/finance/financial-accounts`, `/finance/journals`,
  `/finance/accounting-periods`.
- Master data: `/master-data/{business-parties,places,trade-directions,
  container-types,transport-types,transport-assets,fee-types}`.
- Configuration: `/configuration/{component-attributes,component-groups,
  component-tabs}`.
- Administration: `/administration/{users,roles,document-sequences,audit-logs,
  system-settings}`.
- Reports: `/reports`, `/reports/:slug`, `/reports/:area/:slug`.
- Print: `/print/:collection/:id` (print layout, no app chrome).

Most list/detail routes reuse two generic views: `FreightWorkspaceView`
(`components/freight/WorkspaceView.vue`) and `FreightModulePage`
(`components/freight/ModulePage.vue` → `DocumentView.vue`), driven by the
`freight-modules` metadata catalogue.

### State and data access

- Pinia stores: `auth` (session, permission checks), `freight` (module cache and
  remote persistence), `preferences` (theme, locale, font size).
- Repositories under `app/repositories/` (`contracts/` + `http/` + `index.ts`
  factories) are the only HTTP layer; all module endpoints are registered in
  `app/utils/api/freight-remote.ts` (`REMOTE_ENDPOINTS`).
- `useApi()` is the central fetch client (auth, CSRF, query compaction, 401
  refresh-and-retry, error toasts).

### Configuration-driven forms and tables

- `app/config/freight-modules.ts` and `lcs-reference-modules.ts` describe every
  module (columns, fields, filters, tables, actions).
- `app/utils/freight/document-tabs.ts` compiles module metadata into the
  `AppDocumentForm` tab/section/field schema rendered by
  `AppDynamicFieldRenderer.vue`.
- A field or a tab may declare what it applies to: `FreightField.documentTypes`
  and `documentTypes`/`statuses` on the compiled tab.
  `moduleDocumentTabs(module, { documentType, status })` drops everything else, so
  the financial-document form shows payment method, financial account and value
  date only on a receipt or payment, a due date only on an invoice or bill, and the
  journal tab only once the document is posted. The constraint is metadata; no
  screen hides a field by hand, and an unknown type or status leaves the form
  untouched rather than empty.
- The same fields are enforced on write: the finance service reads a settlement
  field only for the document types that carry one, so a stale client value cannot
  land on a document it does not belong to.
- Service-order dynamic tabs are configured in the database and surfaced through
  `useComponentTabs` / `AppComponentTabs.vue`, filtered by the order's trade
  direction and pinned to the published configuration version the order was
  captured under.

### Record status

- Status is never an editable form field: `moduleDocumentTabs` strips it from every
  compiled form, and a create still seeds the module default
  (`defaultStatusForModule` / `emptyFreightRecord`) so a new record always starts
  with a valid status.
- The list keeps the Status column with its colour-coded badge, and every change
  is offered from the row's (or record's) "..." menu under **Change Status**:
  `useRecordStatus()` fetches the backend policy, renders only the transitions
  that are legal from the record's current status *and* permitted for this
  caller, asks for confirmation (and a reason for a reversal), runs the change
  and reports the outcome.
- Plain transitions (activate / deactivate / mark / reopen) go through
  `POST /{collection}/{id}/status`; workflow transitions run the endpoint that
  owns them (`utils/freight/status-commands.ts`), so posting, reversal, issuing a
  charge, closing a period and the quotation workflow stay inside their engines.
  A policy `command` transition without a runner is hidden rather than run — the
  pair is pinned by `backend/tests/test_record_status.py`.
- A refusal (closed period, invalid state, missing permission) lands on the page
  or form-level message, never a toast; only a confirmed change toasts.

### Form validation and error presentation

One shared pipeline covers every form; no page implements its own.

- `app/utils/validation/` holds the leaf, framework-free core:
  `field-rules.ts` (rules → `{ code, params }` issues), `record-validation.ts`
  (document fields, repeatable rows and flat drafts), `component-rules.ts`
  (database-driven Service Order attributes, including the admin-managed
  `validationRules` blob), `error-paths.ts` (canonical camelCase model paths
  and `table.<row>.<column>` cell keys), `api-error.ts` (one normaliser for the
  FastAPI envelope, a raw Pydantic `detail` array and an `LcsDomainError`),
  `messages.ts` (`validation.*` copy) and `focus.ts` (first-invalid-field
  navigation).
- `useFormValidation()` (`app/composables/common/`) owns the three error buckets
  — field, row cell and form level — plus submission state, error clearing and
  the reveal/focus contract. A form supplies only its field order, its label
  resolver and a way to open the section that owns a key.
- Every addressable input carries `data-field-key` with its canonical model
  path. That attribute is what `focus.ts` scrolls to and focuses after asking
  the host to reveal the owning tab, section, accordion or dynamic group.
- `UFormField :error` supplies `aria-invalid` / `aria-describedby` and renders
  the message under the control; `AppFormErrorSummary` lists everything that
  failed, including fields inside hidden tabs. Pass the message or `undefined`
  for a clean field — **never `''`**: the prop is `[Boolean, String]`, and Vue
  casts an empty string to `true`, which reds out and marks invalid a field that
  has no error. Use the normalisers in
  `app/utils/validation/form-field-error.ts` (`formFieldError` for an error map,
  `fieldErrorMessage` for a lone message).
- Policy: **validation errors and business-rule refusals are never toasts.**
  Success is announced only after the backend confirms. Business-rule refusals
  with no input to own them become a persistent page- or form-level message.

### Layout and navigation

- `layouts/default.vue` mounts the sidebar (`useMenu`), header
  (`LayoutAppHeader` + `LayoutAppHeaderPageActions`) and the global search
  dashboard.
- `middleware/auth.global.ts` enforces session, setup state, and page
  permissions; `report-area-auth.ts` guards report areas.

## 17. Observability

Log request ID, correlation ID, user ID where safe, module/operation, duration,
and result/error code. Measure API latency and error rates, authorization
denials, posting failures, database connections, storage failures, and backup
success.

## 18. Future Extraction Criteria

Extract a module into a service only when at least one is true: independent
scaling is required; separate team ownership is established; external
integration isolation is necessary; deployment cadence creates operational risk;
data ownership can be made explicit; distributed transaction complexity is
acceptable.

## Appendix A — Backend module reference

Generated from the live FastAPI routers and SQLAlchemy models. Paths are relative to the `/api/v1` prefix. Dynamic reference/generic collections are registered from `master_data/service.py`; their guard accepts the codes shown.

### A.1 First-run setup (served by `auth`)

Service functions: `setup_initialize`, `setup_status`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| POST | `/auth/setup/initialize` | `setup_initialize` | public |
| GET | `/auth/setup/status` | `setup_status` | public |

### A.2 Identity and authorization (`auth`)

Tables: `users`, `user_credentials`, `user_sessions`, `roles`, `permissions`, `role_permissions`, `user_role_assignments`, `password_reset_tokens`

Service functions: `assign_role`, `authenticate`, `build_auth_user`, `build_context`, `change_password`, `clear_user_avatar`, `create_role`, `create_session`, `create_user`, `delete_roles`, `delete_users`, `expand_source_permissions`, `get_role`, `get_user_avatar`, `get_user_by_login`, `list_role_assignments`, `list_roles`, `list_users`, `request_password_reset`, `reset_password`, `resolve_page_keys`, `resolve_permissions`, `revoke_session`, `role_label`, `role_payload`, `rotate_refresh_token`, `set_user_avatar`, `setup_initialize`, `setup_status`, `sync_role_permissions`, `update_role`, `update_user`, `user_payload`, `user_with_credential`, `verify_reset_code`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| POST | `/auth/change-password` | `change_password` | authenticated |
| POST | `/auth/forgot-password` | `forgot_password` | public |
| POST | `/auth/forgot-password/resend` | `resend_code` | public |
| POST | `/auth/forgot-password/reset` | `reset_password` | public |
| POST | `/auth/forgot-password/verify` | `verify_code` | public |
| POST | `/auth/login` | `login` | public |
| POST | `/auth/logout` | `logout` | authenticated |
| GET | `/auth/me` | `me` | authenticated |
| DELETE | `/auth/profile/avatar` | `remove_profile_avatar` | authenticated |
| POST | `/auth/profile/avatar` | `update_profile_avatar` | authenticated |
| POST | `/auth/refresh` | `refresh` | public |
| GET | `/permissions` | `list_permissions` | `role.read` |
| DELETE | `/roles` | `delete_roles` | `role.manage` |
| GET | `/roles` | `list_roles` | `role.read` |
| POST | `/roles` | `create_role` | `role.manage` |
| GET | `/roles/{role_id}` | `get_role` | `role.read` |
| PUT | `/roles/{role_id}` | `update_role` | `role.manage` |
| DELETE | `/users` | `delete_users` | `user.manage` |
| GET | `/users` | `list_users` | `user.read` |
| POST | `/users` | `create_user` | `user.manage` |
| GET | `/users/{user_id}` | `get_user` | `user.read` |
| PATCH | `/users/{user_id}` | `update_user` | `user.manage` |
| PUT | `/users/{user_id}` | `update_user` | `user.manage` |
| GET | `/users/{user_id}/role-assignments` | `list_role_assignments` | `role.read` |
| POST | `/users/{user_id}/role-assignments` | `assign_role` | `role.manage` |

### A.3 Quotations (`quotations`)

Tables: `quotations`, `quotation_revisions`, `quotation_revision_places`, `quotation_revision_containers`, `quotation_revision_lines`, `quotation_conversions`

Service functions: `accept_revision`, `cancel_revision`, `convert_revision`, `create_revision`, `delete_quotations`, `get_latest_revision`, `get_quotation`, `list_quotations`, `normalize_status`, `quotation_record`, `reject_revision`, `resolve_direction`, `resolve_party_by_name`, `revision_status`, `save_quotation`, `send_revision`, `submit_revision`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| POST | `/quotation-revisions/{revision_id}/accept` | `accept_revision` | `quotation.accept` |
| POST | `/quotation-revisions/{revision_id}/cancel` | `cancel_revision` | `quotation.update_draft` |
| POST | `/quotation-revisions/{revision_id}/convert` | `convert_revision` | `quotation.convert` |
| POST | `/quotation-revisions/{revision_id}/reject` | `reject_revision` | `quotation.accept` |
| POST | `/quotation-revisions/{revision_id}/send` | `send_revision` | `quotation.send` |
| POST | `/quotation-revisions/{revision_id}/submit` | `submit_revision` | `quotation.send` |
| DELETE | `/quotations` | `delete_quotations` | `quotation.update_draft` |
| GET | `/quotations` | `list_quotations` | `quotation.read` |
| POST | `/quotations` | `save_quotation` | `quotation.create` |
| GET | `/quotations/{quotation_id}` | `get_quotation` | `quotation.read` |
| PUT | `/quotations/{quotation_id}` | `update_quotation` | `quotation.update_draft` |
| POST | `/quotations/{quotation_id}/revisions` | `create_revision` | `quotation.update_draft` |

### A.4 Operations (service orders, charges, attachments) (`operations`)

Tables: `service_orders`, `service_order_places`, `service_order_container_requirements`, `service_order_containers`, `service_order_pricing`, `service_order_pricing_lines`, `service_order_component_rows`, `service_order_movements`, `service_order_milestones`, `service_order_charges`, `service_order_charge_lines`, `attachments`, `attachment_links`

Service functions: `add_container`, `charge_record`, `charge_status`, `charge_to_invoice`, `complete_component`, `create_service_order_from_quotation`, `ensure_component`, `finish_service_order`, `get_charge`, `get_service_order`, `issue_charge`, `list_all_components`, `list_attachments`, `list_charges`, `list_components`, `list_containers`, `list_service_orders`, `normalize_order_status`, `order_record`, `order_status`, `presign`, `read_attachment`, `record_charge_status_change`, `record_order_status_change`, `remove_component`, `replace_component_values`, `resolve_order`, `save_charge`, `save_service_order`, `set_service_order_status`, `store_upload`, `update_status`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| GET | `/attachments` | `list_attachments` | `attachment.read` |
| POST | `/attachments` | `create_attachment` | `attachment.upload` |
| GET | `/attachments/file/{storage_key:path}` | `download_attachment` | `attachment.read` |
| POST | `/attachments/presign` | `presign_attachment` | `attachment.upload` |
| POST | `/attachments/upload` | `upload_attachment` | authenticated + `attachment.upload` (body context) |
| DELETE | `/service-charges` | `delete_service_charges` | `service_charge.create` |
| GET | `/service-charges` | `list_service_charges` | `service_charge.create` |
| POST | `/service-charges` | `create_service_charge` | `service_charge.create` |
| GET | `/service-charges/{charge_id}` | `get_service_charge` | `service_charge.create` |
| PUT | `/service-charges/{charge_id}` | `update_service_charge` | `service_charge.create` |
| POST | `/service-charges/{charge_id}/create-finance-invoice` | `create_finance_invoice` | `service_charge.convert_to_invoice` |
| POST | `/service-charges/{charge_id}/issue` | `issue_service_charge` | `service_charge.issue` |
| GET | `/service-order-components` | `list_all_components` | `service_order.read` |
| DELETE | `/service-order-components/{component_id}` | `delete_component` | `service_order.update` |
| GET | `/service-order-components/{component_id}` | `get_component` | `service_order.read` |
| POST | `/service-order-components/{component_id}/complete` | `complete_component` | `service_order.update` |
| POST | `/service-order-components/{component_id}/values` | `save_component_values` | `service_order.update` |
| PUT | `/service-order-components/{component_id}/values` | `put_component_values` | `service_order.update` |
| DELETE | `/service-orders` | `delete_service_orders` | `service_order.update` |
| GET | `/service-orders` | `list_service_orders` | `service_order.read` |
| POST | `/service-orders` | `create_service_order` | `service_order.create` |
| GET | `/service-orders/{identifier}` | `get_service_order` | `service_order.read` |
| POST | `/service-orders/{identifier}` | `update_service_order` | `service_order.update` |
| PUT | `/service-orders/{identifier}` | `update_service_order` | `service_order.update` |
| GET | `/service-orders/{identifier}/charges` | `list_order_charges` | `service_charge.create` |
| POST | `/service-orders/{identifier}/charges` | `create_order_charge` | `service_charge.create` |
| GET | `/service-orders/{identifier}/components` | `list_components` | `service_order.read` |
| POST | `/service-orders/{identifier}/components` | `add_component` | `service_order.update` |
| GET | `/service-orders/{identifier}/containers` | `list_containers` | `service_order.read` |
| POST | `/service-orders/{identifier}/containers` | `add_container` | `service_order.update` |
| GET | `/service-orders/{identifier}/dynamic-tabs` | `list_dynamic_tabs` | `service_order.read` |
| GET | `/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows` | `list_dynamic_rows` | `service_order.read` |
| POST | `/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows` | `create_dynamic_row` | `service_order.update` |
| POST | `/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows/bulk` | `bulk_save_dynamic_rows` | `service_order.update` |
| DELETE | `/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows/{row_id}` | `delete_dynamic_row` | `service_order.update` |
| PATCH | `/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows/{row_id}` | `update_dynamic_row` | `service_order.update` |

### A.5 Finance and accounting (`finance`)

Tables: `chart_of_accounts`, `financial_accounts`, `accounting_periods`, `document_sequences`, `financial_documents`, `financial_document_lines`, `financial_document_sources`, `financial_document_allocations`, `posting_rules`, `journal_entries`, `journal_entry_lines`, `financial_document_postings`

Service functions: `account_payload`, `allocate_payment`, `close_period`, `create_account`, `create_financial_account`, `create_invoice_from_charge`, `create_posting_rule`, `delete_accounts`, `delete_financial_accounts`, `delete_posting_rules`, `document_payload`, `financial_account_payload`, `get_account`, `get_document`, `get_financial_account`, `get_journal`, `get_period`, `get_posting_rule`, `get_sequence`, `journal_payload`, `list_accounts`, `list_documents`, `list_financial_accounts`, `list_journals`, `list_periods`, `list_posting_rules`, `list_sequences`, `period_payload`, `post_document`, `post_journal`, `posting_rule_payload`, `reopen_period`, `resolve_period`, `reverse_document`, `save_document`, `save_journal`, `sequence_payload`, `update_account`, `update_financial_account`, `update_period`, `update_posting_rule`, `upsert_sequence`

Supporting modules: `posting_rules.py` (`PostingRuleResolver`, `PostingRuleAccounts`, `RuleSource`, `validate_postable`) and `posting.py` (`AccountingPostingService`, `JournalDraft`, `PostingStrategy`, `STRATEGIES`, `ALLOCATABLE_TYPES`). §9 explains how the two compose, and §9.5 how a rule's history is derived rather than stored twice.

Document types (`DOCUMENT_TYPE_LABELS`) and their posting meanings (`STRATEGIES`) are declared together, so a type cannot be configurable without a posting meaning. `backend/tests/test_posting_rules.py` asserts the frontend registry (`FINANCIAL_DOCUMENT_TYPES`) has not drifted from `DOCUMENT_TYPE_LABELS`.

Service functions added for history: `posting_rule_history`, `list_posting_rule_history`, `posting_rule_usage`.

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| GET | `/accounting-periods` | `list_periods` | `accounting_period.read` |
| GET | `/accounting-periods/{period_id}` | `get_period` | `accounting_period.read` |
| PATCH | `/accounting-periods/{period_id}` | `update_period` | `accounting_period.close` |
| PUT | `/accounting-periods/{period_id}` | `update_period` | `accounting_period.close` |
| POST | `/accounting-periods/{period_id}/close` | `close_period` | `accounting_period.close` |
| GET | `/accountingPeriods` | `list_periods` | `accounting_period.read` |
| GET | `/accountingPeriods/{period_id}` | `get_period` | `accounting_period.read` |
| DELETE | `/chart-of-accounts` | `delete_accounts` | `chart_of_accounts.manage` |
| GET | `/chart-of-accounts` | `list_accounts` | `journal_entry.read` |
| POST | `/chart-of-accounts` | `create_account` | `chart_of_accounts.manage` |
| GET | `/chart-of-accounts/{account_id}` | `get_account` | `journal_entry.read` |
| PUT | `/chart-of-accounts/{account_id}` | `update_account` | `chart_of_accounts.manage` |
| DELETE | `/chartOfAccounts` | `delete_accounts` | `chart_of_accounts.manage` |
| GET | `/chartOfAccounts` | `list_accounts` | `journal_entry.read` |
| POST | `/chartOfAccounts` | `create_account` | `chart_of_accounts.manage` |
| GET | `/chartOfAccounts/{account_id}` | `get_account` | `journal_entry.read` |
| PUT | `/chartOfAccounts/{account_id}` | `update_account` | `chart_of_accounts.manage` |
| GET | `/document-sequences` | `list_sequences` | `configuration.manage` |
| POST | `/document-sequences` | `upsert_sequence` | `configuration.manage` |
| GET | `/document-sequences/{sequence_id}` | `get_sequence` | `configuration.manage` |
| GET | `/documentSequences` | `list_sequences` | `configuration.manage` |
| POST | `/documentSequences` | `upsert_sequence` | `configuration.manage` |
| GET | `/documentSequences/{sequence_id}` | `get_sequence` | `configuration.manage` |
| DELETE | `/financial-accounts` | `delete_financial_accounts` | `chart_of_accounts.manage` |
| GET | `/financial-accounts` | `list_financial_accounts` | `journal_entry.read` |
| POST | `/financial-accounts` | `create_financial_account` | `chart_of_accounts.manage` |
| GET | `/financial-accounts/{account_id}` | `get_financial_account` | `journal_entry.read` |
| PUT | `/financial-accounts/{account_id}` | `update_financial_account` | `chart_of_accounts.manage` |
| DELETE | `/financial-documents` | `delete_financial_documents` | `financial_document.update_draft` |
| GET | `/financial-documents` | `list_financial_documents` | `financial_document.read` |
| POST | `/financial-documents` | `create_financial_document` | `financial_document.create` |
| GET | `/financial-documents/{document_id}` | `get_financial_document` | `financial_document.read` |
| PUT | `/financial-documents/{document_id}` | `update_financial_document` | `financial_document.update_draft` |
| POST | `/financial-documents/{document_id}/allocate` | `allocate_payment` | `financial_document.allocate` |
| POST | `/financial-documents/{document_id}/post` | `post_financial_document` | `financial_document.post` |
| POST | `/financial-documents/{document_id}/reverse` | `reverse_financial_document` | `financial_document.reverse` |
| DELETE | `/financialAccounts` | `delete_financial_accounts` | `chart_of_accounts.manage` |
| GET | `/financialAccounts` | `list_financial_accounts` | `journal_entry.read` |
| POST | `/financialAccounts` | `create_financial_account` | `chart_of_accounts.manage` |
| GET | `/financialAccounts/{account_id}` | `get_financial_account` | `journal_entry.read` |
| PUT | `/financialAccounts/{account_id}` | `update_financial_account` | `chart_of_accounts.manage` |
| GET | `/journal-entries` | `list_journals` | `journal_entry.read` |
| POST | `/journal-entries` | `create_journal` | `journal_entry.create` |
| GET | `/journal-entries/{journal_id}` | `get_journal` | `journal_entry.read` |
| PUT | `/journal-entries/{journal_id}` | `update_journal` | `journal_entry.create` |
| POST | `/journal-entries/{journal_id}/post` | `post_journal` | `journal_entry.post` |
| GET | `/journals` | `list_journals` | `journal_entry.read` |
| POST | `/journals` | `create_journal` | `journal_entry.create` |
| GET | `/journals/{journal_id}` | `get_journal` | `journal_entry.read` |
| PUT | `/journals/{journal_id}` | `update_journal` | `journal_entry.create` |
| POST | `/journals/{journal_id}/post` | `post_journal` | `journal_entry.post` |
| DELETE | `/posting-rules` | `delete_posting_rules` | `posting_rule.manage` |
| GET | `/posting-rules` | `list_posting_rules` | `posting_rule.read` |
| POST | `/posting-rules` | `create_posting_rule` | `posting_rule.manage` |
| GET | `/posting-rules/{rule_id}` | `get_posting_rule` | `posting_rule.read` |
| PUT | `/posting-rules/{rule_id}` | `update_posting_rule` | `posting_rule.manage` |
| DELETE | `/postingRules` | `delete_posting_rules` | `posting_rule.manage` |
| GET | `/postingRules` | `list_posting_rules` | `posting_rule.read` |
| POST | `/postingRules` | `create_posting_rule` | `posting_rule.manage` |
| GET | `/postingRules/{rule_id}` | `get_posting_rule` | `posting_rule.read` |
| PUT | `/postingRules/{rule_id}` | `update_posting_rule` | `posting_rule.manage` |

### A.6 Shared record status (`status`)

Tables: none — the module owns no storage.

Service functions: `change_status`, `policy_for`, `serialize_policy`.

Every collection that owns a lifecycle `status` changes it through this one small
module. `policy.py` is the single source of truth: which statuses a collection
can hold, which transitions are legal from each one, which permission each
requires, and who applies it — `kind: "status"` is a plain, audited status write
(activate / deactivate / mark / reopen) that this endpoint performs, while
`kind: "command"` belongs to the collection's own workflow endpoint (posting,
reversal, issuing a charge, closing a period, the quotation workflow). The table
is code-defined on purpose (`docs/17` §4): a configuration mistake must not be
able to weaken a workflow or an authorization rule.

`service.py` resolves the policy, proves the transition is legal and permitted,
refuses a `command` transition with `TRANSITION_REQUIRES_COMMAND` (so an
accounting status can never be written outside its posting engine), calls the
collection's existing service to apply a plain status write, and records one
audit event with the previous status, the new status, the actor and the
timestamp.

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| GET | `/{collection}/status-policy` | `read_status_policy` | authenticated; transitions filtered to the caller's permissions |
| POST | `/{collection}/{item_id}/status` | `change_record_status` | the transition's own permission (`master.reference.manage`, `chart_of_accounts.manage`, `posting_rule.manage`, `configuration.manage`, `accounting_period.close`, `service_order.update`, `user.manage`, `role.manage`…) |

The router is registered before the data modules so the literal
`/{collection}/status-policy` wins over the generic `/{collection}/{item_id}`
lookup, and the `POST` path has three segments, which no other router claims.

Status is no longer an editable form field anywhere: the create/edit forms keep
the Status *column* in the list and the colour-coded badge, and every transition
is offered from the row's "..." menu (`useRecordStatus`), which renders only what
the policy returns.

### A.7 Reporting (`reports`)

Service functions: `dashboard`, `expenses`, `financial_summary`, `income`, `ledger_lines`, `payables`, `profitability`, `quotation_performance`, `receivables`, `service_order_report`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| GET | `/payables` | `payables_alias` | `report.read` |
| GET | `/profitability` | `profitability_alias` | `report.read` |
| GET | `/receivables` | `receivables_alias` | `report.read` |
| GET | `/reports/dashboard` | `dashboard` | `report.read` |
| GET | `/reports/expenses` | `expenses` | `report.read` |
| GET | `/reports/financial-summary` | `financial_summary` | `report.read` |
| GET | `/reports/income` | `income` | `report.read` |
| GET | `/reports/payables` | `payables` | `report.read` |
| GET | `/reports/profitability` | `profitability` | `report.read` |
| GET | `/reports/ledger-lines` | `ledger_lines` | `report.read` |
| GET | `/reports/quotation-performance` | `quotation_performance` | `report.read` |
| GET | `/reports/receivables` | `receivables` | `report.read` |
| GET | `/reports/service-order-profitability` | `profitability` | `report.read` |
| GET | `/reports/service-orders` | `service_orders_report` | `report.read` |

### A.8 Master data, configuration and generic collections (`master_data`)

Tables: `places`, `trade_directions`, `container_types`, `transport_types`, `fee_types`, `business_parties`, `transport_assets`, `customer_customs_accounts`, `component_attributes`, `component_groups`, `component_group_attributes`, `component_tabs`, `component_tab_groups`, `module_records`

Service functions: `apply_input`, `create_generic`, `create_reference`, `delete_generic`, `delete_reference`, `get_generic`, `get_reference`, `get_spec`, `list_generic`, `list_reference`, `resolve_reference`, `serialize`, `update_generic`, `update_reference`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| DELETE | `/businessParties` | `delete_businessParties` | `master.reference.manage` / `configuration.manage` |
| GET | `/businessParties` | `list_businessParties` | `master.reference.view` / `configuration.manage` |
| POST | `/businessParties` | `create_businessParties` | `master.reference.manage` / `configuration.manage` |
| POST | `/businessParties/bulk-delete` | `bulk_delete_businessParties` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/businessParties/{item_id}` | `delete_businessParties` | `master.reference.manage` / `configuration.manage` |
| GET | `/businessParties/{item_id}` | `get_businessParties` | `master.reference.view` / `configuration.manage` |
| PUT | `/businessParties/{item_id}` | `update_businessParties` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/companies` | `delete_companies` | `master.reference.manage` / `configuration.manage` |
| GET | `/companies` | `list_companies` | `master.reference.view` / `configuration.manage` |
| POST | `/companies` | `create_companies` | `master.reference.manage` / `configuration.manage` |
| GET | `/companies/{item_id}` | `get_companies` | `master.reference.view` / `configuration.manage` |
| PUT | `/companies/{item_id}` | `update_companies` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/componentGroups` | `delete_componentGroups` | `master.reference.manage` / `configuration.manage` |
| GET | `/componentGroups` | `list_componentGroups` | `master.reference.view` / `configuration.manage` |
| POST | `/componentGroups` | `create_componentGroups` | `master.reference.manage` / `configuration.manage` |
| POST | `/componentGroups/bulk-delete` | `bulk_delete_componentGroups` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/componentGroups/{item_id}` | `delete_componentGroups` | `master.reference.manage` / `configuration.manage` |
| GET | `/componentGroups/{item_id}` | `get_componentGroups` | `master.reference.view` / `configuration.manage` |
| PUT | `/componentGroups/{item_id}` | `update_componentGroups` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/componentTemplates` | `delete_componentTemplates` | `master.reference.manage` / `configuration.manage` |
| GET | `/componentTemplates` | `list_componentTemplates` | `master.reference.view` / `configuration.manage` |
| POST | `/componentTemplates` | `create_componentTemplates` | `master.reference.manage` / `configuration.manage` |
| POST | `/componentTemplates/bulk-delete` | `bulk_delete_componentTemplates` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/componentTemplates/{item_id}` | `delete_componentTemplates` | `master.reference.manage` / `configuration.manage` |
| GET | `/componentTemplates/{item_id}` | `get_componentTemplates` | `master.reference.view` / `configuration.manage` |
| PUT | `/componentTemplates/{item_id}` | `update_componentTemplates` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/containerTypes` | `delete_containerTypes` | `master.reference.manage` / `configuration.manage` |
| GET | `/containerTypes` | `list_containerTypes` | `master.reference.view` / `configuration.manage` |
| POST | `/containerTypes` | `create_containerTypes` | `master.reference.manage` / `configuration.manage` |
| POST | `/containerTypes/bulk-delete` | `bulk_delete_containerTypes` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/containerTypes/{item_id}` | `delete_containerTypes` | `master.reference.manage` / `configuration.manage` |
| GET | `/containerTypes/{item_id}` | `get_containerTypes` | `master.reference.view` / `configuration.manage` |
| PUT | `/containerTypes/{item_id}` | `update_containerTypes` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/customerPayments` | `delete_customerPayments` | `master.reference.manage` / `configuration.manage` |
| GET | `/customerPayments` | `list_customerPayments` | `master.reference.view` / `configuration.manage` |
| POST | `/customerPayments` | `create_customerPayments` | `master.reference.manage` / `configuration.manage` |
| GET | `/customerPayments/{item_id}` | `get_customerPayments` | `master.reference.view` / `configuration.manage` |
| PUT | `/customerPayments/{item_id}` | `update_customerPayments` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/customs` | `delete_customs` | `master.reference.manage` / `configuration.manage` |
| GET | `/customs` | `list_customs` | `master.reference.view` / `configuration.manage` |
| POST | `/customs` | `create_customs` | `master.reference.manage` / `configuration.manage` |
| GET | `/customs/{item_id}` | `get_customs` | `master.reference.view` / `configuration.manage` |
| PUT | `/customs/{item_id}` | `update_customs` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/deliveries` | `delete_deliveries` | `master.reference.manage` / `configuration.manage` |
| GET | `/deliveries` | `list_deliveries` | `master.reference.view` / `configuration.manage` |
| POST | `/deliveries` | `create_deliveries` | `master.reference.manage` / `configuration.manage` |
| GET | `/deliveries/{item_id}` | `get_deliveries` | `master.reference.view` / `configuration.manage` |
| PUT | `/deliveries/{item_id}` | `update_deliveries` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/documents` | `delete_documents` | `master.reference.manage` / `configuration.manage` |
| GET | `/documents` | `list_documents` | `master.reference.view` / `configuration.manage` |
| POST | `/documents` | `create_documents` | `master.reference.manage` / `configuration.manage` |
| GET | `/documents/{item_id}` | `get_documents` | `master.reference.view` / `configuration.manage` |
| PUT | `/documents/{item_id}` | `update_documents` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/feeTypes` | `delete_feeTypes` | `master.reference.manage` / `configuration.manage` |
| GET | `/feeTypes` | `list_feeTypes` | `master.reference.view` / `configuration.manage` |
| POST | `/feeTypes` | `create_feeTypes` | `master.reference.manage` / `configuration.manage` |
| POST | `/feeTypes/bulk-delete` | `bulk_delete_feeTypes` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/feeTypes/{item_id}` | `delete_feeTypes` | `master.reference.manage` / `configuration.manage` |
| GET | `/feeTypes/{item_id}` | `get_feeTypes` | `master.reference.view` / `configuration.manage` |
| PUT | `/feeTypes/{item_id}` | `update_feeTypes` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/places` | `delete_places` | `master.reference.manage` / `configuration.manage` |
| GET | `/places` | `list_places` | `master.reference.view` / `configuration.manage` |
| POST | `/places` | `create_places` | `master.reference.manage` / `configuration.manage` |
| POST | `/places/bulk-delete` | `bulk_delete_places` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/places/{item_id}` | `delete_places` | `master.reference.manage` / `configuration.manage` |
| GET | `/places/{item_id}` | `get_places` | `master.reference.view` / `configuration.manage` |
| PUT | `/places/{item_id}` | `update_places` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/service-order-columns/{column_id}` | `delete_service_order_column` | `service_order_config.delete` / `configuration.manage` |
| PATCH | `/service-order-columns/{column_id}` | `update_service_order_column` | `service_order_config.update` / `configuration.manage` |
| GET | `/service-order-tabs` | `list_service_order_tabs` | `service_order_config.view` / `service_order.read` / `configuration.manage` |
| POST | `/service-order-tabs` | `create_service_order_tab` | `service_order_config.create` / `configuration.manage` |
| GET | `/service-order-tabs/meta/column-types` | `service_order_column_types` | `service_order_config.view` / `service_order.read` / `configuration.manage` |
| DELETE | `/service-order-tabs/{tab_id}` | `delete_service_order_tab` | `service_order_config.delete` / `configuration.manage` |
| PATCH | `/service-order-tabs/{tab_id}` | `update_service_order_tab` | `service_order_config.update` / `configuration.manage` |
| GET | `/service-order-tabs/{tab_id}/columns` | `list_service_order_columns` | `service_order_config.view` / `service_order.read` / `configuration.manage` |
| POST | `/service-order-tabs/{tab_id}/columns` | `create_service_order_column` | `service_order_config.create` / `configuration.manage` |
| POST | `/service-order-tabs/{tab_id}/columns/reorder` | `reorder_service_order_columns` | `service_order_config.update` / `configuration.manage` |
| DELETE | `/shipments` | `delete_shipments` | `master.reference.manage` / `configuration.manage` |
| GET | `/shipments` | `list_shipments` | `master.reference.view` / `configuration.manage` |
| POST | `/shipments` | `create_shipments` | `master.reference.manage` / `configuration.manage` |
| GET | `/shipments/{item_id}` | `get_shipments` | `master.reference.view` / `configuration.manage` |
| PUT | `/shipments/{item_id}` | `update_shipments` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/supplierCosts` | `delete_supplierCosts` | `master.reference.manage` / `configuration.manage` |
| GET | `/supplierCosts` | `list_supplierCosts` | `master.reference.view` / `configuration.manage` |
| POST | `/supplierCosts` | `create_supplierCosts` | `master.reference.manage` / `configuration.manage` |
| GET | `/supplierCosts/{item_id}` | `get_supplierCosts` | `master.reference.view` / `configuration.manage` |
| PUT | `/supplierCosts/{item_id}` | `update_supplierCosts` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/supplierPayments` | `delete_supplierPayments` | `master.reference.manage` / `configuration.manage` |
| GET | `/supplierPayments` | `list_supplierPayments` | `master.reference.view` / `configuration.manage` |
| POST | `/supplierPayments` | `create_supplierPayments` | `master.reference.manage` / `configuration.manage` |
| GET | `/supplierPayments/{item_id}` | `get_supplierPayments` | `master.reference.view` / `configuration.manage` |
| PUT | `/supplierPayments/{item_id}` | `update_supplierPayments` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/tradeDirectionComponents` | `delete_tradeDirectionComponents` | `master.reference.manage` / `configuration.manage` |
| GET | `/tradeDirectionComponents` | `list_tradeDirectionComponents` | `master.reference.view` / `configuration.manage` |
| POST | `/tradeDirectionComponents` | `create_tradeDirectionComponents` | `master.reference.manage` / `configuration.manage` |
| POST | `/tradeDirectionComponents/bulk-delete` | `bulk_delete_tradeDirectionComponents` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/tradeDirectionComponents/{item_id}` | `delete_tradeDirectionComponents` | `master.reference.manage` / `configuration.manage` |
| GET | `/tradeDirectionComponents/{item_id}` | `get_tradeDirectionComponents` | `master.reference.view` / `configuration.manage` |
| PUT | `/tradeDirectionComponents/{item_id}` | `update_tradeDirectionComponents` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/tradeDirections` | `delete_tradeDirections` | `master.reference.manage` / `configuration.manage` |
| GET | `/tradeDirections` | `list_tradeDirections` | `master.reference.view` / `configuration.manage` |
| POST | `/tradeDirections` | `create_tradeDirections` | `master.reference.manage` / `configuration.manage` |
| POST | `/tradeDirections/bulk-delete` | `bulk_delete_tradeDirections` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/tradeDirections/{item_id}` | `delete_tradeDirections` | `master.reference.manage` / `configuration.manage` |
| GET | `/tradeDirections/{item_id}` | `get_tradeDirections` | `master.reference.view` / `configuration.manage` |
| PUT | `/tradeDirections/{item_id}` | `update_tradeDirections` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/transportAssets` | `delete_transportAssets` | `master.reference.manage` / `configuration.manage` |
| GET | `/transportAssets` | `list_transportAssets` | `master.reference.view` / `configuration.manage` |
| POST | `/transportAssets` | `create_transportAssets` | `master.reference.manage` / `configuration.manage` |
| POST | `/transportAssets/bulk-delete` | `bulk_delete_transportAssets` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/transportAssets/{item_id}` | `delete_transportAssets` | `master.reference.manage` / `configuration.manage` |
| GET | `/transportAssets/{item_id}` | `get_transportAssets` | `master.reference.view` / `configuration.manage` |
| PUT | `/transportAssets/{item_id}` | `update_transportAssets` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/transportTypes` | `delete_transportTypes` | `master.reference.manage` / `configuration.manage` |
| GET | `/transportTypes` | `list_transportTypes` | `master.reference.view` / `configuration.manage` |
| POST | `/transportTypes` | `create_transportTypes` | `master.reference.manage` / `configuration.manage` |
| POST | `/transportTypes/bulk-delete` | `bulk_delete_transportTypes` | `master.reference.manage` / `configuration.manage` |
| DELETE | `/transportTypes/{item_id}` | `delete_transportTypes` | `master.reference.manage` / `configuration.manage` |
| GET | `/transportTypes/{item_id}` | `get_transportTypes` | `master.reference.view` / `configuration.manage` |
| PUT | `/transportTypes/{item_id}` | `update_transportTypes` | `master.reference.manage` / `configuration.manage` |
| GET | `/ui-schemas/{page:path}` | `get_ui_schema` | authenticated |

### A.9 Settings and search (`settings`)

Service functions: `answer`, `connection_result`, `deep_merge`, `get_app_config`, `get_app_info`, `redact_app_config`, `reset_app_info`, `search`, `update_app_config`, `update_app_info`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| GET | `/search` | `global_search` | authenticated |
| POST | `/search/ask` | `search_ask` | authenticated |
| GET | `/settings/app-config` | `get_app_config` | authenticated |
| PATCH | `/settings/app-config` | `update_app_config` | `configuration.manage` |
| POST | `/settings/app-config/email/send-test` | `send_test_email` | `configuration.manage` |
| POST | `/settings/app-config/email/test-connection` | `test_email_connection` | `configuration.manage` |
| POST | `/settings/app-config/telegram/send-test` | `send_test_telegram` | `configuration.manage` |
| POST | `/settings/app-config/telegram/test-connection` | `test_telegram_connection` | `configuration.manage` |
| GET | `/settings/app-info` | `get_app_info` | authenticated |
| PATCH | `/settings/app-info` | `update_app_info` | `configuration.manage` |
| POST | `/settings/app-info/reset` | `reset_app_info` | `configuration.manage` |
| POST | `/settings/reset-data` | `reset_data` | `settings.manage` |

### A.10 Backup (`backup`)

Tables: `backup_runs`, `backup_records`, `backup_states`, `backup_logs`

Service functions: `active_run_id`, `backupable_columns`, `build_client`, `create_run`, `discover_tables`, `execute_run`, `get_run`, `public_config`, `restore_from_sheets`, `run_now`, `sanitize_title`, `schedule_status`, `serialize_log`, `serialize_row`, `serialize_run`, `start_backup`, `table_by_name`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| POST | `/backup/restore` | `restore_backup` | `backup.manage` |
| POST | `/backup/run` | `run_backup` | `backup.manage` |
| GET | `/backup/runs` | `list_runs` | `backup.read` |
| GET | `/backup/runs/{run_id}` | `get_run` | `backup.read` |
| GET | `/backup/status` | `backup_status` | `backup.read` |
| POST | `/backup/test-connection` | `test_connection` | `backup.manage` |

### A.11 Audit (`audit`)

Tables: `audit_events`

Service functions: `list_events`, `serialize`, `write_audit`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| GET | `/audit-events` | `list_audit_events` | `audit_log.read` |

## Appendix B — Tables by module

Column definitions for every table are in `docs/06_database_design.sql`; relations are in `docs/07_entity_relationship_diagram.mmd`.

| Module | Tables |
|---|---|
| auth | `users`, `user_credentials`, `user_sessions`, `roles`, `permissions`, `role_permissions`, `user_role_assignments`, `password_reset_tokens` |
| quotations | `quotations`, `quotation_revisions`, `quotation_revision_places`, `quotation_revision_containers`, `quotation_revision_lines`, `quotation_conversions` |
| operations | `service_orders`, `service_order_places`, `service_order_container_requirements`, `service_order_containers`, `service_order_pricing`, `service_order_pricing_lines`, `service_order_component_rows`, `service_order_movements`, `service_order_milestones`, `service_order_charges`, `service_order_charge_lines`, `attachments`, `attachment_links` |
| finance | `chart_of_accounts`, `financial_accounts`, `accounting_periods`, `document_sequences`, `financial_documents`, `financial_document_lines`, `financial_document_sources`, `financial_document_allocations`, `posting_rules`, `journal_entries`, `journal_entry_lines`, `financial_document_postings` |
| master_data | `places`, `trade_directions`, `container_types`, `transport_types`, `fee_types`, `business_parties`, `transport_assets`, `customer_customs_accounts`, `component_attributes`, `component_groups`, `component_group_attributes`, `component_tabs`, `component_tab_groups`, `module_records` |
| backup | `backup_runs`, `backup_records`, `backup_states`, `backup_logs` |
| audit | `audit_events` |

## Appendix C — Frontend route reference

Nuxt file-based routes. `permission` is the `definePageMeta` page permission enforced by `middleware/auth.global.ts`.

| Route | Page file | titleKey | permission |
|---|---|---|---|
| `/administration/audit-logs` | `app/pages/administration/audit-logs/index.vue` | `freight.pages.auditLogs` | `admin.audit_logs.view` |
| `/administration/document-sequences/:id` | `app/pages/administration/document-sequences/[id].vue` | `freight.pages.documentSequences` | `configuration.manage` |
| `/administration/document-sequences` | `app/pages/administration/document-sequences/index.vue` | `freight.pages.documentSequences` | `configuration.manage` |
| `/administration/document-sequences/new` | `app/pages/administration/document-sequences/new.vue` | `freight.pages.documentSequences` | `configuration.manage` |
| `/administration/roles/:id` | `app/pages/administration/roles/[id].vue` | `freight.pages.roles` | `admin.roles.view` |
| `/administration/roles` | `app/pages/administration/roles/index.vue` | `freight.pages.roles` | `admin.roles.view` |
| `/administration/roles/new` | `app/pages/administration/roles/new.vue` | `freight.pages.roles` | `admin.roles.view` |
| `/administration/system-settings` | `app/pages/administration/system-settings/index.vue` | `freight.pages.settings` | `settings.app_config.view` |
| `/administration/users/:id` | `app/pages/administration/users/[id].vue` | `freight.pages.users` | `admin.users.view` |
| `/administration/users` | `app/pages/administration/users/index.vue` | `freight.pages.users` | `admin.users.view` |
| `/administration/users/new` | `app/pages/administration/users/new.vue` | `freight.pages.users` | `admin.users.view` |
| `/auth/forget-password` | `app/pages/auth/forget-password.vue` | — | — |
| `/auth/login` | `app/pages/auth/login.vue` | — | — |
| `/auth/reset-password` | `app/pages/auth/reset-password.vue` | — | — |
| `/auth/setup` | `app/pages/auth/setup.vue` | — | — |
| `/auth/verify-code` | `app/pages/auth/verify-code.vue` | — | — |
| `/configuration/component-attributes` | `app/pages/configuration/component-attributes/index.vue` | `freight.pages.componentAttributes` | `configuration.manage` |
| `/configuration/component-groups` | `app/pages/configuration/component-groups/index.vue` | `freight.pages.componentGroups` | `configuration.manage` |
| `/configuration/component-tabs` | `app/pages/configuration/component-tabs/index.vue` | `freight.pages.componentTabs` | `configuration.manage` |
| `/finance/accounting-periods/:id` | `app/pages/finance/accounting-periods/[id].vue` | `freight.pages.accountingPeriods` | `finance.accounting.view` |
| `/finance/accounting-periods` | `app/pages/finance/accounting-periods/index.vue` | `freight.pages.accountingPeriods` | `finance.accounting.view` |
| `/finance/chart-of-accounts/:id` | `app/pages/finance/chart-of-accounts/[id].vue` | `freight.pages.chartOfAccounts` | `finance.accounting.view` |
| `/finance/chart-of-accounts` | `app/pages/finance/chart-of-accounts/index.vue` | `freight.pages.chartOfAccounts` | `finance.accounting.view` |
| `/finance/chart-of-accounts/new` | `app/pages/finance/chart-of-accounts/new.vue` | `freight.pages.chartOfAccounts` | `finance.accounting.view` |
| `/finance/documents/:id` | `app/pages/finance/documents/[id].vue` | `freight.pages.financialDocuments` | `finance.financial_documents.view` |
| `/finance/documents` | `app/pages/finance/documents/index.vue` | `freight.pages.financialDocuments` | `finance.financial_documents.view` |
| `/finance/documents/new` | `app/pages/finance/documents/new.vue` | `freight.pages.financialDocuments` | `finance.financial_documents.view` |
| `/finance/financial-accounts/:id` | `app/pages/finance/financial-accounts/[id].vue` | `freight.pages.financialAccounts` | `finance.accounting.view` |
| `/finance/financial-accounts` | `app/pages/finance/financial-accounts/index.vue` | `freight.pages.financialAccounts` | `finance.accounting.view` |
| `/finance/financial-accounts/new` | `app/pages/finance/financial-accounts/new.vue` | `freight.pages.financialAccounts` | `finance.accounting.view` |
| `/finance/journals/:id` | `app/pages/finance/journals/[id].vue` | `freight.pages.journals` | `finance.accounting.view` |
| `/finance/journals` | `app/pages/finance/journals/index.vue` | `freight.pages.journals` | `finance.accounting.view` |
| `/` | `app/pages/index.vue` | `freight.pages.dashboard` | `dashboard.view` |
| `/master-data/business-parties/:id` | `app/pages/master-data/business-parties/[id].vue` | `freight.pages.businessParties` | `master.reference.view` |
| `/master-data/business-parties` | `app/pages/master-data/business-parties/index.vue` | `freight.pages.businessParties` | `master.reference.view` |
| `/master-data/business-parties/new` | `app/pages/master-data/business-parties/new.vue` | `freight.pages.businessParties` | `master.reference.view` |
| `/master-data/container-types/:id` | `app/pages/master-data/container-types/[id].vue` | `freight.pages.containerTypes` | `master.reference.view` |
| `/master-data/container-types` | `app/pages/master-data/container-types/index.vue` | `freight.pages.containerTypes` | `master.reference.view` |
| `/master-data/container-types/new` | `app/pages/master-data/container-types/new.vue` | `freight.pages.containerTypes` | `master.reference.view` |
| `/master-data/fee-types/:id` | `app/pages/master-data/fee-types/[id].vue` | `freight.pages.feeTypes` | `master.reference.view` |
| `/master-data/fee-types` | `app/pages/master-data/fee-types/index.vue` | `freight.pages.feeTypes` | `master.reference.view` |
| `/master-data/fee-types/new` | `app/pages/master-data/fee-types/new.vue` | `freight.pages.feeTypes` | `master.reference.view` |
| `/master-data/places/:id` | `app/pages/master-data/places/[id].vue` | `freight.pages.places` | `master.reference.view` |
| `/master-data/places` | `app/pages/master-data/places/index.vue` | `freight.pages.places` | `master.reference.view` |
| `/master-data/places/new` | `app/pages/master-data/places/new.vue` | `freight.pages.places` | `master.reference.view` |
| `/master-data/trade-directions/:id` | `app/pages/master-data/trade-directions/[id].vue` | `freight.pages.tradeDirections` | `master.reference.view` |
| `/master-data/trade-directions` | `app/pages/master-data/trade-directions/index.vue` | `freight.pages.tradeDirections` | `master.reference.view` |
| `/master-data/trade-directions/new` | `app/pages/master-data/trade-directions/new.vue` | `freight.pages.tradeDirections` | `master.reference.view` |
| `/master-data/transport-assets/:id` | `app/pages/master-data/transport-assets/[id].vue` | `freight.pages.transportAssets` | `master.reference.view` |
| `/master-data/transport-assets` | `app/pages/master-data/transport-assets/index.vue` | `freight.pages.transportAssets` | `master.reference.view` |
| `/master-data/transport-assets/new` | `app/pages/master-data/transport-assets/new.vue` | `freight.pages.transportAssets` | `master.reference.view` |
| `/master-data/transport-types/:id` | `app/pages/master-data/transport-types/[id].vue` | `freight.pages.transportTypes` | `master.reference.view` |
| `/master-data/transport-types` | `app/pages/master-data/transport-types/index.vue` | `freight.pages.transportTypes` | `master.reference.view` |
| `/master-data/transport-types/new` | `app/pages/master-data/transport-types/new.vue` | `freight.pages.transportTypes` | `master.reference.view` |
| `/print/:collection/:id` | `app/pages/print/[collection]/[id].vue` | `freight.print.previewTitle` | — |
| `/quotations/:id` | `app/pages/quotations/[id].vue` | `freight.pages.quotations` | `sales.quotations.view` |
| `/quotations` | `app/pages/quotations/index.vue` | `freight.pages.quotations` | `sales.quotations.view` |
| `/quotations/new` | `app/pages/quotations/new.vue` | `freight.pages.quotations` | `sales.quotations.view` |
| `/reports/:area/:slug` | `app/pages/reports/[area]/[slug].vue` | `freight.nav.reports` | — |
| `/reports/:slug` | `app/pages/reports/[slug].vue` | `freight.nav.reports` | — |
| `/reports` | `app/pages/reports/index.vue` | `freight.nav.reports` | — |
| `/service-charges/:id` | `app/pages/service-charges/[id].vue` | `freight.pages.serviceCharges` | `finance.service_charges.view` |
| `/service-charges` | `app/pages/service-charges/index.vue` | `freight.pages.serviceCharges` | `finance.service_charges.view` |
| `/service-charges/new` | `app/pages/service-charges/new.vue` | `freight.pages.serviceCharges` | `finance.service_charges.view` |
| `/service-orders/:id` | `app/pages/service-orders/[id].vue` | `freight.pages.serviceOrders` | `operations.service_orders.view` |
| `/service-orders` | `app/pages/service-orders/index.vue` | `freight.pages.serviceOrders` | `operations.service_orders.view` |
| `/service-orders/new` | `app/pages/service-orders/new.vue` | `freight.pages.serviceOrders` | `operations.service_orders.view` |

## Appendix D — Frontend components

| Folder | Components |
|---|---|
| `components/common/` | `AppAuthLocaleSwitch.vue`, `AppColorPicker.vue`, `AppConfirmDialog.vue`, `AppConfirmHost.vue`, `AppConnectionStatusCard.vue`, `AppDatePickerPopover.vue`, `AppDateRangeFilter.vue`, `AppDocumentActionButton.vue`, `AppEntityDialog.vue`, `AppExportDialog.vue`, `AppFilterMenu.vue`, `AppFilterSelect.vue`, `AppImageUploadField.vue`, `AppInputDate.vue`, `AppLiveSearch.vue`, `AppMentionMultiInput.vue`, `AppReferenceSelect.vue`, `AppRolePermissionMatrix.vue`, `AppSecretInput.vue`, `AppSortableList.vue` |
| `components/dashboard/` | `AppChartGrid.vue`, `AppSummaryCard.vue` |
| `components/document/` | `AppCommentsActivity.vue`, `AppComponentTabs.vue`, `AppDocumentContentShell.vue`, `AppDocumentForm.vue`, `AppDocumentPage.vue`, `AppDocumentTabBar.vue`, `AppDynamicFieldRenderer.vue`, `AppDynamicTableField.vue`, `AppFieldGrid.vue`, `SystemSettingsPage.vue` |
| `components/freight/` | `AppLineTable.vue`, `DocumentView.vue`, `DynamicDataTable.vue`, `JobCharges.vue`, `JobContainers.vue`, `JobDetail.vue`, `JobEmptyState.vue`, `JobFiles.vue`, `JobFinance.vue`, `JobLineTable.vue`, `JobOverview.vue`, `JobRoute.vue`, `JobSectionHeader.vue`, `ModulePage.vue`, `ReportsView.vue`, `WorkspaceView.vue` |
| `components/layout/` | `AppAboutDialog.vue`, `AppHeader.vue`, `AppHeaderPageActions.vue`, `AppSlidebar.vue`, `AppUserProfileDialog.vue`, `UserMenu.vue` |
| `components/print/` | `BankBlock.vue`, `DebitNoteLayout.vue`, `DocumentPreview.vue`, `FooterBar.vue`, `IssuerHeader.vue`, `LinesTable.vue`, `MetaGrid.vue`, `SignatureBlock.vue`, `TaxInvoiceLayout.vue`, `TemplateModal.vue`, `TotalsBlock.vue` |
| `components/table/` | `AppListTable.vue`, `AppRelatedRecords.vue`, `AppSaveGrid.vue`, `AppTableRowMeta.vue` |

## Appendix E — Stores, composables, repositories, config, utils

### Pinia stores (`app/stores/`)

- `stores/auth.ts`
- `stores/freight.ts`
- `stores/preferences.ts`

### Composables (`app/composables/`)

- `composables/auth/useAuth.ts`
- `composables/auth/useSetup.ts`
- `composables/common/useConfirm.ts`
- `composables/common/useReferenceOptions.ts`
- `composables/freight/useDocumentActions.ts`
- `composables/freight/useDynamicFieldRegistry.ts`
- `composables/freight/useDynamicServiceOrderTabs.ts`
- `composables/freight/useFinanceCommands.ts`
- `composables/freight/useFreight.ts`
- `composables/freight/useFreightRecordChrome.ts`
- `composables/freight/useJobRelated.ts`
- `composables/freight/useModuleList.ts`
- `composables/freight/useModuleRecord.ts`
- `composables/freight/useQuotationCommands.ts`
- `composables/freight/useServiceOrderTabConfig.ts`
- `composables/layout/useAppHeader.ts`
- `composables/layout/useAppPageTitle.ts`
- `composables/layout/useMenu.ts`
- `composables/layout/useUserMenu.ts`
- `composables/print/usePrintBilingual.ts`
- `composables/search/useGlobalSearch.ts`
- `composables/search/useSearch.ts`
- `composables/settings/useAppBranding.ts`
- `composables/settings/useAppLocalization.ts`
- `composables/useApi.ts`
- `composables/usePageSeo.ts`
- `composables/useSeoAbsoluteUrl.ts`

### Repositories (`app/repositories/`)

- `repositories/contracts/dynamic-tabs.ts`
- `repositories/contracts/lcs.ts`
- `repositories/contracts/module.ts`
- `repositories/contracts/settings.ts`
- `repositories/http/dynamic-tabs.ts`
- `repositories/http/lcs.ts`
- `repositories/http/module.ts`
- `repositories/http/response.ts`
- `repositories/http/settings.ts`
- `repositories/index.ts`

### Config (`app/config/`)

- `config/freight-modules.ts`
- `config/freight-options.ts`
- `config/freight-reports.ts`
- `config/job-workspace-forms.ts`
- `config/lcs-reference-modules.ts`
- `config/print-templates.ts`
- `config/settings-schemas.ts`

### Utils (`app/utils/`)

- `utils/api/freight-remote.ts`
- `utils/api/query.ts`
- `utils/auth/password-reset.ts`
- `utils/auth/remember-me.ts`
- `utils/auth/session.ts`
- `utils/auth/user-avatar.ts`
- `utils/client-id.ts`
- `utils/constants/api-endpoints.ts`
- `utils/constants/api-v1-endpoints.ts`
- `utils/constants/select-options.ts`
- `utils/date-picker.ts`
- `utils/document-sequences.ts`
- `utils/export/csv.ts`
- `utils/field-help.ts`
- `utils/file-icon.ts`
- `utils/filter/select-ui.ts`
- `utils/filter/values.ts`
- `utils/format/format-service.ts`
- `utils/format/number.ts`
- `utils/freight/attachments.ts`
- `utils/freight/audit-logs.ts`
- `utils/freight/charge-print.ts`
- `utils/freight/component-instance-mode.ts`
- `utils/freight/document-tabs.ts`
- `utils/freight/dynamic-tab-columns.ts`
- `utils/freight/dynamic-table.ts`
- `utils/freight/finance.ts`
- `utils/freight/format.ts`
- `utils/freight/job-component-line-table.ts`
- `utils/freight/job-component-tabs.ts`
- `utils/freight/job-containers.ts`
- `utils/freight/job-list.ts`
- `utils/freight/job-print.ts`
- `utils/freight/job-task-fields.ts`
- `utils/freight/job-workspace.ts`
- `utils/freight/page-access.ts`
- `utils/freight/print-model.ts`
- `utils/freight/print-navigation.ts`
- `utils/freight/quotation-print.ts`
- `utils/freight/report-access.ts`
- `utils/freight/report-queries.ts`
- `utils/freight/report.ts`
- `utils/freight/traceability.ts`
- `utils/layout/document-action-button.ts`
- `utils/layout/document-header-actions.ts`
- `utils/layout/header-actions.ts`
- `utils/lcs/dashboard.ts`
- `utils/lcs/errors.ts`
- `utils/lcs/idempotency.ts`
- `utils/lcs/permissions.ts`
- `utils/lcs/sequences.ts`
- `utils/lcs/states.ts`
- `utils/object-path.ts`
- `utils/pagination.ts`
- `utils/role/permissions.ts`
- `utils/table/line-table-rules.ts`
- `utils/validation/api-error.ts`
- `utils/validation/component-rules.ts`
- `utils/validation/error-paths.ts`
- `utils/validation/field-rules.ts`
- `utils/validation/focus.ts`
- `utils/validation/messages.ts`
- `utils/validation/record-validation.ts`
- `utils/search/text-extract.ts`
- `utils/security/csrf.ts`
- `utils/security/files.ts`
- `utils/security/url.ts`
- `utils/storage/local.ts`
- `utils/table/line-table-columns.ts`
- `utils/table/list-columns.ts`
- `utils/table/list-table.ts`
- `utils/table/row-meta.ts`
- `utils/table/theme.ts`
- `utils/text/slug.ts`

### Middleware (`app/middleware/`)

- `middleware/auth.global.ts`
- `middleware/report-area-auth.ts`

### Layouts (`app/layouts/`)

- `layouts/auth.vue`
- `layouts/default.vue`
- `layouts/print.vue`

### Module catalogue (`app/config/freight-modules.ts` + `lcs-reference-modules.ts`)

| Path | Title | Group | Collection | Permission |
|---|---|---|---|---|
| `/sales/companies` | Companies / Customers | sales | `companies` | `sales.companies.view` |
| `/sales/quotations` | Quotations | sales | `quotations` | `sales.quotations.view` |
| `/operations/jobs` | Jobs | operations | `jobs` | `operations.jobs.view` |
| `/operations/shipments` | Shipments / Transport | operations | `shipments` | `operations.shipments.view` |
| `/operations/customs` | Customs | operations | `customs` | `operations.customs.view` |
| `/operations/documents` | Documents | operations | `documents` | `operations.documents.view` |
| `/operations/deliveries` | Deliveries | operations | `deliveries` | `operations.deliveries.view` |
| `/finance/debit-notes` | Debit Notes | finance | `debitNotes` | `finance.debit_notes.view` |
| `/finance/customer-payments` | Customer Payments | finance | `customerPayments` | `finance.customer_payments.view` |
| `/finance/job-charges` | Job Charges / Cost | finance | `jobCharges` | `finance.job_charges.view` |
| `/finance/supplier-costs` | Supplier Costs | finance | `supplierCosts` | `finance.supplier_costs.view` |
| `/finance/supplier-payments` | Supplier Payments | finance | `supplierPayments` | `finance.supplier_payments.view` |
| `/finance/accounts-receivable` | Accounts Receivable | finance | `receivables` | `finance.accounts_receivable.view` |
| `/finance/accounts-payable` | Accounts Payable | finance | `payables` | `finance.accounts_payable.view` |
| `/finance/job-profitability` | Job Profitability | finance | `profitability` | `finance.job_profitability.view` |
| `/administration/users` | Users | admin | `users` | `admin.users.view` |
| `/administration/roles` | Roles & Permissions | admin | `roles` | `admin.roles.view` |
| `/administration/audit-logs` | Audit Logs | admin | `auditLogs` | `admin.audit_logs.view` |
| `/reports` | General Ledger | reports | `reports` | `reports.view` |
| `/master-data/business-parties` | Business Parties | master | `businessParties` | `master.reference.view` |
| `/master-data/places` | Places | master | `places` | `master.reference.view` |
| `/master-data/trade-directions` | Trade Directions | master | `tradeDirections` | `master.reference.view` |
| `/master-data/container-types` | Container Types | master | `containerTypes` | `master.reference.view` |
| `/master-data/transport-types` | Transport Types | master | `transportTypes` | `master.reference.view` |
| `/master-data/transport-assets` | Transport Assets | master | `transportAssets` | `master.reference.view` |
| `/master-data/fee-types` | Fee Types | master | `feeTypes` | `master.reference.view` |
| `/configuration/component-groups` | Component Groups | configuration | `componentGroups` | `configuration.manage` |
| `/configuration/component-templates` | Component Templates | configuration | `componentTemplates` | `configuration.manage` |
| `/configuration/trade-direction-components` | Trade Direction Components | configuration | `tradeDirectionComponents` | `configuration.manage` |
| `/administration/document-sequences` | Document Sequences | admin | `documentSequences` | `configuration.manage` |
| `/finance/chart-of-accounts` | Chart of Accounts | finance | `chartOfAccounts` | `finance.accounting.view` |
| `/finance/financial-accounts` | Financial Accounts | finance | `financialAccounts` | `finance.accounting.view` |
| `/finance/journals` | Journal Entries | finance | `journals` | `finance.accounting.view` |
| `/finance/accounting-periods` | Accounting Periods | finance | `accountingPeriods` | `finance.accounting.view` |

### Remote endpoint map (`app/utils/api/freight-remote.ts`)

Collections registered in `REMOTE_ENDPOINTS`: `quotations`, `jobs`, `jobCharges`, `debitNotes`, `customerPayments`, `supplierCosts`, `supplierPayments`, `journals`, `auditLogs`, `receivables`, `payables`, `profitability`, `users`, `roles`, `businessParties`, `places`, `tradeDirections`, `containerTypes`, `transportTypes`, `transportAssets`, `feeTypes`, `chargeTypes`, `suppliers`, `componentGroups`, `componentTemplates`, `tradeDirectionComponents`, `postingRules`, `chartOfAccounts`, `financialAccounts`, `accountingPeriods`, `documentSequences`, `companies`, `shipments`, `customs`, `documents`, `deliveries`, `cashAccounts`, `serviceComponents`.

`JOB_DERIVED_COLLECTIONS = ['containerRequirements', 'actualContainers']` are derived from service orders rather than fetched directly.

### Archive / Recycle Bin

The reusable archive module keeps supported business rows in their source tables
with `deleted_at` and `deleted_by_user_id` markers. `archive_records` stores the
cross-module index, readable snapshot, actor, owner and lifecycle state. Normal
module queries exclude marked rows. Restore clears the markers only after unique
and parent-dependency checks; permanent delete locks the archive/source rows and
is rejected whenever any database relationship still references the source row.
Every delete, restore and permanent-delete attempt is written through the common
`audit_events` service.

Supported entity types are master references (`businessParties`, `places`,
`tradeDirections`, `containerTypes`, `transportTypes`, `transportAssets`,
`feeTypes`) and selected generic records (`companies`, `shipments`, `documents`,
`deliveries`, `currencies`). Finance/accounting, quotations, service orders,
service charges, users, roles, attachments and technical configuration records
are intentionally excluded pending entity-specific lifecycle rules.

| Method | Route | Permission |
|---|---|---|
| GET | `/archive` | `archive.view` |
| GET | `/archive/options` | `archive.view` |
| GET | `/archive/{entity_type}/{entity_id}` | `archive.view` |
| POST | `/archive/{entity_type}/{entity_id}/restore` | `archive.restore` |
| DELETE | `/archive/{entity_type}/{entity_id}` | `archive.hard_delete` |

### i18n namespaces

| Locale | Top-level namespaces |
|---|---|
| `en.json` | `freight`, `lcs`, `actions`, `common`, `components`, `pages`, `settings`, `api`, `app` |
| `km.json` | `freight`, `lcs`, `actions`, `common`, `api`, `app`, `components`, `pages`, `settings` |
