# Solution Architecture

> This document is the architecture reference. API contracts are in `07_api_documentation.md`; frontend structure in `08_frontend_and_ui_design.md`; RBAC in `09_roles_and_permissions.md`; testing in `10_testing_and_quality.md`; deployment and security in `11_deployment_and_security.md`.

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

Owns users, credentials, sessions, roles, permissions, Casbin policies
(`casbin_rule`), password-reset tokens, and the login/refresh/logout and profile
flows. It also owns the users/roles/permissions administration endpoints. It does
not own business records. Authorization itself lives in
`app/core/authorization/` (model plus enforcer); this module only persists the
rows that engine reads and writes.

Authentication uses one stable `user_sessions` row per login and indexed
`used_refresh_tokens` hashes for rotation/replay detection. Access JWTs carry
the session ID; one joined user/session lookup enforces account state, token
version, revocation and idle/absolute deadlines on every protected request.
Silent refresh never extends activity or the original absolute lifetime.

### Reference data — `master_data`

Owns the administrator-managed party-role and place-role vocabularies, business
parties, trade directions, container
types, transport types, transport assets, fee types, customer customs accounts,
the reusable
component attribute/group catalogue, component tabs (each bound to one trade
direction), and the generic `module_records` JSON store. A group is reusable;
its **layout** (`form_only`, `table_only`, `form_and_table`, cardinality, form
columns, title/read-only/collapse flags and order) lives on the tab assignment
(`component_tab_groups`), so one tab can render forms and tables side by side.
Component configuration is served by `component_config.py`; service-order tab
rendering by `component_tabs.py` and the frontend
`document/Dynamic*Renderer.vue` components.

### Quotations — `quotations`

Owns quotation aggregates, immutable revisions, route stops/containers/lines,
and the quotation→service-order conversion ledger. Lifecycle:
`DRAFT → SENT → ACCEPTED → CONVERTED`.

### Operations — `operations`

Owns service orders, their route stops, container requirements, actual containers,
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
receivables, payables, income, expenses, profitability, financial summary) plus
the on-demand generation engine. Three files split the responsibilities:

- `engine.py` — the report registry (`ReportDefinition` per report key), the
  permission the route guards on, execution, and the shared `meta` envelope
  (`generatedAt`, period, page, total, warnings). No accounting arithmetic.
- `ledger_reports.py` — the accounting calculations (trial balance, general
  ledger) in `Decimal`, plus the fiscal-year/date resolution and refusal rules.
- `repository.py` — the set-based SQL, all reading `POSTED` journals only.

The module owns no tables.

### Settings — `settings`

Owns app info (branding) and app config (general/localization/email/telegram/
notifications/security/system/backup) in `app_settings`, mirrored into
`module_records`. Also provides global search / Ask, email and Telegram test
endpoints, and reset-data. It owns `app_settings`.

### First-run setup (in `auth`)

Served by the `auth` module: the public `/api/v1/auth/setup/status` and
`/api/v1/auth/setup/initialize` endpoints. Setup is accepted only while no user
exists.

### Backup — `backup`

Owns the Google Sheets append-only mirror, its run/log/record tables, and the
in-process scheduler toggled by `BACKUP_SCHEDULER_ENABLED`.

### Audit — `audit`

Owns the append-only audit event log and its read endpoint. High-risk actions
(financial post/reverse/allocate, period close, journal post), permission
changes, and quotation/service-order status transitions write events; ordinary
field edits are not all audited.

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
- Finance converts an issued service-charge snapshot on the explicit `create-finance-invoice` command and creates one idempotent draft customer invoice; repeating the command returns that draft. Ledger posting remains a separate authorized command.
- Reporting reads read-only queries.
- Authorization (`get_current_context`, `require_permission`) runs before
  repository access.
- No UI rule is treated as a security rule.

## 4. Repository Structure (actual)

```text
backend/
  app/
    main.py               FastAPI app, lifespan, exception handlers, middleware
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
      permissions.py      permission catalog, page catalog, seeded role definitions
      redis.py            lazy Redis + safe_* helpers
      security.py         Argon2 hashing, JWT, reset codes
      sequences.py        document-number allocation
      serialization.py    camel/snake + model serialization
      authorization/
        model.conf        Casbin RBAC model (p, g, default deny)
        models.py         casbin_rule table
        service.py        enforcer lifecycle, Redis sync, policy writers
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
  i18n/locales/           en.json, km.json, zh.json
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
  schemas.py    Pydantic request bodies where a module needs schema-level validation (auth, master_data component attributes)
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
  → audit event (financial, security, and workflow actions)
  → {"data": ...} envelope (or {code, message, request_id, field_errors})
```

## 7. API Contract

The API is versioned under `/api/v1`. The request/response envelope, error
catalogue, authentication, pagination, filtering, and the complete endpoint
catalogue are in `docs/07_api_documentation.md`. Routers stay thin: they parse
and validate the request, resolve the current context and permission, and call a
service function.


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
the removal is intentional; do not re-add the screens.

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

