# Master Roadmap

Last updated: 2026-11-05

## Approved milestones and ordered vertical slices

This is the approved S01–S13 mandatory-release roadmap for the existing application.
Statuses indicate slice verification/delivery, not absence of existing implementation.
S01 completed 2026-11-04 (evidence E09–E24 in the checklist: E23 per-page action gating,
E24 renewal/expiry on a disposable stack). Remaining S01 limits are recorded in
PLAN-0002's Handoff. S02 completed the same day (PLAN-0006). S03 completed 2026-11-05
(PLAN-0007/E26 files batch + PLAN-0008/E27 remaining acceptance), and S04 completed the
same day (PLAN-0009–0012/E28–E31); deferred items carry recorded owners.
Foundation creation did not start its execution.

| Slice | Milestone | Outcome area | Dependencies | Requirements | Status | Testable acceptance outcome |
|---|---|---|---|---|---|---|
| S01 | Secure Access | Login and Page Authorization | Existing auth/Casbin and 44-page inventory | LCS-001,002,009,013 | Completed 2026-11-04 (E09–E24: deny matrix, disposable PostgreSQL, 44-page browser matrix, action gating + renewal/expiry on disposable stack; limits: Chromium-only, cross-browser→NT02/S13) | Permitted login/pages/actions; denied API access and logout invalidation |
| S02 | Operational Continuity | Quotation to Service Order | Completed S01 + reference/config prerequisites | LCS-003,014 | Completed 2026-11-04 (PLAN-0006: reuse/replay backend 56 passed, PG concurrency 3 passed on disposable DB, browser journey 4 passed; AppLineTable silent-seeding + save-label defects fixed) | Multiple intentional source-linked SOs may reuse an offer; each keyed command creates one order with preserved independent snapshots |
| S03 | Operational Continuity | Operational Execution | S02 | LCS-004,010 | Completed 2026-11-05 (PLAN-0007 files/attachments E26 + PLAN-0008 acceptance E27: API-level journeys for movements/milestones/required values/INACTIVE-FINISHED guards, containers separation + deleted-refs refusal, conversion transfers routes/requirements/boxes/snapshots, config snapshot pinned; movement-sequence unique constraint added via migration c0d1e2f3a4b5 verified on PG. Deferred: storage recovery drill →S12, DATA-011 catalog scope →S11, movements browser journey →NT02) | Actual containers, dynamic data and authorized files persist; Save/Finish protect operations without posting |
| S04 | Operational Continuity | Service Charge to Financial Draft | S03; finance setup | LCS-004,005 | Completed 2026-11-05 (PLAN-0009/E28 map + PLAN-0010/E29 issue isolation + PLAN-0011/E30 bill-once concurrency + PLAN-0012/E31 profit layers: issue → no document/journal, explicit convert → one draft (PG race-proven, DB backstop b7c8d9e0f1a2), posted layers ledger-true base sums, mixed currencies grouped; deferred: per-currency report redesign → S09/S10, container-level P&L has no source (documented absent)) | Charge issue has no ledger effect; explicit conversion yields one draft |
| S05 | Accounting Integrity | Customer Invoice Posting | S04; accounts/rules/open period | LCS-005,006 | Completed 2026-11-05 (PLAN-0013/E32 posting contract + PG post race; PLAN-0014/E33 receipt allocation + AR reconcile + PG allocation race; PLAN-0015/E34 supplier flow + AP reconcile/race; PLAN-0016/E35 reversals/allocation-undo/permission isolation + acceptance review. Deferred: allocation period-gate → S06/S08, audit split → S06+, presentation → S09/S10) | Atomic unique balanced posting with source and rate snapshots |
| S06 | Accounting Integrity | Customer Receipt and Settlement | S05 | LCS-006,007 | Not Started | Partial/full allocation reconciles; excess allocation denied |
| S07 | Accounting Integrity | Supplier Bill and Payment | S05 | LCS-005,006,007 | Not Started | Supplier posting/payment/settlement reconcile with AP control |
| S08 | Accounting Integrity | Corrections and Accounting Period Controls | S05–S07 | LCS-006,009 | Partly 2026-11-05 (PLAN-0017/E36: Period Closing feature — validation pipeline, atomic period-row-locked close shared with posting (PG race), reasoned reopen; authorized /finance/period-closing page. 10.4 remaining: closing-report evidence retention + reopening dependency checks (S09/S10 baseline); corrections ledger work follows S06/S07) | Preserved reversal; balanced journals; custom dates; backend review/close/reopen with audit and closed-period denial (P10 uses verified report baseline) |
| S09 | Reliable Reporting | Operational Reporting | S02–S07 | LCS-008 | Not Started | Approved operational reports distinguish quoted/issued/draft/posted values |
| S10 | Reliable Reporting | Financial Reconciliation | S05–S08 | LCS-006,008 | Not Started | GL/TB/AR/AP/P&L/Balance Sheet/Cash Flow reconcile |
| S11 | Complete Business Functionality | Remaining Approved Page Workflows | S01; reference setup verified as needed earlier | LCS-001,009,014 | Not Started | Required remaining CRUD/config/admin/archive/audit actions verified |
| S12 | Recoverability | Isolated Recovery Drill | Representative earlier-slice data; approved safe recovery controls | LCS-012 | Not Started | Coordinated DB/files/config recovery passes integrity and measured-time checks |
| S13 | Release Acceptance | Cross-browser, Performance, Accessibility, and Business Acceptance | S01–S12; approved datasets/targets | LCS-010,011,013,015,016,019 | Not Started | Required browser/print/localization checks and authorized acceptance evidence |

## Agent setup completion (2026-11-04)

