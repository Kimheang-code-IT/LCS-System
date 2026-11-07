# PLAN-0017 — Smart Accounting Period Closing (P10/S08 feature batch)

## Metadata

Slice/Phase: P10 — Smart Accounting Period Closing (execution owner S08; page authorized
by the owner as the 45th business page alongside the 44-page baseline)
Status: Completed (tasks 10.1–10.3 + the page; reopening-dependency checks remain open)
Last updated: 2026-11-05
Task level: DEEP (financial locking + new page; PostgreSQL race evidence)

## Objective and requirement IDs

Authorized review → validation → confirm → lock with reasoned reopen, per
[P10](../phases/P10-period-closing.md) (LCS-CLS-001–003; user-approved feature spec).
Dependencies: P09 account/rule/period prerequisite ✓ (S05 evidence E32–E35); the
GL/TB/AR/AP reconciliation baseline exists (report suites) — the S10-owned deep
reconciliation stays out of scope here (documented).

## Reused architecture (nothing rebuilt)

- Period model already carries `name/description/closed_at/closed_by_user_id` and the
  statuses DRAFT/OPEN/CLOSED (+ legacy REOPENED read) — the Accounting Periods page and
  its permission aggregate own creation/overlap (`PERIOD_OVERLAP`) and date changes are
  refused on posted periods (`PERIOD_HAS_POSTINGS`).
- The close/reopen endpoints, audit events (`PERIOD_CLOSED`/`PERIOD_REOPENED` with
  reason) and the Casbin codes (`accounting_period.read/close/reopen`) already existed
  and stay the only paths (the status-policy engine refuses generic bypass: updating a
  CLOSED period through `update_period` is refused; reopen routes through the dedicated
  reopen with the reason schema).

## New: one authoritative validation pipeline

`backend/app/modules/finance/period_closing.py`:

- `run_closing_validation` — 8 structured checks (§7): PERIOD_STATE (OPEN only, else
  BLOCKED), DRAFT_DOCUMENTS (WARNING, never a blocker — P10 policy), JOURNAL_BALANCE /
  JOURNAL_LINES / POSTING_LINKS (BLOCKING: unbalanced posted journals, unresolvable
  account references, orphaned posting links), ACCOUNTS_RECEIVABLE / ACCOUNTS_PAYABLE
  (PASS/REVIEW: unpaid documents are valid carry-overs, never errors), ALLOCATION_CUTOFF
  (PASS/REVIEW: the documented §11 policy), TRIAL_BALANCE (BLOCKED when the ledger does
  not balance), BANK_RECONCILIATION (**NOT_AVAILABLE** — the feature does not exist;
  never claimed PASS). Payload: period + checks (code/name/status/severity/message/
  affectedCount/relatedIds/recommendedAction) + summary + blockingCount/Codes +
  `baseCurrency`.
- `_financial_summary` — revenue/expenses/profit (posted journals of the period, base
  currency via `account_type`), AR/AP outstanding + unapplied payment balances from the
  authoritative `financial_documents` state. Report-service reuse (`trial_balance`) for
  the ledger control.
- `closing_history` — the period's audit trail (`PERIOD_*` event types, actor + reason).

## New: atomic lock with a real serialization strategy (§9)

- `close_period` now **locks the period row `FOR UPDATE`** and re-runs the blocking
  checks inside the lock; a reviewed validation is advisory history — the lock-time
  replay decides. Closed with `closed_at`/`closed_by` stamps as before (audited).
- The **posting paths join the same lock**: `post_document` and `reverse_document` take
  the period-row `FOR UPDATE` after resolving the posting date and re-check OPEN —
  a posting racing the close either commits first (the close re-validates against it)
  or waits and refuses `PERIOD_CLOSED`. Lock order is document → period everywhere, so
  no new deadlock surface. A backdated journal into a closed range is refused by the
  same re-check (verified).
- Reopening stays: `accounting_period.reopen` + reason + one audited transition; the
  closure stamps clear on reopen and the audit history persists.

## Allocation cutoff policy (§11, documented — not silently changed)

