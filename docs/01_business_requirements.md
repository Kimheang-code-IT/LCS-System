# Business Requirements

## 1. Purpose

The Freight Forwarding and Administrative Platform manages quotations, service
orders, operational components, documents, service charges, payments, expenses,
and double-entry financial records for a single-tenant freight forwarder.

## 2. Business Goals

- Standardize freight-forwarding operations.
- Support Import, Export, Transit, and related trade directions.
- Track dynamic operational components without creating a physical table for
  every component.
- Link services, containers, transport movements, documents, and milestones.
- Generate customer-facing service charges and invoices.
- Maintain reusable financial documents and balanced double-entry accounting
  entries.
- Preserve audit history and document traceability.
- Let administrators extend master data without a source-code change.

## 3. Scope

### In scope

- Master data management, including business parties, dynamic Party Roles,
  Place Roles, trade directions, container types, transport types, transport
  assets, fee types, currencies, and financial accounts.
- Route stops with a configurable Place Role and a free-text location (port,
  warehouse, checkpoint, or destination).
- Dynamic component templates and trade-direction configuration.
- Quotation revisions and conversion to service orders.
- Service-order execution and document attachments.
- Service-order charges and container-linked fee lines.
- Financial documents for invoices, receipts, payments, income, expenses,
  transfers, and adjustments.
- Chart of accounts, accounting periods, posting rules, and double-entry
  journals.
- Payment allocation.
- Audit, authorization, backup, and reporting foundations.
- First-run provisioning of the administrator, the built-in Platform
  Administrator role, and baseline configuration (currency catalog, seeded
  Party Roles and Place Roles, current-year document sequences, and default app
  info/config) on an empty database. All other user roles are created from
  Roles & Permissions.

### Delivered in the current version

- Dashboard KPIs and report tables are served by the backend reporting API.
- First-run setup provisions the initial administrator and baseline
  configuration from the browser (`/auth/setup`).
- Single-tenant runtime: organizations and branches were removed from the
  schema and UI (migration `b7f1c2a9d4e0`); access is governed by users, roles,
  and permissions.
- Explicit quotation flow: Save (draft, editable/deletable) → Send → Accept →
  Convert, with each transition an authorized action; conversion is idempotent.
- Reference data (Master Data and Configuration) and Service Orders expose
  status from each row’s action menu: active rows cannot be deleted until they
  are deactivated. Service orders use `ACTIVE` / `INACTIVE` rather than a
  draft/closed lifecycle.
- Master Data includes an administrator-managed Party Roles screen (`party_roles`
  plus the `business_party_roles` many-to-many table). A role can be renamed or
  deactivated; a role still assigned to a party cannot be deleted.
- The separate Places collection is no longer exposed in Master Data. Migration
  `c3d4e5f6a7b8` preserves the legacy `places` table and its historical
  references; new route stops use a dynamic Place Role plus a free-text location.
- Posting Rules are configurable in the UI and resolved per document type and
  optional fee type; the service layer has a last-resort fallback only.
- Google Sheets backup mirrors supported database tables automatically; sensitive
  columns (passwords, tokens, secrets) are never exported.
- Activity feeds and comments are not shown on quotation or service-order
  documents and lists. Status transitions and high-risk finance operations are
  audited; ordinary field edits are not all written to the audit log.

### Out of scope for the first release

- Full tax-regulatory integration.
- Automated customs-system submission.
- Payroll accounting.
- Inventory accounting.
- Multi-company consolidation.
- Automated supplier-rate procurement.

## 4. Actors

- System administrator.
- Operations officer.
- Sales or quotation officer.
- Finance officer.
- Finance manager.
- Operations manager.
- Auditor or read-only reviewer.

## 5. Core Requirements

### BR-001 Master data

The system shall manage trade directions, Party Roles, Place Roles, container
types, transport types, transport assets, fee types, currencies, financial
accounts, chart-of-accounts records, and business parties.

### BR-002 Shared business parties

One business party shall be able to hold multiple administrator-managed roles,
such as customer, supplier, carrier, customs broker, or transport operator. New
active roles shall become selectable without a deploy; inactive roles shall not
be offered for new assignments.

### BR-003 Dynamic operations

The system shall support configurable service components grouped by business
category and configured per trade direction. Configuration is versioned and
snapshotted into service orders.

### BR-004 Quotations

Users shall create quotations containing multiple revisions, route stops,
transport options, container requirements, and pricing lines.

### BR-005 Explicit conversion

Only an authorized user action shall convert an accepted quotation revision into
a service order. Conversion is idempotent and returns the existing order when a
revision has already been converted.

### BR-006 Service orders

The system shall track service-order `ACTIVE` / `INACTIVE` status, requirements,
actual containers, operational components, documents, and milestones. An active
order must be deactivated before it can be deleted.

### BR-007 Service charges

A service order shall support informational customer charges consisting of fee
lines, optionally linked to actual containers. A service charge shall not itself
be an accounting journal entry.

### BR-008 Financial documents

The finance module shall use one reusable financial-document model for invoices,
supplier bills, receipts, payments, income, expenses, transfers, and
adjustments.

### BR-009 Double-entry accounting

Every posted journal entry shall contain balanced debit and credit lines.

### BR-010 Payment allocation

Payments shall be allocatable to one or more invoices or bills, with support for
partial settlement. Allocation shall never exceed the payment amount or the
target balance.

### BR-011 Traceability

Financial documents generated from service-order charges shall retain their
source relationship.

### BR-012 Auditability

Posted financial records and completed operational records shall not be
destructively edited. Corrections shall use reversal or adjustment mechanisms.

## 6. Business Rules

- Quotation revisions become immutable after sending.
- Only an accepted quotation revision may be converted.
- A service-order charge may exist without a financial document.
- A financial invoice may be created manually or from a service-order charge.
- Posting a financial document creates or links a journal entry.
- A posted journal must balance.
- Historical exchange rates are snapshotted on the posting and are not
  recalculated from newer rates.
- Closed accounting periods reject new postings.
- Payment allocation cannot exceed the available payment amount or target
  balance.
- User passwords are Argon2id hashes and are never retrievable; API tokens and
  integration secrets are stored as hashes or secret references.
- Actual containers are distinct from container requirements.
- A service-order component uses the template version captured when it was
  created.
- A role or other master record referenced by business data is deactivated
  instead of deleted.

## 7. Success Criteria

- Operations can process a service order without custom tables for every service
  component.
- Administrators can add, rename, deactivate, and assign Party Roles entirely
  through the UI.
- Finance can record both service-order-related and standalone transactions.
- Management can determine customer receivables, supplier payables, income,
  expenses, and service-order profitability.
- Every posted accounting entry is balanced and traceable to its source.
