# Software Requirements Specification

## 1. Document Purpose

This Software Requirements Specification (SRS) defines the functional, non-functional, data, security, workflow, accounting, interface, and operational requirements for the Freight Forwarding and Administrative Finance Platform.

The specification is intended for:

- business stakeholders;
- system architects;
- backend and frontend developers;
- QA engineers;
- DevOps engineers;
- implementation and support teams.

Each requirement has a stable identifier so it can be traced to design, implementation, and testing artifacts.

## 2. Product Definition

The product is a single-tenant platform for managing freight-forwarding operations and reusable financial accounting.

The system separates three concepts:

```text
Operational service charge
        ≠
Financial document
        ≠
Accounting journal entry
```

### Operational service charge

A service-order charge is an informational/commercial record. It contains fee types, amounts, descriptions, and optional container links. It may generate a customer-facing note or become the source of a draft finance invoice, but it does not itself post accounting.

### Financial document

A financial document is a reusable business transaction such as a customer invoice, supplier bill, receipt, payment, income, expense, transfer, or adjustment. It may be related to a service order or created independently.

### Accounting journal entry

A journal entry records the double-entry effect of a posted financial document or manual accounting operation. Every posted journal must balance.

An empty (freshly migrated) database exposes a one-time **first-run setup** flow that provisions the permission catalog, the built-in Platform Administrator role, the administrator credential, the current-year document sequences and the default app info/config. No finance or business data is seeded, and no additional roles are created — every other role is entered manually from Roles & Permissions. Setup is accepted only while no user exists. Dashboard and report figures are served by the backend reporting API.

## 3. Scope

### 3.1 In scope

The platform is **single-tenant**: organizations and branches were removed from the schema and product (migration `b7f1c2a9d4e0_remove_organization_and_branch.py`), and there is no organization or branch scope anywhere.

- Authentication, users, sessions, roles, permissions, and audit logs.
- Permission-based authorization governed entirely by users, roles, and permissions.
- Master data.
- Dynamic service-component templates.
- Quotations and immutable revisions.
- Explicit quotation-to-service-order conversion.
- Service-order operations.
- Cargo, containers, transport, customs, milestones, and attachments.
- Informational service-order charges.
- Reusable financial documents.
- Customer and supplier settlement.
- Chart of accounts.
- Accounting periods.
- Double-entry journal posting.
- Payment allocation.
- Reports and exports.

### 3.2 Out of scope for the baseline release

- Automated customs submission.
- Full inventory management.
- Payroll.
- Multi-company consolidation.
- Automated bank feeds.
- Automated tax filing.
- Advanced budgeting.
- Foreign-exchange revaluation.
- Automated supplier-rate negotiation.

## 4. Definitions

| Term | Definition |
|---|---|
| Organization / Branch | Removed from the schema and product; the platform is single-tenant and no longer models either entity |
| Business party | Customer, supplier, carrier, broker, or other counterparty |
| Trade direction | Import, export, transit, re-export, or another movement direction |
| Place | Administrative area, customs zone, SEZ, checkpoint, port, airport, warehouse, or destination |
| Component template | Configurable structure defining attributes for an operational component |
| Service component | Runtime instance of a template attached to a service order |
| Service charge | Informational customer-fee record under a service order |
| Financial document | Reusable invoice, bill, receipt, payment, income, expense, transfer, or adjustment |
| Journal entry | Accounting record containing balanced debit and credit lines |
| Posting | Finalizing a financial document and recording its journal effect |
| Scope | The set of permission codes granted to a user through roles; there is no organization or branch scope |

## 5. User Classes

### UR-001 Platform administrator

Manages the platform, system roles, global configuration, and technical support operations. This role is built in and provisioned at first-run setup with every permission code.

### UR-002 Administrator

Manages users, roles, operational configuration, and global application settings.

### UR-003 Operations manager

Manages operations, reviews operational work, and holds broad quotation and service-order permissions.

