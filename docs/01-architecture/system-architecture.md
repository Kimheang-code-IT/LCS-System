# System Architecture

## Product context

LCS centralizes freight forwarding and accounting for one deployment's business.
The [design brief](../00-project/requirements.md) defines the 44-page scope and approved requirements.
Runtime is single-tenant; organization/branch scoping is not part of the current design.

## Architecture and request flow

Nuxt 4 static SPA → nginx same-origin `/api/` proxy → FastAPI `/api/v1` routers
→ application services → repositories/models → PostgreSQL.
Redis supports configured caching/rate limiting; S3-compatible storage holds attachments.
The SPA uses TypeScript, Nuxt UI, Tailwind, Pinia, repository factories, and HTTP repositories.
Auth is session-bound; Casbin decides authorization before protected business access.

## Major modules and responsibilities

### Inspected technology declarations (2026-11-04)

These are repository manifest/image declarations, not installed/live version certification.

| Layer | Declared version / evidence |
|---|---|
| Backend | Python >=3.12; FastAPI >=0.115.0; SQLAlchemy >=2.0.36; Alembic >=1.14.0; Pydantic >=2.9.0; Casbin >=1.40.0 in backend/pyproject.toml; resolved packages in backend/uv.lock |
| Frontend | Nuxt ^4.6.1, Vue ^3.5.43, Nuxt UI ^4.11.3, Tailwind ^4.3.3, Pinia ^3.0.4, i18n ^10.6.0, TypeScript ^5.9.3; frontend/package.json and pnpm-lock.yaml |
| Toolchain | Node >=20; pnpm 10.30.3; Vitest ^4.1.11; uv-managed Python lock |
| Datastores/storage | Compose declares PostgreSQL 16-alpine, Redis 7-alpine and pgsty/minio RELEASE.2026-06-18T00-00-00Z; existing infrastructure only |

Do not confuse a minimum/caret range with the deployed version. No dependency installation,
upgrade or infrastructure change is part of this audit.

| Module | Responsibility |
|---|---|
| auth / core authorization | Setup, identity, sessions, roles, Casbin policies |
| master_data | Reference catalogs, component attributes/groups/tabs, versioned configuration |
| quotations | Drafts, revisions, lifecycle, conversion snapshots |
| operations | Service orders, containers, dynamic components, charges, attachment metadata |
| finance | Documents, accounts, periods, posting rules, journals, reversals, allocations |
| reports | Backend report queries and accounting calculations; no owned business tables |
| settings | App configuration, branding, search, guarded reset |
| audit / archive | Important event history and guarded record lifecycle |
| backup / telegram / excel_io | Existing mirror, notification, and import/export integrations |

Source: [router registration](../../backend/app/api/v1/router.py),
[detailed boundaries](implementation-reference.md), and [frontend design](../02-business/ui-ux-standards.md).
The legacy README's separate setup module description is superseded: setup routes live in auth.

## Module boundaries and dependencies

Routers handle HTTP and permission dependencies. Services own business rules and transaction
boundaries. Repositories construct queries and load aggregates; they do not authorize or
commit cross-step workflows. Cross-module commands use application services and a shared
transaction/session rather than duplicating business logic.
Quotation conversion depends on reference/configuration snapshots and operations.
Charge-to-invoice conversion depends on operations and finance but never posts automatically.
Reports depend on operational snapshots and posted accounting sources as appropriate.

## Architecture constraints

### Existing reuse and responsibility map

| Responsibility | Existing owner / contract |
|---|---|
| Page title/actions/refresh | Layout header actions and CommonAppDocumentActionButton; use current action props/events and permission gates |
| Lists/search/filter/sort/pagination/empty/loading | WorkspaceView, AppListTable, DynamicDataTable and module metadata; query state belongs to the page/store, not ad hoc fetches |
| Forms/money/currency/reference/period selection | AppDocumentForm/AppDocumentPage, metadata fields and AppReferenceSelect; reuse declared field types rather than new MoneyInput/PartySelect abstractions |
| Validation and refusal | useFormValidation, shared validation rules, UFormField field-path errors and AppFormErrorSummary; server validation remains mandatory |
| Unsaved drafts/quick entry | Existing document state and AppReferenceCreateDialog; creation returns/selects the new reference without navigating away |
| Source references/totals/print | Existing document tabs, source relationship columns, computeRow previews and print TotalsBlock; backend recomputes persisted values |
| Data access/state | Repository factories → HTTP repositories → freight-remote/useApi; Pinia stores; no parallel client cache or mock layer |
| Posting | PostingRuleResolver selects accounts; AccountingPostingService builds journals; finance service orchestrates one transaction |
| Shared infrastructure | core sequences, fx/localization, pagination, validation, exceptions, session/Casbin, storage and audit; no business-specific rule in a generic utility |

