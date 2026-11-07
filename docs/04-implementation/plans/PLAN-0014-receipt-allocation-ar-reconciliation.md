# PLAN-0014 — S05 receipt allocation + AR reconciliation (P08 task 08.2)

## Metadata

Slice: S05 — Customer Invoice Posting (P08 task 08.2)
Status: Completed
Last updated: 2026-11-05
Task level: DEEP-lite (settlement integrity; PostgreSQL concurrency evidence)

## Objective and requirement IDs

Verify partial/full allocation, unapplied receipts, party ownership, concurrency and the
AR/GL reconciliation for posted customer invoices. Requirements: LCS-005, LCS-006/007
cross-cut; [P08 task 08.2](../phases/P08-financial-documents.md). 08.1's posting
architecture untouched.

## Allocation behavior verified (already correct, now regression-pinned)

`allocate_payment` (finance/service.py): validates the ALLOCATION schema → **both payment
and target rows `SELECT … FOR UPDATE`** → type gates (PAYMENT_TYPES → INVOICE_TYPES) →
both POSTED → same currency (`CURRENCY_MISMATCH`) → amount > 0 → receipt-balance check
(`ALLOCATION_EXCEEDS_BALANCE`) → target-outstanding check → Decimal settlement with the
payment/target documents' own stored rates (exchange difference reported, base amounts
computed — no rate guessing) → `paid_amount` += amount on both sides → commit. Receipts
first post cash against the control accounts (posting task 08.1 behavior); allocations
write no journal and recognize no revenue — they reclassify already-posted postings.
`financial_document_allocations.idempotency_key` (unique) replays with
`idempotentReplay: true`. Unapplied receipts: `total − paid_amount` tracked on the
document and surfaced as `paymentBalance`; the receivables/payables reports read
POSTED invoices/bills as `balance = total − paid` with OPEN/PARTIAL/PAID status.

## Demonstrated defects fixed

1. **No party-ownership guard**: a posted receipt could allocate another party's invoice
   (both sides' paid_amounts moved across customers). Fixed: `PARTY_MISMATCH` 409 when
   both documents carry a party and they differ (NULL-party documents keep working, e.g.
   legacy records). Pinned: the other party's invoice stays unpaid, the receipt stays
   fully unapplied.
2. **Replayed allocation duplicated the `PAYMENT_ALLOCATED` audit event** (same family as
   the 08.1 fix): the router now writes the audit only when the allocation is new
   (`idempotentReplay` absent). Pinned: exactly one audit event per settled allocation.

## Files changed

- `backend/app/modules/finance/service.py` — party-ownership guard (4 lines).
- `backend/app/modules/finance/router.py` — transition-aware allocation audit.
- Tests: `tests/test_job_finance_entries.py` — shared `_receipt` helper + two tests:
  the partial→full settlement journey and the cross-party refusal;
  `tests/test_financial_allocation_postgres.py` (new, disposable PG race harness).

## PostgreSQL evidence (disposable `lcs_verify7`, created and dropped after)

`LCS_TEST_PG_* → uv run --no-sync pytest -q tests/test_financial_allocation_postgres.py`
— 2 passed, 2026-11-05, real independent sessions + barrier:

- **Test I (race)**: two simultaneous 200 allocations on a 200-limit receipt → exactly
  one accepted, one `Conflict ALLOCATION_EXCEEDS_BALANCE` (409 semantics in the API path);
  `invoice.paid_amount == 200`, `receipt.paid_amount == 200`, one allocation row,
  outstanding 300 — no negative or double settlement.
- **Test H (same-key)**: sequential retry with `settle-once` → `idempotentReplay`,
  one allocation row.

## Focused verification (SQLite)

| Check | Command | Result / date |
|---|---|---|
| Settlement journey (Tests B/C/M/N + replay-audit) | `uv run --no-sync pytest -q tests/test_job_finance_entries.py` | 6 passed, 2026-11-05: 200 → PARTIAL 300, `paymentBalance` 0; replay → `idempotentReplay`, audit count == 2 (two new settlements only); 300 → outstanding 0/paid 500; invoice keeps exactly one 500/500 journal (revenue once); AR control (1100) nets 0 in the ledger-lines report == receivables' balance sum |
| Party mismatch + unapplied state (Tests D/G) | same file | 409 `PARTY_MISMATCH`; the foreign invoice unpaid; the receipt unapplied (`paidAmount` 0) |
| Broader regression | 15 focused files (job_finance, financial_documents_module, finance_automation, posting_rules, accounting_periods, multi_currency, workflows, reporting_values, charge_tax, created_by + 3 PG files env-guarded + chain/schema gates) | **190 passed / 6 skipped**, `ruff check app tests scripts` clean |
| Dev release | backend image rebuilt | healthy, no DB migration |

## Acceptance criteria (§14)

All 13 met: partial/full/unapplied/refusal/ownership verified; concurrency evidence on
real PostgreSQL; settlements atomic (row locks + single commit, DB-queried balances);
no duplicate revenue (invoice journal untouched: one 500/500 entry); periods/permissions
enforced (08.1's gates + `financial_document.allocate` Casbin); AR↔GL reconciled; rate
snapshots untouched (settlement FX reported as realized difference, never rewritten).

## Handoff

- Task 08.2 closed 2026-11-05. **S05 remains IN PROGRESS.** Next: **08.3 — supplier
  bill/payment flow** (the mirrored AP control: post bills, allocate eligible payments,
  over-allocation denied; the same service path already gates types/currency/party).
- Risks carried: allocations skip the OPEN-period gate (they write no journal —
  balance facts against posted documents; if S08/S06 requires period-gating of
  settlements, decide there); audit-write/post-commit two-transaction split (documented
  house pattern); no allocation deletion/adjustment workflow beyond reversals.
- No commit authorized yet.
