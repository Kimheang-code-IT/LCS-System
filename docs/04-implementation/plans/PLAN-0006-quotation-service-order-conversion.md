# PLAN-0006 — Quotation to Service Order (reuse and keyed commands)

## Metadata

Slice: S02 — Quotation to Service Order
Status: Completed
Last updated: 2026-11-04
Task level: STANDARD (operation) with PostgreSQL concurrency evidence for keyed conversion

## Objective and requirement IDs

Verify and complete the reuse model: multiple intentional, source-linked Service Orders may
be raised from one quotation; each keyed command creates exactly one order with preserved
independent snapshots; legacy payloads/data keep working. Requirements: LCS-003, LCS-014
(reference/master prerequisites), LCS-009/013 cross-cutting; P05 tasks 05.1–05.4.

## Dependencies and current implementation evidence

The reuse model was already implemented in the uncommitted working tree
(`f3a4b5c6d7e8_quotation_reuse_and_order_finish.py` migration + quotations service
E18/E21 changes + `backend/tests/test_quotation_reuse.py`). Verified fresh 2026-11-04.

## Scope and planned changes

Verification-first: no rewrite of the existing reuse engine; fix only demonstrated defects.

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| 05.1/05.2/05.3 backend acceptance (reuse, replay, Finish lock, legacy compat) | `uv run --no-sync pytest -q tests/test_quotation_reuse.py tests/test_quotations.py tests/test_quotation_versions.py` | 56 passed / 0 failed, 2026-11-04 |
| 05.4 PostgreSQL concurrency on disposable PG | `LCS_TEST_PG_*` → `uv run --no-sync pytest tests/test_quotation_postgres.py -q` | 3 passed (two concurrent different-key conversions → 2 independent orders with preserved quotation status; same-key barrier race → exactly 1 order/1 conversion; order delete nulls the re-quotation link); DB dropped after, 2026-11-04 |
| Browser journey (real UI): quotation create (Save), SO create via quotation pick, actual containers numbered + persisted, Finish lock, reports see both; plus viewer deny-side | `browser e2e run of e2e/qa-business-workflows.spec.ts` | 4 passed, 2026-11-04 (Chromium, local dev compose stack) |

## Demonstrated defects fixed

1. **Create-form save label** (E22 DEF-03): the quotation create save action rendered
   "Submit" from `freight.moduleActions.submitQuotation` while `submitQuotation` → `save()`
   keeps the quotation a Draft. The key value is now "Save" (en/km/zh), matching the action
   and the retained E2E journey wording.
2. **Silent line seeding**: `AppLineTable.addRow` pre-seeded every newly added line with the
   first list item of every select column (fee type/container type/charge basis). A user-added
   line silently carried a fee type nobody chose, and the sample journey's differing quantities
   (1 vs 2 boxes) produced conflicting-quantity refusals that blocked conversion. New rows now
   start blank; intentional seeding stays with `rowDefaults`.
3. Test-fixture hardening (no product change): the journey now creates its own transport-type
   fixture, selects the container type by its visible name (the stored value is the code), and
   polls the SO list for the keyed result instead of racing the in-flight save. Dev-DB fixture
   repair: trade direction "Improt" renamed to "Import".
4. `e2e/auth-renewal.spec.ts` (S01, E24) already updated for the mandatory `quotationId`.

## Acceptance criteria

1. Multiple intentional source-linked SOs may reuse an offer — proven (backend + PG concurrent + browser).
2. Each keyed command creates one order — replay via idempotency key returns the same order; concurrent same-key race returns one order (PG barrier test).
3. Preserved independent snapshots — copied rows/pricing totals stay per-order; editing one side never rewrites the other (backend test + journey).
4. Refusals/boundaries: conflicting container quantities (422), missing/unknown quotation (422), duplicate id (422? codes verified by suites), delete-with-SO 409, Finish lock 409.
5. Legacy SENT/ACCEPTED data and legacy payload shapes keep working; no historical record rewritten.

## Handoff

- Plan closed 2026-11-04. No commit authorized yet; the whole slice rides in the uncommitted
  tree. Checklist: register row E25 for this batch; MOD-002/MOD-003 page rows own the journey
  evidence (S01 AUTH rows already closed; business rows for conversion belong to FLOW-002/003).
- Limits: browser evidence Chromium-only (NT02); the journey leaves namespaced QSPEC residues
  in the disposable dev DB (documented in the spec header). No production data touched.