### UR-004 Sales officer

Creates quotations, revisions, customer-facing documents, and commercial records.

### UR-005 Operations officer

Creates and processes service orders, components, containers, milestones, and attachments.

### UR-006 Finance officer

Creates financial documents, receipts, payments, allocations, and journal entries.

### UR-007 Finance manager

Posts or reverses financial documents, manages accounting periods, and reviews accounting.

### UR-008 Auditor

Reads authorized operational, financial, accounting, and audit records without changing them.

> The eight roles above correspond to the code-defined role templates (`ROLE_DEFINITIONS`) documented in `docs/11_permissions_matrix.md`. Only Platform Administrator is provisioned automatically; the other seven must be created from Roles & Permissions, and custom roles may be defined as needed.

## 6. General Functional Requirements

### 6.1 Context and tenancy

The platform is single-tenant. Every request is authorized against an authenticated user and the effective permissions derived from that user's active role assignments. There is no organization or branch context.

**FR-001** The system shall require every protected request to have an active user context.

**FR-002** The system shall resolve the requesting user's effective permissions from active role assignments before authorizing an action.

**FR-003** The system shall reject a request when the required permission is not granted.

**FR-004** The system shall attach a request identifier and correlation identifier to each request for tracing and audit.

**FR-005** A granted permission shall apply to all records of the corresponding module, since the platform is single-tenant.

**FR-006** The system shall deny access when no active role assignment grants the requested permission.

**FR-007** The system shall treat future-dated and expired role assignments as inactive when computing effective permissions.

**FR-008** The system shall apply authorization on the server side for every protected endpoint.

**FR-009** The system shall not use frontend filtering as a security mechanism.

### 6.2 Authentication

**FR-010** The system shall authenticate users using username or email and password, unless an external identity provider is configured.

**FR-011** The system shall store application passwords only as one-way password hashes.

**FR-012** The system shall support logout and session revocation.

**FR-013** The system shall support refresh-token rotation or equivalent secure session renewal.

**FR-014** The system shall support password reset using a time-limited, single-use token.

**FR-015** The system shall track failed login attempts.

**FR-016** The system shall temporarily lock or throttle an account after configured failed-attempt thresholds.

**FR-017** The system shall record successful and failed authentication events in the audit log.

**FR-018** The system shall allow an administrator to disable a user and revoke active sessions.

### 6.3 Users and roles

**FR-019** Administrators shall create, invite, activate, suspend, lock, and disable users.

**FR-020** The system shall support roles containing multiple permissions.

**FR-021** The system shall support assigning multiple roles to one user.

**FR-022** The system shall support an optional start date (`starts_at`) on a role assignment.

**FR-023** The system shall support an optional expiry date (`expires_at`) on a role assignment.

**FR-024** Role assignments that are not yet started or that have expired shall not contribute permissions.

**FR-025** The system shall calculate effective permissions from active role assignments.

**FR-026** Permission changes shall be auditable.

**FR-027** The system shall deny access when no active assignment grants the requested permission.

### 6.4 Audit

**FR-028** The system shall record the actor, action, target entity, result, timestamp, and request correlation identifier for audited actions.

**FR-029** The system shall audit financial posting, reversal, allocation, period closure, permission changes, credential retrieval, and authorization denial.

**FR-030** The system shall not include plaintext passwords, tokens, or encryption keys in audit payloads.

**FR-031** Authorized users shall search audit records by actor, event type, entity, result, and date range.

## 7. Organization and Branch Requirements (Removed)

The organization and branch capability has been **removed** from the schema and product (migration `b7f1c2a9d4e0_remove_organization_and_branch.py`). There are no `organization_id` or `branch_id` columns, no organization or branch scope, and no organization or branch administration in the product. Access is governed entirely by users, roles, and permissions, with role assignments carrying optional start/expiry dates. The requirements below are retained for traceability and are **not applicable** to the current implementation; the permission-management capability that replaces them is specified in Section 6.3.

