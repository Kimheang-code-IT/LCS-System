# P02 — Shared UI and UX Components

## A. Phase summary

- Objective / expected result: Consistent, permission-aware forms/tables with no duplicated page framework.
- Priority: High.
- Dependencies: P01.
- Execution owner: Cross-cutting within each approved slice. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-010,011,013,016; LCS-UI-001. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Metadata-driven tables/documents, shared field validation, reference Quick Entry and action buttons already exist; inspect exact composable path before edit.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [frontend/app/components/freight/WorkspaceView.vue](../../../frontend/app/components/freight/WorkspaceView.vue)
- [frontend/app/components/freight/DocumentView.vue](../../../frontend/app/components/freight/DocumentView.vue)
- [frontend/app/components/table/AppListTable.vue](../../../frontend/app/components/table/AppListTable.vue)
- [frontend/app/components/common/AppReferenceSelect.vue](../../../frontend/app/components/common/AppReferenceSelect.vue)
- [frontend/app/composables/common/useFormValidation.ts](../../../frontend/app/composables/common/useFormValidation.ts)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Consistent, permission-aware forms/tables with no duplicated page framework. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Frontend props/events/validation/state only where a demonstrated gap exists; API/schema changes none unless a separate contract defect is proven.

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
| 02.1 | Audit one representative flow: Trace existing table/form/action/permission/error/loading pipeline | `frontend/app/components/freight/WorkspaceView.vue`; `frontend/app/components/freight/DocumentView.vue` | P01 | Identify actual shared defect and affected callers |
| 02.2 | Verify keyboard and editing continuity: Exercise focus/caret, row identity, errors, unsaved draft and Quick Entry | Owning files listed above; trace actual callers for this task | 02.1 | Typing and locale switches preserve entered values |
| 02.3 | Fix the shared defect narrowly: Reuse metadata, persistent field errors and permitted actions | Owning files listed above; trace actual callers for this task | 02.2 | One fix reaches affected callers without generic rewrite |
| 02.4 | Validate callers and document contract: Run impacted Vitest and browser checks; localize changed strings | Owning files listed above; trace actual callers for this task | 02.3 | No new missing labels, inaccessible field or permission leak |

## F. Error handling

Failed fetch/save retains draft and persistent message; duplicate click disabled; stale response cannot overwrite newer state; denial cannot appear as success.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

frontend: pnpm vitest run tests/form-field-error.spec.ts; inspect tests/global-search.spec.ts and e2e/form-typing.spec.ts for relevant cases; pnpm lint; pnpm typecheck. Run i18n check if labels change.

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

Full redesign, new generic component library, unrelated CSS or new dependencies.

