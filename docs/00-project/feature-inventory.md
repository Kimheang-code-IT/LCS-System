# Feature inventory and page acceptance

Snapshot: 2026-11-04 working tree on dev. Exactly 44 business pages, stable MOD-001–MOD-044.
[Scope authority](requirements.md#approved-44-page-inventory) owns names/routes.
Supporting auth/new/detail/print routes and API-only currency rates do not increase the count.
Period Closing is a proposed workspace inside MOD-013, not a delivered 45th page.

## Evidence and status rules

Sources inspected: frontend route files, freight-modules.ts canonical overrides,
lcs-reference-modules.ts, freight-reports.ts, page/action permission definitions, backend router/
service/model declarations and the critical quotation conversion, SO Save/Finish and period
bodies. Schema fields/constraints remain in [generated SQL](../01-architecture/database-design.sql).
A route/config declaration proves presence, not a successful browser journey. Source review
of a subset does not prove every API/service/model behavior. No runtime tests were run here.

COMPLETE requires executed current acceptance evidence. PARTIAL means implemented paths exist
but required behavior/evidence is incomplete. MISSING means no implementation of the target
was located (rich closing review). NEEDS_REVIEW means insufficient or conflicting evidence.
All 44 pages below are PARTIAL in the whole-page target sense; this does not erase narrower
historical passes in [feature status](feature-status.md) or relevant
[checklist rows](../04-implementation/project-status-checklist.md). Do not copy the old per-AUTH COMPLETE label
to a whole feature. Known gaps are candidates for tests, not proof of failure unless demonstrated.

## Shared page contract

Each record below supplies purpose through its business logic; module/route, columns, forms,
actions, filters, backend/entities, permissions, related modules/automation, status/limits and
acceptance. A profile supplies repeated requirements once:

### Reference profile

Create/edit/detail use the same declared field metadata and shared validation. Search/sort/
pagination are server-backed; filter support must be checked per collection rather than inferred.
Code/name requirements and uniqueness follow collection schemas and DB indexes (including
active-only uniqueness where used). Status comes from policy commands, not arbitrary form edits.
Deactivate before deletion; a referenced/used/system record remains protected. Archive applies
only where the backend registry allows it; never claim universal archive support.
New dropdown selections hide inactive/archived options, but stored historical references remain
visible. Quick Entry uses the module's own fields and create capability and preserves the parent
draft. Import/export is limited to excel_io registry collections, with validation preview and
atomic revalidation on commit. Every page must test duplicate/invalid/missing/refused cases.

### Document profile

List columns and nested read-only source links coexist with permitted create/edit forms.
Server owns totals, references, dates, state and permission decisions. Save failure leaves
persistent field/page errors and user input intact; loading/saving disables duplicate action.
Details retain audit/source history; posted/finished restrictions apply by lifecycle.
Draft deletion and archive are distinct and not universally offered. Print uses authorized
source reads and existing English–Khmer layouts where applicable. No new generic CRUD engine.

### Finance-setup profile

Reuse shared list/form/error handling, but do not infer ordinary reference lifecycle or archive
support. Financial account/period/rule changes require finance invariants, action-specific
permission checks, historical preservation and focused DEEP evidence. Model fields absent from
a page are requirements gaps, not permission to add columns or tables during documentation.

### Configuration profile

Typed metadata and assignments define future configuration. Required/options/reference/range/
regex/order rules are validated server-side. Publish/activate/rollback are explicit protected
commands. Captured SO data continues to use its original version. Existing rows must not be
silently reinterpreted by a new schema. Verify invalid options, used deletion and duplicate
membership; no invented hardcoded attribute vocabulary.

### Administration profile

Apply least privilege, safe inputs, read-only history and protected administrator safeguards.
No secret value is ordinary list/detail data. Audit and archive do not get create/edit forms.
No live reset, external test-message send or restore is authorized by this specification.

### Report profile

Reports are read-only: no create/edit business form, financial transaction or hidden posting.
Declare purpose, columns/grouping, filters/date basis, calculations/currency and full-set totals.
Source/date/formula targets are in [report requirements](../02-business/accounting-and-posting.md#report-and-dashboard-contract).
A generated result states filters/cutoff/currency/freshness; loading/empty/error/stale states
remain visible. No-data displays zero totals plus an explanatory empty state, not fabricated rows.
Drill-down requires source permission. Export/print retain filters, headings, currency and
calculation parity. GL/TB currently have server generation/streaming CSV; other reports must
not claim whole-dataset export or server filtering merely because the UI renders controls.
Print target is readable complete output with applicable bilingual labels, no clipped totals.
Each report requires allowed/denied access, empty results, date boundary/reversal, currency,
pagination/whole-export checks and reconciliation to its stated source.

### Dashboard profile

Read-only summary cards reuse permitted server data. No business form; loading/empty/refusal
and freshness/date context required. Drill-down observes source capabilities; a broad summary
grant is not blanket access to all finance. Target metrics and basis are specified separately.

## Page index

| ID | Page | Route | Package / slice | Whole-page status |
|---|---|---|---|---|
| MOD-001 | [Dashboard](#mod-001) | `/` | P13 / S09–S10 | PARTIAL |
| MOD-002 | [Quotations](#mod-002) | `/quotations` | P05 / S02 | PARTIAL |
| MOD-003 | [Service Orders](#mod-003) | `/service-orders` | P06 / S02–S03 | PARTIAL |
| MOD-004 | [Service Charges](#mod-004) | `/service-charges` | P07 / S04 | PARTIAL |
| MOD-005 | [Service Order Register](#mod-005) | `/reports/operations/service-orders` | P12 / S09 | PARTIAL |
| MOD-006 | [Service Order Status](#mod-006) | `/reports/operations/service-order-status` | P12 / S09 | PARTIAL |
| MOD-007 | [Containers](#mod-007) | `/reports/operations/containers` | P12 / S09 | PARTIAL |
| MOD-008 | [Profitability](#mod-008) | `/reports/operations/profitability` | P12 / S09 | PARTIAL |
| MOD-009 | [Financial Documents](#mod-009) | `/finance/documents` | P08 / S05–S07 | PARTIAL |
| MOD-010 | [Chart of Accounts](#mod-010) | `/finance/chart-of-accounts` | P09 / S05,S08 | PARTIAL |
| MOD-011 | [Financial Accounts](#mod-011) | `/finance/financial-accounts` | P09 / S05–S08 | PARTIAL |
| MOD-012 | [Journal Entries](#mod-012) | `/finance/journals` | P09 / S08 | PARTIAL |
| MOD-013 | [Accounting Periods](#mod-013) | `/finance/accounting-periods` | P09–P10 / S08 | PARTIAL |
| MOD-014 | [Posting Rules](#mod-014) | `/finance/posting-rules` | P09 / S05,S08 | PARTIAL |
| MOD-015 | [Revenue & Expense](#mod-015) | `/reports/finance/revenue-expense` | P11 / S10 | PARTIAL |
| MOD-016 | [Accounts Receivable](#mod-016) | `/reports/finance/accounts-receivable` | P11 / S10 | PARTIAL |
| MOD-017 | [Accounts Payable](#mod-017) | `/reports/finance/accounts-payable` | P11 / S10 | PARTIAL |
| MOD-018 | [General Ledger](#mod-018) | `/reports/finance/general-ledger` | P11 / S10 | PARTIAL |
| MOD-019 | [Trial Balance](#mod-019) | `/reports/finance/trial-balance` | P11 / S10 | PARTIAL |
| MOD-020 | [Profit & Loss](#mod-020) | `/reports/finance/profit-loss` | P11 / S10 | PARTIAL |
| MOD-021 | [Balance Sheet](#mod-021) | `/reports/finance/balance-sheet` | P11 / S10 | PARTIAL |
| MOD-022 | [Cash Flow](#mod-022) | `/reports/finance/cash-flow` | P11 / S10 | PARTIAL |
| MOD-023 | [Business Parties](#mod-023) | `/master-data/business-parties` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-024 | [Party Roles](#mod-024) | `/master-data/party-roles` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-025 | [Place Roles](#mod-025) | `/master-data/place-roles` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-026 | [Trade Directions](#mod-026) | `/master-data/trade-directions` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-027 | [Container Types](#mod-027) | `/master-data/container-types` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-028 | [Transport Types](#mod-028) | `/master-data/transport-types` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-029 | [Transport Assets](#mod-029) | `/master-data/transport-assets` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-030 | [Asset Identity Types](#mod-030) | `/master-data/asset-identity-types` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-031 | [Capacity Units](#mod-031) | `/master-data/capacity-units` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-032 | [Fee Types](#mod-032) | `/master-data/fee-types` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-033 | [Currencies](#mod-033) | `/master-data/currencies` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-034 | [Document Types](#mod-034) | `/master-data/document-types` | P03 / prerequisite slices,S11 | PARTIAL |
| MOD-035 | [Component Attributes](#mod-035) | `/configuration/component-attributes` | P04 / S03,S11 | PARTIAL |
| MOD-036 | [Component Groups](#mod-036) | `/configuration/component-groups` | P04 / S03,S11 | PARTIAL |
| MOD-037 | [Component Tabs](#mod-037) | `/configuration/component-tabs` | P04 / S03,S11 | PARTIAL |
| MOD-038 | [Configuration Versions](#mod-038) | `/configuration/versions` | P04 / S03,S11 | PARTIAL |
| MOD-039 | [User Management](#mod-039) | `/administration/users` | P14 / S01,S11 | PARTIAL |
| MOD-040 | [Roles & Permissions](#mod-040) | `/administration/roles` | P14 / S01,S11 | PARTIAL |
| MOD-041 | [Document Sequences](#mod-041) | `/administration/document-sequences` | P14 / S02–S08,S11 | PARTIAL |
| MOD-042 | [Settings](#mod-042) | `/administration/system-settings` | P14 / S11 | PARTIAL |
| MOD-043 | [Archive](#mod-043) | `/administration/archive` | P14 / S11 | PARTIAL |
| MOD-044 | [Audit Logs](#mod-044) | `/administration/audit-logs` | P14 / S01,S08,S11 | PARTIAL |

<a id="mod-001"></a>

## MOD-001 — Dashboard

- Module / route / profile: reports; `/`; dashboard.
- Main columns: Revenue, expense, profit, AR/AP and operational summary cards.
- Create/edit/detail or filter form: Granularity; target explicit interval/as-of controls.
- Search and filters: day/month/year currently; target date range; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh; navigate to permitted source records.
- Backend contract: GET /reports/dashboard; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines, financial_documents, financial_document_allocations, service_orders.
- Permissions: dashboard.view; backend dashboard.summary/report.read. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Read-only KPIs; target definitions in smart ERP requirements.
- Current status / limitation / recommended improvement: PARTIAL — All requested alerts, period status, role-scoped metrics and arbitrary dates not proven. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Every shown KPI reconciles to its declared source/date/currency; finance-denied users see no restricted values. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P13 / S09–S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-002"></a>

## MOD-002 — Quotations

- Module / route / profile: quotations; `/quotations`; document.
- Main columns: Quotation No., linked SO, Business Party, revision, direction, total, status, creator/time.
- Create/edit/detail or filter form: Party, printed name, direction, date/valid-until, currency, description; route stops; pricing fee/container/basis/qty/rate; revision history.
- Search and filters: Search, party, direction; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit, Save Changes, Submit, Convert, Re-Quotation; authorized print/files.
- Backend contract: /quotations; /quotation-revisions/{id}/submit; /convert; /quotations/{id}/revisions; /quotations/from-service-order/{identifier}; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: quotations, quotation_revisions, quotation_revision_places, quotation_revision_containers, quotation_revision_lines, quotation_conversions.
- Permissions: sales.quotations.view; quotation.create/update/submit/convert/revise per router. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Source-linked copies; unique numbers; server totals; dates and active refs; independent SO pricing.
- Current status / limitation / recommended improvement: PARTIAL — Current conversion has no state gate; latest-revision selection and multi-order UI linkage need verification. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Create two SOs from one offer; same-key retry returns one; quotation/requote edits leave prior SO snapshots intact. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P05 / S02; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-003"></a>

## MOD-003 — Service Orders

- Module / route / profile: operations; `/service-orders`; document.
- Main columns: SO/quotation numbers, party, direction, container count, charges, started/ended, status, creator/time.
- Create/edit/detail or filter form: Selected quotation, copied header/currency/routes, reference numbers, remark; pricing; actual containers; dynamic tabs; files.
- Search and filters: Search, party, direction; only claim server behavior after adapter/handler verification.
- Primary actions: Create/select quotation, Save, Finish; manage permitted operational rows; review finance.
- Backend contract: /service-orders; /service-orders/{identifier}/finish; nested containers/component-tabs/movements/milestones/charges/invoice; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: service_orders, service_order_places, service_order_pricing, service_order_pricing_lines, service_order_containers, service_order_component_rows.
- Permissions: operations.service_orders.view; service_order.create/update; Finish requires service_order.submit. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Save captures quotation; Finish stamps actor/time and locks operations; neither posts; actual boxes are entered manually.
- Current status / limitation / recommended improvement: PARTIAL — ACTIVE_STATUS config vs FINISHED service, completion validation and per-row locking need tests. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Save/Finish leave journal count unchanged; prohibited post-Finish edits denied; financial activity remains possible. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P06 / S02–S03; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-004"></a>

## MOD-004 — Service Charges

- Module / route / profile: operations + finance; `/service-charges`; document.
- Main columns: SC/SO/invoice numbers, party, total, status, creator/time.
- Create/edit/detail or filter form: SO, party, currency, remarks; fee/description/qty/unit amount; source/journal references.
- Search and filters: Search, SO, party, document type, status; only claim server behavior after adapter/handler verification.
- Primary actions: Save Draft, Issue, Print, Create Finance Invoice, View Invoice.
- Backend contract: /service-charges; /service-charges/{id}/issue; /service-charges/{id}/create-finance-invoice; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: service_order_charges, service_order_charge_lines, financial_document_sources.
- Permissions: finance.service_charges.view; service_charge.create/update/issue/convert_to_invoice. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Positive quantities, Decimal totals, container ownership; issue is informational; draft invoice explicit.
- Current status / limitation / recommended improvement: PARTIAL — Cost-side/provenance/manual override metadata and direct-SO/charge duplicate billing not fully verified. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Issue creates no draft/journal; racing conversion yields one source-linked editable draft and no journal. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P07 / S04; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-005"></a>

## MOD-005 — Service Order Register

- Module / route / profile: reports; `/reports/operations/service-orders`; report.
- Main columns: SO, quotation, party, direction, containers, charges, status, creator/time.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: party/status/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/service-orders; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: service_orders, service_order_containers, service_order_charges.
- Permissions: reports.service_order_register.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Register total counts physical containers, not requirements; target revenue/cost/profit separate.
- Current status / limitation / recommended improvement: PARTIAL — Service column and requested financial columns/date basis need verification. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Filtered SO population/count and source-linked totals reconcile. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P12 / S09; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-006"></a>

## MOD-006 — Service Order Status

- Module / route / profile: reports; `/reports/operations/service-order-status`; report.
- Main columns: SO, party, direction, status, days open, pending components, last activity, creator.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: party/status/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: Inspect ReportsView/store adapter; do not infer /reports/service-order-status endpoint; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: service_orders, service_order_component_rows, service_order_milestones.
- Permissions: reports.service_order_status.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Operational state/age/pending work, no accounting status changes.
- Current status / limitation / recommended improvement: PARTIAL — Finished date, updated-date basis, pending-item completeness not proven. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Finish removes stale pending-age indicators as specified; cutoff and missing-data states visible. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P12 / S09; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-007"></a>

## MOD-007 — Containers

- Module / route / profile: reports; `/reports/operations/containers`; report.
- Main columns: Number, type, SO, party, seal, status, net/gross kg.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: party/status; date target; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/container-register; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: service_order_containers → service_orders, container_types.
- Permissions: reports.service_order_containers.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Actual physical boxes; group/count by type/status/SO; gross >= net.
- Current status / limitation / recommended improvement: PARTIAL — Grouping, date cutoff, historical reuse/normalization policy need test evidence. Verify first and implement only demonstrated missing acceptance.
- Acceptance: One physical container counted once; search links correct SO; invalid weight/duplicate number refused at entry. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P12 / S09; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-008"></a>

## MOD-008 — Profitability

- Module / route / profile: reports; `/reports/operations/profitability`; report.
- Main columns: SO, customer, quoted, issued charges, posted revenue/cost, gross profit, margin.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: party/currency/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/service-order-profitability; /reports/profitability; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: service_orders, quotation_revisions, service_order_charges, financial_documents, journal_entry_lines.
- Permissions: reports.service_order_profitability.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Separate quoted/issued/draft/posted layers; profit/margin formula in target.
- Current status / limitation / recommended improvement: PARTIAL — Currency/date/reversal attribution and missing draft column need evidence. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Estimated and posted values labeled and reconcile without mixed-currency addition. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P12 / S09; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-009"></a>

## MOD-009 — Financial Documents

- Module / route / profile: finance; `/finance/documents`; document.
- Main columns: Document/SO, type, party, document date, total, outstanding, status, creator/time.
- Create/edit/detail or filter form: Type, party, SO, document/posting/due/value dates, currency/rate/base, lines, payment method/account/reference, allocations, source/journal.
- Search and filters: Search, type, party, SO, status, currency; only claim server behavior after adapter/handler verification.
- Primary actions: Draft create/edit/delete; Post; Allocate; Reverse; source/journal drill-down.
- Backend contract: /financial-documents; /{id}/post; /allocate; /reverse; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: financial_documents, financial_document_lines, financial_document_sources, financial_document_postings, financial_document_allocations.
- Permissions: finance.financial_documents.view; financial_document.read/create/update/delete/submit/allocate/reverse. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Server totals, eligible accounts, atomic posting, settlement limits, immutable posted history.
- Current status / limitation / recommended improvement: PARTIAL — Type/date/currency/allocation/reversal cases need revision-specific integration evidence. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Invoice + partial/full receipt and supplier equivalent reconcile; denial/duplicate/closed-period attempts leave no partial effects. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P08 / S05–S07; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-010"></a>

## MOD-010 — Chart of Accounts

- Module / route / profile: finance; `/finance/chart-of-accounts`; finance-setup.
- Main columns: Account code/name/type, normal balance, postability, status.
- Create/edit/detail or filter form: Code, name, type, parent, normal balance, postable flag, status via supported command.
- Search and filters: Search, account type/status where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; guarded deactivate/delete.
- Backend contract: /chart-of-accounts; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: chart_of_accounts; journal_entry_lines references.
- Permissions: finance.chart_of_accounts.view; chart_of_accounts.read/create/update/delete. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Unique code, valid parent/hierarchy, active postable account needed for posting.
- Current status / limitation / recommended improvement: PARTIAL — Account-level currency restriction not present in inspected model; parent cycles/reclassification of used accounts need review. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Duplicate/cycle/invalid-posting account refused; historical journals survive account deactivation. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P09 / S05,S08; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-011"></a>

## MOD-011 — Financial Accounts

- Module / route / profile: finance; `/finance/financial-accounts`; finance-setup.
- Main columns: Name/type, ledger account, currency, bank, status.
- Create/edit/detail or filter form: Name/type, linked ledger, currency, bank name, masked account number.
- Search and filters: Search, type, currency, status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; guarded deactivate/delete; target reconciliation review.
- Backend contract: /financial-accounts; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: financial_accounts → chart_of_accounts.
- Permissions: finance.financial_accounts.view; financial_account.read/create/update/delete. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Unique ledger link, valid currency and postable account; balance derived from posted ledger.
- Current status / limitation / recommended improvement: PARTIAL — No standalone bank reconciliation workflow or bank feed proven; unsupported account types need confirmation. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Posted cash/bank movement agrees with linked ledger; invalid or duplicate mapping refused. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P09 / S05–S08; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-012"></a>

## MOD-012 — Journal Entries

- Module / route / profile: finance; `/finance/journals`; document.
- Main columns: Journal/posting date/source/SO, description, debit/credit, status, creator.
- Create/edit/detail or filter form: Entry type/date, posting date, period/source, description; account/party/SO/currency/debit/credit lines.
- Search and filters: Search, type, status, period; only claim server behavior after adapter/handler verification.
- Primary actions: Create/edit manual draft; Post; inspect source/reversal; guarded draft deletion.
- Backend contract: /journal-entries; /journal-entries/{id}/post; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines.
- Permissions: finance.journal_entries.view; journal_entry.read/create/update/post/delete per router. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: At least debit/credit, active postable mappings, balanced base amounts and OPEN period; posted lines immutable.
- Current status / limitation / recommended improvement: PARTIAL — Manual journal FX and reversal behavior require PostgreSQL acceptance; no fabricated edit-posted action. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Balanced journal posts once; unbalanced/closed/denied attempts fail atomically; reversal preserves original. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P09 / S08; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-013"></a>

## MOD-013 — Accounting Periods

- Module / route / profile: finance; `/finance/accounting-periods`; finance-setup.
- Main columns: Period, start/end, status, posting count, closed by/at.
- Create/edit/detail or filter form: Name, start/end, optional description; state action; target close review and reopen reason.
- Search and filters: Search/status where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; Open/Close/Reopen via policy; guarded delete; target review workspace.
- Backend contract: /accounting-periods; /accounting-periods/{id}; /{id}/close; /accountingPeriods/{id}/status; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: accounting_periods, journal_entries, audit_events.
- Permissions: finance.accounting_periods.view; accounting_period.read/create/update/close/reopen/delete. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Custom dates; year/month derived; no overlap; posted-period dates protected; target backend closing review.
- Current status / limitation / recommended improvement: PARTIAL — Same-start-month unique constraint, auto-created OPEN period, generic update state bypass; rich closing MISSING. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Disjoint custom ranges accepted as approved; overlap/closed posting/bypass refused; closure/reopening retains audit history. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P09–P10 / S08; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-014"></a>

## MOD-014 — Posting Rules

- Module / route / profile: finance; `/finance/posting-rules`; finance-setup.
- Main columns: Document type, optional fee, debit/credit/tax accounts, priority, status.
- Create/edit/detail or filter form: Type, fee, description, account mappings, priority, status.
- Search and filters: Search/type/status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; guarded deactivate/delete.
- Backend contract: /posting-rules; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: posting_rules → chart_of_accounts, fee_types.
- Permissions: finance.posting_rules.view; posting_rule.read/create/update/delete. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Fee-specific tier then default; highest priority; validate mapping; STRATEGIES controls journal shape.
- Current status / limitation / recommended improvement: PARTIAL — Arbitrary event/conditions/effective dates/rule names not implemented by inspected form; retain as proposed requirements only if justified. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Rules select deterministically; ambiguous/invalid mappings refused; edits never change old posted lines. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P09 / S05,S08; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-015"></a>

## MOD-015 — Revenue & Expense

- Module / route / profile: reports; `/reports/finance/revenue-expense`; report.
- Main columns: Posting date, SO, party, account, description, revenue, expense.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: party/currency/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/income; /reports/expenses; inspect ReportsView composition; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines, chart_of_accounts.
- Permissions: reports.revenue_expense.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Posted revenue credit−debit and expense debit−credit over posting interval.
- Current status / limitation / recommended improvement: PARTIAL — Screen composition/export filters may differ from server totals. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Posted source totals agree with P&L for same interval/mappings. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-016"></a>

## MOD-016 — Accounts Receivable

- Module / route / profile: reports; `/reports/finance/accounts-receivable`; report.
- Main columns: Invoice, SO, party, invoice/due date, total/paid/outstanding, status.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: party/status/currency/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/receivables; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: financial_documents, financial_document_allocations, journal_entry_lines.
- Permissions: reports.accounts_receivable.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: As-of receivables and effective allocations; due-date aging; unpaid/partial/paid/overdue derived.
- Current status / limitation / recommended improvement: PARTIAL — Historical allocation cutoff, reversals and control bridge need review. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Partial payment and later payment produce correct as-of balance; AR matches control bridge. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-017"></a>

## MOD-017 — Accounts Payable

- Module / route / profile: reports; `/reports/finance/accounts-payable`; report.
- Main columns: Bill, SO, supplier, bill/due date, total/paid/outstanding, status.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: party/status/currency/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/payables; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: financial_documents, financial_document_allocations, journal_entry_lines.
- Permissions: reports.accounts_payable.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: As-of supplier liabilities and allocation aging.
- Current status / limitation / recommended improvement: PARTIAL — Historical cutoff/unapplied payments and reversal handling need review. Verify first and implement only demonstrated missing acceptance.
- Acceptance: AP aged balances and unapplied-payment bridge reconcile to posted control accounts. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-018"></a>

## MOD-018 — General Ledger

- Module / route / profile: reports; `/reports/finance/general-ledger`; report.
- Main columns: Posting date, journal/source/account, description, debit/credit/running balance.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: date/account/party/voucher/currency; generated report filters; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: POST /reports/general-ledger/generate; POST /reports/general-ledger/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines, chart_of_accounts.
- Permissions: reports.general_ledger.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Posted base ledger; opening before interval; stable date/journal/line ordering across pages.
- Current status / limitation / recommended improvement: PARTIAL — Current revision not runtime-tested; print/source drill-down and export format parity need checks. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Page two continues balance; full filtered CSV matches screen totals; posted sources traceable. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-019"></a>

## MOD-019 — Trial Balance

- Module / route / profile: reports; `/reports/finance/trial-balance`; report.
- Main columns: Account code/name, opening/period/closing debit/credit.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: date/fiscal year/account range; generated filters; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: POST /reports/trial-balance/generate; POST /reports/trial-balance/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines, chart_of_accounts.
- Permissions: reports.trial_balance.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Posted base balances, opening + movement = closing; full-set totals, imbalance visible.
- Current status / limitation / recommended improvement: PARTIAL — Fiscal-year filter must coexist with custom periods; current runtime unverified. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Full control set nets zero, account-range subsets labeled; draft excluded and reversal included. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-020"></a>

## MOD-020 — Profit & Loss

- Module / route / profile: reports; `/reports/finance/profit-loss`; report.
- Main columns: Grouped Revenue/Expense accounts and net result statement.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: currency/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/profit-loss; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines, chart_of_accounts.
- Permissions: reports.profit_loss.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Posted period revenue less expenses; consistent account sign/group rules.
- Current status / limitation / recommended improvement: PARTIAL — Date/currency filter and whole-dataset export behavior need evidence. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Net result agrees with ledger and Revenue & Expense over identical interval. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-021"></a>

## MOD-021 — Balance Sheet

- Module / route / profile: reports; `/reports/finance/balance-sheet`; report.
- Main columns: Asset/Liability/Equity groups, totals and difference statement.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: currency/date as-of; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/balance-sheet; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines, chart_of_accounts.
- Permissions: reports.balance_sheet.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Assets = liabilities + equity with current/accumulated result counted once.
- Current status / limitation / recommended improvement: PARTIAL — Retained/current earnings presentation and historical mapping gaps need finance confirmation. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Equation reconciles at cutoff including unclosed current-year result without automatic monthly retained-earnings journal. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-022"></a>

## MOD-022 — Cash Flow

- Module / route / profile: reports; `/reports/finance/cash-flow`; report.
- Main columns: Date, cash account, source, party, description, cash in/out/running balance.
- Create/edit/detail or filter form: Read-only report filters; no business create/edit form.
- Search and filters: currency/date; only claim server behavior after adapter/handler verification.
- Primary actions: Refresh/generate, export/print and permitted drill-down per report profile.
- Backend contract: /reports/cash-flow; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: journal_entries, journal_entry_lines, financial_accounts, chart_of_accounts.
- Permissions: reports.cash_flow.view. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Posted cash/bank movements; opening + net movement = closing; consolidated transfers cancel.
- Current status / limitation / recommended improvement: PARTIAL — Formal direct/indirect statutory classifications not supported by evidence. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Cash movements reconcile to cash/bank GL; no double counting internal transfers. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P11 / S10; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-023"></a>

## MOD-023 — Business Parties

- Module / route / profile: master_data; `/master-data/business-parties`; reference.
- Main columns: Party code/name, roles, contact, phone, status, creator/time.
- Create/edit/detail or filter form: partyCode/legalName required; display name, tax ID, contact, phone/email/address, roleIds.
- Search and filters: role/status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /businessParties; /businessParties/{id}; /businessParties/{id}/status; /excel/businessParties/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: business_parties + business_party_roles.
- Permissions: master.business_parties.view; per-action master.business_parties grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: One party holds multiple dynamic Party Roles; no separate customer/supplier store.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Reject duplicate code/role assignment; preserve referenced history. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-024"></a>

## MOD-024 — Party Roles

- Module / route / profile: master_data; `/master-data/party-roles`; reference.
- Main columns: Code, name, description, status, creator/time.
- Create/edit/detail or filter form: code/name required; description.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /partyRoles; /partyRoles/{id}; /partyRoles/{id}/status; /excel/partyRoles/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: party_roles.
- Permissions: master.party_roles.view; per-action master.party_roles grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Unique code/name; roles become selectable without deploy; delete denied while assigned.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Rename reflects in party displays; inactive role excluded from new assignments. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-025"></a>

## MOD-025 — Place Roles

- Module / route / profile: master_data; `/master-data/place-roles`; reference.
- Main columns: Code/name, sort order, description, status, creator/time.
- Create/edit/detail or filter form: code/name and nonnegative integer sortOrder; description.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /placeRoles; /placeRoles/{id}; /placeRoles/{id}/status; /excel/placeRoles/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: place_roles.
- Permissions: master.place_roles.view; per-action master.place_roles grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Classifies free-text route stops; legacy places retained.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Referenced route-role cannot be destructively deleted; stop location persists. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-026"></a>

## MOD-026 — Trade Directions

- Module / route / profile: master_data; `/master-data/trade-directions`; reference.
- Main columns: Code/name, description, status, creator/time.
- Create/edit/detail or filter form: code/name; description.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /tradeDirections; /tradeDirections/{id}; /tradeDirections/{id}/status; /excel/tradeDirections/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: trade_directions.
- Permissions: master.trade_directions.view; per-action master.trade_directions grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Direction controls operational configuration selection.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Inactive direction rejected on new offer; existing SO snapshots remain. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-027"></a>

## MOD-027 — Container Types

- Module / route / profile: master_data; `/master-data/container-types`; reference.
- Main columns: Code/name, size/ISO, max gross weight, status, creator/time.
- Create/edit/detail or filter form: code/name; size/kind/ISO; length/width/height/max gross; description.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /containerTypes; /containerTypes/{id}; /containerTypes/{id}/status; /excel/containerTypes/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: container_types.
- Permissions: master.container_types.view; per-action master.container_types grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Nonnegative dimensions/weights; referenced by quoted requirements and actual boxes.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Duplicate code/invalid dimension refused; archived type still readable historically. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-028"></a>

## MOD-028 — Transport Types

- Module / route / profile: master_data; `/master-data/transport-types`; reference.
- Main columns: Code/name, description, status, creator/time.
- Create/edit/detail or filter form: code/name; description.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /transportTypes; /transportTypes/{id}; /transportTypes/{id}/status; /excel/transportTypes/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: transport_types.
- Permissions: master.transport_types.view; per-action master.transport_types grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Real transport-type references drive assets and charge basis.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Inactive option excluded from new choices without clearing stored references. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-029"></a>

## MOD-029 — Transport Assets

- Module / route / profile: master_data; `/master-data/transport-assets`; reference.
- Main columns: Code/name, type, identity, capacity, owner, status, creator/time.
- Create/edit/detail or filter form: assetCode, transportType, identityType, identity; optional name, capacityValue/unit, owner/operator, description.
- Search and filters: transport type/status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /transportAssets; /transportAssets/{id}; /transportAssets/{id}/status; /excel/transportAssets/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: transport_assets.
- Permissions: master.transport_assets.view; per-action master.transport_assets grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Identity label/pattern comes from vocabulary; capacity pair, owner/operator from parties; MAINTENANCE supported.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Invalid identity/pair refused; historical inactive type/unit still renders correctly. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-030"></a>

## MOD-030 — Asset Identity Types

- Module / route / profile: master_data; `/master-data/asset-identity-types`; reference.
- Main columns: Name, applicable type, label/pattern, status and attribution where rendered.
- Create/edit/detail or filter form: name, optional transport type, identityLabel/placeholder, validationPattern.
- Search and filters: status/type where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /transportAssetIdentityTypes; /transportAssetIdentityTypes/{id}; /transportAssetIdentityTypes/{id}/status; /excel/transportAssetIdentityTypes/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: transport_asset_identity_types.
- Permissions: master.transport_assets.view; per-action master.transport_assets grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Unique active name; valid bounded regex; filters by transport type.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Malformed/unsafe pattern refused; type edits do not corrupt saved identities. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-031"></a>

## MOD-031 — Capacity Units

- Module / route / profile: master_data; `/master-data/capacity-units`; reference.
- Main columns: Code/name, status and attribution where rendered.
- Create/edit/detail or filter form: code/name; optional description.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /capacityUnits; /capacityUnits/{id}; /capacityUnits/{id}/status; /excel/capacityUnits/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: capacity_units.
- Permissions: master.transport_assets.view; per-action master.transport_assets grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Unique active unit code; assets store code and display label.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Duplicate code refused; historical asset retains unit after deactivation. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-032"></a>

## MOD-032 — Fee Types

- Module / route / profile: master_data; `/master-data/fee-types`; reference.
- Main columns: Code/name, description, status, creator/time.
- Create/edit/detail or filter form: code/name; description and supported classification/defaults.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /feeTypes; /feeTypes/{id}; /feeTypes/{id}/status; /excel/feeTypes/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: fee_types.
- Permissions: master.fee_types.view; per-action master.fee_types grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Shared pricing/charge/posting-rule classification; no inferred ledger effect.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Invalid/duplicate code refused; referenced fees preserved; account resolution tested. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-033"></a>

## MOD-033 — Currencies

- Module / route / profile: master_data; `/master-data/currencies`; reference.
- Main columns: Code/name/symbol, decimal places, status, creator/time.
- Create/edit/detail or filter form: three-letter code/name/decimalPlaces; symbol/numericCode/description.
- Search and filters: status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /currencies; /currencies/{id}; /currencies/{id}/status; /excel/currencies/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: currencies + currency_rates.
- Permissions: master.currencies.view; per-action master.currencies grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Precision 0–6; approved positive effective FX rows maintained by API, no extra rate page.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Invalid code/precision/rate refused; later rates never change posted amounts. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-034"></a>

## MOD-034 — Document Types

- Module / route / profile: master_data; `/master-data/document-types`; reference.
- Main columns: Code/name/category/postingRequired/status, creator/time.
- Create/edit/detail or filter form: code/name/category/availableIn/accountingBehavior/postingRequired; description.
- Search and filters: category/status; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/edit; activate/deactivate; guarded archive/delete; allowlisted import/export.
- Backend contract: /documentTypes; /documentTypes/{id}; /documentTypes/{id}/status; /excel/documentTypes/template,/validate,/export; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: document_types.
- Permissions: master.reference.view; per-action master.reference grants compiled by backend. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Custom label maps to canonical behavior; canonical types protected; custom inactive rows may archive.
- Current status / limitation / recommended improvement: PARTIAL — Source/config and historical evidence only; full page CRUD/denial/reference/export journey not rerun. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Canonical delete/archive refused; custom restore retains status and validates code uniqueness. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P03 / prerequisite slices,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-035"></a>

## MOD-035 — Component Attributes

- Module / route / profile: master_data; `/configuration/component-attributes`; configuration.
- Main columns: Code/label/type/input type/required/order/status as configured.
- Create/edit/detail or filter form: Code, labels, data/input type, options/reference type, validationRules, required/repeatable/order.
- Search and filters: Search/type/status where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/edit/reorder; guarded deactivate/delete.
- Backend contract: /component-attributes; /component-attributes/{id}; /component-attributes/reorder; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: component_attributes, component_group_attributes.
- Permissions: configuration.view/manage; specific action compilation. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Stable unique code; typed rules, valid options/reference; archive if captured/used.
- Current status / limitation / recommended improvement: PARTIAL — Visibility/required-condition expression scope and historical schema validation need checks. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Invalid pattern/type refused; used attribute cannot disappear from historical SO. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P04 / S03,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-036"></a>

## MOD-036 — Component Groups

- Module / route / profile: master_data; `/configuration/component-groups`; configuration.
- Main columns: Code/name, layout/status/order as rendered.
- Create/edit/detail or filter form: Code/name/layout; ordered attribute memberships, required/width/display settings.
- Search and filters: Search/status where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/edit; add/remove/reorder attributes; guarded delete.
- Backend contract: /component-groups; /component-groups/{id}/attributes; /component-group-attributes/{id}; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: component_groups, component_group_attributes.
- Permissions: configuration.view/manage. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: No duplicate memberships; valid referenced attributes/layout; snapshot when captured.
- Current status / limitation / recommended improvement: PARTIAL — Published/used deletion and layout compatibility require verification. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Group reorder/layout affects new captures while old SO structure stays stable. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P04 / S03,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-037"></a>

## MOD-037 — Component Tabs

- Module / route / profile: master_data; `/configuration/component-tabs`; configuration.
- Main columns: Code/name, trade direction, order/status as rendered.
- Create/edit/detail or filter form: Code/name/direction/visibility/order; group assignments and ordering.
- Search and filters: Direction/status/search where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/edit; group assignment/reorder; guarded delete.
- Backend contract: /component-tabs; /component-tabs/{id}/groups; /component-tab-groups/{id}; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: component_tabs, component_tab_groups.
- Permissions: configuration.view/manage. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Directional visibility and membership uniqueness; validate required/repeatable constraints.
- Current status / limitation / recommended improvement: PARTIAL — No claim every requested conditional-visibility rule exists. Verify first and implement only demonstrated missing acceptance.
- Acceptance: New SO captures configured tabs once; required values validated; stored snapshot unaffected by later tab edit. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P04 / S03,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-038"></a>

## MOD-038 — Configuration Versions

- Module / route / profile: master_data; `/configuration/versions`; configuration.
- Main columns: Version, status, description, activation/history metadata.
- Create/edit/detail or filter form: Description and snapshot preview; comparison version; activation/rollback reason as supported.
- Search and filters: Version/status/search where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Preview, publish, view, compare, activate, retire, rollback; guarded delete.
- Backend contract: /configuration-versions; /active; /preview; /{id}/activate,/retire,/rollback; /{id}/compare/{other}; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: configuration_versions, configuration payloads; SO snapshots.
- Permissions: configuration.view/manage. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Draft configuration becomes captured published version; activation history; rollback not retroactive data rewrite.
- Current status / limitation / recommended improvement: PARTIAL — Concurrent publish/activation and old-version render compatibility need integration checks. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Rollback changes future capture only; existing SO values/version survive; invalid snapshot refused. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P04 / S03,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-039"></a>

## MOD-039 — User Management

- Module / route / profile: auth; `/administration/users`; administration.
- Main columns: User code/name/email, status, assigned role, attribution as rendered.
- Create/edit/detail or filter form: Code, username/email/display name, locale/timezone, initial/reset password, one role.
- Search and filters: Search/status/role where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/view/update, disable, role replace, reset password/revoke sessions; guarded deletion.
- Backend contract: /users; /users/{id}; /{id}/password; /{id}/revoke-sessions; /{id}/role-assignments; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: users, user_credentials, user_sessions, casbin_rule.
- Permissions: admin.users.view; user capabilities via existing compile. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Unique identities, password policy, active single role, protected last administrator.
- Current status / limitation / recommended improvement: PARTIAL — Session/role changes and every action gate not fully accepted. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Disable/revoke blocks next request; unauthorized reset denied; last active protected admin remains. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P14 / S01,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-040"></a>

## MOD-040 — Roles & Permissions

- Module / route / profile: auth; `/administration/roles`; administration.
- Main columns: Role name, permission/user counts/status per UI.
- Create/edit/detail or filter form: Role name and page/action grant matrix; no parallel permission mapping.
- Search and filters: Search/status where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/edit/duplicate, grant/revoke; guarded delete; inspect assignments.
- Backend contract: /roles; /roles/{id}/permissions; /permissions/catalog; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: casbin_rule and role metadata.
- Permissions: admin.roles.view; role/permission capabilities via compile. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: One active role, no inheritance; backend compiles page grants; protected SUPER_ADMIN.
- Current status / limitation / recommended improvement: PARTIAL — Period close/reopen matrix mapping must be tested independently of generic update. Verify first and implement only demonstrated missing acceptance.
- Acceptance: View-only role cannot post/close; role replacement takes effect server-side; protected role cannot be weakened. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P14 / S01,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-041"></a>

## MOD-041 — Document Sequences

- Module / route / profile: finance + core; `/administration/document-sequences`; finance-setup.
- Main columns: Type, year, prefix, last value, padding, next preview, status.
- Create/edit/detail or filter form: Type/year/prefix/padding/status and permitted counter configuration.
- Search and filters: Type/year/status where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Create/upsert/view; guarded configuration changes.
- Backend contract: /document-sequences; /document-sequences/{id}; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: document_sequences.
- Permissions: admin.document_sequences.view; configuration.manage / compiled create/update. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Unique type/year; allocate transactionally under concurrency; preview not reservation.
- Current status / limitation / recommended improvement: PARTIAL — Never reset used counter or promise gapless numbers; concurrent evidence pending. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Concurrent creations yield unique numbers; retry does not create another document. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P14 / S02–S08,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-042"></a>

## MOD-042 — Settings

- Module / route / profile: settings; `/administration/system-settings`; administration.
- Main columns: Grouped settings panels, not a transaction table.
- Create/edit/detail or filter form: Branding/localization/security/upload/integration settings; secret presence only.
- Search and filters: Settings sections; no fabricated table search; only claim server behavior after adapter/handler verification.
- Primary actions: View/update permitted settings; explicit guarded diagnostics/reset.
- Backend contract: /settings/app-config; /settings/app-info; /settings/reset-data; documented diagnostic endpoints; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: app_settings/app configuration models; secure integration settings.
- Permissions: settings.app_config.view; settings.manage and specific guards. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Central validated settings; reset is consequential and outside this task; secret fields redacted.
- Current status / limitation / recommended improvement: PARTIAL — Existing reset/diagnostic side effects need isolated fixtures and separate explicit authorization. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Invalid config refused; secrets absent from logs/ordinary payloads; existing security identities protected. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P14 / S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-043"></a>

## MOD-043 — Archive

- Module / route / profile: archive; `/administration/archive`; administration.
- Main columns: Entity/type/reference, deleted by/time and status as rendered.
- Create/edit/detail or filter form: Read-only archived details; restore/conflict information.
- Search and filters: Entity/search/date as supported; only claim server behavior after adapter/handler verification.
- Primary actions: View; permitted restore; guarded hard delete.
- Backend contract: /archive; /archive/options; /archive/{type}/{id}; /restore; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: archive_records plus allowlisted soft-deletable entities.
- Permissions: admin.archive.view; archive restore/delete capabilities. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: No automatic purge; restore revalidates unique refs; finance/config entities not assumed archivable.
- Current status / limitation / recommended improvement: PARTIAL — Per-entity coverage incomplete; no blanket archive support. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Referenced/protected financial history cannot be hard-deleted; restore conflict is clear and atomic. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P14 / S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


<a id="mod-044"></a>

## MOD-044 — Audit Logs

- Module / route / profile: audit; `/administration/audit-logs`; administration.
- Main columns: Actor/action/entity/reference/time/result/request correlation.
- Create/edit/detail or filter form: Read-only event detail, safe before/after when recorded.
- Search and filters: Actor/type/entity/date/result where supported; only claim server behavior after adapter/handler verification.
- Primary actions: Read/filter permitted event details; export only if allowlisted.
- Backend contract: GET /audit-events; paths are relative to /api/v1; exact verbs and payloads in [API](../01-architecture/api-design.md).
- Database entities: audit_events.
- Permissions: admin.audit_logs.view; audit read capability. Page grants compile to backend capabilities through Casbin; do not invent suffixes for nonexisting actions.
- Purpose, business logic, validation, automation and related modules: Append-only important auth/finance/period events; redact secrets.
- Current status / limitation / recommended improvement: PARTIAL — Ordinary edit coverage/filter/export completeness not proven. Verify first and implement only demonstrated missing acceptance.
- Acceptance: Post/reverse/allocate/close/reopen events trace actor/source without password/token/key exposure. Apply the shared profile's refusal, empty/loading, localization and applicable export/print checks.
- Traceability: P14 / S01,S08,S11; LCS-001 plus the owning requirements in [acceptance matrix](../04-implementation/acceptance-criteria.md).


