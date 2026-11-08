# P08 — Financial Documents

## A. Phase summary

- Objective / expected result: Atomic documents and partial/full customer/supplier settlement with reliable balances.
- Priority: High.
- Dependencies: P07; P09 account/rule/open-period prerequisite; S01.
- Execution owner: S05–S07, one document/settlement slice at a time. [Master roadmap](../master-plan.md) controls sequence.
- Status: COMPLETED 2026-11-05 — all four tasks closed: 08.1 posting contract
  ([PLAN-0013](../plans/PLAN-0013-atomic-invoice-posting.md)/E32), 08.2 receipt
  allocation + AR ([PLAN-0014](../plans/PLAN-0014-receipt-allocation-ar-reconciliation.md)/E33),
  08.3 supplier bill/payment + AP
  ([PLAN-0015](../plans/PLAN-0015-supplier-bill-payment-ap-reconciliation.md)/E34) and
  08.4 corrections/reversals with the acceptance review
  ([PLAN-0016](../plans/PLAN-0016-reversals-corrections-s05-acceptance.md)/E35).
  Deferred with owners: allocation OPEN-period gate (S06/S08), audit split (S06+),
  per-currency presentation (S09/S10), browser journeys (NT02).
- Requirement references: LCS-005,006,007; MOD-009; FR-111–136. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Reusable invoice/bill/receipt/payment types, lines/sources, posting/reversal and allocations exist. Existing tests are not current runtime acceptance.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/finance/service.py](../../../backend/app/modules/finance/service.py)
- [backend/app/modules/finance/models.py](../../../backend/app/modules/finance/models.py)
- [backend/app/modules/finance/schemas.py](../../../backend/app/modules/finance/schemas.py)
- [backend/app/modules/finance/router.py](../../../backend/app/modules/finance/router.py)
- [frontend/app/config/freight-modules.ts](../../../frontend/app/config/freight-modules.ts)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Atomic documents and partial/full customer/supplier settlement with reliable balances. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Document form/types/dates/source references, payment allocation and posting integration; preserve supported behaviors and audit trail.

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
| 08.1 | Verify draft/type/source contract: Inspect canonical types, manual and generated drafts, date/rate/line validation | `backend/app/modules/finance/service.py`; `backend/app/modules/finance/models.py` | P07; P09 account/rule/open-period prerequisite; S01 | Invalid type/reference/rate refused; valid draft editable |
| 08.2 | Verify customer invoice/receipt flow: Post invoice then partial and full receipt allocation | Owning files listed above; trace actual callers for this task | 08.1 | AR and unapplied balances reconcile without second revenue |
| 08.3 | Verify supplier bill/payment flow: Post bill and eligible supplier payment allocations | Owning files listed above; trace actual callers for this task | 08.2 | AP control bridge reconciles and over-allocation denied |
| 08.4 | Verify correction/races and fix gaps: Test reversal, duplicate post/allocation and closed invoice/new-period receipt | Owning files listed above; trace actual callers for this task | 08.3 | Atomic history-preserving effects; no lost or excess settlement |

## F. Error handling

Unposted/incompatible target, party/currency mismatch, excess allocation, closed date, duplicate/reversed document and database failure leave no partial journal/allocation.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_financial_documents_module.py tests/test_finance_automation.py tests/test_multi_currency.py tests/test_workflows.py (scoped S05/S06/S07 cases); disposable PostgreSQL allocation/posting guards; frontend relevant form/action tests.

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

New approval statuses, blanket auto-post, rewriting history or adding tax workflows.

