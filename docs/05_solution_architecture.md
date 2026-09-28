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
 ├── setup        first-run provisioning (public)
 ├── auth         users, credentials, sessions, roles, permissions
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
assets, fee types, business parties (+ party roles/places), customer customs
accounts, component groups/templates/attributes, trade-direction components, and
the generic `module_records` JSON store. It also owns service-order tab/column
configuration (`service_order_tabs.py`).

### Quotations — `quotations`

Owns quotation aggregates, immutable revisions, revision places/containers/lines,
and the quotation→service-order conversion ledger. Lifecycle:
`DRAFT → SENT → ACCEPTED → CONVERTED`.

### Operations — `operations`

Owns service orders, their places, container requirements, actual containers,
pricing snapshots, dynamic components and values, movements, milestones, service
charges and charge lines, dynamic tab rows, and attachment metadata.
(`service_order_tabs.py` validates/serves dynamic-table rows.)

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

### First-run setup — `setup`

Owns the public `/setup/status` and `/setup/initialize` endpoints. Setup is
accepted only while no user exists.

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
Models / transaction manager (async SQLAlchemy session)
   ↓
PostgreSQL
```

Rules:

- Cross-module work goes through application services, not direct table access.
- Finance consumes a service-charge snapshot through the conversion service.
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
      quotations/ reports/ settings/ setup/
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
  service.py    business logic / queries
  models.py     SQLAlchemy models (only modules that own tables)
  schemas.py    Pydantic bodies (currently only auth)
  <name>_tabs.py  dynamic tab/column helpers (master_data, operations)
```

## 6. Request Flow

```text
HTTP request
  → optional Redis-backed rate limiting / helpers
  → authentication (JWT bearer or HttpOnly cookie)
  → permission dependency (require_permission / guard)
  → request validation
  → application service
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
- 39 source permissions gate the endpoints (see `docs/11_permissions_matrix.md`).
- Several finance paths register both kebab-case and camelCase aliases to the
  same handler.
- Master-data and generic collections are registered dynamically from
  `service.SPECS` / `service.GENERIC_COLLECTIONS`:
  - relational: businessParties, places, tradeDirections, containerTypes,
    transportTypes, transportAssets, feeTypes, componentGroups,
    componentTemplates, tradeDirectionComponents
  - generic (`module_records`): companies, customs, customerPayments,
    deliveries, documents, shipments, supplierCosts, supplierPayments

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

## 9. Finance Posting Architecture

```text
Financial document
        │
        ▼
Posting service
        ├── validate document state
        ├── resolve period
        ├── resolve account/posting rules
        ├── build journal lines
        ├── validate debit = credit
        └── persist document + journal atomically