**FR-032** *(Removed)* Organization creation is not applicable; the platform is single-tenant.

**FR-033** *(Removed)* Branch entities are not modelled; there is no parent-organization relationship.

**FR-034** *(Removed)* Organization-relative branch codes are not applicable.

**FR-035** *(Removed)* The head-office designation is not applicable.

**FR-036** *(Removed)* Branch contact, address, and place details are not maintained.

**FR-037** *(Removed)* Users are not assigned to branches; access is granted through roles.

**FR-038** *(Removed)* There is no default-branch selection for a user.

**FR-039** *(Removed)* The interface does not display an active organization or branch context.

**FR-040** *(Removed)* There are no organization or branch selectors.

**FR-041** *(Removed)* Records do not carry a branch identifier.

**FR-042** *(Removed)* There is no organization-wide ownership tier; all records are global to the single tenant.

## 8. Master Data Requirements

**FR-043** The system shall manage trade directions with stable codes and names.

**FR-044** The system shall manage places with categories, parent relationships, addresses, and optional coordinates.

**FR-045** The system shall manage physical container types with size, kind, ISO code, dimensions, and weight attributes.

**FR-046** The system shall manage transport types.

**FR-047** The system shall manage reusable transport assets with identity, identity type, owner, and operator.

**FR-048** The system shall manage fee types.

**FR-049** The system shall manage shared business parties.

**FR-050** The system shall assign multiple roles to a business party.

**FR-051** The system shall support customer, supplier, carrier, broker, and transport-operator roles.

**FR-052** The system shall deactivate master records instead of deleting records referenced by historical transactions. Reference records (Master Data and Configuration) expose their status from each list row's action menu, and an active record cannot be deleted until it is deactivated; the API rejects deleting an active reference record with a conflict.

**FR-053** The system shall reject references to inactive records for new transactions unless explicitly permitted.

**FR-054** The system shall store customer customs credentials separately from the party profile.

**FR-055** The system shall encrypt or externally reference retrievable customs passwords.

**FR-056** Only authorized users shall retrieve customs passwords.

**FR-057** Password retrieval shall require audit logging and may require a reason.

## 9. Dynamic Component Requirements

**FR-058** Administrators shall create component groups.

**FR-059** Administrators shall create versioned component templates.

**FR-060** A template shall define attributes with code, label, data type, input type, required status, repeatability, display order, and validation rules.

**FR-061** Administrators shall configure templates per trade direction and component group.

**FR-062** Direction-specific configuration shall define whether a component is required and repeatable.

**FR-063** The system shall create runtime service components from configured templates.

**FR-064** The system shall automatically create required non-repeatable components during service-order creation.

**FR-065** The system shall allow users to add repeatable components manually.

**FR-066** The system shall store component values vertically using typed values or structured JSON where appropriate.

**FR-067** The system shall validate component values against the template data type and rules.

**FR-068** The system shall preserve the template version used by each service component.

**FR-069** The system shall prevent completion of a component while required values are missing.

**FR-070** The system shall support cargo items as repeatable service components.

**FR-071** The system shall support component references to actual service-order containers.

## 10. Quotation Requirements

**FR-072** Users shall create a quotation with customer and trade direction.

**FR-073** A quotation shall contain one or more revisions.

**FR-074** A revision shall contain currency, dates, descriptions, places, transport options, container requirements, and pricing lines.

**FR-075** A revision shall support multiple container types and quantities.

**FR-076** A pricing line shall optionally reference a container requirement.

**FR-077** A pricing line shall support fee type, description, quantity, unit, unit price, discount, tax, and calculated total.

**FR-078** The quotation revision shall use one currency for all lines.

**FR-079** The system shall calculate and display subtotal, discount, tax, and total amounts.

**FR-080** A draft revision shall be editable.

**FR-081** A sent revision shall be immutable.

