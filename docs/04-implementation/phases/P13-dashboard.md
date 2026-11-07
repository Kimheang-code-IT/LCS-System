# P13 — Dashboard

## A. Phase summary

- Objective / expected result: Source-defined permitted KPIs with consistent interval/as-of/currency.
- Priority: Medium after correctness prerequisites.
- Dependencies: P11,P12; S01.
- Execution owner: S09–S10 aggregates; S13 presentation acceptance. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-008,011; LCS-AUTO-004; MOD-001. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Backend dashboard endpoint supports day/month/year granularity. Full requested pending/overdue/activity/period metrics and per-metric permission rules not proven.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/reports/service.py](../../../backend/app/modules/reports/service.py)
- [backend/app/modules/reports/router.py](../../../backend/app/modules/reports/router.py)
- [frontend/app/pages/index.vue](../../../frontend/app/pages/index.vue)
- [frontend/app/components/dashboard/AppSummaryCard.vue](../../../frontend/app/components/dashboard/AppSummaryCard.vue)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Source-defined permitted KPIs with consistent interval/as-of/currency. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Existing dashboard service/cards/query contract; no browser financial aggregation or new infrastructure.

Frontend changes use existing metadata/shared components/repositories and permission-aware
actions. Backend changes stay in existing owning services/routers. Database/API changes are
none by default: if required, document the demonstrated need, callers, additive compatibility,
migration/downgrade and exact contract before editing. Relevant permissions come from
permissions.py, router guards and existing compilation, never a parallel role map.

## E. Small implementation tasks

Each task inherits this package's source list, requirement references and execution-slice
dependency. "Fix" is conditional: verification alone closes a task whose behavior already
passes. Activate only the required subset in an implementation plan.

| Task | Goal and expected change | Files / discovery | Dependency | Validation and measurable acceptance |
|---|---|---|---|---|
| 13.1 | Specify each metric before UI changes: Use target dashboard source/date rules and actual capability map | `backend/app/modules/reports/service.py`; `backend/app/modules/reports/router.py` | P11,P12; S01 | Every metric has a source/interval/as-of/currency/permission |
| 13.2 | Verify existing metrics against reports: Use same posted/operational fixture and compare control totals | Owning files listed above; trace actual callers for this task | 13.1 | Revenue/expense/profit/AR/AP and SO counts match owners |
| 13.3 | Implement only missing safe metrics: Reuse queries/cards; prevent data leakage and unnecessary requests | Owning files listed above; trace actual callers for this task | 13.2 | Pending/overdue/period states shown only to authorized viewers |
| 13.4 | Verify stale/empty/loading behavior: Check date/locale changes and out-of-order requests | Owning files listed above; trace actual callers for this task | 13.3 | No stale overwrite, hidden finance exposure or invented zero-on-error |

## F. Error handling

Partial permission or unavailable metric is explicit; do not show unauthorized source drill-down or convert failed query to zero.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_reports_dashboard.py plus focused permission tests; frontend dashboard tests and one synthetic browser date/denial journey; inspect query count for new aggregation.

Commands above are **not run by documentation work**. Inspect fixture flags before execution;
PostgreSQL tests must point only to an explicitly disposable target. SQLite cannot prove
locking/triggers. For changed stacks apply [testing gates](../../03-development/testing-guide.md).
For applicable DEEP implementation use the read-only reviewer after integration/regression/
denial checks. Run manual/browser success, refusal, loading/empty, relevant locale and print
scenarios for the scoped UI. Do not weaken tests or replace fresh evidence with old counts.

## H. Definition of Done and handoff

- Every activated task meets its row acceptance and linked requirement.
- Relevant success/refusal/boundary/concurrency/regression checks pass with exact commands,
  revision/environment, results and skips. No critical regression or hidden acceptance gap.
- Review confirms preserved security/accounting/history and reuse of existing patterns.
- Update directly affected docs, active slice plan/Handoff, [tracker](../phase-tracker.md)
  and evidence records only where actual verification changed.
- Stop after assigned scope. Do not automatically start the next package or commit.

Handoff at creation: planning detail only; no implementation/test completion recorded.
Next action: read active slice Handoff and select only its remaining task. Remaining package
work: all runtime acceptance (P00 retains sanitized legacy review and doc limitations).
Open blockers: prerequisites, safe fixtures, required business decisions and evidence gaps
described above. Leave work uncommitted unless explicitly authorized.

## I. Out of scope

External AI insights, new dashboard pages, invented revenue recognition or speculative cache/queue.

