# P09 — Accounting and Posting Rules

## A. Phase summary

- Objective / expected result: Stable account mappings, balanced immutable journals and custom-date OPEN-period controls.
- Priority: High.
- Dependencies: P03 finance references; P14.1 identity/numbering prerequisite; S01.
- Execution owner: Setup before S05; corrections/custom periods in S08. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-006,009; LCS-PER-001; MOD-010–014. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Rule resolver and strategy posting are separate. Custom period UI derives year/month, model retains same-month unique key, resolver auto-creates OPEN gaps.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/finance/posting.py](../../../backend/app/modules/finance/posting.py)
- [backend/app/modules/finance/posting_rules.py](../../../backend/app/modules/finance/posting_rules.py)
- [backend/app/modules/finance/service.py](../../../backend/app/modules/finance/service.py)
- [backend/app/modules/finance/models.py](../../../backend/app/modules/finance/models.py)
- [backend/tests/test_accounting_periods.py](../../../backend/tests/test_accounting_periods.py)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Stable account mappings, balanced immutable journals and custom-date OPEN-period controls. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Existing setup UI, posting/period/journal services and database guards; additive migrations only if demonstrated necessary, never hand-edit SQL.

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
| 09.1 | Verify required accounting setup: Test account hierarchy/postability, financial-account currency/link, rule tiers and ambiguity | `backend/app/modules/finance/posting.py`; `backend/app/modules/finance/posting_rules.py` | P03 finance references; P14.1 identity/numbering prerequisite; S01 | Valid deterministic mapping for each scoped source type |
| 09.2 | Verify posting invariants and reversals: Inspect transaction/audit boundaries, Decimal/FX snapshots and unique effects | Owning files listed above; trace actual callers for this task | 09.1 | Debit=credit; rollback leaves no partial status/journal; posted history immutable |
| 09.3 | Verify custom dates and permission bypass: Test non-overlap, disjoint same-month ranges, missing period, generic state update and close/post race | Owning files listed above; trace actual callers for this task | 09.2 | No year input; invalid/unauthorized/closed posting denied on every path |
| 09.4 | Fix demonstrated integrity gap safely: Use existing constraints/transactions; additive migration plus regenerated SQL only if needed | Owning files listed above; trace actual callers for this task | 09.3 | Downgrade/schema docs and PostgreSQL guards verified without historical rewrite |

## F. Error handling

Invalid/cyclic account, ambiguous rule, unbalanced journal, overlap/missing/closed period, stale mapping or duplicate posting fail atomically; elevated role has no closed-period bypass.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_posting_rules.py tests/test_accounting_periods.py tests/test_finance_automation.py tests/test_schema_integrity.py tests/test_multi_currency.py (affected scope); PostgreSQL trigger/race tests mandatory; uv run python scripts/generate_schema_docs.py --check --strict if models/migrations change.

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

Replacement accounting engine, monthly automatic retained-earnings close, production migration or schema edits in documentation task.