The explicit agent-configuration task added concise .agents context and six on-demand skills,
reconciled existing OpenCode instructions and documented optional MCPs. It changes no ERP
business behavior or slice acceptance. [Setup evidence](../03-development/agent-tooling.md#setup-verification-record)
records validation; S01/PLAN-0002 remains the unfinished resume pointer. No next phase started.

## Smart Settings documentation package (2026-11-04)

[PLAN-0005 A–G](plans/PLAN-0005-settings-integrations.md) specifies Settings/notifications,
email/recovery/security, encrypted cloud backup/restore and reusable bulk IO. Documentation is
complete; runtime tasks are NOT_STARTED. P14 owns administration, P03/P04 bulk IO, P06 SO event
producers, P15 integration and S12/P16 recovery/release evidence. S01/PLAN-0002 remains the
unfinished active pointer. No new pages, provider activation or execution authorization follows.

## Active implementation plan

The explicit 2026-11-04 printing request is tracked separately in
[PLAN-0004](plans/PLAN-0004-financial-printing.md), a bounded read-only financial-printing
change. Its scoped verification does not complete S02 or activate the remaining P08 work.

S01's [PLAN-0002](plans/PLAN-0002-access-and-page-authorization.md) closed 2026-11-04,
S02 the same day, S03 closed 2026-11-05 (PLAN-0007/0008), S04 the same day
(PLAN-0009–0012, evidence E28–E31), and S05 closed the same day
(PLAN-0013–0016, evidence E32–E35). S06 is the next open slice
([P08 financial documents](phases/P08-financial-documents.md) owns S05–S07, one
document/settlement slice at a time).

[Project status checklist](project-status-checklist.md) is the verification index for requirements,
all 44 pages, technical evidence and remaining gaps. This roadmap controls sequence; the active
plan controls implementation scope. Checklist completion never authorizes unrelated work.

[PLAN-0002 — Access and Page Authorization](plans/PLAN-0002-access-and-page-authorization.md)
is `Completed` (2026-11-04) with executed backend/browser evidence E09–E24 and two read-only
reviewer passes. Read its Handoff before touching auth/Casbin behavior.
[PLAN-0001 template](plan-template.md) defines future plan contents; an S02 plan is created
only when that slice starts. The current documentation master task also explicitly
requests detailed future topic packages: see [ERP modernization planning](planning-guide.md),
[tracker](phase-tracker.md), [dependencies](dependency-map.md) and
[acceptance](acceptance-criteria.md). P00–P16 are planning detail mapped to these S01–S13 slices,
not additional active plans or permission to start implementation. Create later active plans
only when their slice starts and has a real need.
The superseded finance-verification proposal is preserved in the history section below;
it is not an active plan or a completed verification.

## Execution rules and dependencies

Verify existing behavior first and fix only demonstrated gaps, one independently testable
slice at a time. Preserve protected admin/permission semantics and working integrations.
Verify necessary master data/configuration before dependent slices; S11 is remaining coverage,
not permission to defer prerequisite configuration. Recovery planning stays active in parallel;
live infrastructure changes need separate authorization. Include localization, validation,
applicable printing, audit and denial checks in each relevant slice.

## Definition of Done and release blockers

Apply [canonical DoD](../03-development/ai-agent-guidelines.md#definition-of-done) and per-plan acceptance.
Require exact executed evidence, meaningful failure/boundary tests, relevant PostgreSQL
financial guards, reconciled reports and safe recovery validation. Update status only after
verification. Critical/high defects and unresolved critical finance/security/integrity/
recovery/operational/legal issues block production; noncritical TBDs require explicit acceptance.
Capacity, performance, RPO/RTO, budget, WCAG target, retention/legal and named owners remain
open as recorded in [design brief](../00-project/requirements.md).

## Optional backlog

Supporting audit: the former PLAN-0003 codebase-cleanup audit (removed 2026-11-04, consolidated
here) completed two bounded batches: dead Excel-registry helper/constant removal
(`excel_io/registry.py`, with before/after API regression) and global-search lifecycle fixes
(21-regression suite in `frontend/tests/global-search.spec.ts`). The completed fixes remain in
the codebase; do not reimplement them. Broader cleanup remains open: on an explicit separate
cleanup request, prove dynamic/import/re-export reachability before removing
`COMPONENT_DISPLAY_MODES`. It does not replace S01, reorder S01–S13, or authorize broader
refactors/database changes.

Should: Telegram delivery/monitoring improvements, nonblocking usability, additional safely
anonymized business scenarios; tablet and essential mobile viewing remain Should.
Could: Google Sheets mirror enhancements, optional integrations, advanced nonessential features.
Preserve existing functionality. Optional improvements are not release blockers unless needed
for a Must or explicitly committed. No extra business page is approved. Rich Period Closing
is planned within Accounting Periods; a standalone navigation page remains proposed.
Explicitly requested future package planning does not authorize feature implementation.

## History

### Finance and financial-report audit close-out — 2026-11-14

Verified and corrected the Finance/Financial Reports slice already in the working tree.
Confirmed fixes: posted-financial projections now expose amounts as JSON numbers with
AR/AP aging buckets (`Current`, `1-30`, `31-60`, `61-90`, `90+`); trial balance keeps its
posted-only movement rows (no zero-balance or draft-only rows); a period cannot be closed
through the generic record edit (only the validated/audited close action); account
deactivation is refused while an active posting rule or financial account still uses it;
allocation reversal retains history via `reversed_at` and the additive migration
`a8b9c0d1e2f3`; posting-rule creation keeps its priority uniqueness tests aligned with the
seeded production-parity rules.
- Frontend: duplicate Period Closing menu item removed (routes redirect to Accounting
  Periods); period status is no longer editable in the form; journal/document status and
  manual entry-type selects removed from forms (status comes from row actions/backend);
  AR/AP status filter removed because the as-of projection does not filter by paid state;
  AR/AP Aging column added; table Actions column is sticky and neutral with red Delete only.
- Verification (owning directories): backend focused suites `test_financial_documents_module`,
  `test_job_finance_entries`, `test_report_export`, `test_report_generation`,
  `test_accounting_periods`, `test_period_closing`, `test_posting_rules`,
  `test_financial_report_cutoffs`, `test_finance_audit_controls`, `test_document_totals`,
  `test_order_finance_sync`, `test_deletion_policy` → all pass; `test_multi_currency`,
  `test_finance_automation`, `test_reporting_values` → pass. `ruff check` passes on changed
  backend files. Frontend `vitest run` → 934 passed / 115 files; `nuxt typecheck`, scoped
  ESLint and `i18n:check` pass.
- Limits: PostgreSQL-only allocation/period-closing tests skipped (no disposable PG target);
  Playwright browser acceptance was not run (no configured server/browser credentials). No
  production data, mobile code, deployment or commit changed.

### Service Order tables, drafts and Finance simplification - 2026-11-14

Scoped web change: Route-style dynamic table headers/actions; page Save coordinates
configured rows and the existing charge save boundary. Shared local drafts retain
configured forms, Finance rows/payment intent and conflicts. Finance has four shared
summary cards, one currency-aware entries table, details/dialog actions, scoped
paginated document reads and targeted mutation refresh. Receipt/expense creation
replays keyed requests under the existing order lock; posting/allocation rules stay
in their existing services. No mobile, schema, deployment or production-data change.

Task-owned files (other dirty work preserved):
- `backend/app/modules/finance/{repository,router,service}.py`; `backend/tests/test_order_finance_sync.py`.
- `frontend/app/components/freight/{AppLineTable,DynamicDataTable,JobCharges,JobDetail,JobFinance,JobRoute}.vue`.
- `frontend/app/components/document/{DynamicFormTableRenderer,DynamicGroupRenderer,DynamicTableRenderer}.vue`.
- `frontend/app/composables/common/useRecordFormDraft.ts`; `frontend/app/composables/freight/{useComponentTabs,useLcs}.ts`.
- `frontend/app/config/job-workspace-forms.ts`; `frontend/app/repositories/{contracts,http}/lcs.ts`; `frontend/app/stores/freight.ts`; `frontend/app/utils/freight/finance-draft.ts`.
- `frontend/i18n/locales/{en,km,zh}.json`; `frontend/tests/{component-tab-drafts,finance-cache-refresh,finance-draft,record-form-draft,service-charge-save}.spec.ts`; this evidence note.

Executed verification (owning directory):
- Frontend: `pnpm typecheck` and scoped ESLint passed. Final focused command: `pnpm exec vitest run tests/component-tab-drafts.spec.ts tests/finance-cache-refresh.spec.ts tests/finance-draft.spec.ts tests/finance-summary.spec.ts tests/service-order-draft.spec.ts tests/record-form-draft.spec.ts tests/document-draft-integration.spec.ts tests/service-charge-save.spec.ts tests/app-line-table.spec.ts tests/i18n-locales.spec.ts` → 80 passed / 10 files.
- Backend: `uv run --no-sync pytest -q tests/test_order_finance_sync.py tests/test_job_finance_entries.py tests/test_frontend_api_contract.py tests/test_route_authorization.py` initially exposed the new conflict-handler constructor error; corrected it. Existing selectors: 15 passed; `uv run --no-sync pytest -q tests/test_order_finance_sync.py` → 4 passed, including receipt/expense retry, posted immutability, validation rollback and scoped pagination.
- Backend: `uv run --no-sync ruff check app/modules/finance/service.py app/modules/finance/router.py app/modules/finance/repository.py tests/test_order_finance_sync.py --fix` passed. `git diff --check` passed. Independent read-only review findings corrected; final focused review found no remaining critical issue.

Limits/Handoff: browser acceptance and real PostgreSQL concurrency remain unexecuted
(no configured browser credentials or disposable PostgreSQL target). Graphify query
and update unavailable because the tool command allowlist blocks Graphify. Next
acceptance step: isolated browser Route/Customs/configured form → refresh → page
Save, then partial receipt/expense and responsive Finance check; run the keyed-create
race against a disposable PostgreSQL target. No roadmap phase advanced or commit made.

### Service Charges list unified — 2026-11-13

The `/service-charges` list stopped hiding order-linked charges: the standalone-only
client filter in `WorkspaceView.vue` (rows with a `jobNo` were dropped) is removed, so
the global list now shows every accessible charge — order-linked and standalone —
from the single `service_order_charges` table the backend `GET /service-charges`
(`scope=all`) already returns and tests already pin (`test_linked_charges_are_listed_per_scope_and_keep_the_order_customer`).
Columns, filters, row actions and the standalone create form were already shared and
are unchanged. `frontend/tests/service-charge-list.spec.ts` now pins the unified list
(no `jobNo` filter in `WorkspaceView`). Evidence: `pnpm lint` / `pnpm typecheck` /
`pnpm test` → 916 passed / 112 files. No backend or migration changes. Playwright e2e
not executed (no running stack/credentials in this session). No Git commit.

### Accounting bootstrap seed — 2026-11-12

The explicit seeder now has an `accounting` module (part of `--all` and
`--configuration`): a 32-row standard freight-forwarding chart of accounts
(assets, liabilities, equity, revenue, expenses with header/parent links), two
settlement accounts (Bank - Operating and Cash on Hand, both USD) linked to
1010/1020, and one active document-default posting rule for every financial
document type (customer invoice/credit note, supplier bill/credit note,
customer receipt, supplier payment, other income/expense, transfer,
adjustment). Tax rules use 2200 VAT Output for sales and 1300 VAT Input for
purchases; the legacy default account codes the posting engine expects
(1010/1020/1100/2010/4010/4020/5010/5030) are all present.

Insert-missing only: an existing chart row, financial-account link or active
document-default posting rule is skipped, never overwritten. Run explicitly with
`python scripts/seed.py --module accounting` (or `--all`).

Changed: `backend/scripts/seed.py`, `backend/scripts/seed_data/accounting.py`,
`backend/tests/test_seed_script.py`, `docs/03-development/deployment-guide.md`.
Evidence: `ruff` clean, `pytest -q tests/test_seed_script.py` → 4 passed; seeded
on the local stack → 44 inserted (32 accounts + 2 financial accounts + 10 rules),
replay 0 inserted / 44 skipped. No schema, API or financial-posting change. No
Git commit.

### Backup archive path hardening — 2026-11-12

CodeQL reported eight `py/path-injection` alerts in
`backend/app/modules/backup/dr.py` (archive names, sidecar manifests, the
decryption temp prefix and attachment `storage_key` joins). Every user- or
database-derived value is now reduced to one basename before it reaches the
filesystem: `_safe_archive_name`/`_safe_archive_path` confine archives to
`FULL_BACKUP_DIR`, `_safe_member_name` and `_confined_child` guard attachment
members, and the decryption temp file uses a fixed prefix. Archive members are
stored as `attachments/<index>-<basename>` with the original key kept in the
manifest (`archivePath` maps to `storageKey`), so a crafted key can no longer
traverse out of the archive root. Behaviour and the CLI/API surface are
unchanged; restore still verifies every checksum before extracting with
`filter="data"`.

Changed: `backend/app/modules/backup/dr.py`,
`backend/tests/test_full_backup.py`. Evidence: `ruff check` clean,
`pytest -q tests/test_full_backup.py tests/test_backup.py` → 20 passed. No
schema, API or financial change. No Git commit.

### Shared document drafts + editable-table cleanup — 2026-11-12

One draft state machine now serves every document form. `useRecordFormDraft`
(on the existing `useRecordDraft` storage helpers) owns the debounced write,
restore, conflict and clear rules; the form model stays the single authoritative
copy. Draft envelopes are v2 (collection + user scope), and v1 copies are still
read. A newer server row always wins: the stale local draft is dropped without a
prompt (no Restore/Discard banner). Successful saves clear only their own
record/new slot; failed saves keep the draft. Service Order screens present the
stored `ACTIVE` lifecycle as **Draft** (detail badge and list badge); Finish,
Deactivate, filters and operations reports keep the backend values.

Coverage: every editable `DocumentView` detail form — quotations, master data,
configuration and administration — plus standalone Service Charges, financial
documents and journals (workflow documents draft only while DRAFT). Service
Orders (header + route/containers/files state +
dynamic component-tab rows), the Service Order Service Charge tab (per charge,
keyed by the stable `clientRowId` for a new charge, so a second new charge no
longer overwrites the first) and the Service Order Finance entries (posted rows
stay server-owned). Route and Files edits update the page model and are saved by
the order Save instead of a per-keystroke whole-order PUT. Numbered containers
keep their immediate API write, now single-flight through `useAutosave` and
flushed on navigation. `AppLineTable` gained opt-in client row ids (`_rowId`,
stripped from payloads/drafts) and `aria-busy`; it remains the only editable
grid renderer.

Removed after verifying no production consumers: `components/table/AppSaveGrid.vue`,
`utils/freight/service-charge-autosave.ts`, the legacy one-row-per-charge grid in
`utils/freight/job-charges.ts` (only `isDeletableCharge` remains), and the unused
change-set helpers in `types/save-grid.ts`. Their tests were replaced with tests
of the live `feeLines`/`serviceChargeFormPayload` path.

Changed: `frontend/app/composables/common/{useRecordDraft.ts,useRecordFormDraft.ts}`,
`frontend/app/components/freight/{DocumentView.vue,JobDetail.vue,JobCharges.vue,JobFinance.vue,JobRoute.vue,JobFiles.vue,JobContainers.vue,AppLineTable.vue}`,
`frontend/app/config/{freight-modules.ts,lcs-reference-modules.ts,route-stop-table.ts,job-workspace-forms.ts}`,
`frontend/app/utils/freight/{job-charges.ts,job-workspace.ts}`,
`frontend/app/types/save-grid.ts`; docs `02-business/ui-ux-standards.md`.
Tests: new `record-form-draft` + `document-draft-integration`, rewritten
`workspace-tables`/`line-details`, removed the dead save-grid/autosave specs.
Evidence: frontend vitest 906/906, `pnpm typecheck`, `pnpm lint`,
`pnpm i18n:check` all clean. No backend, schema, permission or posting change.
No browser journey; no Git commit.

### Internal Service Charges + generated order financial drafts — 2026-11-12

Service Charges now carry a `charge_side` (`CUSTOMER`/`INTERNAL`). Internal fee
lines store supplier cost (`cost_unit_price`, `cost_amount`) beside the existing
selling price/discount/tax fields and require a supplier. Customer documents never
read cost fields; internal charges cannot be issued or invoiced to the customer.
The embedded tab has separate Customer/Internal fee-line views, both using the
shared `AppLineTable`.

Finish (and an explicit `POST /service-orders/{id}/refresh-financial-documents`
retry) generates only DRAFT documents; ordinary Save never generates invoices or
bills. One customer invoice is generated per container, with container pricing,
issued customer charge selling lines and eligible internal selling lines. Shared
components are allocated by direct container charge-out using Decimal arithmetic,
with the rounding remainder on the last container. Internal cost is generated as
one supplier bill per supplier + currency + order context. Every generated document
has a unique `generated_key`; component sources/amounts are recorded in
`financial_document_component_allocations`. Posted/reversed documents are never
modified and repeated Finish/retry updates the same drafts.

The Finance summary adds internal cost preview only until its supplier draft exists,
then uses the supplier bill, avoiding double counting. It keeps the existing
Total Charge-out / Charged / Uncharged / Total Expenses / Estimated Net Margin /
Outstanding cards and per-currency grouping.

Migration `c1a2b3d4e5f6` is additive: charge side/supplier/cost columns,
`financial_documents.generated_key`, and the component-allocation table. Existing
charges backfill to CUSTOMER and cost fields to zero. Schema DDL/descriptions and
deployment head documentation were regenerated. Evidence: latest focused backend
pytest 99 passed (generated documents, service charges/tax, quotation reuse,
finance entries, schema docs, migration chain and schema integrity); broader
backend suite 909 passed / 19 skipped before the final guards; frontend vitest
912/912, eslint/typecheck clean, i18n check pass, `pnpm generate` pass. No Git
commit. Limits: real-PostgreSQL upgrade/downgrade was not exercised in this
environment; generated supplier bills are grouped per supplier/currency/order,
not per existing supplier invoice.

### Service Order Finance summary + fee-line-only embedded Service Charge — 2026-11-12

The Finance tab now starts with six compact summary cards (Total Charges, Charged,
Uncharged, Total Expenses, Net Amount, Outstanding Balance) above the existing entry
grid, grouped per currency. Posted documents contribute their authoritative totals and
`outstanding`; only DRAFT documents/charges use live edited amounts, and the card group
is marked Estimated when any contribution is unposted. Arithmetic runs on 4-dp scaled
integers (BigInt) so credits, discounts and taxes never drift; negative uncharged/net
values are shown, not clamped. Outstanding is posted receivable balance only (never raw
cash/journal rows). `store.isLoaded` keeps zeroes hidden until the related collections
finish loading.

The Finance entries grid remains the shared `FreightAppLineTable`, now with the
supplier-bill/other-finance documents included and a cached supplemental document read
for configured behaviours that the invoice/bill projections omit. The table gained
optional `loading`/`emptyText` props and stable row identity (`id` → `clientRowId` →
index); existing callers are unchanged. Finance entries have their own debounced
`localStorage` draft (user + order + schema version), restoring new rows and edits to
DRAFT documents only, never posted/reversed rows; stale draft documents are skipped with
a visible count. Successful row saves adopt the confirmed server row and clear the
committed draft; failed saves keep it. A delayed response only adopts identity/stamp,
never overwriting cells typed while the request was in flight.

The embedded Service Charge tab now renders only the approved Fee Lines tab of the same
`ServiceChargeForm`/`DocumentAppForm`/`FreightAppLineTable` stack (`fee-lines-only`), with
the linked-charge selector kept unobtrusive. Standalone `/service-charges` keeps its
General/Traceability tabs and save. The tab emits its live charge totals to the Service
Order so the Finance summary preview follows fee-line, discount and tax edits without a
second calculation. No backend or schema change; persistence and posting rules are
unchanged.

Changed: `frontend/app/components/freight/{JobFinance.vue,JobCharges.vue,JobDetail.vue,ServiceChargeForm.vue,AppLineTable.vue}`,
`frontend/app/stores/freight.ts`,
`frontend/app/utils/freight/{finance-summary.ts,finance-draft.ts,service-charge-form.ts}`,
`frontend/app/utils/constants/document-types.ts`, i18n bundles; tests
`frontend/tests/{finance-summary,finance-draft,app-line-table,service-charge-shared-form}.spec.ts`.
Evidence: frontend vitest 899/899, eslint clean, typecheck clean, i18n check pass.
No backend change, no migration, no Git commit.

### Service Order breadcrumb, page draft, shared Service Charge form — 2026-11-12

The Service Order header now derives `Service Orders > {so number}` from the API's
`jobNo`/`serviceOrderNo` (never the database id), keeps the parent crumb linked to the
list, and shows a placeholder while loading / only the parent for a missing record.

Tab data loss had two causes: tabs were `v-if`-mounted (destroying local controls on
every switch) and no page-level draft existed for refresh/reopen. Every visited editable
tab now stays mounted (`v-show`), and `JobDetail` writes a versioned, debounced
`localStorage` draft keyed by user + Service Order. It restores only when the server
`updatedAt` still matches the draft base; a newer server row produces a Restore/Discard
banner instead of a silent overwrite. Successful save/finish clears only that record's
draft. File/Blob values, credentials and server-owned attachment/activity copies are
excluded. Storage corruption/denial degrades to no draft.

The Service Order Service Charge tab now renders the same `ServiceChargeForm` as the
standalone `/service-charges` page (`DocumentAppForm` + `jobCharges` module config +
`moduleDocumentTabs` + `recalculateFreightRecord` + record/table validation). The tab
owns its save boundary (page Save never creates/posts charges), loads the order's linked
charges, creates a linked draft with the existing `createForOrder`, edits through
`saveDraft`, and keeps a per-order/charge draft. Repeated clicks are blocked; a retried
create adopts the row by its stable `clientRowId` (backend also returns the existing
linked charge for the same marker) so no duplicate is inserted. Permissions, draft-only
status checks, optimistic `updatedAt` conflicts and financial posting paths are unchanged.

Changed: `frontend/app/components/freight/{JobDetail.vue,JobCharges.vue,ServiceChargeForm.vue,DocumentView.vue}`,
`frontend/app/utils/freight/{job-workspace.ts,service-charge-form.ts}`,
`frontend/app/composables/common/useRecordDraft.ts`,
`frontend/i18n/locales/{en,km,zh}.json`,
`backend/app/modules/operations/service.py`,
tests `frontend/tests/{service-charge-save,service-order-breadcrumb,service-order-draft,service-charge-shared-form}.spec.ts`
and `backend/tests/test_service_charge_workflows.py`. Evidence: frontend vitest 878/878,
eslint clean, typecheck clean, i18n check pass; backend focused pytest 47 passed,
ruff clean. No migration. No Git commit.

### Autosave made reusable + duplicate-charge and concurrency fixes — 2026-11-12

The draft autosave moved out of the Service Charge tab into the shared
`AppSaveGrid` (the wrapper every `AppLineTable` save-grid uses): optional
`autosave-key`, `persist`, `canAutosave`, `reconcile`, `prepareRestored`, draft
record/stamp props, and exposed `flushAutosave`/`retryAutosave`/`saveFailed`/
`clearLocalDraft`. Any grid can opt in; `JobCharges` now supplies only the business
mapping (charge API call, persistability rule, marker reconciliation) and contains no
second autosave implementation. Configuration grids are unaffected (the feature is
opt-in).

Duplicate-charge root cause: a created row was re-identified by matching **rendered field
values** against the response, so editing the row while its POST was in flight (or a lost
response) left the row id-less and the next autosave created it again. Every new row now
gets a stable `clientRowId` (from the table's `rowDefaults`) that travels in the charge's
`data` and comes back on create/list; ids are reattached by that marker only. Before
creating, the tab checks the loaded charges for the marker (adopting a row whose response
was lost), retry reloads first, and a row deleted while its create was in flight has the
just-created charge removed instead of reappearing. Older local drafts are stamped with a
marker before reconciliation.

Optimistic concurrency: charge payloads now expose `updatedAt`; `save_charge` refuses an
update whose `updatedAt` no longer matches with `409 STALE_CHARGE` (callers that omit the
stamp keep working). Autosave keeps the local draft and shows the inline Retry on a
conflict; Retry reloads first. No migration was needed.

Changed: `frontend/app/components/table/AppSaveGrid.vue`,
`frontend/app/components/freight/JobCharges.vue`,
`frontend/app/utils/freight/{job-charges.ts,service-charge-autosave.ts}`,
`backend/app/modules/operations/service.py`,
`backend/tests/test_service_charge_workflows.py`,
`frontend/tests/{service-charge-autosave.spec.ts,service-charge-save.spec.ts}`. Evidence:
frontend `vitest run` → 861 passed / 104 files, eslint + typecheck clean; backend
`pytest -q -n auto` → 905 passed, 19 skipped (PostgreSQL-only), exit 0. Frontend image
rebuilt/recreated locally. No Git commit.

### Service Charge autosave: status indicator removed, Route-pattern preservation — 2026-11-12

Removed the "Unsaved changes" / Saving… / Saved / Save failed header indicator introduced
with the autosave pass: `AppHeader` no longer renders a save status, and the
`saveState`/`chargeSaveStatus` plumbing was withdrawn from `AppDocumentPage`,
`AppHeaderPageActions`, `useAppHeader` and `JobDetail`; the four `freight.ui.autosave*`
locale keys were deleted. A failed draft save still shows the inline form-error summary
above the grid and now offers a small **Retry** action there (not a save button).
Everything else is unchanged and reuses the established draft behaviour: the editable
tabs keep their values in the page model like the Route tab (Route also background-saves
via the store), Service Charge and Finance stay mounted after their first visit, and the
Service Charge draft keeps autosaving 800 ms after edits with a localStorage restore, so
tab switches, refreshes and reopens never drop entered fee lines.

Changed: `frontend/app/components/layout/{AppHeader.vue,AppHeaderPageActions.vue}`,
`frontend/app/components/document/AppDocumentPage.vue`,
`frontend/app/components/freight/{JobCharges.vue,JobDetail.vue}`,
`frontend/app/composables/layout/useAppHeader.ts`,
`frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/service-charge-save.spec.ts`. Evidence: `vitest run` → 853 passed / 103
files; eslint clean; `pnpm typecheck` clean; `pnpm i18n:check` pass; frontend image
rebuilt and recreated locally. No backend change. No Git commit.

### Service Charge autosave + local draft (no data loss across tabs/refresh) — 2026-11-12

Root cause of the reported loss: the Service Charge tab is a component-local draft
(one charge record per row, kept in `AppSaveGrid`) and switching Service Order tabs used
to unmount it; the page save was the only persistence, so an unmounted draft and a
refresh lost the rows. Additionally `AppSaveGrid` reset its draft on every `rows` prop
change, so a background reload could erase edits made while a request was in flight.

Now: `useAutosave` (new, debounced 800 ms, single-flight with one queued trailing run)
persists the changed/new/deleted charge rows through the existing
`createForOrder`/`saveDraft`/`delete` endpoints — no new API, no schema change, no
financial posting (charges stay DRAFT SERVICE_NOTE documents). Incomplete new rows are
kept in a `localStorage` record draft (reusing `useRecordDraft`, now with a storage
choice) and re-attached after a refresh/reopen; successful, fully persisted saves clear
it. Created rows adopt their server ids by value fingerprint, so a later save updates
instead of duplicating, and `AppSaveGrid` no longer resets a dirty draft on a prop
refresh. Leaving the tab (tab button or URL/back navigation) flushes the pending save,
and the page header's Save changes waits for/flushes the autosave before its strict
validation pass.

UI: a quiet status next to Save changes — Unsaved changes / Saving… / Saved / Save
failed with a Retry action (`AppHeader` save-status config threaded through
`AppDocumentPage` → `AppHeaderPageActions`); autosave shows no success toast. The Finance
tab is now kept alive on first visit too, since its inline entries are the same kind of
local draft. No other tab changed shape: their values live in the page model.

Known limits: concurrency is guarded client-side (never two requests in flight, one
queued follow-up, no reload clobber) rather than by a server version column; a row edited
while its create is in flight and whose values no longer match the created snapshot is
saved as a second row on the next autosave (the original stays editable/deletable). No
migration was needed.

Changed: `frontend/app/composables/common/{useAutosave.ts,useRecordDraft.ts}`,
`frontend/app/components/table/AppSaveGrid.vue`,
`frontend/app/components/freight/{JobCharges.vue,JobDetail.vue}`,
`frontend/app/components/document/AppDocumentPage.vue`,
`frontend/app/components/layout/{AppHeader.vue,AppHeaderPageActions.vue}`,
`frontend/app/composables/layout/useAppHeader.ts`,
`frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/{autosave.spec.ts,service-charge-save.spec.ts}`. Evidence: `vitest run` →
852 passed / 103 files; eslint clean; `pnpm typecheck` clean; `pnpm i18n:check` pass; the
production frontend image was rebuilt and recreated locally. No backend change. No Git
commit.

### First-run setup inserts nothing but the admin — 2026-11-11

`/auth/setup` and the administrative "Reset data" now insert only the administrator
account and the permission/role catalog. The last automatic reference rows (document
sequences, currency master, app settings + their legacy rollback mirror) were removed from
`provision_baseline`, which is deleted; a fresh or reset database stays completely empty
until the operator seeds deliberately. Document sequences and app settings moved into
`scripts/seed.py` as the `document-sequences` and `app-settings` modules, so `--all` /
`--demo` now produce a fully working database (numbering, currency selects, settings
defaults). Startup still synchronizes the permission/role catalog only — that is the
security baseline login depends on, not reference data. The settings API keeps answering
from the code defaults while no `app_settings` row exists, so the UI still loads on an
unseeded database. Tests updated: `test_setup.py` now asserts setup/reset leave sequences
and currencies empty, and `test_seed_script.py` proves the new modules insert once then
replay as skips. Deployment guide updated with the setup → seed order.

Changed: `backend/app/core/bootstrap.py`, `backend/app/modules/master_data/service.py`
(docstrings), `backend/scripts/seed.py`, `backend/tests/{test_setup.py,test_seed_script.py}`,
`docs/03-development/deployment-guide.md`. Evidence: backend `pytest` → 14 passed (setup +
seed) and 81 passed (auth sessions, maintenance, API completeness, localization, quotations);
ruff clean. Note: Alembic's own migrations still seed the canonical financial document
types, transport identity types and capacity units on a brand-new schema (schema bootstrap,
idempotent with the seed command); nothing else inserts rows automatically. No Git commit.

### Automatic reference-data seeding removed; explicit `--demo` seed — 2026-11-11

No Master Data/Configuration row is inserted automatically any more. The `/auth/setup`
baseline (and `reset-data`) now provision only what the application cannot run without —
document-number sequences, the currency master, default app settings and their legacy
mirror — plus the permission/role catalog at startup; place roles, party roles,
transport identity types and capacity units were removed from `provision_baseline`.

`backend/scripts/seed.py` stays the single explicit seeder (insert-missing only, no
deletes, no ConfigurationVersion publish) and gains `--demo`: `--all` plus five sample
business parties (role links resolved by code) and two extra Configuration groups / four
extra Component tabs (linked to the seeded attributes/groups, IMPORT direction only) so
every Master Data and Configuration table starts with five records. Links degrade to
"skipped" when an administrator trimmed one side instead of failing the module. The script
now puts the backend directory on `sys.path` itself, so it runs from any cwd or container,
and `backend/Dockerfile` ships the whole `scripts/` folder for one-off production
containers. Commands are documented in `docs/03-development/deployment-guide.md`
(`--dry-run`, `--all`, `--demo`, and the `docker compose run --rm --no-deps backend …`
production form). New test `backend/tests/test_seed_script.py` proves the demo rows insert
once and replay as skips.

Changed: `backend/app/core/bootstrap.py`, `backend/scripts/seed.py`,
`backend/scripts/seed_data/{master_data.py,configuration.py}`, `backend/Dockerfile`,
`backend/tests/test_seed_script.py`, `docs/03-development/deployment-guide.md`.
Evidence: backend `pytest` → 13 passed (seed script + setup) and 69 passed (master data,
transport assets, quotations); ruff clean. Not executed: a live seed against a real
PostgreSQL database (local credentials rejected the dry run), so verify on the target host
with `--dry-run` first. No Git commit.

### Service Orders come from a Quotation only — 2026-11-11

Manual Service Order creation is retired end to end. The `/service-orders` list module has
`canCreate: false`, so the header New button is gone (search/filters/sort/pagination/row
actions/refresh unchanged), and its dead create-gate branch was removed from
`WorkspaceView`. The old `/service-orders/new` route now renders a redirect page: it shows
`freight.ui.serviceOrderNeedsQuotation` ("Service Orders must be created from a Quotation.
Please select a quotation and use Convert to Service Order.") and replaces the route with
`/quotations`; its page-permission mapping moved to the list's view code so any user who
can see orders is redirected rather than denied. The SO Overview's source quotation is
now `readOnly` — visible for reference and openable through the existing View Quotation
header action, but never editable; the backend already refused to repoint it on update.

Backend: `save_service_order` refuses any new order without a source quotation
(`ValidationFailed` on `quotationId`), so `POST /service-orders` cannot be used to bypass
conversion; quotation existence and a revision to copy are validated as before, and the
conversion ledger still records every create with its idempotency key. The approved
Quotations → Convert to Service Order workflow is untouched (`convert_revision` →
`create_service_order_from_quotation`, one quotation → many independent orders, unique SO
numbers, quantity-expanded payment rows). Update APIs and historical orders (nullable
`quotation_revision_id`) are preserved. Tests that relied on manual creation were
rewritten or removed (`test_a_manual_service_order_create_is_refused`, the direct-replay
test deleted, the payment-aggregation re-quotation test now converts a pricing-less
quotation first) and a frontend pin covers the list/redirect/read-only field.

Changed: `backend/app/modules/operations/service.py`,
`backend/tests/test_quotation_reuse.py`, `frontend/app/config/freight-modules.ts`,
`frontend/app/pages/service-orders/new.vue`, `frontend/app/utils/freight/page-access.ts`,
`frontend/app/components/freight/WorkspaceView.vue`,
`frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/{page-access.spec.ts,service-order-creation.spec.ts}`. Evidence: backend
`pytest` → 51 passed (quotation reuse, request schemas, auth sessions) and 74 passed
(quotations, job finance entries, created-by, movements/milestones, multi-currency);
frontend `vitest run` → 844 passed / 102 files; eslint clean; `pnpm i18n:check` pass;
typecheck clean except the pre-existing `TelegramSettingsPanel.vue` error. Limits: no
browser journey; PG-only race tests still skip without a live database. No Git commit.

### Service Charge tab: page-level save + live totals — 2026-11-11

The Service Charge tab's line grid no longer owns a Cancel / Save changes button: its
section header keeps only Print Invoice and Add charge, and the page header's Save
changes writes the pending charge change set (`AppSaveGrid` exposes `pendingChange` and
gains `hideSaveActions`; `JobCharges` exposes `savePending`, which `JobDetail.save()` calls
before persisting the order — a refused charge save stops the page save so its inline
errors stay visible). The tab is mounted on first visit and then kept alive (hidden) so
unsaved fee-line rows survive tab switches, and its dirty state feeds the order's
unsaved-changes guard. The totals block (Subtotal / Discount / Tax Rate / Tax / Grand
Total) now follows the grid's unsaved working rows (`update:draft`) and renders as soon as
a row exists, instead of only after a save.

Changed: `frontend/app/components/table/AppSaveGrid.vue`,
`frontend/app/components/freight/{JobCharges.vue,JobDetail.vue}`,
`frontend/tests/service-charge-save.spec.ts`. Evidence: `vitest run` → 841 passed / 101
files. No backend changes. No Git commit.

### Service Charges page + charge-line actions completed — 2026-11-11

Service Charges (`/service-charges`) list now shows exactly Checkbox (shared select
column), SC No., Business Party, Description, Grand Total, Created By, Created At and the
row-actions menu — SO No., Invoice No. and Status columns are gone, and the list is
unconditionally standalone-only (linked charges live on their order's tab; the SO No.
and Status toolbar filters went with the columns). Each charge still appears once: the
backend payload gains a `description` summarising its fee lines (first line's
description, "+N more" when several). The page's New button and document title say
"Service Charge" via a new `FreightModule.singularKey`/`titleKey` override
(`freight.modules.serviceCharges.*` added in all locales) instead of the shared
`jobCharges` collection noun.

Standalone charge detail (Fee Lines tab): rows gained the shared Delete command
(`_delete` column; disabled while the charge is read-only), and both the table header
("Print Invoice") and the row menu now drive the **finance** invoice workflow through the
existing charge→invoice command — an already-invoiced charge opens its existing invoice's
print preview, an issued one is confirmed then converted (bill-once
`FinancialDocumentSource`, no duplicate possible), a draft one explains it must be issued
first. `useFinanceCommands.createInvoiceFromCharge` gained an optional destination so the
created invoice lands on its print preview; the header "Create Finance Invoice" action
keeps its old behaviour. Additional Details (per-line discount + tax rate) and the live
Subtotal/Discount/Tax-Rate/Tax/Grand-Total summary below the grid were already in place
and are reused unchanged. Service Orders → Service Charge (previous entry below) is
unchanged by this pass.

Stale test pins from the interrupted finance-grid pass (Date column, no Business-Party
column, `hideAddRow`) were aligned to the current implementation; the service-charge list
spec was rewritten to the new columns.

Changed: `frontend/app/config/freight-modules.ts`,
`frontend/app/composables/freight/{useFreight.ts,useFinanceCommands.ts}`,
`frontend/app/components/freight/{WorkspaceView.vue,DocumentView.vue}`,
`backend/app/modules/operations/service.py` (payload `description` only),
`frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/{service-charge-list.spec.ts,document-tabs.spec.ts,finance-tab.spec.ts,workspace-tables.spec.ts}`.
Evidence: `vitest run` → 838 passed / 100 files; eslint + typecheck clean on touched
files (`TelegramSettingsPanel.vue` remains the one pre-existing typecheck error);
`pnpm i18n:check` → pass; backend `test_service_charge_workflows.py` +
`test_quotation_reuse.py` → 29 passed. Limits: no browser journey; no live-PostgreSQL
race tests. No Git commit.

### Service Charge tab: inline grid cleanup + individual/combined invoice printing — 2026-11-11

Service Orders → Service Charge keeps the shared `AppLineTable` (via `AppSaveGrid`) with
exactly `#` (renderer's row-number column), Fee Type, Description, Qty, Unit Price, Line
Total and a row-menu Delete command — the `Invoice No.` column was removed and the row's
`financialDocumentId` now identifies the owning invoice. Every row's `...` menu reads
Additional Details / Print Invoice / Delete: `AppLineTable` now puts its built-in
Additional Details entry first (per-line discount + tax rate through the existing
`AppLineDetailsDialog`, applied via `applyLineAdjustments` and saved through the existing
save-grid change set), and Delete is a real column again (`type: 'delete'`), disabled on
locked rows. Issued/invoiced charges are row-locked through a new `AppSaveGrid`
`rowDisabled` passthrough (`serviceChargeRowDisabled`); document-level discount/tax rate
stay editable from the summary's Discount/Tax-Rate buttons as before, and the Tax-Rate
summary shows "Mixed" when lines carry several different rates instead of one wrong
percentage.

Print Invoice exists at two levels, both backed by the existing finance workflow with no
backend changes: per-row — an already-invoiced charge opens its existing invoice's print
preview (`/print/debitNotes/{id}?template=tax-invoice`), a DRAFT charge explains it must
be issued first, and an ISSUED charge is confirmed then converted via the existing
`POST /service-charges/{id}/create-finance-invoice` (idempotency key + bill-once
`FinancialDocumentSource`, so retries and races can never draft a second invoice); top
header — one combined invoice for all issued, uninvoiced lines after a confirmation
listing the eligible charge numbers, reusing `POST /service-charges/combined-invoice`,
opening the created invoice's print preview, opening the shared invoice when every line
already belongs to one, and explaining when lines span several invoices. Add Charge is
still the grid's own add-row button (one unsaved row, nothing persisted), and it now
focuses the new row's first editable cell (`AppLineTable` `addRow`, generic). The old
"Create Combined Invoice"/"Print Statement" header buttons are replaced by the single
Print Invoice action.

Fixed a latent save bug in shared code: `isDeletableCharge` compared the API's display
status "Draft" against "DRAFT" exactly, so every saved-row edit in the tab was silently
skipped; it now compares on the domain value.

Changed: `frontend/app/components/freight/{JobCharges.vue,AppLineTable.vue}`,
`frontend/app/components/table/AppSaveGrid.vue`,
`frontend/app/utils/freight/job-charges.ts`, `frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/workspace-tables.spec.ts`. No backend changes — `create_invoice_from_charge`,
`create_combined_invoice_from_charges`, the per-charge bill-once source link and the
DRAFT-only delete guard already enforced everything. Evidence: `vitest run` → 837 passed
/ 100 files; eslint clean on touched files; `pnpm i18n:check` → pass. Limits: no browser
journey; the print previews and posting remain exercised by the existing finance tests.
No Git commit.

### Finance grid inline editing via AppLineTable — 2026-11-11

Service Orders → Finance now uses the shared `AppLineTable` for inline row editing — no new
table component. `AppLineTable` gained one small backward-compatible extension: a per-column
`lockCell(row)` predicate for mixed read-only/editable grids (its existing `rowDisabled`
already locked per row). The Finance grid columns are Type (select of Document Types master
data; lockable only on unsaved rows), Description, Business Party and Currency (searchable
reference selects from the store), Amount (number); `#` is the table's own row-number
column. Add Entry appends exactly one unsaved row (`new-*` id, date and currency seeded)
that is saved through the existing `finance.createDocument` / `finance.saveDraft` APIs via
the row menu's Save — repeated clicks are guarded, backend field errors map back onto the
offending cells, and user input is preserved. Posted/reversed documents and multi-line
drafts are row-locked (View/Post/Reverse/Allocate only — accounting immutability
preserved). Settlement types (receipts/payments) hand the unsaved row to the existing Add
Entry dialog, which owns the mandatory Financial Account field; the dialog (also reachable
from the header and from a draft row's Details action for Date / Fee Type / Reference /
Remark) completes the row through the same create path. The summary now totals **POSTED
documents only** per currency, with drafts shown as a separately labelled "Unposted drafts
(preview)" line — drafts are never counted as posted amounts.

Quotation Pricing, Fee Lines and Container Payments already run on `AppLineTable` and are
untouched; `DynamicDataTable` remains the record-list table.

Changed: `frontend/app/components/freight/{AppLineTable.vue,JobFinance.vue}`,
`frontend/app/config/{freight-modules.ts,job-workspace-forms.ts}`,
`frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/{finance-tab.spec.ts,workspace-tables.spec.ts,line-table-rules.spec.ts}`.
No backend changes. Evidence: `vitest run` → 836 passed; eslint + typecheck clean for
touched files; `pnpm i18n:check` → pass. Limits: no browser journey (inline save flows
exercised at the API-contract level by existing finance tests). No Git commit.

### Standalone charge creation simplified — 2026-11-11

Root cause of "Must be a company id.": the form's Business Party picker keyed the customer
by **legal name** (`referenceOptionSource('customer')` → `valueField: 'legalName'`), while
the new standalone branch resolved a party **id** — a missing/None id hit
`resolve_party_by_id`'s "Must be a company id." error. Fixed in `save_charge`: a supplied
`customerPartyId` resolves by id, a `customer` **name** resolves (or creates) the party via
`resolve_party_by_name` (the quotation rule), and a missing party is a clean field error;
an edit with a supplied party id now updates it (previously ignored).

Form: the `/service-charges` create form now shows General (Business Party picker by id —
searchable, required — Currency required, Remarks) + Fee Lines only; the Service Order
(jobNo) field is removed from the form (linked charges are created from the Service Order's
Service Charge tab; the saved record's Traceability tab shows invoice / posted journal /
source Service Order / quotation links, which already resolve through the existing
traceability util); the Traceability tab is hidden during creation; the create save label is
"Save Charge" (was "Submit"). A new charge starts with one empty fee line that is dropped on
save when completely untouched (partially filled lines stay and are caught by the existing
validation). Saving creates only a DRAFT charge — no invoice, no journal (existing rules).

Changed: `backend/app/modules/operations/service.py`,
`backend/tests/test_service_charge_workflows.py` (+1 name-only test, 6 total),
`frontend/app/config/freight-modules.ts`,
`frontend/app/components/freight/DocumentView.vue`, locales (+`saveCharge`),
`frontend/tests/{document-form-validation.spec.ts,document-tabs.spec.ts}`. Evidence:
`pytest test_service_charge_workflows.py` → 6 passed; charge/workflow/validation batch →
53 passed; `vitest run` → 836 passed; eslint + ruff clean; i18n check pass. Limits: legacy
linked charges whose party was inherited (NULL column) show an empty picker on edit and
keep their order party unless a new one is picked. No Git commit.

### Finance tab: summary + Additional Details dialog — 2026-11-11

Service Order → Finance: the entries table now shows the required minimal columns (#, Type,
Description, Business Party, Amount, Currency — Date/Status stay in the payload and the row
menu/dialog); editing remains dialog-based through the existing row actions (the shared
tables have no per-row mixed editability, and financial documents need the full dialog
fields — posted rows stay protected by the existing lifecycle rules). New summary block:
per-currency **Total Income / Total Expenses / Net Amount** — income behaviors
(CUSTOMER_INVOICE, OTHER_INCOME) minus expense behaviors (SUPPLIER_BILL, OTHER_EXPENSE),
resolving behaviors through Document Types master data; settlements (receipts/payments)
are excluded to avoid double counting, REVERSED/CANCELLED documents are excluded by the
existing status rules, currencies are never converted.

Service Charge tab summary: Discount and Tax Rate are now clickable values that open the
existing shared Additional Details dialog (`AppLineDetailsDialog`, retitled to
"Additional Details"), which validates discount ∈ [0, subtotal] and tax rate ∈ [0, 100]
(red borders only on real validation errors — the app's inputs otherwise use the standard
gray Nuxt UI borders; the old always-editable inline inputs are gone from this summary).
Save persists through the existing job-record update path (discount/vatRate), totals
recalculate from the shared `serviceChargeTotals` util. No backend or database changes —
all APIs, posting rules, period controls and audit behavior are the existing ones.

Changed: `frontend/app/components/freight/{JobFinance.vue,JobCharges.vue}`,
`frontend/app/config/job-workspace-forms.ts`, `frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/{finance-tab.spec.ts,workspace-tables.spec.ts}`. Evidence: `vitest run`
→ 836 passed; `pnpm i18n:check` → pass; eslint clean; typecheck clean for touched files
(pre-existing TelegramSettingsPanel error remains). Limits: no browser journey. No Git commit.

### Unified service charges + combined invoicing — 2026-11-11

The existing single charge model now supports both workflows. Standalone charges: `service_order_charges.service_order_id` became **nullable** (migration `b5c9d1e4f2a7`, additive) and a new nullable `customer_party_id` column carries the billing customer (linked charges keep mirroring their order's party at save time; existing rows are untouched and keep inheriting the order's party). `save_charge` accepts no order when a customer is supplied (customer mandatory for standalone, order's customer forced for linked); the charges list endpoint gained a `scope` query param (`all` default, `standalone` optional) and the Service Charges page hides order-linked rows unless the SO No. filter is used (client-side, so the store cache keeps serving the SO Finance tab). An invoiced charge (any charge with a `SERVICE_ORDER_CHARGE` finance source) can no longer be deleted.

Combined invoicing: new finance service `create_combined_invoice_from_charges` + `POST /api/v1/service-charges/combined-invoice` (permission `service_charge.convert_to_invoice`, Idempotency-Key replay) — validates issued-only, not-already-invoiced (per-charge bill-once index), one customer, one currency; drafts ONE `CUSTOMER_INVOICE` with sequential lines from every charge and **one `FinancialDocumentSource` row per charge**, so existing bill-once/retry protection applies per charge; totals are Decimal sums; the document is a finance DRAFT that posts only through the existing workflow. Printing unchanged: combined statements (order statement print) and per-invoice print reuse the existing finance print templates; printing never posts.

UI: Service Charges page shows a "Create Combined Invoice" toolbar action on selection (navigates to the drafted document); the Service Order's Service Charge tab gains a "Create Combined Invoice" header action (combines the order's issued, uninvoiced charges), relabels the ambiguous "Print All" to "Print Statement", and shows an Invoice No. reference column.

Changed: `backend/app/modules/operations/{models.py,service.py,router.py}`, `backend/app/modules/finance/service.py`, migration `b5c9d1e4f2a7`, `backend/tests/{test_service_charge_workflows.py(new),test_workflows.py,test_migration_chain.py}`; frontend `repositories/{http,contracts}/lcs.ts`, `utils/constants/api-v1-endpoints.ts`, `components/freight/{WorkspaceView.vue,JobCharges.vue}`, `utils/freight/job-charges.ts`, locales. Evidence: `pytest test_service_charge_workflows.py` → 5 passed; charge/workflow/migration batch → 76 passed; full frontend `vitest run` → 836 passed; eslint + ruff clean. Limits: no live-PostgreSQL race replay; printing-creates-no-invoice covered by existing flows (print opens the existing document); combined selection UI relies on backend validation for cross-customer/mixed-status selections. No Git commit.

### Detail header actions simplified — 2026-11-11

Quotation detail: the "Open Service Order" header menu action is removed (relationship,
conversion and stored references untouched); with no other valid actions the quotation
header's three-dot trigger is hidden automatically (the shared header already hides an
empty `moreItems`). Service Order detail: the standalone Finish button, the Change Status
submenu and the header Delete/Deactivate actions are removed; the menu now offers exactly
View Quotation (order's own `quotationId`, number fallback, "No quotation is linked…"
warning otherwise), Finish (the same `finishJob` workflow — existing confirmation,
idempotent command, status refresh, toast; disabled when finished or not editable) and
Re-Quotation (shared `useRequotation` composable, also used by the list row menu, so no
duplicate logic). Both Finish and Re-Quotation warn on unsaved edits first (new lightweight
`savedSnapshot`/`jobDirty` in JobDetail; proceeding is an explicit discard decision).
"View Source Quotation" renamed to "View Quotation" in en/km/zh; new
`noLinkedQuotation` key. The pinned `document-action-button.spec` updated for the removed
standalone button.

Changed: `frontend/app/components/freight/{JobDetail.vue,DocumentView.vue,WorkspaceView.vue}`,
new `frontend/app/composables/freight/useRequotation.ts`,
`frontend/app/repositories/{http,contracts}/lcs.ts`, `frontend/i18n/locales/{en,km,zh}.json`,
`frontend/tests/document-action-button.spec.ts`. No backend changes. Evidence: `vitest run`
→ 836 passed; `pnpm i18n:check` → pass; eslint on all touched files → pass; `pnpm typecheck`
→ no errors in touched files (one pre-existing error remains in TelegramSettingsPanel.vue,
from prior unrelated dirty work; the committed baseline also failed typecheck). Limits: no
browser journey. No Git commit.

### Re-Quotation workflow — 2026-11-11

Service Order row menus now show exactly Edit / Finish / Re-Quotation (Open, Change Status
and per-row delete removed for jobs only; all backend functionality stays). Finish reuses
the record's own status transition (existing confirmation/validation/permissions) and is
disabled when the policy offers no finish transition (already FINISHED). Re-Quotation opens
the shared confirm dialog ("Create Re-Quotation?" with the SO number, "original Service
Order will remain unchanged"), shows loading on Confirm (keepOpenOnConfirm), then calls the
existing `POST /api/v1/quotations/from-service-order/{id}` endpoint and navigates to
`/quotations/{id}`. Backend: the endpoint accepts an Idempotency-Key — a retry is answered
with the quotation it already created (key stored on the quotation's data; a deliberate
re-quotation runs with a fresh key); when the order has no stored pricing lines, its
container-payment rows are aggregated back into pricing lines (grouped by fee type,
description, unit, unit price and discount/tax treatment, Decimal sums, tax derived from
stored totals; unparseable amounts → clean ValidationFailed); orders with pricing lines
re-quote those lines directly (they are the aggregated form of the payments). The
quotation detail payload now exposes `sourceServiceOrderNo`, and the quotation page shows a
clickable read-only "Source Service Order" reference above the form. `source_service_order_id`
(nullable, indexed, non-unique, SET NULL) already existed — no migration. Locales en/km/zh
updated.

Changed: `backend/app/modules/quotations/{service.py,router.py}`,
`backend/tests/test_quotation_reuse.py` (+4 tests),
`frontend/app/repositories/{http,contracts}/lcs.ts`,
`frontend/app/components/freight/{WorkspaceView.vue,DocumentView.vue}`,
`frontend/i18n/locales/{en,km,zh}.json`. Evidence: `pytest tests/test_quotation_reuse.py`
→ 23 passed; quotation/workflow/PG/access/migration batch → 96 passed, 3 skipped (PG-only);
`vitest run` → 836 passed; `pnpm i18n:check` → pass (3574 keys × 3); ruff clean. Limits:
concurrent same-key re-quotations are deduplicated sequentially (no unique index over the
JSON key); no browser e2e. No Git commit.

### Container payments: one row per quoted unit — 2026-11-11

`_attach_quotation_copy` (the shared copy behind both the Convert confirmation and the
Service Order form's quotation selector) now also generates `data.containerPayments`: each
whole-number quotation pricing-line Qty N becomes N independent rows of Qty 1 at the line's
unit price (line total = unit price; the rows' sum equals the line subtotal before
adjustments; fee type, description, unit and `sourceQuotationLineId` are carried; no
container number is fabricated). Fractional quantities (supported by pricing) and lines
above `MAX_PAYMENT_ROWS_PER_LINE = 500` keep the line's own single billing-count row instead
of being rounded or exploding the payload. Rows are stored once at creation — page loads,
refreshes and later saves never regenerate them; a blank client-side `containerPayments`
list on create is ignored (mirroring the existing places guard). No quotation changes, no
schema change (payments stay in `service_orders.data` per the existing design); actual
containers, invoices, payments and journals are still never copied. Legacy orders without
stored rows keep the existing frontend derivation.

Changed: `backend/app/modules/operations/service.py`, `backend/tests/test_quotation_reuse.py`
(4 new tests). Evidence: `pytest tests/test_quotation_reuse.py` → 19 passed; quotation/
workflow/finance/API-contract batch → 68 passed, 3 skipped (PG-only); `vitest run` → 836
passed; ruff clean. Limits: no live-PostgreSQL race replay. No Git commit.

### Convert to Service Order: confirm dialog + direct creation — 2026-11-11

The row action now opens the shared confirm dialog ("Convert to Service Order?" with the
quotation number interpolated and a note that the original quotation stays unchanged).
Confirm shows loading on the button (new additive `keepOpenOnConfirm` option in
`useConfirm`/`AppConfirmHost`; existing callers unchanged), then creates the order through
the existing `POST /api/v1/quotation-revisions/{revisionId}/convert` endpoint — permission
`quotation.convert`, atomic transaction, allocated unique SO number, independent child-row
copies, conversion-ledger source link, idempotency replay on retry (the sessionStorage key
survives a failed request, so a retry is answered with the created order; a later deliberate
conversion runs with a fresh key), concurrent-retry rollback answered with the winner's
order. Success closes the dialog, toasts and navigates to the new Service Order; failure
closes the dialog and shows the backend refusal above the list. No new endpoint, no new
field-mapping code: the conversion reuses `_attach_quotation_copy` (header party/direction/
currency/description/data, route stops, container requirements + derived expected
containers, own pricing lines and totals), which is also the copy path behind the Service
Order form's quotation selector (Workflow B). Locales en/km/zh updated for the dialog copy.

Changed: `frontend/app/components/freight/WorkspaceView.vue`,
`frontend/app/composables/common/useConfirm.ts`, `frontend/i18n/locales/{en,km,zh}.json`.
No backend or database changes. Evidence: `vitest run` → 836 passed; `pnpm i18n:check` → pass;
`pytest tests/test_quotations.py tests/test_quotation_reuse.py tests/test_quotation_postgres.py
tests/test_workflows.py tests/test_access_enforcement.py` → 78 passed, 3 skipped (PG race
tests need live PostgreSQL). Limits: dialog loading state not unit-tested (`import.meta.client`
is false in vitest); no browser journey. No Git commit.

### Quotation row actions: Edit / Convert / Delete / Duplicate — 2026-11-11

The quotation row menu now offers exactly four actions in order — Edit, Convert to Service
Order, Delete, Duplicate — with Open, Open Service Order, Re-quote and status actions
removed for quotations (other modules keep their menus). Delete stays clickable and shows
the backend's `QUOTATION_HAS_SERVICE_ORDER` refusal above the list when a service order
depends on the quotation (robust even when the jobs cache is incomplete; never cascades
orders). `delete_quotations` now maps a commit-time FK refusal (a concurrent service-order
creation linked the quotation between check and commit) to the same clean Conflict instead
of a 500. Duplicate reuses the existing New Quotation form and create API: the row action
navigates to `/quotations/new?duplicate=<id>`, DocumentView prefills business fields and
items from the source record (identity, revision, traceability and attachment keys are
skipped; `DUPLICATE_SKIP_KEYS`), and the backend allocates a fresh Quotation No. on save —
so a duplicate is an ordinary create with full existing validation and permissions.
Accidental duplicate submission protection is the form's existing double-submit guard
(there is no server-side idempotency store for quotation creates; documented limit).

Changed: `frontend/app/components/freight/{WorkspaceView.vue,DocumentView.vue}`,
`backend/app/modules/quotations/service.py`. Evidence: `vitest run` → 836 passed;
`pytest tests/test_quotation_reuse.py tests/test_quotations.py tests/test_quotation_versions.py
tests/test_access_enforcement.py` → 66 passed. Limits: no PostgreSQL race replay, no browser
journey. No Git commit.

### Quotation → Service Order (1 → many) completion — 2026-11-11

Implemented the two shared-path creation methods on top of the existing reusable-quotation
design. No new pages, forms or conversion service: Method A (quotation row menu → Convert to
Service Order) navigates to the existing Service Order form with `?quotationId=` preselected;
Method B picks the quotation on the same form. The form's prefill watch now re-runs when the
quotation list finishes loading, and a Service Order can be saved without any quotation.
Backend `save_service_order` treats the quotation as optional prefill (explicit party/
direction/currency/description win over the copied values), validates an unknown quotation,
and records every new order — with or without a quotation — in the conversion ledger so a
retried create stays an idempotent replay. One quotation → many Service Orders was already
true at the schema level (`service_orders.quotation_revision_id`, nullable, non-unique FK to
the revision, which traces to `quotations.id`); no `service_orders.quotation_id` column was
added because the revision link already provides the optional quotation reference with FK
integrity. Quotation Status UI is removed (list column, form field, status badge; the
revision-history table keeps its own revision status vocabulary).

Migration `d8e4b2c6f7a1` (after `c3d5f7a9b1e2`): PostgreSQL-only
`ALTER TABLE quotation_conversions ALTER COLUMN quotation_revision_id DROP NOT NULL` so
direct creates can record their idempotency key without a source revision. Additive;
existing rows unchanged.

Changed files: backend `app/modules/operations/service.py`, `app/modules/quotations/{models.py,service.py}`,
`alembic/versions/d8e4b2c6f7a1_*.py`, `tests/{conftest.py,test_quotation_reuse.py,test_migration_chain.py}`;
frontend `app/config/freight-modules.ts`, `app/utils/freight/quotation-actions.ts`,
`app/components/freight/{WorkspaceView.vue,DocumentView.vue,JobDetail.vue}`,
`tests/{quotation-actions.spec.ts,quotation-revisions.spec.ts}`.

Evidence: `pytest tests/test_quotation_reuse.py tests/test_quotations.py` → 52 passed;
`pytest tests/test_workflows.py tests/test_record_status.py tests/test_write_validation.py
tests/test_request_schemas.py tests/test_migration_chain.py` → 100 passed;
`pytest tests/test_quotation_postgres.py tests/test_deletion_policy.py
tests/test_frontend_api_contract.py tests/test_page_api_integration.py
tests/test_job_finance_entries.py tests/test_movements_and_milestones.py` → 34 passed, 3 skipped
(PostgreSQL-only race tests need a live PG; SQLite cannot prove them);
`vitest run` (frontend) → 836 passed / 100 files. Limits: no live-PostgreSQL run, no browser
journey, no build/typecheck, single-tenant system so "workspace isolation" is the existing
permission model (`require_permission`); old `/quotation-revisions/{id}/convert` endpoint
retained (still used by tests/legacy callers). No Git commit.

### Compact Settings UI follow-up — 2026-11-04

User clarified the compact maintenance editor also belongs in the existing Backup tab and
Telegram should simplify existing controls only. STANDARD UI scope; backend guards, permissions,
verification API and database schema were unchanged. Maintenance now renders only toggle/Reason,
saves through the existing document header, and shares one editor state across both tabs.
Hidden settings/revisions are preserved; an existing schedule survives a Reason-only edit.
Reopening still requires prior backend recovery verification through the authorized API.
Telegram rules now update the parent draft and use header Save; connection/pairing remain,
rules/history collapse, and history loads on first opening. Fixed its demonstrated invalid
empty select option and passed interpolation parameters to the existing validation translator.

Files: `SystemSettingsPage.vue`, `MaintenanceSettingsPanel.vue`, `TelegramSettingsPanel.vue`,
`TelegramDeliveryHistory.vue`, new `composables/settings/useMaintenanceSettings.ts`,
`utils/settings/maintenance.ts`, `tests/maintenance-settings.spec.ts`; UI standards and operator
instructions updated. Save targets the current tab's changed settings group; Backup saves its
changes before maintenance activation, or reopens first if backend verification permits it.
Separate API writes are not atomic; failed requests keep the remaining draft and show errors.

Evidence: `pnpm exec vitest run tests/maintenance-settings.spec.ts tests/maintenance.spec.ts`
→ **5 passed**; scoped ESLint on seven changed frontend files → pass; `pnpm typecheck` → pass.
Synthetic browser checks on 127.0.0.1:3018 observed shared drafts across Maintenance/Backup,
header-only maintenance persistence, Telegram invalid-rule refusal, successful header rule save
and delivery-history rendering without its select error. Screenshots:
`output/browser/maintenance-compact.png`, `output/browser/telegram-compact.png`.
Existing missing translation/dev-environment warnings and a blocked synthetic avatar request
were not resolved. No real Telegram send/backend deployment test was run; browser/server stopped.
No commit or automatic next phase. Prior production/PostgreSQL acceptance limits remain.

### Scoped maintenance implementation — 2026-11-04

The explicit maintenance request was implemented independently of unfinished S01. It does
not complete S01, PLAN-0005 integrations, full disaster recovery, or release acceptance.
No migration: existing `app_settings`, `audit_events` and `notification_outbox` are reused.
No deployment, real provider send, production data operation or Git commit was performed.

Changed runtime owners: backend `app/modules/settings/{maintenance.py,router.py,service.py}`,
`app/core/{access_modes.py,config.py}`, `app/api/v1/router.py`, `app/main.py`,
`app/modules/backup/scheduler.py`, `app/modules/telegram/{worker.py,outbox.py,monitor.py}`;
frontend `app/components/document/{MaintenanceSettingsPanel.vue,SystemSettingsPage.vue}`,
`app/components/layout/MaintenanceNotice.vue`, `app/pages/maintenance.vue`,
`app/layouts/{default.vue,maintenance.vue}`, `app/composables/useApi.ts`,
`app/middleware/auth.global.ts`, `app/repositories/http/maintenance.ts`,
`app/types/maintenance.ts`, `app/utils/auth/maintenance.ts`,
`app/utils/constants/api-v1-endpoints.ts`, `app/config/settings-schemas.ts`, and en/km/zh locales.
Tests: new `backend/tests/test_maintenance.py`, updated `test_access_enforcement.py` and
`test_route_authorization.py`; new `frontend/tests/maintenance.spec.ts`.
Owning API/security/deployment docs describe the contracts and operator recovery boundary.
Preexisting dirty work was preserved; baseline hashes/times were captured before edits.

Executed evidence (existing environments, focused only):

- Backend: `uv run --no-sync pytest -q tests/test_maintenance.py tests/test_telegram.py tests/test_backup.py tests/test_access_enforcement.py tests/test_auth_sessions.py tests/test_route_authorization.py tests/test_frontend_api_contract.py --disable-warnings`
  → **54 passed**, 38 existing/deprecation/schema/OpenAPI warnings, 59.64s.
  Covers activation/confirmation/denial, stale revisions, blocked financial/public integration
  writes, preserved session records, persisted/scheduled state, no end-time reopening, failed
  backup/deployment, CSRF, notification routing/retry/consent and emergency DB-down status.
- Frontend: `pnpm exec vitest run tests/maintenance.spec.ts tests/auth-session.spec.ts`
  → **2 passed** in the new maintenance spec; `auth-session.spec.ts` does not exist and was
  not run. Corrected regression selection
  `pnpm exec vitest run tests/session.spec.ts tests/auth-renewal.spec.ts` → **13 passed**.
  Total executed frontend checks: **15 passed** across three actual specs.
- Scoped `uv run --no-sync ruff check` on the 14 touched Python files and scoped
  `pnpm exec eslint` on the 14 touched frontend source/test files → pass.
  `pnpm typecheck` → pass. `pnpm i18n:check` → pass, 3386 keys per locale.
  Scoped `git diff --check` → pass; 27 local links in the four affected docs resolve.
- Browser e2e runs with an isolated frontend on 127.0.0.1:3018 and synthetic API responses:
  desktop/mobile public page, administrator direct recovery/settings tab despite ancillary
  503s, hidden generic Save on Maintenance, and field validation/input preservation observed.
  Screenshots: `output/browser/maintenance-{desktop,mobile,settings-validation}.png`.
  Initial browser interception mistakenly matched a Vite dependency; corrected to API paths.
  One initial CLI inspection timed out; a fresh isolated browser completed recovery checks.
  Existing dev dependency scan warnings, missing `common.moreActions`, and deliberately
  refused synthetic branding/avatar requests are not claimed resolved. Browser/server stopped.
- Independent read-only DEEP review: recovery redirect, bounded/canonical group IDs, shared
  Save and system-notification opt-out issues fixed; fresh review reports no blocking issues.

Handoff: implementation complete in this scope; operational acceptance remains **unverified**.
Exact next step for an authorized release owner: follow the
[maintenance deployment/recovery procedure](../03-development/deployment-guide.md#maintenance-deployment-and-emergency-recovery)
on an isolated PostgreSQL stack, prove concurrent replica admission/revision behavior and
request drain, then exercise the actual backup/restore/deployment and Telegram destinations.
SQLite is not PostgreSQL-lock evidence. Reopening checks are operator attestations; no automatic
backup/deployment/drain verification was added. Emergency server configuration provides DB-independent
lockdown/status, not database repair or an auth bypass. No automatic next phase is authorized.

- 2026-11-04 folder-layout request: moved documentation into 00-project, 01-architecture,
  02-business, 03-development, 04-implementation and archive; updated navigation, generator,
  status-tool and reference paths. This changes no implementation status or S01–S13 order.

- 2026-11-04 documentation master task: added 44-page detail, Smart ERP targets and seventeen
  dependency-aware topic packages; corrected reusable-quotation/Finish expectations and stale
  S01 execution wording. No implementation status or historical test evidence was promoted.

- 2026-11-04: Removed PLAN-0003 and docs/qa on user request; completed cleanup outcomes are
  summarized in the Optional backlog. Updated the testing reference to focused-first gates.
- 2026-10-31: Reviewed draft documentation consolidated; the superseded finance plan is
  preserved in the proposal history below. S01 references now use the canonical inventory
  and requirement tables. Slice statuses and execution scope are unchanged.
- 2026-10-30: Approved discovery roadmap S01–S13 replaces the earlier verification scaffold.
  Prior milestone intentions are represented by secure access, configuration/operations,
  finance/reporting, UI/localization, integration/recovery and production acceptance above.
  Earlier first-slice finance proposal is summarized below as superseded.

## Superseded finance verification proposal

The old `PLAN-0002-first-slice.md` and draft implementation plan were reviewed and consolidated
here, then removed to eliminate the duplicate PLAN-0002 identity. Their proposal was to verify
financial_documents/posting and trial-balance reconciliation, map finance/report endpoints,
inspect targeted finance/report tests and `test_frontend_api_contract.py`, and record gaps.
Relevant source areas: `finance/service.py`, `posting.py`, `posting_rules.py`, reports engine
and ledger reports. SQLite cannot prove PostgreSQL triggers/locking; use separate safe
PostgreSQL evidence. No tests were executed by those draft plans and no finance slice was
completed. Their former next action is deferred to S05/S10; S01 remains first.
The old oversized quote-to-trial-balance slice is now split across S02–S10; configuration
comparison/rollback fits S03/S11, exports S09/S10, denial S01 and every applicable slice.
