# P10 — Smart Accounting Period Closing

## A. Phase summary

- Objective / expected result: Authorized review→confirm→lock and reasoned reopen preserving historical evidence.
- Priority: High.
- Dependencies: P09; P11.1 GL/TB/AR/AP reconciliation baseline.
- Execution owner: S08 control work with S10 reconciliation evidence. [Master roadmap](../master-plan.md) controls sequence.
- Status: IN PROGRESS — the Period Closing feature batch closed 2026-11-05
  ([PLAN-0017](../plans/PLAN-0017-period-closing.md), evidence E36: task 10.1 result
  contract, 10.2 bounded review (8 checks + summary + history), 10.3 atomic close with
  period-row serialization shared with posting (PG race evidence), and the authorized
  Period Closing page. Remaining: 10.4 — closing-report evidence retention, stale-review
  acknowledgments and reopening dependency checks across multiple periods.
- Requirement references: LCS-CLS-001–003; LCS-006,009; MOD-013 extension. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Basic close/reopen and metadata exist. Rich review, warning acknowledgments, stale-review validation and preserved closing report evidence are MISSING/unverified.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/finance/service.py](../../../backend/app/modules/finance/service.py)
- [backend/app/modules/finance/router.py](../../../backend/app/modules/finance/router.py)
- [backend/app/modules/master_data/status_policy.py](../../../backend/app/modules/master_data/status_policy.py)
- [backend/app/modules/reports/ledger_reports.py](../../../backend/app/modules/reports/ledger_reports.py)
- [frontend/app/pages/finance/accounting-periods/index.vue](../../../frontend/app/pages/finance/accounting-periods/index.vue)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Authorized review→confirm→lock and reasoned reopen preserving historical evidence. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Existing Accounting Periods workspace; review/close/reopen service contracts; Casbin compilation; conditional additive persistence if audit/storage cannot retain required evidence.

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
| 10.1 | Define check result and evidence contract: Apply smart-ERP closing specification; confirm severity/materiality/reconciliation ownership | `backend/app/modules/finance/service.py`; `backend/app/modules/finance/router.py` | P09; P11.1 GL/TB/AR/AP reconciliation baseline | Blocking vs warning policy and record drill-down fields explicit |
| 10.2 | Build bounded read-only review after gap proof: Reuse existing queries; include drafts, AR/AP, accounts, charges/accruals, GL/TB/BS checks | Owning files listed above; trace actual callers for this task | 10.1 | Each check has code, severity/count/cutoff and authorized source links |
| 10.3 | Enforce close atomically on every path: Revalidate stale inputs and serialize with posting; deny generic status/update bypass | Owning files listed above; trace actual callers for this task | 10.2 | No post-close posting or partial close/audit; repeated confirmation safe |
| 10.4 | Preserve/reopen and verify race/refusal: Require reason/capability; retain every close and report cutoff | Owning files listed above; trace actual callers for this task | 10.3 | Prior report/history remains; denied/stale/failed/repeated actions safe |

## F. Error handling

Incomplete/unauthorized review is not zero exceptions; stale token/state/concurrent posting or report failure blocks confirmation; transaction failure keeps period OPEN.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

Extend focused tests/test_accounting_periods.py and finance/report tests with invalid review, warning acknowledgment, stale cutoff, close-vs-post race, rollback and generic API bypass. PostgreSQL required; browser review/confirm/drill-down/denied reopen.

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

Dedicated 45th page without scope decision, annual earnings transfer, deleting/resetting history, automatic posting of drafts.

