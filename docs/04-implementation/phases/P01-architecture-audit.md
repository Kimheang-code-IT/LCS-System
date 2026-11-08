# P01 — Architecture and Codebase Audit

## A. Phase summary

- Objective / expected result: A revision-specific route→guard→service→entity→test map and bounded gap list.
- Priority: High.
- Dependencies: P00.
- Execution owner: S01 baseline and owning later slices. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-001,002,006,013,014; DOC-01–DOC-11. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

FastAPI/Nuxt/PostgreSQL modular monolith exists. Dirty reuse/Finish/period changes are source evidence only; configured metadata can outlive routes.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/api/v1/router.py](../../../backend/app/api/v1/router.py)
- [backend/app/core/permissions.py](../../../backend/app/core/permissions.py)
- [frontend/app/config/freight-modules.ts](../../../frontend/app/config/freight-modules.ts)
- [frontend/app/config/lcs-reference-modules.ts](../../../frontend/app/config/lcs-reference-modules.ts)
- [frontend/app/config/freight-reports.ts](../../../frontend/app/config/freight-reports.ts)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

A revision-specific route→guard→service→entity→test map and bounded gap list. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Read-only architecture/code/test review first; no schema or new abstraction by default.

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
| 01.1 | Map actual entry points: Trace route/config aliases, handlers and capability compilation | `backend/app/api/v1/router.py`; `backend/app/core/permissions.py` | P00 | Each approved page resolves to actual code; supporting routes distinct |
| 01.2 | Verify critical workflow contracts: Inspect reuse/Finish/custom-period callers, models, migrations and tests | Owning files listed above; trace actual callers for this task | 01.1 | Record current/target differences without inferring deployment |
| 01.3 | Assess existing reuse and query cost: Trace shared forms/repositories/posting and high-cost report queries | Owning files listed above; trace actual callers for this task | 01.2 | Each proposed change has a demonstrated gap and existing reuse option |
| 01.4 | Assign bounded work: Attach source/evidence to acceptance and S01–S13 owner | Owning files listed above; trace actual callers for this task | 01.3 | No duplicate implementation of passing existing behavior |

## F. Error handling

Missing path/ambiguous alias → discovery item; stale runtime/schema → do not mark COMPLETE.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

Inspect existing test files and exact candidate commands; run focused tests only when the active slice authorizes verification. Record PostgreSQL-only gaps.

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

Stack migration, broad cleanup, speculative performance dependencies or active-plan replacement.

