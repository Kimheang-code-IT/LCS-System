# Design Brief and Approved Requirements

## Problem and users

Disconnected records cause repeated quotation/order entry, manual invoice/payment tracking,
weak cost/profitability visibility, inconsistent documents, slow reporting and poor traceability.
Specific use of Excel, paper, messaging or another system is unconfirmed.
Users include administrators, sales/quotation officers, operations officers/managers, finance
officers/managers and auditors/read-only reviewers. Personnel assignments remain unconfirmed.

## Goals and scope

Centralize the [approved business journey](../02-business/workflows.md), preserve financial correctness,
reduce unnecessary fields/re-entry, and provide secure, traceable reporting.
Exactly 44 business pages are approved: Dashboard 1; Operations 7; Finance & Accounting 14;
Master Data 12; Configuration 4; Administration 6. Archive and Audit Logs are Administration.
The complete named inventory and routes are in the
[Approved 44-page inventory](#approved-44-page-inventory). S01 verifies actual page/capability
mappings; the superseded draft's permission guesses were not retained as requirements.
Supporting routes are outside the count.

## Smart Settings and Integration scope extension (2026-11-04)

The current request adds detailed documentation/planning for two-destination Telegram,
transactional email and secure recovery, security configuration, encrypted R2/Drive backup and
coordinated restore, and reusable Master Data/Configuration bulk IO. Preserve working features,
five Settings tabs and the 44-page boundary. No implementation, provider, infrastructure or
production-data authorization is implied.

Canonical extension IDs: SET-001/002, MAIL-001, REC-001 and SEC-001 in
[settings/provider specification](../03-development/settings-and-provider-configuration.md);
NOT-001–005 in [notifications](../02-business/notification-requirements.md);
BAK-001–008 in [recovery](../02-business/backup-and-recovery.md);
IO-001–007 in [import/export](../02-business/import-export-requirements.md).
[Inventory/architecture](../01-architecture/integration-architecture.md) and
[PLAN-0005](../04-implementation/plans/PLAN-0005-settings-integrations.md) own source evidence and
dependency-aware tasks. Existing LCS/FR/BR priorities remain stable; this documentation request
does not promote all optional integrations to mandatory release blockers. Operational targets,
owners and provider spending remain explicit open decisions.

## Requirement IDs and priorities

These foundation IDs trace the approved discovery decisions. Existing BR/FR/NFR/INV/UR IDs
are preserved in the canonical topic traceability tables; do not renumber them.

| ID | Requirement | Priority |
|---|---|---|
| LCS-001 | Essential actions across all 44 pages; supporting routes preserved | Must |
| LCS-002 | Session authentication, logout/invalidation, Casbin page/action/API enforcement; protected Super Administrator | Must |
| LCS-003 | Reusable quotation conversion retains required snapshots and prevents duplicate execution of one booking request | Must |
| LCS-004 | Configured operations, containers, snapshots, attachments and service charges | Must |
| LCS-005 | Source-linked financial drafts, authorized posting, standalone documents | Must |
| LCS-006 | Decimal, balanced/atomic/unique posting, immutable history, reversal and open-period controls | Must |
| LCS-007 | Customer/supplier settlement; partial/full allocation within balances | Must |
| LCS-008 | Operational and financial reports reconcile with their correct sources | Must |
| LCS-009 | Important financial/security audit events and protected history | Must |
| LCS-010 | Documents, authorized files, applicable accurate bilingual printing | Must |
| LCS-011 | en/km/zh localization; switching and complete messages | Must |
| LCS-012 | Daily encrypted off-host PostgreSQL backup and coordinated, tested recovery | Must |
| LCS-013 | Validation, refusal paths, security and synthetic end-to-end acceptance evidence | Must |
| LCS-014 | Required master data, configuration and administration workflows | Must |
| LCS-015 | Chrome/Edge/Firefox/Safari compatibility; desktop/laptop access | Must |
| LCS-016 | Keyboard, focus, labels, contrast, forms/dialog/table accessibility | Must; WCAG compliance target proposed |
| LCS-017 | Telegram improvements, optional usability, anonymized business scenarios | Should |
| LCS-018 | Google Sheets mirror enhancements and nonessential integrations | Could |
| LCS-019 | Tablet and essential mobile-browser viewing/navigation | Should |

Page inclusion does not make all optional advanced features mandatory. Preserve implemented
integrations; optional enhancements do not block release unless needed for a Must requirement
or explicitly committed. No new second-person approval workflow is required.

## Non-goals

No native mobile app, additional approved business pages, multi-tenant SaaS, customer/agent portals, real-time
GPS, payroll, inventory accounting, multi-company consolidation, automated customs submission,
supplier-rate procurement or full tax-regulatory integration. Do not add tax workflows from
historical tax fields. No framework/provider migration or replacement accounting engine.

## Success criteria and acceptance

The 2026-11-04 documentation master task adds detailed targets in
[Smart ERP requirements](../02-business/accounting-and-posting.md), with page contracts in
[feature inventory](feature-inventory.md). Period Closing is specified inside the existing
Accounting Periods page; a separate navigation page remains proposed, not a 45th approved page.
Quotation reuse means multiple intentional SOs are valid; LCS-003 prevents duplicate execution
of one request, not another legitimate booking. Save/Finish are operational, not posting events.

All required workflows work without lost conversion data; postings balance and are atomic,
unique and immutable; allocations stay within balances; closed periods reject postings;
backend permissions deny unauthorized actions; reports reconcile; important actions are audited.
Required tests, localization, printing and safe backup/restore validation must pass.
Critical/high-priority defects are resolved before production approval.
Proposed sign-off responsibilities: business stakeholders for operations, finance for results,
technical lead for architecture/security/integration/tests, project owner for final acceptance.
Named assignments are TBD. Synthetic representative scenarios are mandatory; safely authorized
anonymized real cases are Should. Never label business acceptance complete without required approval.

## Non-functional constraints and open requirements

Small-to-medium business context; 10–30 concurrent users is a preliminary assumption only.
Total users, approved concurrency, annual order/document volume, attachment sizes/storage and
growth are TBD. Define realistic datasets before load testing.
Proposed p95: typical reads <500 ms, common actions <2 s, complex reports <5 s subject to volume.
These are not acceptance thresholds or measured capabilities. Use server pagination/filtering,
avoid N+1/unnecessary requests, backend reporting and safe concurrent transactions.
RPO 24 hours / RTO 4 hours, WCAG 2.2 AA and USD 35/month are unapproved proposals.
Planned coordinated maintenance is acceptable; availability percentage remains TBD.
Financial/file/audit/application-log/backup retention, residency, personal-data deletion,
legal/contractual rules and named operational owners are TBD. No automatic purge.
Hosting budget coverage and actual service costs remain unassessed.
See [operations](../03-development/deployment-guide.md) for mandatory recovery/monitoring controls.

## UI direction

Reuse existing Nuxt UI/Tailwind patterns and branding; minimize repeated input and unnecessary
fields. Maintain keyboard access, visible focus, accessible labels, readable contrast,
responsive dialogs/tables and clear field errors. Desktop/laptop are Must; tablet/mobile
viewing are Should. Do not claim audited accessibility conformance without evidence.

## Approved 44-page inventory

This replaces the reviewed draft inventory without adding or removing a page.
Source navigation: `frontend/app/composables/layout/useMenu.ts`; report routes:
`frontend/app/config/freight-reports.ts`; permission candidates:
`frontend/app/utils/freight/page-access.ts` and existing Casbin compilation.
The old draft's guessed view-permission labels are not an authority; S01 verifies actual grants.

| Category | Approved business page | Route |
|---|---|---|
| Dashboard | Dashboard | `/` |
| Operations | Quotations | `/quotations` |
| Operations | Service Orders | `/service-orders` |
| Operations | Service Charges | `/service-charges` |
| Operations | Service Order Register | `/reports/operations/service-orders` |
| Operations | Service Order Status | `/reports/operations/service-order-status` |
| Operations | Containers | `/reports/operations/containers` |
| Operations | Profitability | `/reports/operations/profitability` |
| Finance & Accounting | Financial Documents | `/finance/documents` |
| Finance & Accounting | Chart of Accounts | `/finance/chart-of-accounts` |
| Finance & Accounting | Financial Accounts | `/finance/financial-accounts` |
| Finance & Accounting | Journal Entries | `/finance/journals` |
| Finance & Accounting | Accounting Periods | `/finance/accounting-periods` |
| Finance & Accounting | Posting Rules | `/finance/posting-rules` |
| Finance & Accounting | Revenue & Expense | `/reports/finance/revenue-expense` |
| Finance & Accounting | Accounts Receivable | `/reports/finance/accounts-receivable` |
| Finance & Accounting | Accounts Payable | `/reports/finance/accounts-payable` |
| Finance & Accounting | General Ledger | `/reports/finance/general-ledger` |
| Finance & Accounting | Trial Balance | `/reports/finance/trial-balance` |
| Finance & Accounting | Profit & Loss | `/reports/finance/profit-loss` |
| Finance & Accounting | Balance Sheet | `/reports/finance/balance-sheet` |
| Finance & Accounting | Cash Flow | `/reports/finance/cash-flow` |
| Master Data | Business Parties | `/master-data/business-parties` |
| Master Data | Party Roles | `/master-data/party-roles` |
| Master Data | Place Roles | `/master-data/place-roles` |
| Master Data | Trade Directions | `/master-data/trade-directions` |
| Master Data | Container Types | `/master-data/container-types` |
| Master Data | Transport Types | `/master-data/transport-types` |
| Master Data | Transport Assets | `/master-data/transport-assets` |
| Master Data | Asset Identity Types | `/master-data/asset-identity-types` |
| Master Data | Capacity Units | `/master-data/capacity-units` |
| Master Data | Fee Types | `/master-data/fee-types` |
| Master Data | Currencies | `/master-data/currencies` |
| Master Data | Document Types | `/master-data/document-types` |
| Configuration | Component Attributes | `/configuration/component-attributes` |
| Configuration | Component Groups | `/configuration/component-groups` |
| Configuration | Component Tabs | `/configuration/component-tabs` |
| Configuration | Configuration Versions | `/configuration/versions` |
| Administration | User Management | `/administration/users` |
| Administration | Roles & Permissions | `/administration/roles` |
| Administration | Document Sequences | `/administration/document-sequences` |
| Administration | Settings | `/administration/system-settings` |
| Administration | Archive | `/administration/archive` |
| Administration | Audit Logs | `/administration/audit-logs` |

Counts: 1 + 7 + 14 + 12 + 4 + 6 = 44. Authentication, create/edit/detail, print and error
routes remain supporting routes. No application route is deleted by this cleanup.

## Legacy requirement traceability

Stable identifiers migrated from the reviewed SRS. These are requirements, not assertions
that implementation or acceptance has passed. The approved LCS scope/priorities govern;
retired IDs and deferred advanced capabilities do not create extra pages or new workflows.

| ID | Requirement |
|---|---|
| FR-032 | *(Removed)* Organization creation is not applicable; the platform is single-tenant. |
| FR-033 | *(Removed)* Branch entities are not modelled; there is no parent-organization relationship. |
| FR-034 | *(Removed)* Organization-relative branch codes are not applicable. |
| FR-035 | *(Removed)* The head-office designation is not applicable. |
| FR-036 | *(Removed)* Branch contact, address, and place details are not maintained. |
| FR-037 | *(Removed)* Users are not assigned to branches; access is granted through roles. |
| FR-038 | *(Removed)* There is no default-branch selection for a user. |
| FR-039 | *(Removed)* The interface does not display an active organization or branch context. |
| FR-040 | *(Removed)* There are no organization or branch selectors. |
| FR-041 | *(Removed)* Records do not carry a branch identifier. |
| FR-042 | *(Removed)* There is no organization-wide ownership tier; all records are global to the single tenant. |
| FR-043 | The system shall manage trade directions with stable codes and names. |
| FR-044 | The system shall manage administrator-defined route-stop roles and store a free-text location on each route stop. The separate Places collection is no longer exposed; migration `c3d4e5f6a7b8` preserves the legacy table and historical references, and `d4e5f6a7b8c9` guards those structures. |
| FR-045 | The system shall manage physical container types with size, kind, ISO code, dimensions, and weight attributes. |
| FR-046 | The system shall manage transport types. |
| FR-047 | The system shall manage reusable transport assets with identity, identity type, owner, and operator. |
| FR-048 | The system shall manage fee types. |
| FR-049 | The system shall manage shared business parties. |
| FR-050 | The system shall assign multiple administrator-managed Party Roles to a business party. |
| FR-051 | The system shall let administrators create, rename, deactivate, and delete Party Roles. Customer, Supplier, and Company are seeded as initial data; carrier, customs broker, transport operator, and other roles are administrator-created. None are hardcoded UI options. A role still assigned to a party cannot be deleted. |
| FR-052 | The system shall deactivate master records instead of deleting records referenced by historical transactions. Reference records (Master Data and Configuration) expose their status from each list row's action menu, and an active record cannot be deleted until it is deactivated; the API rejects deleting an active reference record with a conflict. |
| FR-053 | The system shall reject references to inactive records for new transactions unless explicitly permitted. |
| NFR-001 | All external traffic shall use TLS. |
| NFR-002 | Sensitive credentials shall be encrypted or stored in a secrets manager. |
| NFR-003 | The system shall follow least privilege for users, services, and secret access. |
| NFR-004 | Authorization shall be enforced at the API layer; every protected endpoint shall declare a permission dependency. |
| NFR-005 | Security-sensitive actions shall be auditable. |
| NFR-006 | The API shall expose liveness and readiness health checks. |
| NFR-007 | PostgreSQL backups shall be scheduled and restore-tested. |
| NFR-008 | Object storage shall support retention and recovery appropriate to business requirements. |
| NFR-009 | Background work shall be retryable and observable. |
| NFR-010 | Common list screens shall use indexed filters and pagination. |
| NFR-011 | Financial posting shall complete atomically without exposing partial journal entries. |
| NFR-012 | Large files and document rendering shall use asynchronous processing where appropriate. |
| NFR-013 | Database changes shall use versioned migrations. |
| NFR-014 | APIs shall be documented using OpenAPI. |
| NFR-015 | Modules shall have clear ownership and interfaces. |
| NFR-016 | Business rules shall be covered by automated unit and integration tests. |
| NFR-017 | The UI shall support English, Khmer, and Simplified Chinese labels; print output is bilingual English + Khmer. |
| NFR-018 | Date, number, currency, and timezone formatting shall be configurable in application settings; the UI language choice may be remembered per browser. |
| NFR-019 | Logs shall include request and correlation IDs. |
| NFR-020 | Metrics shall cover API latency, errors, posting failures, and authorization denials. |
| NFR-021 | Logs shall not contain passwords, tokens, or secret values. |

## Business requirement IDs

| ID | Requirement |
|---|---|
| BR-001 Master data | The system shall manage trade directions, Party Roles, Place Roles, container types, transport types, transport assets, fee types, currencies, financial accounts, chart-of-accounts records, and business parties. |
| BR-002 Shared business parties | One business party shall be able to hold multiple administrator-managed roles, such as customer, supplier, carrier, customs broker, or transport operator. New active roles shall become selectable without a deploy; inactive roles shall not be offered for new assignments. |
| BR-003 Dynamic operations | The system shall support configurable service components grouped by business category and configured per trade direction. Configuration is versioned and snapshotted into service orders. |
| BR-004 Quotations | Users shall create quotations containing multiple revisions, route stops, transport options, container requirements, and pricing lines. |
| BR-005 Explicit conversion | An authorized explicit action creates a Service Order from a selected quotation/revision. One quotation may source multiple intentional orders; replay of the same keyed command returns the original order. Preserve independent historical snapshots and revision history. |
| BR-006 Service orders | Track operational status, requirements, actual containers, copied/override pricing, components, documents and milestones. Save persists operations; Finish records operational completion without accounting posting and protects completed work. Preserve inactive/deletion guards and financial traceability. |
| BR-007 Service charges | A service order shall support informational customer charges consisting of fee lines, optionally linked to actual containers. A service charge shall not itself be an accounting journal entry. |
| BR-008 Financial documents | The finance module shall use one reusable financial-document model for invoices, supplier bills, receipts, payments, income, expenses, transfers, and adjustments. |
| BR-009 Double-entry accounting | Every posted journal entry shall contain balanced debit and credit lines. |
| BR-010 Payment allocation | Payments shall be allocatable to one or more invoices or bills, with support for partial settlement. Allocation shall never exceed the payment amount or the target balance. |
| BR-011 Traceability | Financial documents generated from service-order charges shall retain their source relationship. |
| BR-012 Auditability | Posted financial records and completed operational records shall not be destructively edited. Corrections shall use reversal or adjustment mechanisms. |

BR-005/006 now reflect the current master task's reuse and Save/Finish decisions. This
supersedes the former one-order-per-quotation and Active/Inactive-only requirement wording.
Source evidence is not runtime acceptance; eligibility/replay/snapshot/Finish gaps remain in
the lifecycle and audit. BR-012 protects completed operational history without equating it
with financial settlement or ledger posting.

## Role and term traceability

UR-001 Platform administrator; UR-002 Administrator; UR-003 Operations manager; UR-004 Sales
officer; UR-005 Operations officer; UR-006 Finance officer; UR-007 Finance manager; UR-008
Auditor. These are user responsibilities/templates, not confirmed personnel assignments.
Only the existing protected role is provisioned automatically; other roles are configured.
Business Party Roles are distinct from authorization roles.
Trade directions include import/export/transit; a Place Role classifies a free-text route
location. A component template defines attributes; a service component is its runtime instance.
FR-032–042 remain retired organization/branch IDs, not applicable requirements.
Legacy out-of-scope items also include automated bank feeds, advanced budgeting and FX
revaluation; no implementation of these capabilities is authorized by cleanup.

NFR-007 requires scheduled/restore-tested backups, not Google Sheets alone. NFR-009 background
reliability applies to existing in-process services; the earlier statement that no background
processing exists was obsolete. NFR-020 is a monitoring requirement, not evidence of deployment.