## 12. Security and Authorization

Authentication, the Casbin role model, permission catalog, page-to-API compile,
and frontend route/button enforcement are in `docs/09_roles_and_permissions.md`.
Transport, secret handling, and host hardening are in
`docs/11_deployment_and_security.md`. The architectural rule is that every
authenticated request resolves one current user, its account state, and the
policy copy before the router calls a service; each permission decision is then
asked of Casbin (`app/core/authorization`), never of a cached copy.

- **One authorization engine.** `casbin_rule` holds every grant and every
  user→role assignment. `roles` and `permissions` are display
  metadata for the administration UI and decide nothing.
- **Default deny.** A request without an explicit policy for its subject is
  refused; an unknown role, a deactivated role, a deleted policy or an
  unloadable policy table all deny.
- **Single role, no inheritance.** A user holds exactly one role (enforced by a
  partial unique index); its effective permissions are that role's direct
  grants.
- **Fail closed.** If the policy table cannot be read, the in-memory copy is
  dropped and every check answers *deny* until a reload succeeds.


## 13. Database and Consistency

- PostgreSQL is the transactional source of truth.
- Migrations are versioned and reviewed (`backend/alembic/versions/`).
- Number allocation uses row locks (`with_for_update`) plus unique constraints.
- Positive/negative invariants not expressible as constraints are enforced in
  services (for example, journal balance before posting).
- The schema has 77 tables and the current Alembic head is `b4c5d6e7f8a9`.
  `docs/06_database_design.sql` is the single generated reference: DDL, indexes,
  constraints, and a `COMMENT ON` description for every table and column.
  Relationships are summarised in `docs/04_functional_design.md` section 17.
- PostgreSQL integrity triggers and reporting views are installed by
  `alembic/versions/e6f7a8b9c0d1_reporting_views_and_integrity.py`; they are not
  part of the SQLAlchemy models, so they do not appear in the generated SQL.

## 14. Reporting

Reports are served by the backend `/reports/*` API (dashboard, receivables,
payables, income, expenses, profitability, financial summary) and the
frontend report catalogue (`FREIGHT_REPORTS`, 12 reports). Accounting reports read
posted journal lines only.

Trial Balance and General Ledger are generated on demand:
`POST /reports/trial-balance/generate` and
`POST /reports/general-ledger/generate` accept validated filters and return one
server-paginated page plus the metadata that produced it. Both read the same
posted-ledger projection, so the trial balance control and the ledger rows can
never disagree about what "posted" means. Their CSV exports reuse that same
calculation and stream every matching row from a server-side cursor. Statements
keep their existing whole-ledger endpoints. Report data is never cached: every
generation stamps `generatedAt`, and the SPA marks a result stale as soon as a
filter changes.

## 15. Deployment Topology

Two runtimes are supported: Docker Compose for local/development and the
production Compose bundle in `infrastructure/docker-compose.prod.yml` behind nginx. PostgreSQL,
Redis, MinIO, the FastAPI API, and the static Nuxt SPA run as separate services.
Environment configuration, CI/CD, backup/restore, migration, and rollback
procedures are in `docs/11_deployment_and_security.md`.


## 16. Frontend Architecture

The Nuxt 4 static SPA, route table, page components, metadata-driven forms,
tables, stores, repositories, i18n, and validation pipeline are documented in
`docs/08_frontend_and_ui_design.md`. The frontend never computes financial
balances; it renders backend report data.


## 17. Observability

Structured request logging, request ids, health endpoints, audit events, and
backup status are operated as part of deployment. The operational checks are in
`docs/11_deployment_and_security.md`.


## 18. Future Extraction Criteria

Extract a module into a service only when at least one is true: independent
scaling is required; separate team ownership is established; external
integration isolation is necessary; deployment cadence creates operational risk;
data ownership can be made explicit; distributed transaction complexity is
acceptable.

## Appendix A - Tables by module

The schema has 77 tables. Column definitions for every table are in
`docs/06_database_design.sql`; relations are in `docs/04_functional_design.md` §17.

| Module | Tables |
|---|---|
| auth | `users`, `user_credentials`, `user_sessions`, `used_refresh_tokens`, `roles`, `permissions`, `casbin_rule`, `password_reset_tokens` |
| quotations | `quotations`, `quotation_revisions`, `quotation_revision_places`, `quotation_revision_containers`, `quotation_revision_lines`, `quotation_conversions` |
| operations | `service_orders`, `service_order_places`, `service_order_container_requirements`, `service_order_containers`, `service_order_pricing`, `service_order_pricing_lines`, `service_order_component_rows`, `service_order_movements`, `service_order_milestones`, `service_order_charges`, `service_order_charge_lines`, `attachments`, `attachment_links` |
| finance | `chart_of_accounts`, `financial_accounts`, `accounting_periods`, `document_sequences`, `financial_documents`, `financial_document_lines`, `financial_document_sources`, `financial_document_allocations`, `posting_rules`, `journal_entries`, `journal_entry_lines`, `financial_document_postings` |
| master_data | `places`, `place_roles`, `place_role_places`, `party_roles`, `business_party_roles`, `trade_directions`, `currencies`, `currency_rates`, `container_types`, `transport_types`, `fee_types`, `business_parties`, `transport_assets`, `customer_customs_accounts`, `configuration_versions`, `component_attributes`, `component_groups`, `component_group_attributes`, `component_tabs`, `component_tab_groups`, `module_records` |
| backup | `backup_runs`, `backup_records`, `backup_states`, `backup_logs` |
| audit | `audit_events` |
| settings | `app_settings` |
| archive | `archive_records` |

