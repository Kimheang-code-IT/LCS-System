# P16 — Final Quality and Production-Readiness Review

## A. Phase summary

- Objective / expected result: Evidence-based release decision with explicit business/security/finance/recovery sign-off.
- Priority: High release gate.
- Dependencies: P15; S12 authorized isolated recovery; S01–S12 acceptance.
- Execution owner: S13. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-010–016,019; existing release blockers. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

No current production/cross-browser/capacity/restore evidence established by documentation. Numeric capacity/RPO/RTO/WCAG/retention targets and named owners remain unapproved.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [docs/03-development/testing-guide.md](../../03-development/testing-guide.md)
- [docs/03-development/deployment-guide.md](../../03-development/deployment-guide.md)
- [docs/00-project/requirements.md](../../00-project/requirements.md)
- [infrastructure/restore-db.sh](../../../infrastructure/restore-db.sh)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Evidence-based release decision with explicit business/security/finance/recovery sign-off. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Read-only review and authorized isolated tests; no deployment/provider/infrastructure change implicit in acceptance.

Frontend changes use existing metadata/shared components/repositories and permission-aware
actions. Backend changes stay in existing owning services/routers. Database/API changes are
none by default: if required, document the demonstrated need, callers, additive compatibility,
migration/downgrade and exact contract before editing. Relevant permissions come from
permissions.py, router guards and existing compilation, never a parallel role map.

## Settings and integrations refinement

[PLAN-0005 G](../plans/PLAN-0005-settings-integrations.md#phase-g--integration-review) checks
routing isolation, recovery, encryption, job/restore replay, bulk IO and complete DB/files/config.
Source specifications do not establish release acceptance. Task 16.3 still needs a separately
authorized isolated full restore with measured RPO/RTO; no production/provider test is implied.

## E. Small implementation tasks

Each task inherits this package's source list, requirement references and execution-slice
dependency. "Fix" is conditional: verification alone closes a task whose behavior already
passes. Activate only the required subset in an implementation plan.

| Task | Goal and expected change | Files / discovery | Dependency | Validation and measurable acceptance |
|---|---|---|---|---|
| 16.1 | Audit architecture/security/finance evidence: Review scoped results, dependency risks and unresolved high/critical defects | `docs/03-development/testing-guide.md`; `docs/03-development/deployment-guide.md` | P15; S12 authorized isolated recovery; S01–S12 acceptance | No critical integrity/auth/financial blocker hidden |
| 16.2 | Verify supported browsers/accessibility/print: Test Chrome/Edge/Firefox/Safari plus keyboard/focus/labels and bilingual documents | Owning files listed above; trace actual callers for this task | 16.1 | Approved target behaviors work; unsupported limits explicit |
| 16.3 | Verify measured performance and recoverability: Use approved realistic dataset/targets and isolated coordinated DB/file/config recovery | Owning files listed above; trace actual callers for this task | 16.2 | No invented speed/RPO/RTO pass; restore ledger/files/source links reconcile |
| 16.4 | Reconcile docs and obtain acceptance: Update source/requirement/test traceability, tracker and Handoff; present business result | Owning files listed above; trace actual callers for this task | 16.3 | Release only after required approvals; open noncritical issues explicitly accepted |

## F. Error handling

Missing target/owner/environment/evidence → NEEDS_REVIEW/BLOCKED release acceptance; do not infer readiness from green unit tests.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

Approved cross-browser e2e/manual matrix, relevant full release gates, load/query profiling with approved targets, separately authorized restore drill. Documentation links/coverage and secret-safe diff checks.

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

Automatic production deploy/commit, destructive restore/reset, unapproved thresholds or claims of legal/statutory compliance.

