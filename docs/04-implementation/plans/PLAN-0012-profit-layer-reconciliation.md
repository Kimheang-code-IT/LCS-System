# PLAN-0012 — S04 profit-layer reconciliation (P07 task 07.4)

## Metadata

Slice: S04 — Service Charge to Financial Draft (P07 task 07.4)
Status: Completed (task + slice closure)
Last updated: 2026-11-05
Task level: STANDARD (read-model fix in the reporting layer; no migration, no service/flow change)

## Objective and requirement IDs

Verify the four profit layers and their currencies, remove double counting and
mixed-currency sums from the profitability report, and close S04.
Requirements: LCS-004, LCS-005, LCS-008 (currency/presentation prerequisites for
S09/S10); workflows.md §9 (automatic service-order finance reporting: "calculates gross
profit, margin, and uninvoiced issued charges without browser-side aggregation").

## Layer map (verified before any change)

| Layer | Source | Status filter | Currency | Method |
|---|---|---|---|---|
| Estimated revenue/cost | `quotation_revisions.total_amount` via the order's pinned revision | any | revision currency | report column `quoted`; **no cost-estimate source exists in the approved schema** (quotation is one-sided, supplier quotes absent) — not invented |
| Issued charges | `service_order_charges.total_amount` | ISSUED | **charge document currency** (defaults to order currency) | operational layer, never posting |
| Charge → draft | `financial_documents.total_amount` linked by `financial_document_sources` (SERVICE_ORDER_CHARGE) | DRAFT | invoice's currency (charge's, + own approved rate → `base_total_amount`) | same underlying charge, separate lifecycle column |
| Posted layers | POSTED CUSTOMER_INVOICE / SUPPLIER_BILL documents (and their balanced journals) | POSTED (REVERSED excluded — its reversal journal keeps the ledger net) | document currency + **rate snapshot in `base_total_amount`** | ledger-true reporting (GL/trial-balance precedent) |
| Profit / Margin | posted revenue − posted cost; margin = profit/revenue×100 | — | base | Decimal; revenue == 0 → margin 0 (documented rule), losses never hidden |

Reused as-is: Decimal arithmetic (`Numeric` columns, no float in backend), the 07.3
bill-once source links (attribution), the receivables/paid views, `cache.bump`-driven
report refresh, the frontend `formatFreightCell` row-currency formatting.

## Demonstrated defects fixed

1. **Mixed-currency posted/draft sums** (07.1 risk, confirmed): `posted_revenue`,
   `posted_cost` and `draft_revenue` summed document-currency `total_amount`, so a KHR
   invoice posted against a USD order injected raw KHR into the profit. The finance
   layers now sum `base_total_amount` — the ledger's own conversion with each document's
   approved rate snapshot (no guessing, no current-rate recalculation; original amounts
   untouched on the documents).
2. **Mixed-currency charge layers** (07.1 risk, edge case): the charges layer summed all
   ISSUED/DRAFT charges of an order across currencies. New
   `ReportRepository.profitability_charge_layers` groups per (`order_id`, **document
   currency**): issued/draft charges and the non-reversed linked finance documents. The
   numeric columns keep the **order currency's** group; foreign layers surface as
   explicit grouped strings (`layersByCurrency`, `uninvoicedByCurrency`) with
   `mixedCurrency: true` — never silently summed.
3. **`uninvoicedCharges` mixed-arithmetics**: the old formula subtracted the posted and
   draft *finance* amounts (now base) from the issued *charge* total (document currency).
   Replaced with per-currency attribution: `uninvoiced(currency) = max(0, issued −
   linked)`, where linked = DRAFT + POSTED documents with a charge source link, REVERSED
   excluded. A converted-then-posted charge therefore reports 0 exactly once, and a direct
   (non-charge) invoice can no longer distort the charge-attributed figure.

No service or document-write code changed: the report is read-only (test-asserted), and
no layer creates journals or financial records.

## Files changed

- `backend/app/modules/reports/repository.py` — finance layers sum `base_total_amount`;
  new `profitability_charge_layers` (doc-currency groups, source-link attribution).
- `backend/app/modules/reports/service.py` — layer assembly (order-currency group vs
  mixed grouped fields), `baseCurrency` field, Decimal→string formatting without
  scientific notation.
- `frontend/app/config/freight-reports.ts` — profitability catalog gains 4 columns
  (Draft Finance, Uninvoiced, In, Mixed Currencies — plain labels, existing col/n()
  pattern; no new page, no new component).
- `frontend/tests/operations-reports.spec.ts` — pinned column list extended.

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| Backend focused regression (incl. chain/schema/integrity + the PG race fixture skip-guarded) | `uv run --no-sync pytest -q` on the 14 focused files (finance_automation, charge_tax, multi_currency, reporting_values, created_by, job_finance_entries, financial_documents_module, reports_dashboard, report_generation, workflows, charge_conversion_postgres, migration_chain, schema_docs, schema_integrity) | **151 passed / 4 skipped** (skips = PG env absent for the race file), `ruff check app tests scripts` clean |
| Test A/B/C/F/H — KHR order lifecycle in one test | `tests/test_reporting_values.py::test_profitability_layers_follow_the_ledger_currency_rules` | passed: quoted 100 (KHR estimate), serviceCharges 110 (charge doc currency), postedRevenue = base-converted (≈110×0.00025, not the raw 110), uninvoicedCharges 0 (no double count), margin 100, zero-revenue/zero-division rule exercised by the mixed test, report GET writes no journal (before/after counts) |
| Test D/E — mixed currencies grouped | `…::test_mixed_currency_charges_are_grouped_never_summed` | passed: `mixedCurrency` flag; serviceCharges keeps 110 (order currency), KHR group only in `layersByCurrency`/`uninvoicedByCurrency`; margin 0 without division error |
| Test B/C/G/H | prior E29/E30 suites rerun in the 151 | issue isolation, single-draft conversion, posting-only journals, no historical rewrite |
| Frontend gates | `pnpm exec vitest run`; `pnpm typecheck`; eslint; `pnpm i18n:check` | 825 passed (99 files); typecheck 0; eslint 0; locale check passed |
| Dev compose | both images rebuilt | healthy, 2026-11-05 |

Disposable PostgreSQL was **not** needed for this task (no migration, no PG-specific
behavior — the layer queries ran in the suites; the race file skipped with its guard).

## Acceptance criteria (07.4)

§16 tests A–H all executed with the results above; no estimated-cost source was invented
(documented absent); no new tables; all money arithmetic stays backend Decimal.

## Handoff / S04 closure

- **S04 is COMPLETE 2026-11-05** (PLAN-0009–0012; evidence E28–E31). The slice outcome —
  issue has no ledger effect, explicit conversion yields exactly one draft — is proven at
  API, unit and PostgreSQL concurrency levels.
- Deferred with owners: per-currency report redesign + date semantics → S09/S10
  (LCS-008 full acceptance, P11/P12); container-level profitability (no money allocations
  exist in the schema — container register carries no amounts; do not invent); browser
  journeys for charge issue/convert → NT02.
- Remaining risks: `layersByCurrency`/`uninvoicedByCurrency` are plain strings (S09/S10
  will formalize presentation); margin=0 at zero revenue is the documented display rule.
- No commit authorized yet; the whole S04 batch rides uncommitted.
