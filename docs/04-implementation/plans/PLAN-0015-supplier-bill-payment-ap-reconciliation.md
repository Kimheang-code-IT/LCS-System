# PLAN-0015 — S05 supplier bill/payment + AP reconciliation (P08 task 08.3)

## Metadata

Slice: S05 — Customer Invoice Posting (P08 task 08.3)
Status: Completed
Last updated: 2026-11-05
Task level: STANDARD (verification of shared finance services; no product code change)

## Objective and requirement IDs

Verify the supplier bill/payment lifecycle and AP reconciliation on the sharing finance
architecture established in 08.1/08.2. Requirements: LCS-005, LCS-006/007 cross-cut;
[P08 task 08.3](../phases/P08-financial-documents.md); posting design in
[posting.py](../../../backend/app/modules/finance/posting.py): SUPPLIER_BILL →
Dr expense per fee line (5010) / Cr payable control (2010), tax split when configured;
SUPPLIER_PAYMENT → Dr payable (2010) / Cr bank (1020) — no unapplied clearing account
exists; payments settle directly against the control account, allocations stay
journal-free (documented design, not changed).

## Verified behavior (reusing the 08.1/08.2 services — no new AP code)

- **Bill lifecycle**: DRAFT create (party, lines, currency) → `financial_document.submit`
  post through the OPEN-period gate → one balanced journal (Dr 5010/Cr 2010, totals 300);
  replay/second post idempotent (POSTED no-op + `DUPLICATE_POSTING` guard); posted
  documents keep their stamped values and rate snapshots.
- **Payment lifecycle**: `SUPPLIER_PAYMENT` DRAFT → post (period/permission/Decimals) —
  never re-records the bill's expense; allocations move only `paid_amount` balances.
- **Allocation**: the **shared** `allocate_payment` (no AP-only service): both documents
  `FOR UPDATE`-locked, POSTED-only, `CURRENCY_MISMATCH`, positive amount, receipt/payment
  balance and target-outstanding bounds (`ALLOCATION_EXCEEDS_BALANCE`),
  **`PARTY_MISMATCH`** (the 08.2 guard covers the supplier pair — one supplier's payment
  cannot settle another supplier's bill), `idempotency_key` replay
  (`idempotentReplay`), transition-aware audit (08.2 fix, shared router).
- **AP reconciliation**: bills Dr 5010 once (expense recognized once, journal untouched
  by settlements); control account 2010 **nets 0** in the ledger-lines report == the
  payables report's balance sum; unapplied payment = `total − paid_amount` on the
  document (`paymentBalance`).
- **Periods/permissions**: posting (bill + payment) requires `financial_document.submit`
  + an OPEN period; allocation requires `financial_document.allocate`; **allocations
  keep skipping the period gate by documented design (no journal)** — the settlement
  period-gating decision stays with the accounting-period phase (S06/S08), recorded in
  the P08 doc.

## Files changed (tests only)

- `tests/test_job_finance_entries.py` — supplier fixtures (`_bill`, `_supplier_payment`,
  `_supplier_posting_test_parties`) + the AP journey and the cross-supplier refusal test.
- `tests/test_supplier_allocation_postgres.py` — disposable-PostgreSQL race harness
  (mirrors the AR fixture; same `allocate_payment` service, supplier document types).

## PostgreSQL evidence (disposable `lcs_verify8`, created and dropped after)

`LCS_TEST_PG_* → uv run --no-sync pytest -q tests/test_supplier_allocation_postgres.py`
— 2 passed, 2026-11-05, real independent sessions + barrier:

- Concurrent allocations of a 200-limit supplier payment against a posted 300 bill →
  exactly one accepted + one `ALLOCATION_EXCEEDS_BALANCE` `Conflict`; one allocation row;
  both `paid_amount == 200`; bill outstanding 300 (no negative/no double settlement).
- Sequential same-key retry → `idempotentReplay` with a single allocation row.

## Focused verification (SQLite)

| Check | Command | Result / date |
|---|---|---|
| AP journey (Tests A/B/D/E/F/H/O/P) + AR journey re-run | `uv run --no-sync pytest -q tests/test_job_finance_entries.py` | 8 passed, 2026-11-05 |
| Posting/rules/periods/multi-currency/workflows/reporting regression | 15 focused files incl. both PG files (env-guarded) + chain/schema gates | **192 passed / 6 skipped**, `ruff check app tests scripts` clean |
| Dev release | none needed | no product code changed; the running image already matches the tree |

## Acceptance criteria (§17)

All 15 met: bills/payments post balanced and once (5→1 audits), allocations partial/full
work with unapplied accuracy, cross-supplier and over-allocation refused, concurrency
PG-proven, AP report↔GL reconciled (net 0), currency snapshots intact, Casbin enforced,
focused tests + docs done.

## Handoff

- Task 08.3 closed 2026-11-05. **S05 remains IN PROGRESS** (08.4 open). Next:
  **08.4 — correction/races**: reversal + duplicate post/allocation + closed-period
  receipt on the same architecture; reversal/integrity suites already exist and pass —
  verify remaining gaps (closed-period allocation policy question above).
- Carried risks: allocation period-gating deferred to the accounting-period phase; the
  audit-write/post-commit split (house pattern); no allocation-deletion workflow beyond
  reversal. No commit authorized yet.
