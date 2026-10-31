# System Architecture

## Product context

LCS centralizes freight forwarding and accounting for one deployment's business.
The [design brief](09-design-brief.md) defines the 44-page scope and approved requirements.
Runtime is single-tenant; organization/branch scoping is not part of the current design.

## Architecture and request flow

Nuxt 4 static SPA → nginx same-origin `/api/` proxy → FastAPI `/api/v1` routers
→ application services → repositories/models → PostgreSQL.
Redis supports configured caching/rate limiting; S3-compatible storage holds attachments.
The SPA uses TypeScript, Nuxt UI, Tailwind, Pinia, repository factories, and HTTP repositories.
Auth is session-bound; Casbin decides authorization before protected business access.

## Major modules and responsibilities

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

Source: [router registration](../backend/app/api/v1/router.py),
[detailed boundaries](05_solution_architecture.md), and [frontend design](08_frontend_and_ui_design.md).
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

Preserve the modular monolith, existing REST conventions, PostgreSQL, and accounting engine.
Do not add microservices, Kubernetes, GraphQL, external identity providers, or another ledger
without demonstrated need and explicit approval. No external AI/LLM is required at runtime.
AI-assisted development tooling is separate from runtime requirements.
Existing backup scheduler and Telegram processing run in-process; document reliability gaps
before proposing a dedicated queue. No infrastructure is added by this foundation.

## Deployment direction and evidence limits

Hostinger VPS with Compose/nginx is the approved intended baseline. Live host resources,
connectivity, service health, cost, and capacity remain unverified.
See [operations](06-operations-runbook.md) and [ADR log](07-adr-log.md).

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