## Appendix B - Hardcoded configuration register

For each item: can a **database row** override it at runtime? `DB` means yes,
with the governing table named; `CODE` means no override exists.

### Database-driven (a row wins)

| Constant | Overriding row | Note |
|---|---|---|
| `DEFAULT_ACCOUNTS` (finance) | `posting_rules` + `chart_of_accounts` | Last-resort fallback only; `PostingRuleResolver` queries rules first, takes the highest priority in the most specific tier, and raises `AMBIGUOUS_POSTING_RULE` on a priority tie |
| `DEFAULT_PREFIXES` (sequences) | `document_sequences` | Editable in the UI; re-seeded each year if a row is missing |
| `DEFAULT_LOCALIZATION` | `app_settings(localization)` | Selection constrained by code allow-lists |
| `DEFAULT_APP_INFO`, `DEFAULT_APP_CONFIG` | `app_settings(app_info, general, ...)` | Deep-merged over defaults; reset deletes the row |
| `ROLE_DEFINITIONS` | `roles` + `casbin_rule` | Seeds the 7 built-in roles on startup by adding missing grants only, so administrator edits survive; custom roles are database-only |
| `DEFAULT_CURRENCY` | `app_settings(localization.currency)` | Value must exist in `currencies` |
| Master-data reference rows | their own tables | Codes, names, symbols, statuses, and ordering are data |

### Code-only (no override)

| Area | Constant | Location |
|---|---|---|
| Order lifecycle | `ORDER_STATUS`, `_LEGACY_INACTIVE`, `SERVICE_ORDER_LIFECYCLE` | `operations/service.py`, `reports/service.py` |
| Movement / milestone states | `MOVEMENT_STATUSES`, `MILESTONE_STATUSES` | `operations/service.py` |
| Quotation states | `STATUS_MAP`, `IMMUTABLE_STATUSES` | `quotations/service.py` |
| Finance document classes | `PAYMENT_TYPES`, `INVOICE_TYPES`, detailed-posting type sets | `finance/service.py` |
| Component field system | `REFERENCE_TYPES`, `DATA_TYPES`, `RENDER_MODES` | `component_config.py`, mirrored in `operations/reference_options.py` |
| Login policy defaults | `MAX_FAILED_ATTEMPTS`, `LOCKOUT_MINUTES` defaults | `auth/service.py`; effective values come from `app_settings('security')`, clamped to 3-100 attempts and 1-1440 minutes |
| Uploads | `_UPLOAD_TYPES` and `UPLOAD_MAX_SIZE_MB` | `operations/service.py`, `core/config.py` |
| Localization allow-lists | `SUPPORTED_LANGUAGES`, `TIMEZONES`, `DATE_FORMATS`, `TIME_FORMATS`, `NUMBER_FORMATS`, `CURRENCIES`, `LOCALES` | `core/localization.py` |
| Aging buckets | `_AGING_BUCKETS` and the 30/60/90 thresholds | `reports/service.py` |
| Permission catalog and page mapping | `SOURCE_PERMISSIONS`, `PAGE_PERMISSIONS`, `MATRIX_PAGE_PERMISSIONS`, aliases, `ROLE_DEFINITIONS` | `core/permissions.py` |
| Collection registries | `SPECS`, `GENERIC_COLLECTIONS`, `ARCHIVABLE_GENERIC_COLLECTIONS` | `master_data/service.py`, `archive/service.py` |
| Record statuses and transitions | `STATUS_POLICIES` | `master_data/status_policy.py`; exposed through `GET /{collection}/status-policy` |
| Secrets and redaction | password denylist, `SENSITIVE_FIELD_NAMES`, `SENSITIVE_HINTS` | `core/security.py`, `core/crypto.py`, `backup/service.py` |
| Model defaults | `SERVICE_NOTE`, `PLATE`, `EXPECTED`, `DEBIT`, `BANK`, `MANUAL`, `ORIGINAL_POSTING`, `GENERATED_FROM` | model definitions |

The split is deliberate: reference data and pricing configuration are
database-driven; status machines, validation allow-lists, and security policy
stay in code so a configuration mistake cannot weaken authorization or
accounting. Lockout thresholds and the upload extension allow-list are
database-configurable, but the code clamps them to the ranges documented above.
