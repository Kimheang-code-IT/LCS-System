# PLAN-0008 — S03 remaining acceptance (operations, movement backstop)

## Metadata

Slice: S03 — Operational Execution (remaining checklist rows FLOW-004/005, DATA-006,
shared portions of DATA-011/TECH-017/DATA-013; P06 tasks 06.1–06.4)
Status: Completed
Last updated: 2026-11-05
Task level: STANDARD (verification of working code + one additive integrity migration)

## Objective and requirement IDs

Demonstrate the remaining S03 acceptance criteria with executed tests and close the
identified integrity gap. Requirements: LCS-004, LCS-010; FLOW-004 (persist configured
rows, required values, movements/milestones, ACTIVE/INACTIVE guards), FLOW-005
(requirement vs actual containers, numbers/weights/ownership, linked-record deletion
refusal), DATA-006 (conversion persists routes/requirements/prepared actual containers/
component snapshots), DATA-011 (historical order keeps its captured configuration
snapshot), TECH-017/DATA-013 (storage round trip + refusals; recovery stays S12).

## Dependencies and current implementation evidence

Backend paths verified read-only first (2026-11-05): `save_service_order` (quotation
mandatory, partial-save merge, idempotency-key replay + commit-race replay),
`finish_service_order`/`_ensure_order_editing` (FINISHED locks, reopen clears the stamp),
`set_service_order_status` lifecycle, `delete_service_orders` (ORDER_ACTIVE /
ORDER_HAS_FINANCIAL_DOCUMENTS / ORDER_HAS_JOURNAL_ENTRIES / ORDER_HAS_SERVICE_CHARGES
conflicts), `delete_containers` (CONTAINER_IN_USE via the order's own containerPayments
rows), movement save (sequence auto-number, DUPLICATE_SEQUENCE, renumber clash,
inactive-order refusal), component-tab bulk rows (required-value 422 with field_errors).

## Scope and planned changes

Verification-first. One demonstrated defect fixed (see below); no behavioral rewrites.

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| FLOW-004/005 API-level journey (real HTTP client → guard → service → DB): movements/milestones CRUD + guards, required component values 422, inactive-order refusal, endpoints not public, conversion prepares pending boxes, numbering normalization + duplicates 409, payment-linked container deletion 409 CONTAINER_IN_USE, active/deletion conflicts, Finish idempotency | `uv run --no-sync pytest -q tests/test_workflows.py tests/test_movements_and_milestones.py tests/test_attachments.py` | 37 passed / 0 failed, 2026-11-05 |
| DATA-006 conversion transfers (routes copied, both sides stay editable; sequence renumbering) | `uv run --no-sync pytest -q tests/test_place_roles.py` | 6 passed, 2026-11-05 |
| DATA-011/TECH-017/DATA-013 S03 portion: publish/activate/rollback lifecycle, historical SO renders its captured snapshot, duplicate-version race refused; upload policy (MIME/extension/size) + attachment round trip/refusals | `uv run --no-sync pytest -q tests/test_config_compare.py tests/test_config_version_lifecycle.py tests/test_component_attributes.py` (45 passed); `tests/test_upload_policy.py` (4 passed) | 49 passed / 0 failed, 2026-11-05 |
| Integrity fix regression: chain/single-head/additive gates + movement suites + Finish-lock | `uv run --no-sync pytest -q tests/test_migration_chain.py tests/test_schema_integrity.py tests/test_schema_docs.py tests/test_workflows.py tests/test_movements_and_milestones.py tests/test_quotation_reuse.py` | 46 chain/integrity/docs passed, then 76 passed, 2026-11-05 |
| Migration applied + rollback on the dev PostgreSQL database (`freight`, additive; pre-checked: 0 duplicate `(service_order_id, sequence_no)` groups, 0 movement rows) | `alembic upgrade head`; `downgrade -1`; re-`upgrade head`; `\d service_order_movements` | c0d1e2f3a4b5 applied, constraint present, head restored; backend container rebuilt + healthy |

Concurrent-same-key conversion race on PG: not repeated — executed in E25
(test_quotation_postgres.py). Browser evidence: the actual-container UI journey was
executed in E25; no new browser run (avoid unnecessary browser interactions; the
movements/milestones tab browser journey belongs to the cross-browser NT02 scope).

## Demonstrated defects fixed

1. **Missing DB backstop for movement sequences** (found by inspection, FLOW-004):
   `ServiceOrderMovement` had no `UniqueConstraint("service_order_id", "sequence_no")`
   while the service docs claim the pair is unique and siblings
   (`service_order_places`, container numbers) carry one. Two concurrent movement
   writes could pass the app-level clash check and persist duplicate sequences.
   Fixed with additive revision `c0d1e2f3a4b5` + the model constraint; verified on the
   dev PostgreSQL database (apply, downgrade, re-upgrade, `\d` shows the constraint);
   `database-design.sql` regenerated (`--check --strict` passes).
2. **Broken in-progress chain test** (uncommitted 2026-11-04 edit): two regexes in
   `tests/test_migration_chain.py` were syntactically invalid (an unescaped `"` inside a
   double-quoted raw string), so the suite could not even be imported. Restored with
   equivalent triple-quoted raw strings, preserving the edit's `/`-exclusion intent, the
   new additive revisions, and the `AUTHORISED_DROPS` mechanism; head expectation moved to
   `c0d1e2f3a4b5`.

## Acceptance criteria

1. Configured rows, required values, movements and milestones persist with
   ACTIVE/INACTIVE/FINISHED guards — proven (API-level suites + E25 browser containers).
2. Quoted requirements and physical boxes stay separate; numbers normalize; duplicates
   and payment-linked deletions refuse — proven.
3. Conversion transfers routes/requirements/prepared boxes/component snapshots; both
   sides editable; historical order keeps its captured snapshot — proven.
4. Authorized save/finish create no journal; finance continues without settlement —
   proven (test_quotation_reuse / test_service_charge_to_invoice_and_posting, balanced
   journals asserted).
5. Storage round trip with type/size/ownership refusal on the real stack — proven
   (test_upload_policy/test_attachments + E26 browser against real MinIO); recovery drill
   remains S12's.

## Handoff

- S03 is COMPLETE 2026-11-05 (checklist E26/E27). Deferred (documented owners):
  TECH-017/DATA-013 isolated recovery drill → S12; DATA-011 remaining S11 scope;
  movements/milestones browser tab journey → NT02 cross-browser evidence.
- No commit authorized yet; the batch rides in the uncommitted tree. Dev DB was migrated
  in place (additive); backend image rebuilt so its alembic head matches the database.
- Limits: SQLite API evidence cannot prove PG lock behavior; the new unique constraint is
  the database-level backstop for exactly that case. No production data touched.