Allocations write no journal, so they are not period-gated; they carry their effective
timestamp (`allocated_at`) and settle older posted documents from new open periods —
the allowed behavior. Because `paid_amount` is a current balance (no versioning), a
historical as-of *reporting cutoff* cannot be reconstructed from this schema: that is an
explicit S09/S10 design item (owner recorded), not a blocker for accounting closure.

## New: the Period Closing page (45th authorized page)

`frontend/app/pages/finance/period-closing/index.vue`: period select (defaults to the
latest OPEN), Section A period card (dates/status/closedAt·closedBy), Section B badges
(passed/warnings/blocking), Section C the full checklist (per-check badge, message,
recommended action, drill-down links to journals/documents), Section D financial summary
(revenue/expenses/profit + AR/AP + unapplied, base-currency caption), Section E actions:
Refresh/Run Validation/Close Period (confirm + reason, disabled while blocking issues
stand, hidden without `accounting_period.close`)/Reopen (authorized + reason)/History
(audit trail)/link to Accounting Periods.
Glue: `/finance/period-closing` in `page-access.ts` (`finance.accounting_periods.view`),
the Finance sidebar group, two new endpoints in `api-v1-endpoints`.
Repos: `finance.reopenPeriod` (generic record-status endpoint, reason payload),
`closingValidation`, `closingHistory`. i18n: `freight.ui.periodClosing` (24 keys) +
`freight.pages.periodClosing` in en/km/zh. Notification policy respected (errors render
inline in the page, never a red toast).

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| Validation contract + closing + backdated refusal | `uv run --no-sync pytest -q tests/test_period_closing.py` | 2 passed: clean period → all PASS + NOT_AVAILABLE bank check + summary (revenue/profit 400, AR 400); close → CLOSED + stamps + audit; backdated post → 409 PERIOD_CLOSED; re-close refusal; draft documents → WARNING + still closable |
| PG race: posting vs closing | `LCS_TEST_PG_* → uv run --no-sync pytest -q tests/test_period_closing_postgres.py` | 1 passed (disposable `lcs_verify9`, created + dropped): two independent sessions racing one period — either "posting won" (one balanced journal, then CLOSED) or "closing won" (posting refused PERIOD_CLOSED); books consistent either way; the repeat close refuses |
| Regression sweep (19 focused files incl. periods/posting/rules/AR/AP/races/chain+schema gates) | `uv run --no-sync pytest -q` | **196 passed / 11 skipped** (skips = PG-env guards), `ruff check app tests scripts` clean |
| Frontend gates | eslint; `pnpm typecheck`; `pnpm exec vitest run` (100 files); `pnpm i18n:check` | 0 errors; **828 passed** (incl. the new `tests/period-closing.spec.ts` source pins: close/reopen permission gates, blocking-disabled Close, validation/history wiring); locale parity passed |
| Live stack | both images rebuilt; `POST …/closing-validation` → 401 (exists, guarded); `/finance/period-closing` → 200 | deployed 2026-11-05 |

## Acceptance criteria (§20)

1–15 verified above; 16 gates green; 17 = this plan + E36 + P10 status + tracker +
master-plan. **P10/S08 stays IN PROGRESS-partial**: remaining (10.4's full closing-report
evidence retention and reopening dependency checks across multiple periods) are recorded
in P10 with their acceptance impact — not marked complete.

## Handoff

- Remaining risks: bank reconciliation NOT_AVAILABLE (honest); allocation cutoff is
  documentation + effective timestamps, not an enforced gate (S09/S10 decision);
  `layersByCurrency`-style presentation of mixed currencies stays a string until S09/S10.
- Spec-reconciliation gaps (recorded 2026-11-05 when the full feature spec was re-checked
  against this plan): the financial summary omits cash/bank balances (S10 owns adding
  them from the Financial Accounts ledger); GL/Balance-Sheet consistency ride on the
  existing report services during review rather than named closing checks; search and
  status filter on the page are served by the Accounting Periods page, the closing page
  keeps a period selector only. These are improvements to record with 10.4 or S10, not
  defects in the verified behavior.
- Next roadmap slice: **S06 — Customer Receipt and Settlement** (FLOW-010) while P10's
  reopening-dependency work waits on its S09/S10 baseline. No commit authorized yet.
