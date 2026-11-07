# PLAN-0013 — S05 atomic customer-invoice posting (P08 task 08.1)

## Metadata

Slice: S05 — Customer Invoice Posting (P08 task 08.1: draft/type/source posting contract)
Status: Completed
Last updated: 2026-11-05
Task level: DEEP-lite (financial atomicity/concurrency; PostgreSQL race fixture executed)

## Objective and requirement IDs

Verify the Customer-Invoice posting contract end to end — authorized, atomic, idempotent,
unique, balanced, period-aware, rate-snapshot safe, audited — and fix demonstrated defects.
Requirements: LCS-005, LCS-006/009 cross-cuts; owner [P08 task 08.1](../phases/P08-financial-documents.md);
approved behaviors: [workflows.md §10](../../02-business/workflows.md) and the double-entry
invariants in [database-design](../../01-architecture/database-design.md).

## Posting sequence verified in the source (unchanged architecture)

`POST /financial-documents/{id}/post` (`financial_document.submit`, Casbin) →
`post_document` (finance/service.py): ① `SELECT … FOR UPDATE` on the document →
② replay: already POSTED returns the payload unmodified (no writes) →
③ non-DRAFT refused (InvalidState) → ④ `FinancialDocumentPosting` existence check
(`DUPLICATE_POSTING` even if the row were reset) → ⑤ posting date = `posting_date` or
`document_date` (creation date is never used) → ⑥ `resolve_period` requires an OPEN
period for that date (`PERIOD_NOT_OPEN` for a future draft, `PERIOD_CLOSED` for closed)
→ ⑦ `AccountingPostingService.build` resolves accounts from the **configured posting
rules** (no hardcoded accounts; fee-specific outranks document default; unconfigured
types refused, never guessed; missing/inactive/header accounts fail per field) →
⑸ journal needs ≥2 lines → ⑧ number allocation + journal header (DRAFT first —
`fn_guard_journal_line` is an immediate trigger that refuses lines on POSTED headers) →
⑨ Decimal lines with the document's stored `exchange_rate`/base conversions
(snapshot recomputation also repairs legacy rows, never today's rate) →
⑩ `assert_balanced()` + posted totals → ⑪ `FinancialDocumentPosting` link + document
POSTED + actor/time stamps → ⑫ **one commit**, then cache bump. Any earlier failure
rolls everything back (proven: `test_a_draft_is_never_half_posted…`).
Journals are written exclusively here (and by reversals/manual journals): charge issue
and explicit conversion write none (E29/E30 evidence, rerun in this batch's suites).

## Existing behavior that was already correct

Balanced/atomic posting (debit==credit asserted everywhere), duplicate-posting guards
(unique `uq_fin_doc_postings` + POSTED no-op), period gates (draft/closed tests),
rate snapshots (posting never uses today's rate; journal lines carry the document rate),
Casbin (`financial_document.submit`; issue/convert/submit codes are distinct pages of
the `finance.service_charges.submit` aggregate), printing read-only, reversal integrity.

## Demonstrated defect fixed

**Duplicate audit events on idempotent replay** (§12): the `post` router wrote
`FINANCIAL_POSTED` unconditionally, so replaying an already-posted document produced a
second audit event; the `issue` route did the same for `SERVICE_CHARGE_ISSUED`. Fixed:
`finance.service.document_status()` pre-reads the status (the same pattern the quotation
`before`/ops status trail uses) and both routers write the audit **only on the observed
transition** (post: `before != "POSTED"`; issue: `record_charge_status_change` returns
early when `before == "ISSUED"`). A posting leaves exactly one audited DRAFT→POSTED row
per document. Accepted-by-design: the `Idempotency-Key` header on post/issue stays
inert — uniqueness is source-based (posting link + state), so replay is already
deterministic without a key store; noted in the Handoff.

## Files changed

- `backend/app/modules/finance/service.py` — `document_status` helper (read-only).
- `backend/app/modules/finance/router.py` — transition-aware `FINANCIAL_POSTED` audit.
- `backend/app/modules/operations/service.py` — `record_charge_status_change` skips the
  replay (no behavioral change to charges themselves).
- Tests: `tests/test_financial_documents_module.py::test_posting_replay_returns_the_
  document_and_writes_one_audit_event` (one journal 100/100, two lines, one audit event
  after post + replay); `tests/test_finance_automation.py` — the re-issued-charge audit
  assertion extended to the replay; `tests/test_financial_posting_postgres.py` (new):
  disposable-PostgreSQL race harness.

## PostgreSQL evidence (disposable `lcs_verify5`, created and dropped after)

| Scenario | Command | Result / date |
|---|---|---|
| Test C — two independent sessions, barrier, simultaneous `post_document` | `LCS_TEST_PG_* → uv run --no-sync pytest -q tests/test_financial_posting_postgres.py` | 2 passed, 2026-11-05: one POSTED document, exactly one journal, one posting link, journal debit==credit==500 (AR debit / revenue credit); both callers answered POSTED |
| Test B — sequential replay on PG | same file | 1 posting; replay returns the same document, `(documents, journals, links) == (1, 1, 1)` |
| Test A/H | same file (the fixture posts a 500 document through the real rule resolution) | POSTED + balanced journal asserted before counts |

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| Posting module + rules + periods + issue/convert isolation (incl. new tests) | `uv run --no-sync pytest -q tests/test_financial_documents_module.py tests/test_finance_automation.py tests/test_posting_rules.py tests/test_accounting_periods.py` | 80 passed, 2026-11-05 |
| Broader focused regression (reporting/currency/created-by/job-finance + both PG files + chain/schema gates) | `uv run --no-sync pytest -q tests/test_reporting_values.py tests/test_charge_tax_round_trip.py tests/test_multi_currency.py tests/test_created_by.py tests/test_job_finance_entries.py tests/test_charge_conversion_postgres.py tests/test_migration_chain.py tests/test_schema_docs.py tests/test_schema_integrity.py` | 89 passed / 4 skipped (PG-env-guarded), ruff `app tests scripts` clean |
| Dev release | backend image rebuilt | healthy at head `b7c8d9e0f1a2` (no DB migration needed) |

## Acceptance criteria (§17)

All 16 points met: 1/5/6/7/11/12/13/14 verified read-only + suites; 2 (period), 3/4
(Decimal/balance), 8 (rollback — never-half-posted test), 9 (rate snapshot suites),
10 (single audited transition), 15 (PG race evidence), 16 (this document + tracker).

## Handoff

- Task 08.1 closed 2026-11-05. **S05 remains IN PROGRESS.** Next task: **08.2 — verify
  customer invoice/receipt flow** (post → partial/full allocation; AR and unapplied
  balances reconcile without a second revenue event); its building blocks exist and passed
  (allocation suites, receivables view). Risks carried: the service commit → router audit
  split is two transactions (an audit-write DB failure would leave a posted document
  without its event — accepted house pattern, recorded); `Idempotency-Key` inert on
  post/issue by design.
- No commit authorized yet.