**FR-082** Users shall create a new revision when changing a sent revision.

**FR-083** The new revision shall copy the previous revision's commercial details unless the user changes them.

**FR-084** The system shall record accepted, rejected, expired, superseded, converted, and cancelled states.

**FR-085** Only an accepted revision shall be eligible for conversion.

**FR-086** Conversion shall require an explicit user action.

**FR-087** Conversion shall be idempotent and shall not create duplicate service orders for the same accepted revision unless explicitly configured.

> Note: the streamlined UI exposes two quotation actions — **Save** (create/edit a draft; a draft with unsaved changes shows Save instead of Accept) and **Accept**. Accepting a saved draft performs send, acceptance and conversion in one explicit user action, then opens the created service order. The underlying revision state machine below is unchanged and remains available through the API.

## 11. Service-Order Requirements

**FR-088** The system shall create globally unique service-order numbers.

**FR-089** A service order shall preserve customer, trade direction, currency, description, and source-revision snapshots.

**FR-090** A service order shall use a simple `ACTIVE` / `INACTIVE` status. A saved order defaults to `ACTIVE`; the status is changed from the record's row action menu rather than the form. An active order cannot be deleted until it is deactivated, and the API rejects deleting an active order with conflict code `ORDER_ACTIVE`.

**FR-091** The system shall copy quotation container requirements to the service order.

**FR-092** The system shall keep container requirements separate from actual containers.

**FR-093** Users shall add actual containers with unique container numbers.

**FR-094** Users shall record container type, seal, status, net weight, and gross weight.

**FR-095** The system shall validate gross weight is not lower than net weight when both are present.

**FR-096** Users shall create, update, and complete service components according to their permissions.

**FR-097** Users shall attach files to service orders and components.

**FR-098** The system shall preserve operational history for completed components and orders.

## 12. Service-Charge Requirements

**FR-099** Users shall create an informational service charge under a service order.

**FR-100** A service charge shall contain charge number, document type, date, currency, status, totals, and remarks.

**FR-101** A service charge shall contain multiple fee lines.

**FR-102** A fee line shall optionally reference a fee type.

**FR-103** A fee line shall optionally reference an actual service-order container.

**FR-104** A fee may apply to the whole service order when the container reference is null.

**FR-105** The system shall calculate service-charge totals from charge lines.

**FR-106** Issuing a service charge shall generate a customer-facing service note or configured document.

**FR-107** Issuing a service charge shall not create a journal entry.

**FR-108** Users shall explicitly convert a service charge into a draft financial invoice when accounting is required.

**FR-109** Conversion shall copy source values and shall not create a live mutable link.

**FR-110** Users shall be able to edit the generated financial draft before posting.

## 13. Financial Document Requirements

**FR-111** The finance module shall use one reusable financial-document table for invoices, bills, receipts, payments, income, expenses, transfers, and adjustments.

**FR-112** A financial document shall contain document number, type, date, status, party, currency, description, reference, and amount.

**FR-113** A financial document shall support multiple lines.

**FR-114** A financial line shall contain description, quantity, unit amount, discount, tax, amount, optional fee type, optional service order, optional container, and optional account mapping.

**FR-115** Users shall manually create financial documents unrelated to service orders.

**FR-116** Users shall create financial documents from service-order charges or other operational sources.

**FR-117** The system shall record source relationships for generated financial documents.

**FR-118** Financial documents shall support draft, posted, cancelled, and reversed states.

**FR-119** Draft financial documents shall be editable by authorized users.

**FR-120** Posted financial documents shall be immutable.

**FR-121** The system shall use reversal or adjustment documents for corrections.

**FR-122** The system shall apply configurable posting rules for routine document types.

**FR-123** The system shall allow authorized users to create manual journal entries when posting rules are insufficient.

## 14. Payment and Settlement Requirements

**FR-124** A customer receipt shall be represented as a financial document.

