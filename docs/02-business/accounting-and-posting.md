# Smart ERP requirements and business specifications

Status: target requirements and source-reviewed gaps, 2026-11-04. This document expands the
current master task without claiming implementation. [Design brief](../00-project/requirements.md) owns
scope/priority, [lifecycle](business-rules.md) owns transitions, and
[data invariants](../01-architecture/database-design.md#financial-data-integrity--canonical-invariants) own accounting
protection. Existing LCS/BR/FR/NFR/INV identifiers remain stable; the IDs below add testable detail.

## Requirement register

| ID | Observable target | Package / slice |
|---|---|---|
| LCS-AUTO-001 | Concurrent document creation yields unique configured numbers; retry of one keyed command returns its original record | P14 / S02–S08,S11 |
| LCS-AUTO-002 | Quotation/party/fee defaults populate related fields once; subsequent reference/config edits do not overwrite saved overrides | P05–P07 / S02–S04 |
| LCS-AUTO-003 | Server recomputes totals with Decimal and declared rounding; UI preview reconciles with persisted values | P07–P09 / S04–S08 |
| LCS-AUTO-004 | Settlement, overdue and profitability indicators derive from eligible events and disclose their source/date basis | P08,P11–P13 / S06–S10 |
| LCS-QUO-001 | One quotation can source multiple SOs; distinct intentional creations work, same-key retry does not duplicate | P05–P06 / S02 |
| LCS-SO-001 | Save preserves selected quotation/revision and editable pricing snapshot; Finish locks operational edits without posting | P06 / S02–S03 |
| LCS-CHG-001 | Issued charge converts to one source-linked draft; neither issue nor conversion creates a journal | P07–P08 / S04 |
| LCS-PER-001 | Custom named date ranges need no user-entered year; non-overlap and OPEN-period posting enforced server-side | P09 / S08 |
| LCS-CLS-001 | Review results identify blocking errors/warnings with authorized record drill-down | P10 / S08,S10 |
| LCS-CLS-002 | Close revalidates under transaction protection, records actor/time and prevents concurrent late posting | P10 / S08 |
| LCS-CLS-003 | Reopen requires permission/reason and preserves all prior close/reopen/report evidence | P10 / S08 |
| LCS-RPT-001 | Each report declares date basis, sources, currency, filters, totals, drill-down, export/print and empty state | P11–P13 / S09–S10,S13 |
| LCS-UI-001 | Shared forms/tables expose persistent field errors, loading/empty/refusal states and permitted actions | P02 / all UI slices |
| LCS-CFG-001 | Publishing/rollback affects future capture; existing SO snapshots retain the captured version | P04 / S03,S11 |

## Quotation to Service Order specification

Preconditions: authenticated permitted actor, existing quotation/revision, valid party/direction,
currency, route and pricing references. Save Changes persists allowed edits; Submit validates
the commercial offer and records submission. No mandatory Sent/Accepted steps are introduced.
Re-Quotation from a quotation creates a new draft revision; re-quotation from an SO creates a
new quotation linked to that SO, preserving the original and its prices.

Select the quotation and capture the actual revision used, its party/direction/currency/routes,
container requirements, prices and required configuration. Multiple SOs may reference the same
offer. Editing one SO's copied price must not change the quotation or another SO. Changing a
quotation later must not rewrite an existing SO. Actual containers start empty and are entered
when physical container details are known.

One intentional creation has a stable idempotency key; network retries reuse it, while another
intentional booking gets a fresh key. Reusing a key for a different revision/payload must be
refused, never return an unrelated booking. Inspect current replay scope before declaring this
requirement met. Retain a conversion ledger with every source revision/order relationship.

Current evidence: quotations/service.py convert_revision allows repeated conversions without
a status gate; save_service_order selects the latest revision. This is broader than the normal
Submit-first journey. S02 must verify and resolve eligibility, inactive/cancelled offers,
specific revision selection, same-key/different-payload refusal and concurrent retries.
Do not silently invent a new status or require legacy customer acceptance.

## Operational completion and charge-to-finance specification

Save and Finish are operational commands. Finish records actor/time and prevents prohibited
operational mutation; it does not require full settlement and does not recognize revenue.
Financial documents/payments remain traceable and usable after Finish. An inactive order is
not eligible to Finish. Historical finished data must not be erased to make corrections.

Configured quotation prices, an SO's copied/overridden pricing, actual customer charge lines and
posted ledger values are separate data layers. Charge lines retain fee type, quantity, unit,
rate, currency, optional container, price source and authorized override information where
implemented; missing provenance/cost-side features remain gaps, not invented schema fields.

Only an eligible issued charge is billable through explicit invoice conversion. Preserve the
source charge and line relationships; repeated/racing charge-to-draft requests must reuse one
draft. Check direct SO invoicing and charge conversion together for duplicate billing. A
generated draft remains editable before separately authorized finance posting.
Supplier cost recognition follows supplier bills; do not count estimated cost as a posted expense.

## Financial documents, settlement and posting

Use the existing document type catalog and accounting strategies; custom display types map to
supported accounting behaviors. Do not introduce a new lifecycle to represent payment progress.
Document status remains the lifecycle authority; Unpaid, Partially Paid, Fully Paid and Overdue
are derived settlement indicators.

Paid amount is the sum of effective allocations as of the reporting cutoff. Outstanding is
eligible document amount less effective allocations and authorized corrections. Unapplied
receipt/payment balance remains separate. An invoice can receive multiple payments, one payment
can settle multiple eligible targets, and neither side can be over-allocated. Check party/type,
currency/rate compatibility, reversals and races under locks. A payment dated in an open later
period may settle an old invoice; do not reopen the invoice period just to receive payment.

Posting recalculates the document, resolves eligible rules/accounts and an OPEN period by
posting date, builds a balanced journal and preserves source/rate snapshots. Journal/lines,
posting relationship, status and required audit must succeed together or roll back. Posting
rule updates affect future decisions, never rewrite posted history. Reversals preserve original
entries and add linked opposing effects in an eligible open period. Allocation is not a second
invoice-revenue event; any realized FX journal must be separately specified and traceable.

## Stored invoice and container printing

Implemented for the explicit printing task on 2026-11-04; verification is recorded in
[PLAN-0004](../04-implementation/plans/PLAN-0004-financial-printing.md). Existing Financial
Documents and print components remain the owning workflow; no new business page is added.

- Consolidated output includes every stored financial-document line exactly once. It never
  adds unbilled SO fees or reprices from current quotations, catalogs or exchange rates.
- The Tax Invoice title requires saved `documentTypeCode=TAX_INVOICE`; generic customer
  invoices retain Invoice. DRAFT output is watermarked. This classification does not certify
  regulatory acceptance. CANCELLED/REVERSED sources cannot use these layouts.
- Debit Note selects a stable actual-container ID and number belonging to the billed SO and
  customer. Same-type containers remain separate. Only that container's stored billed lines
  appear. Shared/unassigned lines remain consolidated only; they are never duplicated.
- Container output is labeled a breakdown of the original invoice and preserves its number.
  Printing creates no new receivable, journal, sequence number or settlement event.
- Decimal line/header reconciliation is mandatory. Stored discounts, explicit tax, currency,
  base amount and exchange-rate snapshot are used; no automatic VAT percentage applies.
  Document and base currencies use their separate configured display precision.
- Issuer identity comes from exactly one active Company party and branding settings, with
  the supplied LCS logo as fallback. Missing/ambiguous company setup blocks the UI. Customer
  details use the linked party. These existing master records are current display data;
  immutable historical issuer/contact snapshots are not introduced by this task.
- Bank display uses the selected financial account, or the unique active bank account for
  the document currency. Ambiguous accounts are omitted. Only stored masked account numbers
  are available; missing bank/signature details are never invented.

## Precision and currency contract

Current source evidence: finance monetary columns use NUMERIC(19,4), rates NUMERIC(19,8);
currency metadata permits 0–6 display decimals. Quotation _money rounds to two decimals.
These differ; they are not a single verified system-wide precision policy.
P07/P09 must test each existing calculation path before changing anything.

Target: quantities/rates preserve their accepted input precision; line net = quantity × rate
minus explicit discount plus explicit tax amount where supported. Sum rounded persisted lines
for document totals. Declare the rounding mode and scale for each document/currency; never
silently change historical totals. Conversion direction is 1 transaction unit × captured rate
= base units where that is the existing contract. Require positive finite rates, rate 1 for
same currency, effective date/source and base-currency snapshot. Missing historical base
currency/rate evidence is a visible warning, not fabricated history.

Estimated profit = estimated revenue − estimated cost; posted job profit = posted revenue −
posted cost. Margin = profit / revenue × 100; when revenue is zero show an undefined/empty
margin with explanation rather than divide by zero. Never sum mixed currencies without
conversion at the appropriate historical rates. Reconcile calculations after all-page exports,
not just the visible page.

## Smart Accounting Period Closing

Target workspace belongs to the existing Accounting Periods page (MOD-013); a dedicated 45th
navigation page remains a proposal requiring a scope decision before implementation.
The current close/reopen functions do not establish the rich workflow below.

### Review inputs and results

Select one period; display name, dates, status, posting count and existing close metadata.
Read-only review returns a generation timestamp, period identity/range, base currency,
testable check codes, severity, counts, affected record references and permission-aware links.
Only authorized readers see sensitive financial/account details. Missing permission or failed
checks must show incomplete review; do not interpret an inaccessible dataset as zero exceptions.

| Check | Blocking condition | Warning / review outcome |
|---|---|---|
| Period | Missing/invalid/overlapping range, wrong state or stale revision | Derived name/legacy metadata gaps |
| Draft documents/journals | Invalid in-scope item or unresolved item designated a closing blocker | Valid future/unposted work needing cutoff/accrual decision; do not automatically delete/post it |
| Ledger | Unbalanced journals/TB, invalid account/period references, failed control reconciliation | Unusual balance requiring explanation |
| AR/AP | Subledger/control difference, impossible allocation or missing posted source | Overdue amounts and unapplied balances with drill-down |
| Financial accounts | Unexplained reconciliation difference or required evidence missing | Explicit finance acknowledgment of documented timing differences |
| Charges/accruals | Duplicate billing or materially unresolved cutoff exception | Unbilled issued charges / unfinished cost capture requiring finance review |
| Balance Sheet | Assets − liabilities − equity including current result is nonzero under defined precision | Historical mapping gaps requiring resolution |
| Reports | Required result generation fails or snapshot cannot be tied to cutoff | Nonessential export/format warning |

Severity for materiality/cutoff exceptions requires finance approval; no invented numeric
threshold or universal rule that all drafts block month close. Structural integrity failures
always block. Warnings require acknowledgment and remain in history. Outstanding unpaid
invoices alone do not require every period to stay open.

### Close transaction

1. Authenticate and require existing close capability through Casbin; do not rely on UI status.
2. Recheck selected period state and a current review token/version under database transaction protection.
3. Recompute blocking checks or prove the reviewed inputs unchanged; fail stale review explicitly.
4. Serialize close with posting/reversal/FX actions affecting the period. A posting either commits
   before the captured cutoff and appears in it, or is refused after close.
5. Preserve period/actor/time/checks/warning acknowledgments and reproducible report evidence.
6. Mark CLOSED and write the audit event atomically. On any failure keep the period unchanged.
7. Retry returns the original successful close result or a clear already-closed outcome; no duplicate effects.

Do not delete/recreate transactions, reset sequences, purge balances or automatically transfer
annual retained earnings for an ordinary monthly lock. Operational drafts remain usable.

### Reopen and preservation

Require a distinct authorized reopening action, nonblank reason and audit event. Preserve every
previous closure even if current closed_by/closed_at are cleared. Previously preserved reports
remain labeled with their original cutoff; new generation after reopening is a new result.
A retained report needs generation parameters, base currency, cutoff/version and integrity
reference; secure file retention/reconciliation ownership is still TBD. Reuse audit history and
existing storage first. Propose additive closing-history/review persistence only if existing
records cannot preserve the required evidence; no table/API name is approved by this document.

Candidate review/close contracts belong to P10 after source inspection. Current /close and
generic /status paths are real; a /closing-review API is not implemented or promised.
Test all paths including generic period PUT/PATCH/status for bypass, stale review, duplicate
confirmation, rollback, concurrent posting, denied reopen and report preservation.

## Report and dashboard contract

All twelve report pages share the report profile in [inventory](../00-project/feature-inventory.md#report-profile).
Current engine.REPORTS registers only GL and TB for generate/export. Other reports use existing
service/router paths; never promise a generic generate endpoint for all twelve.

| Report | Target source and date basis | Grouping, totals and reconciliation |
|---|---|---|
| SO Register | Orders by declared order/created date; show chosen basis | SO/customer/direction/service/status, revenue/cost/profit with operational vs posted labels |
| SO Status | Orders/component state at cutoff | Created/updated/finished times, age and pending operational items; Finish and Active differ |
| Containers | Actual containers linked to SOs, selected operational cutoff | Type/status/order grouping and physical count; never count requirements as actuals |
| Profitability | Quoted, issued, draft and posted sources displayed separately | SO/customer, revenue/cost/profit/margin; reconcile posted portion to ledger dimensions |
| Revenue & Expense | Posted journal income/expense lines, posting-date interval | Account/party/SO; income = credit − debit, expense = debit − credit |
| AR | Posted receivable control movements and allocations effective at as-of date | Party/document/due-date aging, original/paid/outstanding; control account bridge includes unapplied receipts |
| AP | Posted payable control movements and allocations effective at as-of date | Party/bill/due-date aging; reconcile payable controls including unapplied payments |
| General Ledger | Posted journal lines by posting date, opening strictly before start | Account/party/source, stable date/journal/line ordering, running balance across pages |
| Trial Balance | Posted ledger movement, opening + interval = closing | Account hierarchy, opening/period/closing debit/credit; total net zero |
| Profit & Loss | Posted revenue/expense movement over interval | Account grouping; net result = revenue − expenses, base totals |
| Balance Sheet | Posted balances through as-of date | Assets = liabilities + equity including accumulated/current result exactly once |
| Cash Flow | Supported cash/bank ledger movements over interval | Opening + inflows − outflows = closing; internal cash transfers cancel in consolidated flow |

Cash Flow is the supported cash/bank movement view, not an asserted statutory direct/indirect
statement with unsupported classifications. New classifications need mappings and finance review.
Posted reversals must be represented consistently in every report. Screen/export/print share
filters and calculation semantics; current-source deficiencies remain explicit until tested.

Dashboard target uses posted income/expense/profit for the selected interval, AR/AP at the
displayed cutoff, ACTIVE and FINISHED SO counts by declared operational date basis, pending
financial actions, overdue eligible balances, permitted recent audit activity and period status.
Return metric source, dates and currency with values. Restrict individual metrics by underlying
capabilities; a dashboard permission must not reveal finance detail otherwise denied.
Current granularity endpoint alone is not evidence for arbitrary date filters or every metric.

## Deterministic automation and resource limits

Allocate numbers in the same workflow transaction; a failed operation must not create a
business duplicate. Do not promise gapless numbering. Populate related defaults only on
explicit selection/new capture; preserve user edits. Backend recalculation and state commands
are authoritative. Validate dates, duplicates, active references, status, permissions and
accounting rules with understandable field/page messages; no silent no-op or generic success.

Use existing pagination/filter/sort helpers and indexed query shapes. Avoid N+1, repeated
reference requests, full-history browser aggregates and unnecessary watchers. Cache stable
reference data with explicit invalidation after edit/status/import. Do not cache financial
results across postings without a proven freshness policy; current GL/TB generation is uncached.
No new Redis service, queue, external AI API, bank feed or scheduled job is required.

