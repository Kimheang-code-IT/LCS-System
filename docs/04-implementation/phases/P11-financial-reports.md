# P11 — Financial Reports

## A. Phase summary

- Objective / expected result: Reconciled posted reports with explicit date/currency/sign/whole-export semantics.
- Priority: High.
- Dependencies: P09; P08 scoped posted/settlement fixture for full verification.
- Execution owner: S10. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-008; LCS-RPT-001; MOD-015–022. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Eight financial reports exist; only GL/TB registered for generate/export. Other paths may have UI-only filters/export and legacy float serialization.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/modules/reports/service.py](../../../backend/app/modules/reports/service.py)
- [backend/app/modules/reports/ledger_reports.py](../../../backend/app/modules/reports/ledger_reports.py)
- [backend/app/modules/reports/engine.py](../../../backend/app/modules/reports/engine.py)
- [backend/app/modules/reports/router.py](../../../backend/app/modules/reports/router.py)
- [frontend/app/config/freight-reports.ts](../../../frontend/app/config/freight-reports.ts)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Reconciled posted reports with explicit date/currency/sign/whole-export semantics. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Report query/filter/export UI/API and ledger reconciliation; no financial transaction creation; preserve existing report engine and source dimensions.

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
| 11.1 | Verify reconciliation baseline: Create safe synthetic posted/reversed multi-currency and partial-allocation dataset | `backend/app/modules/reports/service.py`; `backend/app/modules/reports/ledger_reports.py` | P09; P08 scoped posted/settlement fixture for full verification | GL/TB, AR/AP control bridges and date cutoffs reconcile |
| 11.2 | Verify all eight report contracts: Apply source/date/formula/grouping rules to each report and empty set | Owning files listed above; trace actual callers for this task | 11.1 | P&L, BS and cash flow reconcile without operational estimates |
| 11.3 | Verify filter/page/export/print parity: Trace every report adapter; test page 2, full CSV and unsupported format choices | Owning files listed above; trace actual callers for this task | 11.2 | No false full export/filter promises; same totals across supported outputs |
| 11.4 | Fix demonstrated query/UI mismatch: Use existing helpers, database Decimal sums and permission guards | Owning files listed above; trace actual callers for this task | 11.3 | No historical mutation; no mixed-currency or duplicate reversal totals |

## F. Error handling

Invalid date/range/filter/currency or denied source access gives clear refusal; report failure never silently displays cached success; imbalance is visible.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_report_accounting.py tests/test_report_generation.py tests/test_report_export.py tests/test_reporting_values.py tests/test_multi_currency.py (relevant subset); frontend report-focused specs; PostgreSQL for query/precision differences.

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

Statutory cash-flow classification, automated bank feeds, financial posting from reports or speculative analytics warehouse.

