# P07 — Service Charges

## A. Phase summary

- Objective / expected result: Valid revenue/cost visibility and once-only source-linked draft billing.
- Priority: High.
- Dependencies: P06; P09 accounting setup subset before conversion.
- Execution owner: S04. [Master roadmap](../master-plan.md) controls sequence.
- Status: COMPLETED 2026-11-05 — 07.1 map ([PLAN-0009](../plans/PLAN-0009-charge-pricing-source-map.md),
  E28), 07.2 issue isolation ([PLAN-0010](../plans/PLAN-0010-issue-isolation.md), E29),
  07.3 bill-once/idempotency ([PLAN-0011](../plans/PLAN-0011-bill-once-conversion-idempotency.md),
  E30) and 07.4 profit layers ([PLAN-0012](../plans/PLAN-0012-profit-layer-reconciliation.md),
  E31) all verified. Deferred to later phases with recorded owners: per-currency report
  presentation/date semantics → S09/S10; container-level profitability (no money
  allocations exist in the schema).
- Requirement references: LCS-004,005; LCS-CHG-001; MOD-004. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Charge Save/Issue and explicit invoice conversion exist. Keep configured pricing distinct from actual billing lines and posted expense.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/operations/service.py](../../../backend/app/modules/operations/service.py)
- [backend/app/modules/finance/service.py](../../../backend/app/modules/finance/service.py)
- [backend/app/modules/operations/models.py](../../../backend/app/modules/operations/models.py)
- [frontend/app/config/freight-modules.ts](../../../frontend/app/config/freight-modules.ts)
- [frontend/app/components/freight/JobFinance.vue](../../../frontend/app/components/freight/JobFinance.vue)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Valid revenue/cost visibility and once-only source-linked draft billing. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Charge editor/calculations/ownership and charge-to-draft transaction; cost provenance design only if demonstrated missing; no automatic journal.

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
| 07.1 | Map charge calculation and pricing source: Inspect fee lines, currency/precision, container/SO references and manual overrides | `backend/app/modules/operations/service.py`; `backend/app/modules/finance/service.py` | P06; P09 accounting setup subset before conversion | Current vs target cost/provenance fields explicit |
| 07.2 | Verify issue isolation: Issue valid/invalid charge and compare finance/journal counts | Owning files listed above; trace actual callers for this task | 07.1 | Issue changes only approved operational state |
| 07.3 | Verify bill-once across entry paths: Race charge conversion and inspect direct SO invoice overlap | Owning files listed above; trace actual callers for this task | 07.2 | One draft/source relationship; no duplicate billed lines |
| 07.4 | Fix and reconcile profit layers: Reuse existing draft service and compare estimated/issued/draft/posted totals | Owning files listed above; trace actual callers for this task | 07.3 | Source audit preserved; rounding and refusal regression pass |

## F. Error handling

Unissued/missing charge, cross-order box, invalid amount/rate, duplicate billing and rollback failures remain typed refusals, never partial draft+journal.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_charge_tax_round_trip.py tests/test_job_finance_entries.py tests/test_finance_automation.py tests/test_workflows.py (focused subset); PostgreSQL race fixture if source uniqueness changes; focused frontend charge/print tests.

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

Automatic posting, replacing posting engine, conflating estimated costs with supplier bill expenses.

