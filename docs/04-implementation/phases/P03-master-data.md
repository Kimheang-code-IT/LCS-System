# P03 — Master Data

## A. Phase summary

- Objective / expected result: Required reference data usable and safe under inactive, duplicate, archive and import cases.
- Priority: High.
- Dependencies: P01,P02.
- Execution owner: Prerequisite subsets before S02/S05; remaining S11. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-014; BR-001,002; FR-043–053; MOD-023–034. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Twelve pages and allowlisted Excel import/export exist; party roles, identity types and capacity units have historical narrow action evidence.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [frontend/app/config/lcs-reference-modules.ts](../../../frontend/app/config/lcs-reference-modules.ts)
- [backend/app/modules/master_data/router.py](../../../backend/app/modules/master_data/router.py)
- [backend/app/modules/master_data/models.py](../../../backend/app/modules/master_data/models.py)
- [backend/app/modules/master_data/status_policy.py](../../../backend/app/modules/master_data/status_policy.py)
- [backend/app/modules/excel_io/registry.py](../../../backend/app/modules/excel_io/registry.py)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Required reference data usable and safe under inactive, duplicate, archive and import cases. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Frontend metadata + owning backend validation/guards; preserve model/store design. Additive schema only for demonstrated integrity gaps.

Frontend changes use existing metadata/shared components/repositories and permission-aware
actions. Backend changes stay in existing owning services/routers. Database/API changes are
none by default: if required, document the demonstrated need, callers, additive compatibility,
migration/downgrade and exact contract before editing. Relevant permissions come from
permissions.py, router guards and existing compilation, never a parallel role map.

## Settings and integrations refinement

[IO requirements](../../02-business/import-export-requirements.md) and
[PLAN-0005 F](../plans/PLAN-0005-settings-integrations.md#phase-f--data-importexport) refine task
03.3: CSV adapter, stable identity, preview/replay, atomicity and audit. Reuse existing twelve-master
XLSX behavior rather than declaring it missing. No runtime acceptance occurs in documentation.

## E. Small implementation tasks

Each task inherits this package's source list, requirement references and execution-slice
dependency. "Fix" is conditional: verification alone closes a task whose behavior already
passes. Activate only the required subset in an implementation plan.

| Task | Goal and expected change | Files / discovery | Dependency | Validation and measurable acceptance |
|---|---|---|---|---|
| 03.1 | Select dependent reference subset: Use inventory and active slice to pick party/direction/type/currency/fee prerequisites | `frontend/app/config/lcs-reference-modules.ts`; `backend/app/modules/master_data/router.py` | P01,P02 | Only required prerequisites enter active work |
| 03.2 | Verify CRUD and dropdown contracts: Check required/unique/active refs, identity patterns and paired capacity | Owning files listed above; trace actual callers for this task | 03.1 | Invalid/duplicate/inactive new choices refused; old refs render |
| 03.3 | Verify deletion/import safety: Exercise status→archive/restore dependencies and validated import preview/commit | Owning files listed above; trace actual callers for this task | 03.2 | Protected/referenced data survives; unauthorized import denied |
| 03.4 | Fix gaps and record per-page evidence: Use existing validators/config/status registry and focused tests | Owning files listed above; trace actual callers for this task | 03.3 | Each selected page has success/refusal/export evidence without invented generic rules |

## F. Error handling

Reference missing/inactive, duplicate code/name, regex invalid, restore collision and stale import preview use typed refusals; database rollback preserves references.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

backend: uv run pytest -q tests/test_party_roles.py tests/test_place_roles.py tests/test_transport_assets.py tests/test_document_types.py tests/test_deletion_policy.py tests/test_excel_import_export.py (select affected files only); frontend focused metadata/reference tests, lint/typecheck.

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

Separate customer/supplier databases, new Places page, automatic historical purge or new currency-rate page.

