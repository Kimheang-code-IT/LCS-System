# P00 — Documentation Audit and Cleanup

## A. Phase summary

- Objective / expected result: One navigable authority map, preserved unique history and explicit review limitations.
- Priority: High.
- Dependencies: None; preserve dirty-worktree baseline.
- Execution owner: Documentation only. [Master roadmap](../master-plan.md) controls sequence.
- Status: NEEDS_REVIEW — documentation written; sanitized legacy review outstanding.
- Requirement references: All documentation obligations; DOC-01–DOC-11. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Canonical topic documents now live in the user-approved numbered folders. Retained detail has
unique content. Two archived guides remain gateway-withheld; historical review limits persist.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [docs/03-development/documentation-standards.md](../../03-development/documentation-standards.md)
- [docs/00-project/documentation-audit.md](../../00-project/documentation-audit.md)
- [docs/README.md](../../README.md)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

One navigable authority map, preserved unique history and explicit review limitations. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Documentation only; no frontend/backend/database/API mutation.

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
| 00.1 | Inventory and classify: Record every current docs file and inbound/tool dependencies | `docs/03-development/documentation-standards.md`; `docs/00-project/documentation-audit.md` | None; preserve dirty-worktree baseline | All existing docs classified; private keys excluded |
| 00.2 | Reconcile authority and navigation: Repair current links; label preserved legacy conflicts; maintain stable IDs | Owning files listed above; trace actual callers for this task | 00.1 | Current navigation resolves and obsolete examples cannot override lifecycle |
| 00.3 | Publish page/requirement/planning coverage: Write all 44 records, target rules and bounded phase packages | Owning files listed above; trace actual callers for this task | 00.2 | Exactly 44 page IDs and 17 packages, no empty placeholders |
| 00.4 | Validate and retain review exceptions: Run doc checks and compare task-only hashes; preserve withheld guides | Owning files listed above; trace actual callers for this task | 00.3 | No non-document task changes; unresolved review scope explicit |

## F. Error handling

Unavailable source/gateway block → retain and mark NEEDS_REVIEW; unresolved conflict → record owner/decision, never fabricate accuracy.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

Documentation links/anchors, source paths, inventory count, phase dependency DAG, required sections, baseline hashes; no application tests for prose.

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

Feature implementation, document deletion without complete review, migration execution, deployment or commits.