**FR-125** A supplier payment shall be represented as a financial document.

**FR-126** A financial document may contain payment method, financial account, value date, and external reference fields.

**FR-127** The system shall support cash, bank transfer, cheque, card, mobile wallet, and other payment methods.

**FR-128** The system shall support financial accounts such as cash, bank, petty cash, and wallets.

**FR-129** Payment settlement shall use a separate allocation table.

**FR-130** One payment shall be allocatable to multiple target documents.

**FR-131** One target document shall be settleable by multiple payments.

**FR-132** The system shall support partial payment.

**FR-133** The system shall reject allocation greater than available payment balance.

**FR-134** The system shall reject allocation greater than target outstanding balance unless overpayment is explicitly supported.

**FR-135** The system shall validate customer receipts against eligible customer invoices.

**FR-136** The system shall validate supplier payments against eligible supplier bills.

## 15. Accounting Requirements

**FR-137** The system shall maintain a single global chart of accounts.

**FR-138** The system shall support account hierarchy and parent accounts.

**FR-139** The system shall distinguish postable and non-postable accounts.

**FR-140** The system shall maintain global accounting periods.

**FR-141** The system shall reject posting into a closed accounting period.

**FR-142** The system shall create journal entries when eligible financial documents are posted.

**FR-143** A journal entry shall contain one or more journal lines.

**FR-144** Every posted journal entry shall contain at least one debit and one credit.

**FR-145** Every posted journal entry shall satisfy total debits equal total credits.

**FR-146** A journal line shall reference one postable account.

**FR-147** A journal line shall support party, service order, and source-document dimensions.

**FR-148** The system shall support base-currency amounts when the transaction currency differs from the base currency.

**FR-149** The system shall prevent editing posted journal entries.

**FR-150** Reversal journals shall link to the original journal.

**FR-151** The system shall support revenue, expense, receivable, payable, cash, bank, tax, equity, and adjustment account mappings.

**FR-152** The system shall report ledger balances by account, party, service order, and period.

## 16. Attachments and Documents

**FR-153** The system shall store file metadata in PostgreSQL and file content in object storage.

**FR-154** The system shall support attachment links to quotations, revisions, service orders, components, charges, financial documents, and journal sources.

**FR-155** The system shall validate file size, MIME type, authorization, and upload completion.

**FR-156** The system shall calculate and store file checksums where supported.

**FR-157** The system shall support document versions.

**FR-158** The system shall restrict downloads according to permission scope.

**FR-159** The system shall audit sensitive downloads where configured.

## 17. Numbering and Configuration

**FR-160** The system shall allocate quotation, service-order, charge, financial-document, receipt, payment, and journal numbers using transactional sequences.

**FR-161** Number sequences shall be scoped by document type and year.

**FR-162** The system shall prevent duplicate numbers under concurrent requests.

**FR-163** Administrators shall configure global application settings.

**FR-164** Global settings shall apply across the platform; there are no organization or branch overrides.

**FR-165** The system shall preserve the configuration used for historical records where required.

## 18. Reporting Requirements

**FR-166** The system shall report active service orders by customer, direction, and status.

**FR-167** The system shall report service-order charges by fee type and container.

**FR-168** The system shall report issued charges that have not been converted to finance invoices.

**FR-169** The system shall report customer invoices and outstanding receivables.

**FR-170** The system shall report supplier bills and outstanding payables.

**FR-171** The system shall report payments, receipts, and unallocated balances.

**FR-172** The system shall report revenue and expenses by account, party, and service order.

**FR-173** The system shall provide a general ledger report based on posted journal lines.

**FR-174** The system shall provide trial-balance data for a selected period.

**FR-175** Reports shall enforce the same permission and date-range filters as operational screens.

## 19. API Requirements

**FR-176** The API shall expose versioned endpoints under the base path `/api/v1`.

**FR-177** Protected endpoints shall require authentication.

**FR-178** Endpoints shall enforce permission checks.

