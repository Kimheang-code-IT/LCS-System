---
name: finance-accounting
description: Use when implementing or changing LCS double-entry accounting, posting rules, journal entries, accounting periods, financial documents, payments, payment allocations, reversals, multi-currency handling, or financial reports.
---

# Finance and accounting

The ledger is the system of record. Every change here is high-risk: posted history
must stay immutable, every journal must balance, and each posting must be atomic.

## When to use

- Posting or reversing a financial document or journal.
- Changing posting-rule resolution, account mapping, or period handling.
- Allocating a payment, or changing allocation validation.
- Building or fixing a financial report or SQL view.

## Required inputs

1. The accounting event and its debit/credit effect, stated explicitly.
2. Which accounts are involved and whether they are postable.
3. The currency, the exchange rate source, and whether a rate must be snapshotted.

## Project references

| Document | Use it for |
|---|---|
| `docs/05_solution_architecture.md` | Posting engine description and layering |
| `docs/06b_database_design_annotated.sql` | Exact columns, including base-currency amounts |
| `docs/14_47_table_migration_analysis.md` §2.5 | Why payments and allocations keep their current shape |
| `backend/alembic/versions/e6f7a8b9c0d1_reporting_views_and_integrity.py` | The authoritative database-level invariants |
| `backend/tests/sql/integrity_guards.sql` | Executable proof each guard fires |

## Invariants (never weaken)

1. **Total debit equals total credit.** Enforced in the service
   (`Conflict("JOURNAL_UNBALANCED")`) and by the deferred constraint trigger
   `fn_validate_journal_post`, which fires at COMMIT after the lines exist.
2. **Atomic posting.** One transaction: journal + lines + posting link + document
   status. A failure leaves nothing behind.
3. **Open period only.** The entry date must fall inside an `OPEN`
   `accounting_periods` row, or `Conflict("PERIOD_CLOSED")`.
4. **No duplicate posting.** `financial_document_postings` is unique on
   `(financial_document_id, journal_entry_id)`, and `post_document` is idempotent
   for an already-POSTED document.
5. **Posted history is immutable.** `fn_guard_journal_entry` and
   `fn_guard_journal_line` raise on any update or delete of a POSTED journal or its
   lines. Corrections go through `reverse_document`.
6. **Postable accounts only.** An account must exist, be `is_postable`, and be
   `ACTIVE` (`_validate_posting_account`).
7. **No over-allocation.** `fn_guard_allocation` and `allocate_payment` both cap an
   allocation at the remaining balance of the payment *and* the invoice. Allocation
   also requires matching party and currency.
8. **Money is `NUMERIC(19,4)`, rates are `NUMERIC(19,8)`, decoded as `Decimal`.**
9. **Historical rates are preserved.** A posting snapshots the rate it used in
   `financial_documents.exchange_rate` and `journal_entry_lines.exchange_rate`, and
   stores `base_debit_amount` / `base_credit_amount`. Never recompute a posted
   amount from a new rate.
10. **A reversal is a new journal**, with swapped debit/credit, linked by
    `reversal_of_journal_entry_id`, and it unwinds allocations so `paid_amount`
    matches the subledger.

## Workflow

1. **Read the existing flow before editing.** `post_document` resolves the period,
   resolves rules, allocates a journal number, builds the journal as `DRAFT`,
   appends lines, promotes to `POSTED`, links the posting, and stamps the document.
   `reverse_document` mirrors it and then unwinds allocations.
2. **Resolve accounts through `posting_rules`, not a constant.** `_resolve_rule`
   prefers a rule for `(document_type, fee_type_id)`, then the `fee_type_id IS NULL`
   rule, and only then the `DEFAULT_ACCOUNTS` fallback in `finance/service.py`.
   Ambiguity (`>1` active matching rule) is a `Conflict("AMBIGUOUS_POSTING_RULE")`,
   not a coin flip. When behaviour should be configurable, add or seed a rule
   rather than editing `DEFAULT_ACCOUNTS`.
3. **Create the journal as `DRAFT`, then promote.** The line guard forbids adding
   lines to an already-POSTED journal, so the ordering is mandatory, not cosmetic.
4. **Keep the detailed-posting branch intact.** For `CUSTOMER_INVOICE` /
   `OTHER_INCOME` (credit types) and `SUPPLIER_BILL` / `OTHER_EXPENSE` (debit
   types) the control side takes the document total and each source line resolves
   its own rule, with tax split to the rule's `tax_account_id`. Changing this
   changes reported revenue and tax.
5. **Report from posted data only.** Sum `journal_entry_lines` joined to
   `journal_entries WHERE status = 'POSTED'`, or use the supplied views
   (`vw_trial_balance`, `vw_general_ledger`, `vw_invoice_outstanding`,
   `vw_service_order_charge_summary`, `vw_payments`, `vw_payment_allocations`).
   Never sum across currencies without normalising, and never add a derived total
   to a stored column.
6. **Prove the result reconciles.** Trial balance must net to zero; AR/AP must
   equal the posted control accounts; job profitability must equal posted revenue
   minus posted cost for that order.

## Security and validation requirements

- Posting and reversing are separate permissions
  (`financial_document.post`, `financial_document.reverse`); do not fold them.
- Never accept an account id, period id, or amount from the client for a posting
  the backend can derive.
- Reject a negative or zero document total before posting.
- Do not expose another party's balances; report endpoints are permission-gated
  and rate-limited.
- Keep `allocation` creation idempotent via the `Idempotency-Key` header where the
  endpoint already supports it, so a retried request cannot double-allocate.

## Testing

```bash
cd backend
uv run python -m pytest tests/test_finance_automation.py tests/test_workflows.py -q --no-header
uv run python -m pytest -q
uv run ruff check .
```

Required cases for any finance change:

| Case | Expected |
|---|---|
| Balanced journal posted | succeeds, ledger nets to zero |
| Unbalanced journal posted | rejected (`JOURNAL_UNBALANCED` and the DB trigger) |
| Journal with fewer than two lines | rejected |
| Posting into a CLOSED period | rejected (`PERIOD_CLOSED`) |
| Duplicate posting of one document | idempotent, one journal |
| Partial payment | invoice `paid_amount` reduced, status PARTIAL |
| Payment allocated to several invoices | allowed up to the payment total |
| Over-allocation | rejected (`ALLOCATION_EXCEEDS_BALANCE`) |
| Reversal | new POSTED journal, original unchanged, allocations unwound |
| Editing or deleting a POSTED journal | rejected by the trigger |

PostgreSQL-only guards are exercised by
`psql <disposable> -f backend/tests/sql/integrity_guards.sql` — 16 scenarios. Run
it after changing any trigger or view.

## Acceptance criteria

- Debit equals credit for every new journal, proven by a test.
- No posted row is mutated; corrections use reversals.
- Closed periods cannot accept postings.
- Duplicate posting and over-allocation are impossible, proven by a test.
- Amounts are `Decimal` end to end, with no float conversion.
- The affected report reconciles against posted data, and the check is recorded.
- The full backend suite and ruff pass, including the integrity-guard script when
  a trigger or view changed.

## Expected outputs

- Changed `finance/service.py` (and `repository.py` when a query changed).
- A new Alembic revision if an invariant is added at the database level.
- Tests covering each row of the table above that the change can affect.
- An updated posting-rule or report description in `docs/`.
