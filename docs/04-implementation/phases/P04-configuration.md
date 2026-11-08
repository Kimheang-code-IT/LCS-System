# P04 — Dynamic Configuration

## A. Phase summary

- Objective / expected result: Valid published configurations and stable historical SO rendering.
- Priority: High.
- Dependencies: P03 prerequisite catalogs; P02.
- Execution owner: S03 prerequisites and remaining S11. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-004,014; LCS-CFG-001; FR-058–071; MOD-035–038. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Attributes/groups/tabs, publish/compare/activate/rollback and SO snapshots exist. Discover router-imported module filenames if names differ.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/master_data/component_config.py](../../../backend/app/modules/master_data/component_config.py)
- [backend/app/modules/master_data/config_snapshot.py](../../../backend/app/modules/master_data/config_snapshot.py)
- [backend/app/modules/master_data/config_versions.py](../../../backend/app/modules/master_data/config_versions.py)
- [backend/app/modules/operations/component_tabs.py](../../../backend/app/modules/operations/component_tabs.py)
- [frontend/app/pages/configuration/versions/index.vue](../../../frontend/app/pages/configuration/versions/index.vue)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Valid published configurations and stable historical SO rendering. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Metadata UI, configuration services and snapshot boundary; no reinterpretation/backfill of existing operational values.

Frontend changes use existing metadata/shared components/repositories and permission-aware
actions. Backend changes stay in existing owning services/routers. Database/API changes are
none by default: if required, document the demonstrated need, callers, additive compatibility,
migration/downgrade and exact contract before editing. Relevant permissions come from
permissions.py, router guards and existing compilation, never a parallel role map.

## Settings and integrations refinement

[Configuration IO](../../02-business/import-export-requirements.md#io-003--configuration-graph-import)
and [PLAN-0005 F](../plans/PLAN-0005-settings-integrations.md#phase-f--data-importexport) extend
existing validators/registry with dependency-aware DRAFT graph import, separate activation and
unchanged published/SO snapshots. This is proposed, not implemented by documentation.

## E. Small implementation tasks

Each task inherits this package's source list, requirement references and execution-slice
dependency. "Fix" is conditional: verification alone closes a task whose behavior already
passes. Activate only the required subset in an implementation plan.

| Task | Goal and expected change | Files / discovery | Dependency | Validation and measurable acceptance |
|---|---|---|---|---|
| 04.1 | Trace draft-to-snapshot capture: Map attribute/group/tab membership and version capture on order creation | `backend/app/modules/master_data/component_config.py`; `backend/app/modules/master_data/config_snapshot.py` | P03 prerequisite catalogs; P02 | Snapshot version and required/repeatable behavior explicit |
| 04.2 | Verify typed metadata and membership rules: Test invalid types/options/patterns/reference/order/duplicate membership | Owning files listed above; trace actual callers for this task | 04.1 | Invalid config refused before activation |
| 04.3 | Verify publish/rollback concurrency: Test activation, compare, used deletion and concurrent version choices | Owning files listed above; trace actual callers for this task | 04.2 | One effective version; old orders keep old fields/values |
| 04.4 | Fix only captured defects: Reuse validators and snapshot helpers; update relevant acceptance evidence | Owning files listed above; trace actual callers for this task | 04.3 | No history mutation and focused regression passes |

## F. Error handling

Missing/retired version, invalid membership, concurrent activation and database failures return stable typed errors; rollback is configuration selection, not transaction-history erasure.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_component_attributes.py tests/test_component_layouts.py tests/test_config_versions.py tests/test_config_version_lifecycle.py tests/test_config_compare.py (affected subset); UI focused tests and authorized synthetic old/new SO render.

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

New dynamic schema engine, new configuration language without need, mass conversion of old SOs.