**FR-179** Write endpoints shall validate request data and business state transitions.

**FR-180** Posting, conversion, reversal, allocation, and sequence allocation shall be idempotent or protected against duplicate execution.

**FR-181** API errors shall use consistent error structures with a code, message, request ID, and optional field errors.

**FR-182** List endpoints shall support pagination, sorting, filtering, and date-range filtering where applicable.

**FR-183** API responses shall not expose secrets, password hashes, tokens, or encrypted credential material.

### 19.1 Endpoint groups

The API is a modular monolith. The current endpoint groups are:

| Group | Paths (under `/api/v1`) | Notes |
|---|---|---|
| Health | `/health` | Liveness probe returning the `{"data": ...}` envelope |
| Setup | `/setup/status`, `/setup/initialize` | First-run provisioning; gated on no users existing |
| Auth, users, roles, permissions | `/auth/*`, `/users`, `/users/{id}`, `/users/{id}/role-assignments`, `/roles`, `/roles/{id}`, `/permissions` | Login/logout/refresh/me, password reset and change, profile/avatar, user and role administration |
| Quotations | `/quotations`, `/quotations/{id}`, `/quotations/{id}/revisions`, `/quotation-revisions/{id}/send`, `/submit`, `/accept`, `/convert` | Quotation and immutable revision lifecycle |
| Service orders | `/service-orders`, `/service-orders/{identifier}`, `/service-orders/{identifier}/dynamic-tabs`, `/containers`, `/components`, `/charges`, `/service-order-components`, `/attachments/*` | Dynamic tabs and rows, containers, components, charges, and attachments |
| Service charges | `/service-charges`, `/service-charges/{id}`, `/service-charges/{id}/issue`, `/service-charges/{id}/create-finance-invoice` | Informational charges and explicit conversion to a finance draft |
| Finance | `/chart-of-accounts`, `/financial-accounts`, `/accounting-periods` (incl. `/{id}/close`), `/document-sequences`, `/posting-rules`, `/financial-documents` (incl. `/post`, `/allocate`, `/reverse`), `/journal-entries` (aliased as `/journals`, incl. `/post`) | Global chart of accounts, financial accounts, periods, sequences, posting rules, documents, and journals |
| Master data and generic collections | `/trade-directions`, `/places`, `/container-types`, `/transport-types`, `/transport-assets`, `/fee-types`, `/business-parties`, plus metadata-driven generic collections, `/service-order-tabs`, `/service-order-columns`, `/ui-schemas/{page}` | Reference CRUD, dynamic tab/column configuration, and UI schemas |
| Settings and search | `/settings/app-info`, `/settings/app-config`, `/settings/reset-data`, `/search`, `/search/ask` | App info/config, email and Telegram connection tests, data reset, and search |
| Backup | `/backup/status`, `/backup/runs`, `/backup/run`, `/backup/restore`, `/backup/test-connection` | Optional Google Sheets mirror plus restore/test utilities |
| Audit | `/audit-events` | Searchable audit trail |
| Reports | `/reports/dashboard`, `/reports/service-orders`, `/reports/quotation-performance`, `/reports/receivables`, `/reports/payables`, `/reports/income`, `/reports/expenses`, `/reports/profitability`, `/reports/financial-summary`, plus `/receivables`, `/payables`, `/profitability` aliases | Backend-served reporting; frontend exposes a catalogue of 12 reports |

## 20. Non-Functional Requirements

### Security

**NFR-001** All external traffic shall use TLS.

**NFR-002** Sensitive credentials shall be encrypted or stored in a secrets manager.

**NFR-003** The system shall follow least privilege for users, services, and secret access.

**NFR-004** Authorization shall be enforced at the API and data-access layers.

**NFR-005** Security-sensitive actions shall be auditable.

### Availability and recovery

**NFR-006** The API shall expose liveness and readiness health checks.

