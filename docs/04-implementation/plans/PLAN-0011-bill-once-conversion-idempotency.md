# PLAN-0011 — S04 bill-once conversion + idempotency keys (P07 task 07.3)

## Metadata

Slice: S04 — Service Charge to Financial Draft (P07 task 07.3)
Status: Completed
Last updated: 2026-11-05
Task level: DEEP-lite (concurrency + additive migration; PostgreSQL race fixture executed)

## Objective and requirement IDs

Two simultaneous conversions of one issued Service Charge must create exactly one Finance
Document draft — with and without Idempotency-Keys — and a replayed key must return its
document without drafting twice. Requirements: LCS-004, LCS-005; workflows.md §9
(convert-to-finance-invoice procedure); [PLAN-0009](PLAN-0009-charge-pricing-source-map.md)
recorded the race; [PLAN-0010](PLAN-0010-issue-isolation.md) fixed issue isolation.

## Root cause

`create_invoice_from_charge` guards against double conversion with an app-level
"existing source row" check only. The standalone endpoint `POST /service-charges/{id}/
create-finance-invoice` took no lock, so on PostgreSQL two concurrent conversions could
both pass the check (READ COMMITTED, no serialization point) and each commit a
`CUSTOMER_INVOICE` DRAFT plus its own `financial_document_sources` row —
`uq_fin_doc_sources` (financial_document_id, source_type, source_id, relationship_type)
cannot see two links that share the source but not the document.

## Locking strategy and transaction boundaries

- `charge_to_invoice` (operations/service.py) now loads the charge with
  `SELECT … FOR UPDATE` — the row lock covers the whole check-and-create conversion;
  the second concurrent convert waits there and its fresh re-check inside the finance
  service returns the winner's document. Same-commitment as the existing `issue_charge`
  lock style; no new transaction boundary, no nested commits (the single commit lives in
  the finance service).
- Lock order: charge row → source/document inserts (unchanged write order), so no new
  deadlock surface.

## Database enforcement (additive migration `b7c8d9e0f1a2`)

- `financial_document_sources.idempotency_key` — nullable `String(128)`, unique, the
  house pattern (same as `financial_document_allocations.idempotency_key`); retained with
  the relationship (no TTL store; the link carries its own replay key).
- Partial unique index `uq_fin_doc_source_charge` on `(source_type, source_id)`
  WHERE `source_type = 'SERVICE_ORDER_CHARGE'` — one finance document per charge, ever.
  This is exactly the invariant the order-level invoice path already implements
  (`create_invoice_from_service_order` treats any existing charge source row as
  "already invoiced" and never adds a second). Other source types keep their multiplicity.
- Model carries the same index (`postgresql_where` + `sqlite_where`), so `create_all`
  test databases and PostgreSQL migrated databases agree. No existing data conflict:
  index creation proves zero duplicate charge links (dev DB: 0 source rows; disposable
  rehearsal DB fresh).
- Reversal/cancel: reversal keeps the original source link and turns the document
  REVERSED; the unique rule is unaffected and a re-conversion continues to return the
  existing (now reversed) document — no invented re-billing behavior.

## Idempotency behavior

- Scope: the key is bound to the created source relationship
  (`source_type='SERVICE_ORDER_CHARGE'`, `source_id=charge.id`), so the boundary is the
  converted business record — the same shape as allocation keys, no new framework.
- Same key + same charge → returns the linked document (201 envelope, existing API
  contract). Same key + different source → 409 `IDEMPOTENCY_KEY_CONFLICT`. A race that
  loses on either unique key rolls back and answers with the winner's result (same
  charge) or a 409 Conflict (never a hidden second draft, never a raw SQL error).
- Issue keeps accepting the header without key semantics: issuing mutates no financial
  records and its state-level replay is already deterministic; no idempotency table is
  needed for state-only transitions.
- Keys are never logged (the API exception handlers exclude headers).

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| PG Test A — two simultaneous conversions (real independent sessions, barrier, real row lock) | `LCS_TEST_PG_* → uv run --no-sync pytest -q tests/test_charge_conversion_postgres.py` (disposable `lcs_verify3`, created, dropped after) | 4 passed, 2026-11-05: A no keys → one doc/one source/zero journals, both callers same id; B different keys → one doc; C same key concurrently → one result; plus the fixture itself proves issue isolation on PG (0 documents after issue) |
| PG backstop — second source link refuses at the DB | same file, `test_the_bill_once_index_refuses_a_second_source_link` | IntegrityError on insert; counts unchanged |
| Migration rehearsal on clean disposable DB (full chain from scratch) | `DATABASE_URL=… lcs_verify3` `alembic upgrade head` → `downgrade -1` → re-`upgrade head` | all ~40 revisions OK; `alembic current` = `b7c8d9e0f1a2`; index + column verified in psql; disposable DB dropped |
| SQLite API/DB-level regressions (D key-different-charge 409, E replay, G failure/retry, H issue isolation, F authorization) | `uv run --no-sync pytest -q tests/test_finance_automation.py` (+ focused suites) | 114 passed incl. chain/schema docs; ruff `app tests scripts` clean |
| Dev release (no experiment — single additive upgrade) | `alembic upgrade head` (dev `freight` DB) + backend image rebuilt | healthy; `alembic_version` = `b7c8d9e0f1a2`; index + column present |

Note: the dev pre-check was accidentally run against `postgres` (not `freight`) — harmless
because the migration itself succeeded, which is only possible with zero duplicate charge
links, and the dev table held 0 rows.

## Acceptance criteria (07.3)

All §12 points met: concurrency bill-once (PG-proven), DB backstop, same-key replay/conflict,
failure-orphan-free retry (SQLite-proven), Casbin unchanged, issue isolation regression,
no journal on convert, historical links valid, docs updated.

## Handoff

- Task 07.3 closed 2026-11-05. S04 remains IN PROGRESS. **Next: 07.4 — profit-layer
  reconciliation**: reuse the existing draft service and compare estimated/issued/draft/
  posted totals (profitability map in PLAN-0009; the report sums document-currency
  amounts per order — the mixed-currency decision belongs there with S09/S10).
- Remaining risks: keys exist only on charge conversions (allocations carry their own);
  no cross-dialect partial-index test beyond SQLite/PG; the `Idempotency-Key` on the
  issue endpoint stays accepted-but-inert by design. No commit authorized yet.