```

The journal is the source of truth for posted accounting balances. Financial
documents are source/business records.

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

## 13. Database and Consistency

- PostgreSQL is the transactional source of truth.
- Migrations are versioned and reviewed (`backend/alembic/versions/`).
- Number allocation uses row locks (`with_for_update`) plus unique constraints.
- Positive/negative invariants not expressible as constraints are enforced in
  services (e.g., journal balance before posting).
- 63 tables; see `docs/06_database_design.sql` and
  `docs/07_entity_relationship_diagram.mmd`.

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

- Auth/setup (public): `/setup`, `/auth/login`, `/auth/forget-password`,
  `/auth/verify-code`, `/auth/reset-password`.
- Dashboard: `/`.
- Sales/operations/finance: `/quotations`, `/service-orders`,
  `/service-charges`, `/finance/documents`, `/finance/chart-of-accounts`,
  `/finance/financial-accounts`, `/finance/journals`,
  `/finance/accounting-periods`.
- Master data: `/master-data/{business-parties,places,trade-directions,
  container-types,transport-types,transport-assets,fee-types}`.
- Configuration: `/configuration/{component-groups,component-templates,
  trade-direction-components,service-order-tabs}`.
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
- Service-order dynamic tabs are configured in the database and surfaced through
  `useDynamicServiceOrderTabs` / `DynamicServiceOrderTabs.vue`.

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

### A.1 First-run setup (`setup`)

Service functions: `initialize`, `status`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| POST | `/setup/initialize` | `setup_initialize` | public |
| GET | `/setup/status` | `setup_status` | public |

### A.2 Identity and authorization (`auth`)

Tables: `users`, `user_credentials`, `user_sessions`, `roles`, `permissions`, `role_permissions`, `user_role_assignments`, `password_reset_tokens`

Service functions: `assign_role`, `authenticate`, `build_auth_user`, `build_context`, `change_password`, `clear_user_avatar`, `create_role`, `create_session`, `create_user`, `delete_roles`, `delete_users`, `expand_source_permissions`, `get_role`, `get_user_avatar`, `get_user_by_login`, `list_role_assignments`, `list_roles`, `list_users`, `request_password_reset`, `reset_password`, `resolve_page_keys`, `resolve_permissions`, `revoke_session`, `role_label`, `role_payload`, `rotate_refresh_token`, `set_user_avatar`, `sync_role_permissions`, `update_role`, `update_user`, `user_payload`, `user_with_credential`, `verify_reset_code`

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

Service functions: `accept_revision`, `convert_revision`, `create_revision`, `delete_quotations`, `get_latest_revision`, `get_quotation`, `list_quotations`, `normalize_status`, `quotation_record`, `resolve_direction`, `resolve_party_by_name`, `save_quotation`, `send_revision`, `submit_revision`

| Method | Path | Handler | Permission / guard |
|---|---|---|---|
| POST | `/quotation-revisions/{revision_id}/accept` | `accept_revision` | `quotation.accept` |
| POST | `/quotation-revisions/{revision_id}/convert` | `convert_revision` | `quotation.convert` |
| POST | `/quotation-revisions/{revision_id}/send` | `send_revision` | `quotation.send` |
| POST | `/quotation-revisions/{revision_id}/submit` | `submit_revision` | `quotation.send` |
| DELETE | `/quotations` | `delete_quotations` | `quotation.update_draft` |
| GET | `/quotations` | `list_quotations` | `quotation.read` |
| POST | `/quotations` | `save_quotation` | `quotation.create` |
| GET | `/quotations/{quotation_id}` | `get_quotation` | `quotation.read` |
| PUT | `/quotations/{quotation_id}` | `update_quotation` | `quotation.update_draft` |
| POST | `/quotations/{quotation_id}/revisions` | `create_revision` | `quotation.update_draft` |

### A.4 Operations (service orders, charges, attachments) (`operations`)

Tables: `service_orders`, `service_order_places`, `service_order_container_requirements`, `service_order_containers`, `service_order_pricing`, `service_order_pricing_lines`, `service_order_components`, `service_component_values`, `service_order_movements`, `service_order_milestones`, `service_order_charges`, `service_order_charge_lines`, `service_order_tab_rows`, `attachments`, `attachment_links`

Service functions: `add_container`, `charge_record`, `charge_to_invoice`, `complete_component`, `create_service_order_from_quotation`, `ensure_component`, `get_charge`, `get_service_order`, `issue_charge`, `list_all_components`, `list_attachments`, `list_charges`, `list_components`, `list_containers`, `list_service_orders`, `normalize_order_status`, `order_record`, `presign`, `read_attachment`, `remove_component`, `replace_component_values`, `resolve_order`, `save_charge`, `save_service_order`, `store_upload`, `update_status`

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

Service functions: `account_payload`, `allocate_payment`, `close_period`, `create_account`, `create_financial_account`, `create_invoice_from_charge`, `create_posting_rule`, `delete_accounts`, `delete_financial_accounts`, `delete_posting_rules`, `document_payload`, `financial_account_payload`, `get_account`, `get_document`, `get_financial_account`, `get_journal`, `get_period`, `get_posting_rule`, `get_sequence`, `journal_payload`, `list_accounts`, `list_documents`, `list_financial_accounts`, `list_journals`, `list_periods`, `list_posting_rules`, `list_sequences`, `period_payload`, `post_document`, `post_journal`, `posting_rule_payload`, `resolve_period`, `reverse_document`, `save_document`, `save_journal`, `sequence_payload`, `update_account`, `update_financial_account`, `update_period`, `update_posting_rule`, `upsert_sequence`

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
| DELETE | `/posting-rules` | `delete_posting_rules` | `configuration.manage` |
| GET | `/posting-rules` | `list_posting_rules` | `configuration.manage` |
| POST | `/posting-rules` | `create_posting_rule` | `configuration.manage` |
| GET | `/posting-rules/{rule_id}` | `get_posting_rule` | `configuration.manage` |
| PUT | `/posting-rules/{rule_id}` | `update_posting_rule` | `configuration.manage` |
| DELETE | `/postingRules` | `delete_posting_rules` | `configuration.manage` |
| GET | `/postingRules` | `list_posting_rules` | `configuration.manage` |
| POST | `/postingRules` | `create_posting_rule` | `configuration.manage` |
| GET | `/postingRules/{rule_id}` | `get_posting_rule` | `configuration.manage` |
| PUT | `/postingRules/{rule_id}` | `update_posting_rule` | `configuration.manage` |

### A.6 Reporting (`reports`)

Service functions: `dashboard`, `expenses`, `financial_summary`, `income`, `payables`, `profitability`, `quotation_performance`, `receivables`, `service_order_report`

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
| GET | `/reports/quotation-performance` | `quotation_performance` | `report.read` |
| GET | `/reports/receivables` | `receivables` | `report.read` |
| GET | `/reports/service-order-profitability` | `profitability` | `report.read` |
| GET | `/reports/service-orders` | `service_orders_report` | `report.read` |

### A.7 Master data, configuration and generic collections (`master_data`)

Tables: `places`, `trade_directions`, `container_types`, `transport_types`, `fee_types`, `business_parties`, `party_roles`, `party_places`, `transport_assets`, `customer_customs_accounts`, `component_groups`, `component_templates`, `template_attributes`, `service_order_tab_configs`, `service_order_column_configs`, `module_records`, `trade_direction_components`

Service functions: `apply_input`, `assert_reference_exists`, `create_generic`, `create_reference`, `delete_generic`, `delete_reference`, `get_generic`, `get_reference`, `get_spec`, `list_generic`, `list_reference`, `resolve_reference`, `serialize`, `update_generic`, `update_reference`

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

### A.8 Settings and search (`settings`)

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

### A.9 Backup (`backup`)

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

### A.10 Audit (`audit`)

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
| operations | `service_orders`, `service_order_places`, `service_order_container_requirements`, `service_order_containers`, `service_order_pricing`, `service_order_pricing_lines`, `service_order_components`, `service_component_values`, `service_order_movements`, `service_order_milestones`, `service_order_charges`, `service_order_charge_lines`, `service_order_tab_rows`, `attachments`, `attachment_links` |
| finance | `chart_of_accounts`, `financial_accounts`, `accounting_periods`, `document_sequences`, `financial_documents`, `financial_document_lines`, `financial_document_sources`, `financial_document_allocations`, `posting_rules`, `journal_entries`, `journal_entry_lines`, `financial_document_postings` |
| master_data | `places`, `trade_directions`, `container_types`, `transport_types`, `fee_types`, `business_parties`, `party_roles`, `party_places`, `transport_assets`, `customer_customs_accounts`, `component_groups`, `component_templates`, `template_attributes`, `service_order_tab_configs`, `service_order_column_configs`, `module_records`, `trade_direction_components` |
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
| `/auth/verify-code` | `app/pages/auth/verify-code.vue` | — | — |
| `/configuration/component-groups/:id` | `app/pages/configuration/component-groups/[id].vue` | `freight.pages.componentGroups` | `configuration.manage` |
| `/configuration/component-groups` | `app/pages/configuration/component-groups/index.vue` | `freight.pages.componentGroups` | `configuration.manage` |
| `/configuration/component-groups/new` | `app/pages/configuration/component-groups/new.vue` | `freight.pages.componentGroups` | `configuration.manage` |
| `/configuration/component-templates/:id` | `app/pages/configuration/component-templates/[id].vue` | `freight.pages.componentTemplates` | `configuration.manage` |
| `/configuration/component-templates` | `app/pages/configuration/component-templates/index.vue` | `freight.pages.componentTemplates` | `configuration.manage` |
| `/configuration/component-templates/new` | `app/pages/configuration/component-templates/new.vue` | `freight.pages.componentTemplates` | `configuration.manage` |
| `/configuration/service-order-tabs` | `app/pages/configuration/service-order-tabs/index.vue` | `freight.pages.serviceOrderTabs` | `configuration.manage` |
| `/configuration/trade-direction-components/:id` | `app/pages/configuration/trade-direction-components/[id].vue` | `freight.pages.tradeDirectionComponents` | `configuration.manage` |
| `/configuration/trade-direction-components` | `app/pages/configuration/trade-direction-components/index.vue` | `freight.pages.tradeDirectionComponents` | `configuration.manage` |
| `/configuration/trade-direction-components/new` | `app/pages/configuration/trade-direction-components/new.vue` | `freight.pages.tradeDirectionComponents` | `configuration.manage` |
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
| `/setup` | `app/pages/setup.vue` | — | — |

## Appendix D — Frontend components

| Folder | Components |
|---|---|
| `components/common/` | `AppAuthLocaleSwitch.vue`, `AppColorPicker.vue`, `AppConfirmDialog.vue`, `AppConfirmHost.vue`, `AppConnectionStatusCard.vue`, `AppConnectionTestButton.vue`, `AppDatePickerPopover.vue`, `AppDateRangeFilter.vue`, `AppDocumentActionButton.vue`, `AppExportDialog.vue`, `AppFilterMenu.vue`, `AppFilterSelect.vue`, `AppIconPicker.vue`, `AppImageUploadField.vue`, `AppInputDate.vue`, `AppLiveSearch.vue`, `AppMentionMultiInput.vue`, `AppRolePermissionMatrix.vue`, `AppSecretInput.vue`, `AppSortableList.vue` |
| `components/configuration/` | `AppAttributeOptionsBuilder.vue`, `AppNumberingPreview.vue`, `AppTableColumnsBuilder.vue`, `AppValidationRuleBuilder.vue`, `AppVisibilityRuleBuilder.vue`, `AppWorkflowStageBuilder.vue` |
| `components/dashboard/` | `AppChartGrid.vue`, `AppChartPanel.vue`, `AppEChart.vue`, `AppKpiSection.vue`, `AppSummaryCard.vue` |
| `components/document/` | `AppCommentsActivity.vue`, `AppDocumentContentShell.vue`, `AppDocumentForm.vue`, `AppDocumentMetaRail.vue`, `AppDocumentPage.vue`, `AppDocumentTabBar.vue`, `AppDynamicFieldRenderer.vue`, `AppDynamicTableField.vue` |
| `components/freight/` | `DashboardView.vue`, `DocumentView.vue`, `DynamicDataTable.vue`, `DynamicServiceOrderTabs.vue`, `FieldGrid.vue`, `FieldInput.vue`, `JobContainers.vue`, `JobDefinitionList.vue`, `JobDetail.vue`, `JobEmptyState.vue`, `JobFiles.vue`, `JobFinance.vue`, `JobLineTable.vue`, `JobOverview.vue`, `JobRoute.vue`, `JobSectionHeader.vue`, `JobSummaryStrip.vue`, `JobTasks.vue`, `ModulePage.vue`, `ReportsView.vue`, `WorkspaceView.vue` |
| `components/layout/` | `AppAboutDialog.vue`, `AppHeader.vue`, `AppHeaderPageActions.vue`, `AppSlidebar.vue`, `AppUserProfileDialog.vue`, `UserMenu.vue` |
| `components/print/` | `BankBlock.vue`, `DebitNoteLayout.vue`, `DocumentPreview.vue`, `FooterBar.vue`, `IssuerHeader.vue`, `LinesTable.vue`, `MetaGrid.vue`, `SignatureBlock.vue`, `TaxInvoiceLayout.vue`, `TemplateModal.vue`, `TotalsBlock.vue` |
| `components/settings/` | `SystemSettingsPage.vue` |
| `components/table/` | `AppLineTable.vue`, `AppListTable.vue`, `AppRelatedRecords.vue`, `AppTableRowMeta.vue`, `LineTableColumnsCell.vue` |

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
- `composables/lcs/useLcs.ts`
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

### i18n namespaces

| Locale | Top-level namespaces |
|---|---|
| `en.json` | `freight`, `lcs`, `docetra`, `actions`, `common`, `components`, `pages`, `settings`, `api`, `app` |
| `km.json` | `freight`, `lcs`, `docetra`, `actions`, `common`, `api`, `app`, `components`, `pages`, `settings` |