**NFR-007** PostgreSQL backups shall be scheduled and restore-tested.

> Note: in addition to the PostgreSQL dump, an optional in-app Google Sheets backup mirrors **all** database tables automatically (no per-table configuration). It skips the migration marker and the backup engine's own tables, never exports sensitive columns (password/token/secret/credential), and can be run manually or on a schedule from Settings.

**NFR-008** Object storage shall support retention and recovery appropriate to business requirements.

**NFR-009** Background work shall be retryable and observable. *(Deferred: the current release is synchronous and has no background worker.)*

### Performance

**NFR-010** Common list screens shall use indexed filters and pagination.

**NFR-011** Financial posting shall complete atomically without exposing partial journal entries.

**NFR-012** Large files and document rendering shall use asynchronous processing where appropriate. *(Deferred: files currently stream through the API.)*

### Maintainability

**NFR-013** Database changes shall use versioned migrations.

**NFR-014** APIs shall be documented using OpenAPI.

**NFR-015** Modules shall have clear ownership and interfaces.

**NFR-016** Business rules shall be covered by automated unit and integration tests.

### Localization

**NFR-017** The UI shall support Khmer and English labels.

**NFR-018** Date, number, currency, and timezone formatting shall be configurable per user.

### Observability

**NFR-019** Logs shall include request and correlation IDs.

**NFR-020** Metrics shall cover API latency, errors, posting failures, and authorization denials.

**NFR-021** Logs shall not contain passwords, tokens, or secret values.

## 21. State Transition Requirements

### Quotation revision

```text
DRAFT → SENT → ACCEPTED → CONVERTED
DRAFT/SENT → REJECTED
SENT → SUPERSEDED
SENT → EXPIRED
DRAFT/SENT → CANCELLED
```

### Service order

```text
ACTIVE ⇄ INACTIVE
```

Service orders do not use a draft or multi-stage lifecycle. A saved order is
`ACTIVE`; it may be deactivated and reactivated. Only an `INACTIVE` order may be
deleted.

### Financial document

```text
DRAFT → POSTED → REVERSED
DRAFT → CANCELLED
```

### Journal entry

```text
DRAFT → POSTED → REVERSED
DRAFT → VOIDED
```

The API shall reject state transitions not listed or explicitly configured.

## 22. Business Invariants

**INV-001** Effective permissions are the union of the permissions granted by a user's active (started and not expired) role assignments.

**INV-002** A request without an active user context or the required permission must be denied server-side; the platform is single-tenant and has no organization or branch scope.

**INV-003** A sent quotation revision cannot be edited.

**INV-004** Only an accepted quotation revision can be converted.

**INV-005** A service-order charge does not create accounting merely by being issued.

**INV-006** A posted financial document cannot be edited.

**INV-007** A posted journal must balance.

**INV-008** A journal line must use a postable account.

**INV-009** A closed accounting period cannot accept posting.

**INV-010** Payment allocation cannot exceed configured settlement limits.

**INV-011** A financial document source must reference an existing source record of the declared type.

**INV-012** Actual container numbers are unique according to the configured historical-reuse policy.

**INV-013** Required dynamic component attributes must be present before completion.

**INV-014** Sensitive credentials must never be returned in ordinary list or detail responses.

## 23. Acceptance Criteria

The baseline release is acceptable when:

1. Users can authenticate and receive only the permissions granted by their active role assignments.
2. A quotation revision can be created, sent, accepted, and explicitly converted.
3. A service order can contain dynamic repeatable components and actual containers.
4. A service charge can be issued without creating a journal.
5. A service charge can be converted into a draft financial invoice.
6. Standalone income, expense, invoice, receipt, and payment documents use the same reusable model.
7. Posting creates a balanced journal entry.
8. Payments can be partially allocated to invoices or bills.
9. Posted documents and journals cannot be destructively edited.
10. Users cannot perform actions their effective permissions do not grant.
11. Audit logs contain the required actor, action, target, and result data.
12. Required operational and accounting reports reconcile to stored records.

