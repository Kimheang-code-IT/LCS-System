# P15 — Cross-Module Integration

## A. Phase summary

- Objective / expected result: Repeatable source-linked quotation→SO→charge→invoice→settlement→reports journey plus supplier/correction/closing branches.
- Priority: High.
- Dependencies: Relevant P03–P14 accepted subsets; S01–S11 verification.
- Execution owner: S02–S11 integration, final scenarios before S13. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-003–010,013. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Cross-module tests and synthetic browser workflows exist, but file presence and historic passes do not prove current acceptance.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/tests/test_workflows.py](../../../backend/tests/test_workflows.py)
- [backend/tests/test_frontend_api_contract.py](../../../backend/tests/test_frontend_api_contract.py)
- [backend/tests/test_route_authorization.py](../../../backend/tests/test_route_authorization.py)
- [docs/04-implementation/project-status-checklist.md](../project-status-checklist.md)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Repeatable source-linked quotation→SO→charge→invoice→settlement→reports journey plus supplier/correction/closing branches. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Integration and denial verification; narrow reproduced fixes in owning slice only; no bulk cleanup.

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
| 15.1 | Define isolated scenario and invariants: Pick representative multi-currency/partial-payment/correction data and permitted/denied actors | `backend/tests/test_workflows.py`; `backend/tests/test_frontend_api_contract.py` | Relevant P03–P14 accepted subsets; S01–S11 verification | No production data; side effects controlled; expected ledger totals recorded |
| 15.2 | Run operations-to-finance journey: Create two SOs from one offer; issue/convert/post/settle using explicit commands | Owning files listed above; trace actual callers for this task | 15.1 | No duplicate booking/billing/posting; source snapshots traceable |
| 15.3 | Run supplier/correction/closing branches: Add supplier bill/payment, reversal, old invoice/new-period payment and close/post race | Owning files listed above; trace actual callers for this task | 15.2 | AR/AP/GL/TB/P&L/BS/cash reconcile with preserved history |
| 15.4 | Verify refusal/recovery and handoff: Inject invalid/denied/duplicate/failing steps and reload browser | Owning files listed above; trace actual callers for this task | 15.3 | No partial effects or silent loss; exact failures and evidence recorded |

## F. Error handling

Network retry and transaction/storage failure recover with existing command contracts; mismatched source/refusal leaves no partial state. Route/API denial must agree.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

Focused backend workflow/contract/denial suites, disposable PostgreSQL concurrency/guard coverage and isolated mutating browser e2e flow. Run impacted full stacks only when DEEP change warrants; record skips.

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

Next phase auto-start, production data, broad dependency upgrades, unrelated architecture rewrite.

