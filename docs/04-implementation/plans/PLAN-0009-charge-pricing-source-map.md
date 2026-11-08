# PLAN-0009 — S04 charge calculation and pricing source map (P07 task 07.1)

## Metadata

Slice: S04 — Service Charge to Financial Draft (P07 task 07.1 only)
Status: Completed (task 07.1; 07.2/07.3/07.4 remain)
Last updated: 2026-11-05
Task level: STANDARD (verification + evidence map; one behavioral mismatch recorded, none fixed)

## Objective and requirement IDs

Map how a Service Charge obtains prices, how amounts are calculated, who may override,
where journals may and may not appear, and which bill-once safeguards exist — before any
07.2 change. Requirements: LCS-004, LCS-005; LCS-CHG-001; [P07](../phases/P07-service-charges.md)
tasks 07.1–07.4; approved behavior in [workflows.md](../../02-business/workflows.md) §9.

## Charge schema map (real columns, `backend/app/modules/operations/models.py`)

- `ServiceOrderCharge`: charge_no (unique), document_type/service_note|debit_note|pro_forma
  (UI filter; API accepts CHARGE_DOCUMENT_TYPES), document_date, currency_code
  (defaults to the order's), status DRAFT/ISSUED, subtotal/discount/tax/total
  `Numeric(19,4)`, remark, data (JSON: invoice linkage/audit spill), created_by.
- `ServiceOrderChargeLine`: unique (charge_id, line_no); fee_type_id **nullable**
  (UI config requires it; the API tolerates a missing fee type with a description),
  service_order_container_id (validated to belong to the order — by id, never by type),
  quantity `Numeric(12,3)`, unit_code (free text), unit_price/discount/tax `Numeric(19,4)`,
  tax_rate `Numeric(7,4)`, line_amount `Numeric(19,4)`.
- Exchange rate: the charge has **no** rate column — single-document currency; the
  FinancialDocument carries `exchange_rate Numeric(19,8)` + base amounts.

## Calculation and rounding (Decimal end-to-end, backend authoritative)

`save_charge` (operations/service.py:1169) rebuilds priced lines **only when the caller
sent them** (partial updates never wipe lines/totals): `parse_decimal` refuses more
precision than the column scale (no silent rounding), quantity must be >0, unit price and
tax ≥0, discount bounded by the base; tax resolves rate-vs-amount (explicit rate wins);
`line_total = qty×price − discount + tax`; totals are Decimal sums; DB stores at column
scale. Frontend `computeFeeLine`/`serviceChargeAmounts` (JS Numbers) are display
projections only — money never round-trips through them. Profitability
(reports/service.py) is backend Decimal: revenue/cost from POSTED journals, issued vs
draft charges kept apart, `margin = profit/revenue×100` only when revenue ≠ 0.

## Pricing source map (verified, none invented)

| Candidate source | Status |
|---|---|
| Quotation line | Not used for charges: conversion copies pricing into the *order document*, never into charge lines |
| Configured service pricing | Does not exist |
| Fee Type default | `fee_types` has no price column |
| Manual input | **The only source**: qty/unit price typed in the charge form (SO charges tab one-line draft; Service Charges page editable fee lines) |
| Existing Service Order charge | Duplicating a charge copies nothing; charges are created fresh |

Override rules: qty/unit price/currency editable while DRAFT (`Only draft service charges
can be edited.`, issued charges immutable — `test_service_charge_validation_and_
issued_immutability`); a partially-sent update never recalculates untouched lines; no
recalculation trigger can silently rewrite a saved price (line rebuild happens only on
explicit lines resubmission; the invoice copies the charge's stored values). Permissions:
`service_charge.create`/`update`/`submit` (issue)/`convert_to_invoice`, Casbin-checked at
the router.

## Issue lifecycle and journal boundary (critical rule verified)

- `issue_charge`: `SELECT … FOR UPDATE` row lock, DRAFT/ISSUED only, needs ≥1 positive
  line and positive total → sets ISSUED + `SERVICE_CHARGE_ISSUED` audit event.
- **No journal entry is written on issue** — the issue path creates a DRAFT
  FinancialDocument (+ lines + `SERVICE_ORDER_CHARGE` source row) only; journal entries
  are written exclusively by finance-authorized `post_document`
  (balanced/atomic, proven by the posting suites).
- **Demonstrated mismatch with the approved spec (assigned 07.2)**: workflows.md §9
  steps 9–10 say *issuing must not create a finance draft* and the draft is created by a
  separate finance-authorized action; `issue_charge` (operations/service.py:1338–1344)
  currently calls `create_invoice_from_charge` **automatically** on issue. This gives a
  `service_charge.submit` holder the conversion outcome the spec reserves for
  `service_charge.convert_to_invoice`. No accounting harm (document stays DRAFT, no
  journal) — recorded as a workflow-isolation defect, to be corrected in 07.2 with the
  existing `create-finance-invoice` endpoint retained as the explicit path.

## Bill-once readiness (for 07.3)

- Charge identity: `uq_service_order_charges_no`; draft/edit only pre-issue; already-billed
  edit refused.
- Conversion dedupe: `FinancialDocumentSource` lookup returns the existing document
  (idempotent replay); `uq_fin_doc_sources` is per-(document, source) and therefore
  cannot by itself stop **two different drafts for one charge**.
- Concurrency: concurrent `issue` is serialized by the charge row lock; the standalone
  `/service-charges/{id}/create-finance-invoice` endpoint takes no lock, so two simultaneous
  conversions could pass the existing-check together on PostgreSQL (SQLite cannot prove
  the race). 07.3 must add the missing race fixture/guard (e.g. charge-row lock or DB
  unique index per (source_type, source_id, relationship_type)).
- `Idempotency-Key` headers are accepted but not yet consumed on the issue/convert
  charge endpoints (note for 07.3).

## Error handling (verified behavior, nothing added)

Missing fee type: allowed at API (UI requires it) · invalid quantity/precision: 422 ·
negative price/discount-out-of-range/tax bounds: 422 · currency: must be an active master
(422) · missing rate: charge never needs one (invoice resolves its approved rate) ·
container from another order: 422 · duplicate charge_no: caller-supplied duplicates hit
the unique constraint (500; UI never supplies the number — allocation only; low risk,
note) · locked states: only DRAFT editable, inactive order 409, **finish keeps charges
writable (approved: finance continues after Finish)** · unauthorized: 403 per code.

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| Charge tax shape round trip (rate/amount/both, bounds, issued-immutability) | `uv run --no-sync pytest -q tests/test_charge_tax_round_trip.py tests/test_finance_automation.py tests/test_job_finance_entries.py` | 14 passed / 0 failed, 2026-11-05 |
| Source trace (no code change): save_charge, issue_charge, create_invoice_from_charge, post_document boundary, fee_types schema, computeFeeLine/serviceChargeAmounts, profitability rows | Read-only inspection of the files listed below | Confirms the map above, 2026-11-05 |
| Prior executions reused (not rerun): issue→no-journal, posting balance, charge totals, allocation | E25/E27 evidence (`tests/test_workflows.py`, `test_quotation_reuse.py`) | 2026-11-04/05 |

## Acceptance criteria (07.1)

1–12 from the P07 task table: calculation/price/override/issue/journal/bill-once maps
recorded; Decimal + currency behavior verified; container ownership by id verified;
no code change was required by this task; 07.2 handoff below.

## Handoff

- Task 07.1 closed 2026-11-05. S04 remains IN PROGRESS (07.2 next). No commit authorized.
- **07.2 executed 2026-11-05** — [PLAN-0010](PLAN-0010-issue-isolation.md)/E29: the recorded
  mismatch is fixed (issue no longer auto-creates the draft; convert stays explicit).
- **07.3 executed 2026-11-05** — [PLAN-0011](PLAN-0011-bill-once-conversion-idempotency.md)/E30:
  the recorded convert race is closed (`FOR UPDATE` + partial unique source index +
  idempotency keys; PG race 4 passed). Next: 07.4 profit-layer reconciliation.
- Open risks carried: standalone-convert race (07.3), report mixed-currency sums
  (S09/S10), ignored `Idempotency-Key` (07.3), caller-supplied duplicate charge_no 500
  (note only).