Keep functions focused, but split a high-complexity service only around a demonstrated change
boundary with regression evidence. Do not add repository interfaces or service layers merely
to restate existing SQLAlchemy calls. Full page/target contracts are in
[inventory](../00-project/feature-inventory.md) and [Smart ERP requirements](../02-business/accounting-and-posting.md).

Preserve the modular monolith, existing REST conventions, PostgreSQL, and accounting engine.
Do not add microservices, Kubernetes, GraphQL, external identity providers, or another ledger
without demonstrated need and explicit approval. No external AI/LLM is required at runtime.
AI-assisted development tooling is separate from runtime requirements.
Existing backup scheduler and Telegram processing run in-process; document reliability gaps
before proposing a dedicated queue. No infrastructure is added by this foundation.

## Deployment direction and evidence limits

Hostinger VPS with Compose/nginx is the approved intended baseline. Live host resources,
connectivity, service health, cost, and capacity remain unverified.
See [operations](../03-development/deployment-guide.md) and [ADR log](architecture-decisions.md).

## Legacy requirement traceability

Stable identifiers migrated from the reviewed SRS. These are requirements, not assertions
that implementation or acceptance has passed. The approved LCS scope/priorities govern;
retired IDs and deferred advanced capabilities do not create extra pages or new workflows.

| ID | Requirement |
|---|---|
| FR-058 | Administrators shall create component groups. |
| FR-059 | Administrators shall create versioned component templates. |
| FR-060 | A template shall define attributes with code, label, data type, input type, required status, repeatability, display order, and validation rules. |
| FR-061 | Administrators shall configure templates per trade direction and component group. |
| FR-062 | Direction-specific configuration shall define whether a component is required and repeatable. |
| FR-063 | The system shall create runtime service components from configured templates. |
| FR-064 | The system shall automatically create required non-repeatable components during service-order creation. |
| FR-065 | The system shall allow users to add repeatable components manually. |
| FR-066 | The system shall store component values vertically using typed values or structured JSON where appropriate. |
| FR-067 | The system shall validate component values against the template data type and rules. |
| FR-068 | The system shall preserve the template version used by each service component. |
| FR-069 | The system shall prevent completion of a component while required values are missing. |
| FR-070 | The system shall support cargo items as repeatable service components. |
| FR-071 | The system shall support component references to actual service-order containers. |

## Configuration and integration detail retained from drafts

Component configuration has attribute/group/tab assignments, validation/order/trade-direction
filters, version publish/preview/compare/activation/rollback and service-order snapshots.
Preserve historical snapshots rather than reinterpret old orders from new configuration.
`status_router` is registered before generic collection routes. Shared localization, sequences,
storage, crypto, locking, pagination, exceptions and context live in core.
Telegram uses the existing outbox/worker; optional Google Sheets mirroring uses the existing
in-process scheduler. Excel import/export is allowlisted and does not expose arbitrary tables.
No draft module table is used to invent separate customer/agent/port/vessel tables or new pages;
the generated schema and approved page inventory govern actual entities and product scope.

## Smart Settings and integration target

[Integration architecture](integration-architecture.md) owns the source-reviewed settings,
notification, email, backup/restore and IO design, with current versus proposed contracts.
Reuse the modular monolith, outbox, scheduler, storage and shared UI. No new broker, Redis,
required local MinIO or business page. Preserve current Compose/upload storage until an
authorized migration with object/reference verification. [PLAN-0005](../04-implementation/plans/PLAN-0005-settings-integrations.md)
is documentation/planning only, not deployment or runtime acceptance.
