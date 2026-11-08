# PLAN-0016 — S05 corrections/reversals + acceptance review (P08 task 08.4)

## Metadata

Slice: S05 — Customer Invoice Posting (P08 task 08.4 + S05 acceptance review)
Status: Completed (slice closed)
Last updated: 2026-11-05
Task level: DEEP-lite (reversal integrity + audit/period/concurrency review; tests only)

## Objective and requirement IDs

Verify the correction/reversal contract and duplicate protection end to end, then close
S05. Requirements: LCS-005, LCS-006/009; [P08 task 08.4](../phases/P08-financial-documents.md);
approved reversal model in workflows.md §10 and posting.py (mirrored lines, originals
preserved, reversal-of link).

## Reversal contract verified (existing implementation — no changes needed)

`reverse_document` (finance/service.py, `financial_document.reverse`): FOR UPDATE lock →
`DOCUMENT_ALREADY_REVERSED` replay refusal (409) → POSTED-only → mirror journal: every
original line copied debit↔credit **with the original line's own stored currency/rate
snapshot** (base amounts mirrored the same way — nothing re-rated); header
`REVERSAL OF {original}` + `reversal_of_journal_entry_id` + the original's
`posting_rule_id` (auditor sees both sides of one rule) → posting date = **today**, gated
by the OPEN-period check (reversals are corrections in the current period; the original
period stays untouched — a closed period is never reopened, and a document can never be
rewritten by changing its date) → DRAFT-then-POSTED promotion (trigger-ordered) →
balanced totals → `FINANCIAL_REVERSED` audit with the reason → document REVERSED,
`paid_amount` reset to 0 → one commit.

**Allocation undo is implemented and now verified**: allocations are removed and the
other side's `paid_amount` is restored (`max(0, paid − allocated)`) *so the subledger
matches the ledger*. No refund journal, no money movement: a received amount stays
received (the receipt journal survives); the receipt becomes unapplied and can allocate
another document. A reversed pair leaves the AR control carrying exactly the customer
credit the unapplied receipt represents; the AR report (POSTED invoices only) drops the
reversed row and its balance sum continues to reconcile (money received, not owed).

## Demonstration and verification (tests only — no product code changed)

| Scenario (§18) | Evidence | Result |
|---|---|---|
| A/B/D — customer invoice reversal + supplier bill/payment reversal (shared path) | `test_document_reversal` (existing) + the mirrored-lines code verified read-only; supplier side uses the identical function | PASS |
| E — **reversal after allocation** (the high-risk scenario, previously uncovered) | new `test_reversing_an_allocated_invoice_unsettles_and_money_stays_received` | PASS: allocations removed, receipt `paid_amount` 0 (unapplied, not refunded), original + reversal both POSTED and balanced (500/500), `FINANCIAL_REVERSED` audited **exactly once**, ledger net = AR −200 (the receipt's valid customer credit), receivables balance sum 0 |
| F — duplicate reversal replay | same test (`DOCUMENT_ALREADY_REVERSED` 409, audit count unchanged) | PASS |
| B/C/H/L — mirrored balances, period gates, snapshot preservation | existing suites rerun (posting_rules/accounting_periods/multi_currency/reporting_values) | PASS |
| I/K — reversal posts into today's OPEN period; concurrency by the same FOR-UPDATE pattern already PG-proven for posting + allocation (twice each) | reuse of 08.1/08.2 PG evidence; no new PG run needed for the identical lock pattern | PASS (documented reuse) |
| J — Casbin: view-only finance account cannot post/allocate/reverse | new `test_financial_permissions_stay_separate` (three 403s + read 200, nothing changed) | PASS |
| M/N/O — reconciliation, single audits, no orphans | the E32–E34 suites + this batch | PASS |
| Posted-document editing refusal | `save_document`: `Only draft documents can be edited; posted documents require a reversal.` (existing guard, verified read-only) | PASS |

`uv run --no-sync pytest -q` (17 focused files) → **194 passed / 10 skipped**
(skips = the two race files' env guards on the worker without `LCS_TEST_PG_*`; those
suites' PG evidence was produced earlier this session: posting 2, AR allocation 2,
supplier allocation 2, charge conversion 4 — disposable DBs dropped after each run).
`ruff check app tests scripts` clean. No frontend change → no browser run; printing
stays read-only (verified by source + the PLAN-0004 evidence).

## Audit + period policy findings (documented, non-blocking)

1. **Audit split** (technical debt, owner: finance module maintenance in S06+): the
   service commits the financial change before the router commits the audit event; an
   audit-write DB failure would leave a posted document without its event. Transition-aware
   audits (08.1/08.2) and single-event behavior are preserved and pinned. Non-blocking:
   the acceptance criterion (documented correct behavior) is met by the verified sequence;
   the residual is a rare DB-failure edge, recorded with its owner and rationale.
2. **Allocation period gate** (decision owner: accounting-period phase, S06/S08):
   allocations write no journal, so no OPEN-period check applies today; settlement dates
   can fall in closed periods after a later close. Requirements do not demand a gate;
   policy recorded, nothing silently changed.

## S05 final acceptance review

- 08.1 ✓ (E32), 08.2 ✓ (E33), 08.3 ✓ (E34), 08.4 ✓ (E35) — all four P08 tasks closed with
  executed API/unit/PostgreSQL evidence.
- Outcome verified: "Atomic unique balanced posting with source and rate snapshots" —
  posting/reversal/allocation all lock→validate→settle→commit atomically with database
  uniqueness, typed refusals and single transition-aware audit events; AR/AP reports and
  the GL control accounts reconcile (net zero after settlement/zero after a full pair).
- No blocking financial-integrity defect remains. Deferred with owners: allocation
  period-gate (S06/S08), audit-transaction split (S06+ maintenance), per-currency report
  presentation (S09/S10), browser journeys (NT02).
- **S05 is COMPLETED 2026-11-05.**

## Handoff

- No commit authorized yet; the whole S01–S05 batch rides uncommitted in the working tree.
- Next slice **S06 — Customer Receipt and Settlement** (LCS-006,007): partial/full
  allocation against posted receipts, over-allocation denial, currency/party
  reconciliation — most building blocks exist and pass; the first S06 task should verify
  the *settlement* semantics (multi-document allocation, credit notes, unapplied receipts
  reporting) from [P08](../phases/P08-financial-documents.md) 08.2/08.4 and
  [acceptance-criteria](../acceptance-criteria.md) FLOW-010.
