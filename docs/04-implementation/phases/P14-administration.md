# P14 — Administration

## A. Phase summary

- Objective / expected result: Safe identities/numbering/configuration and preserved searchable history.
- Priority: High prerequisites; remaining Medium.
- Dependencies: P01,P02; P03 for referenced vocabularies.
- Execution owner: S01 auth prerequisite; S02–S08 numbering; remaining S11. [Master roadmap](../master-plan.md) controls sequence.
- Status: NOT_STARTED — planned work package; existing code may already satisfy parts.
- Requirement references: LCS-002,009,014; LCS-AUTO-001; MOD-039–044. Details remain in [acceptance matrix](../acceptance-criteria.md);
  [inventory](../../00-project/feature-inventory.md) owns page contracts. No implementation authorized by package creation.

## B. Current situation and evidence

Users/single-role Casbin, sequences, centralized settings, archive and audit exist. Many browser action checks remain in active S01.

Evidence is source/config inspection at the 2026-11-04 working-tree snapshot and historical
records only. No fresh runtime pass is claimed. Before implementation, inspect these actual
source/discovery locations and their callers/tests:

- [backend/app/core/permissions.py](../../../backend/app/core/permissions.py)
- [backend/app/core/sequences.py](../../../backend/app/core/sequences.py)
- [backend/app/modules/auth/router.py](../../../backend/app/modules/auth/router.py)
- [backend/app/modules/settings/router.py](../../../backend/app/modules/settings/router.py)
- [backend/app/modules/archive/router.py](../../../backend/app/modules/archive/router.py)
- [backend/app/modules/audit/router.py](../../../backend/app/modules/audit/router.py)

Recheck working tree and timestamps; preserve existing changes and untracked migrations.

## C. Requirements and expected behavior

Safe identities/numbering/configuration and preserved searchable history. Apply the referenced requirement IDs and page acceptance rather than copying a
second authoritative rule set. Current implementation differences are verified before any fix.
Maintain Casbin backend enforcement, historical snapshots, meaningful refusal messages and
the accounting invariants whenever the selected task touches them.

## D. Technical scope

Existing six admin pages and code-defined capabilities; source permission semantics preserved; no live destructive reset or external message send.

Frontend changes use existing metadata/shared components/repositories and permission-aware
actions. Backend changes stay in existing owning services/routers. Database/API changes are
none by default: if required, document the demonstrated need, callers, additive compatibility,
migration/downgrade and exact contract before editing. Relevant permissions come from
permissions.py, router guards and existing compilation, never a parallel role map.

## Settings and integrations refinement

[PLAN-0005](../plans/PLAN-0005-settings-integrations.md) refines 14.2 into A audit, D shared
security/settings foundation, B Telegram, C email/recovery, E cloud recovery and G integration.
[Source inventory](../../01-architecture/integration-architecture.md#current-implementation-inventory)
separates existing outbox/private recovery/R2/Sheets/Excel from gaps. New capabilities/providers/
complete restore remain proposed and NOT_STARTED; preserve integrations and the Settings page.

## E. Small implementation tasks

Each task inherits this package's source list, requirement references and execution-slice
dependency. "Fix" is conditional: verification alone closes a task whose behavior already
passes. Activate only the required subset in an implementation plan.

| Task | Goal and expected change | Files / discovery | Dependency | Validation and measurable acceptance |
|---|---|---|---|---|
| 14.1 | Verify access and numbering prerequisites: Continue active S01 exact remaining scope; verify sequence transaction/retry behavior | `backend/app/core/permissions.py`; `backend/app/core/sequences.py` | P01,P02; P03 for referenced vocabularies | Protected administrator/denial rules and unique numbers proven |
| 14.2 | Verify settings validation/redaction: Exercise ordinary settings in isolated fixtures; inspect diagnostic/reset boundaries | Owning files listed above; trace actual callers for this task | 14.1 | Secrets excluded; invalid values refused; no unapproved side effects |
| 14.3 | Verify archive and audit coverage: Test allowlisted restore/dependency conflicts and sensitive financial/auth events | Owning files listed above; trace actual callers for this task | 14.2 | No automatic purge/history loss; audit payload redacted |
| 14.4 | Close per-page workflow gaps: Run focused CRUD/action/export/empty/locale cases and update evidence | Owning files listed above; trace actual callers for this task | 14.3 | Selected admin page accepted without broad refactor |

## F. Error handling

Duplicate identity/number, protected admin mutation, insufficient grant, restore collision and invalid setting are explicit; denied actions have no business side effect.

Applicable refusal matrix: invalid input → persistent field error; unknown related record →
typed missing-reference response; invalid lifecycle → conflict/refusal; insufficient capability
→ backend denial with no business mutation; duplicate/retry → command-specific replay/conflict;
database failure → rollback; concurrency conflict → safe refusal or original result.
Do not invent a universal retry key or apply this matrix as a new API/status model.

## G. Testing and candidate validation

uv run pytest -q tests/test_auth_rbac.py tests/test_role_permissions.py tests/test_settings_validation.py tests/test_archive.py tests/test_audit_logs.py (active scoped subset); existing e2e/page-authorization.spec.ts; disposable auth/session tests when in scope.

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

Role inheritance, second permission engine, autonomous data reset, secret retrieval workflow or production changes.