## Appendix A — Frontend surfaces

The frontend is a Nuxt 4 static SPA (`ssr: false`, built with `nuxt generate`) served by nginx, which also reverse-proxies `/api` so the browser is same-origin. Page access is checked with `useAuthStore().canAccessPage(pageId)`, and all data access goes through `app/repositories/*`, which is backed by `app/utils/api/freight-remote.ts` (`REMOTE_ENDPOINTS`).

| Surface | Routes | Purpose |
|---|---|---|
| Public setup and auth | `/setup`, `/auth/login`, `/auth/forget-password`, `/auth/verify-code`, `/auth/reset-password` | First-run provisioning, login, and password reset |
| Dashboard | `/` | Backend-served dashboard summary |
| Operations | `/quotations`, `/service-orders`, `/service-charges` | Quotation lifecycle, service-order operations, and informational charges |
| Finance | `/finance/documents`, `/finance/chart-of-accounts`, `/finance/financial-accounts`, `/finance/journals`, `/finance/accounting-periods` | Financial documents, chart of accounts, financial accounts, journals, and periods |
| Master data | `/master-data/*` | Trade directions, places, container types, transport types, transport assets, fee types, and business parties |
| Configuration | `/configuration/*` | Component groups, component templates, service-order tabs, and trade-direction components |
| Administration | `/administration/users`, `/administration/roles`, `/administration/document-sequences`, `/administration/audit-logs`, `/administration/system-settings` | Users, roles, document sequences, audit logs, and system settings |
| Reports | `/reports/:area/:slug` | Catalogue of 12 reports grouped into operations and finance |
| Print | `/print/:collection/:id` | Printable document views |

The report catalogue exposes: Service Order Register, Service Order Status, Containers, Profitability (operations); Revenue & Expense, Accounts Receivable, Accounts Payable, General Ledger, Trial Balance, Profit & Loss, Balance Sheet, and Cash Flow (finance). Reports filter by party, status, currency, and date as applicable, never by organization or branch.

## Appendix B — API conventions

- **Base path:** every endpoint is served under `/api/v1`; interactive documentation is exposed through OpenAPI.
- **Success envelope:** successful payloads are `{"data": ...}`; list endpoints return `{"data": {"items": [...], "meta": {"page", "page_size", "total"}}}`.
- **Errors:** failures return `{code, message, request_id, field_errors}`. Authorization is `AUTH_REQUIRED` or `ACCESS_DENIED`; not-found references are `REFERENCE_NOT_FOUND`; request validation is `VALIDATION_ERROR`.
- **Error codes:** `AUTH_REQUIRED`, `ACCESS_DENIED`, `REFERENCE_NOT_FOUND`, `VALIDATION_ERROR`, `INVALID_STATE_TRANSITION`, `REFERENCE_ACTIVE`, `ORDER_ACTIVE`, `DUPLICATE_NUMBER`, `DUPLICATE_CONVERSION`, `DUPLICATE_USERNAME`, `DUPLICATE_EMAIL`, `DUPLICATE_ROLE`, `INVALID_RESET_CODE`, `BACKUP_RUNNING`, `SETUP_COMPLETED`, `PERIOD_CLOSED`, `JOURNAL_UNBALANCED`, `DOCUMENT_ALREADY_REVERSED`, `ALLOCATION_EXCEEDS_BALANCE`, `CURRENCY_MISMATCH`.
- **Auth:** the API issues a JWT access token (default 1440 minutes) and a rotating refresh token (default 30 days), accepted as `Authorization: Bearer` or as HttpOnly cookies; cookie-based writes use a CSRF cookie/header pair.
- **Pagination:** list responses carry `items` plus a `meta` object with `page`, `page_size`, and `total`.
- **Request tracing:** `request_id` is returned on errors and included in logs alongside a correlation identifier.
