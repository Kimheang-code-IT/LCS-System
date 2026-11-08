# P06 — Service Orders

## A. Phase summary

- Objective / expected result: Operational booking, editable copied pricing and controlled Finish without accounting effects.
- Priority: High.
- Dependencies: P05; P04 operational snapshot prerequisite; S01.
- Execution owner: S02–S03. [Master roadmap](../master-plan.md) controls sequence.
- Status: COMPLETED 2026-11-05 — S02 ([PLAN-0006](../plans/PLAN-0006-quotation-service-order-conversion.md)),
  authorized files ([PLAN-0007](../plans/PLAN-0007-authorized-files-attachments.md), E26) and
  the remaining acceptance batch ([PLAN-0008](../plans/PLAN-0008-operations-acceptance-backstop.md),
  E27: FLOW-004/005 + DATA-006 closed, movement-sequence backstop migration c0d1e2f3a4b5).
  Deferred: storage recovery drill → S12; DATA-011 catalog scope → S11; browser journeys → NT02.
- Requirement references: LCS-003,004,010; LCS-SO-001; MOD-003. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

New orders require quotation selection, copy snapshots, Save merges input and Finish sets FINISHED with actor/time. Actual containers are entered manually.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/operations/service.py](../../../backend/app/modules/operations/service.py)
- [backend/app/modules/operations/models.py](../../../backend/app/modules/operations/models.py)
- [backend/app/modules/operations/component_tabs.py](../../../backend/app/modules/operations/component_tabs.py)
- [frontend/app/components/freight/JobDetail.vue](../../../frontend/app/components/freight/JobDetail.vue)
- [frontend/app/config/freight-modules.ts](../../../frontend/app/config/freight-modules.ts)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Operational booking, editable copied pricing and controlled Finish without accounting effects. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

SO form/service, source snapshot, containers/components/files and action guards. No financial-posting side effect.

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
| 06.1 | Verify source selection and saved overrides: Trace latest/specific revision, party/direction/currency/routes and copied prices | `backend/app/modules/operations/service.py`; `backend/app/modules/operations/models.py` | P05; P04 operational snapshot prerequisite; S01 | Selected source persisted; saved override survives refresh |
| 06.2 | Verify physical operations: Test actual boxes, ownership/weight/duplicate normalization, required dynamic values and authorized files | Owning files listed above; trace actual callers for this task | 06.1 | No requirement counted as physical container; validation and downloads enforced |
| 06.3 | Verify Save and Finish boundaries: Test idempotent Finish, inactive refusal, metadata/list status and every prohibited edit path | Owning files listed above; trace actual callers for this task | 06.2 | Finish stamps once, locks scoped operations and leaves finance usable |
| 06.4 | Fix demonstrated mismatch and regress: Align existing UI/status/service behavior with target; no extra completion workflow | Owning files listed above; trace actual callers for this task | 06.3 | Save/Finish create no journal; source and other orders stable |

## F. Error handling

Missing quotation, inactive/finished mutation, cross-order refs, duplicate box, invalid weights and storage/database failure refuse without partial state.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_quotation_reuse.py tests/test_movements_and_milestones.py tests/test_attachments.py tests/test_workflows.py (affected cases); frontend pnpm vitest run tests/service-order-list.spec.ts tests/document-tabs.spec.ts; browser Save/Finish/denial.

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

Automatic posting on Save/Finish, automatic settlement, new logistics pages or prepared physical boxes.

