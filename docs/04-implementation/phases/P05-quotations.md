# P05 — Quotations

## A. Phase summary

- Objective / expected result: Reusable versioned offers, explicit commands and safe request deduplication.
- Priority: High.
- Dependencies: P03,P04 prerequisites; S01.
- Execution owner: S02. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-003; LCS-QUO-001; MOD-002; lifecycle quotation rules. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Save/Submit/revisions/re-quote and multiple distinct conversions exist. convert_revision has no state gate; same-key replay checks precede source loading.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/quotations/service.py](../../../backend/app/modules/quotations/service.py)
- [backend/app/modules/quotations/models.py](../../../backend/app/modules/quotations/models.py)
- [backend/app/modules/quotations/repository.py](../../../backend/app/modules/quotations/repository.py)
- [frontend/app/utils/freight/quotation-actions.ts](../../../frontend/app/utils/freight/quotation-actions.ts)
- [frontend/app/config/freight-modules.ts](../../../frontend/app/config/freight-modules.ts)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Reusable versioned offers, explicit commands and safe request deduplication. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Existing quotation UI/service/revision and conversion relationship only; preserve legacy SENT/ACCEPTED data; schema changes conditional on tests.

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
| 05.1 | Verify current lifecycle and revision history: Inspect save/submit/requote and current legacy compatibility | `backend/app/modules/quotations/service.py`; `backend/app/modules/quotations/models.py` | P03,P04 prerequisites; S01 | No new Send/Accept requirement; prior versions stay readable |
| 05.2 | Prove independent repeated use: Create two intentional bookings from one offer and change copied prices | Owning files listed above; trace actual callers for this task | 05.1 | Source and other SO remain unchanged |
| 05.3 | Prove replay scope and eligibility: Test same key, different payload/revision, cancelled/inactive source, concurrent same key | Owning files listed above; trace actual callers for this task | 05.2 | One keyed operation; unrelated replay cannot return another booking |
| 05.4 | Fix gaps and gate conversion: Preserve transactions/snapshots and add focused tests only for defects | Owning files listed above; trace actual callers for this task | 05.3 | Conversion acceptance and denial pass with PostgreSQL concurrency evidence |

## F. Error handling

Invalid dates/refs/state, missing revision, stale edits, duplicate key payload and race rollback are explicit; no silent Save or duplicated order.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_quotations.py tests/test_quotation_versions.py tests/test_quotation_reuse.py; inspect tests/test_quotation_postgres.py safe disposable configuration; frontend pnpm vitest run tests/quotation-actions.spec.ts; relevant browser actions.

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

New Sent/Accepted steps, rewriting historical revisions, automatic repricing of existing SOs.

