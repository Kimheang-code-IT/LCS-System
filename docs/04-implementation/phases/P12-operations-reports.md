# P12 — Operations Reports

## A. Phase summary

- Objective / expected result: Accurate SO register/status/physical-container/profitability views.
- Priority: High.
- Dependencies: P06,P07; P08 posted comparison fixture.
- Execution owner: S09. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-008; LCS-RPT-001; MOD-005–008. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Four operational reports exist; status/container/pricing meanings changed in dirty code. Automatic load has historical regression evidence.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [frontend/app/config/freight-reports.ts](../../../frontend/app/config/freight-reports.ts)
- [frontend/app/components/freight/ReportsView.vue](../../../frontend/app/components/freight/ReportsView.vue)
- [backend/app/modules/reports/service.py](../../../backend/app/modules/reports/service.py)
- [backend/app/modules/operations/models.py](../../../backend/app/modules/operations/models.py)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Accurate SO register/status/physical-container/profitability views. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Existing four report definitions/adapters and backend queries; no new report pages or financial-recognition rules.

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
| 12.1 | Verify report populations and dates: Trace adapter/API source and declared created/order/finished/as-of basis | `frontend/app/config/freight-reports.ts`; `frontend/app/components/freight/ReportsView.vue` | P06,P07; P08 posted comparison fixture | Each report includes correct operational population/cutoff |
| 12.2 | Verify physical/status counts: Use requirement-only and actual-container fixtures plus pending/finished work | Owning files listed above; trace actual callers for this task | 12.1 | Requirements not counted as boxes; Finish/age/pending fields coherent |
| 12.3 | Verify profit layers and currencies: Compare quotation/issued/draft/posted totals for same SO | Owning files listed above; trace actual callers for this task | 12.2 | Estimated and posted figures distinct; zero-revenue margin safe |
| 12.4 | Fix gaps and verify outputs: Reuse report UI/backend helpers and validate filters/print/export/drill-down | Owning files listed above; trace actual callers for this task | 12.3 | Same declared population/totals and authorized source links |

## F. Error handling

Unknown SO/status/date, missing historical snapshot or denied source remains visible; empty states never fabricate operations.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_reports_dashboard.py tests/test_reporting_values.py tests/test_movements_and_milestones.py (scoped); frontend report tests and current browser autoload/filter checks.

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

Extra logistics pages, counting quoted container units as actuals, deriving official ledger statements from estimates.

