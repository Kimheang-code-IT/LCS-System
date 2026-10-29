# Freight Forwarding — Feature Status Report

## Report Information

- **Last updated:** 2026-10-23
- **Audit mode:** Initial full inventory (baseline). Future updates are incremental (see §12).
- **Git commit / branch:** `a30db459f115dd5e9cedd095cab0c67ca1f9d4b0` on `dev`, with uncommitted work in the tree.
- **Working tree at audit time:** 91 modified/untracked paths. Another session edited files during the audit
  (`backend/tests/test_migration_chain.py`, `AGENTS.md`, `docs/11_deployment_and_security.md` and others have
  timestamps inside the audit window). This is the single most important limitation below.
- **Application version:** backend `0.1.0` (`backend/pyproject.toml`); frontend package is unversioned.
- **Verification environment:** Windows 11; Python 3.12 with `uv`; Node 20+/`pnpm`; Docker Compose stack running
  (`ff-api`, `ff-frontend`, `ff-db`, `ff-redis`, `ff-minio`, all healthy); backend tests on in-memory SQLite;
  no production data touched.
- **Number of features:** 138
- **Audit limitations:**
  1. The tree was being edited concurrently, so "current revision" is a moving target. The backend suite reported
     one failure (`test_the_chain_reaches_the_expected_head`) that was a *stale expectation in the file while the
     run was in progress*; after the other session updated it, the isolated test passed. Current head is
     `f0b1c2d3e4f5` and matches `alembic heads`.
  2. Backend tests run on SQLite with foreign keys **off** and no triggers. PostgreSQL-only guards, FK actions and
     migration behaviour are therefore not verified here.
  3. The live stack was built ~2 hours before the audit and may not contain every uncommitted edit.
  4. Playwright E2E was not executed (it needs the compose stack plus optional credentials, and it is read-only).
  5. No authenticated API calls were made: no credentials were used and no data was created, edited or deleted.
  6. "Production ready" is a feature-level judgement recorded separately from implementation status; it does not
     certify the platform (see §10).

### Evidence commands actually run

| Command | Directory | Observed outcome |
|---|---|---|
| `uv run pytest -q` | `backend/` | 531 passed, 1 failed (stale migration-head expectation, explained above), 9m33s |
| `uv run pytest tests/test_migration_chain.py::test_the_chain_reaches_the_expected_head -q` | `backend/` | 1 passed (re-run after the concurrent edit) |
| `uv run ruff check .` | `backend/` | All checks passed |
| `uv run python scripts/generate_schema_docs.py --check --strict` | `backend/` | Up to date; 76 tables and columns documented |
| `pnpm test` | `frontend/` | 74 files, 606 tests passed |
| `pnpm lint` | `frontend/` | exit 0 |
| `pnpm typecheck` | `frontend/` | exit 0 |
| `pnpm i18n:check` | `frontend/` | passed; `km` and `zh` 3138/3138 keys, 52 values identical to English |
| `Invoke-WebRequest http://localhost:8000/health`, `/api/v1/health` | host | `{"status":"ok"}` / envelope `{"data":{"status":"ok"}}` |
| `GET /api/v1/auth/setup/status` | host | `{"data":{"requiresSetup":false}}` |
| `GET /openapi.json` | host | 207 documented paths |
| `GET /api/v1/quotations` (no token) | host | HTTP 401 (authorization enforced) |
| `GET http://localhost/` | host | HTTP 200, SPA shell served |

Nothing in the application source, database or deployment was changed by this audit.

---

## Executive Summary

| Status | Count |
|---|---|
| WORKING | 103 |
| UNVERIFIED | 11 |
| PARTIAL | 10 |
| BROKEN | 1 |
| MISSING | 7 |
| NEEDS_IMPROVEMENT | 6 |
| BLOCKED | 0 |
| **Total features** | **138** |
| Production-ready features (`Production Ready = Yes`) | 96 |
| Production-ready with conditions (`Conditional`) | 7 |
| Not production-ready (`No`) | 35 |

The implemented core is broad and unusually well tested for its size: 540 backend tests (plus 3 PostgreSQL-only)
and 609 frontend tests pass, the financial posting engine has a 37-test posting-rule suite, and the live stack
answers health checks.
The report is **not** a claim that the product is production-ready. One genuinely broken workflow (user deletion
on PostgreSQL), missing PostgreSQL trigger verification in CI, no monitoring/alerting, no off-host database
backup automation and a private key inside the working tree keep overall readiness at **NO-GO**.

Three findings should be read first:

1. **`AUTH-012` is BROKEN on PostgreSQL.** `audit_events.actor_user_id` has a plain `ForeignKey("users.id")`
   (no `ON DELETE SET NULL`). Deleting a user who has ever acted therefore violates the FK. The SQLite suite has
   foreign keys off, so it cannot catch this.
2. **Unreachable functionality is presented as implemented.** Movements and milestones have complete, tested APIs
   but no UI caller; quotation revision comparison has an API and no UI; currency rates have no screen at all.
3. **The evidence gaps are specific, not general.** Eleven features are simply unverified (for example gross/net
   weight validation, several reports, audit-log filtering), not unknown.

---

## Overall Progress

Rules used, so the numbers can be reproduced from the matrix:

- **Strict verified completion** = `WORKING / total` = 103 / 138 = **74.6%**. Unverified features are *not*
  counted as complete.
- **Weighted delivery progress** = sum of weights / total, where WORKING = 1.00, NEEDS_IMPROVEMENT = 0.85,
  PARTIAL = 0.55, UNVERIFIED = 0.35, BROKEN = 0.10, MISSING = 0.00, BLOCKED = 0.00.
  `(103×1.00 + 6×0.85 + 10×0.55 + 11×0.35 + 1×0.10) / 138` = **85.2%**.
- **Production readiness** = feature-level `Production Ready = Yes / total` = 96 / 138 = **69.6%**, assessed
  separately from status; a feature can be WORKING and still not production-ready (for example
  `BAK-002` passes its scheduler test but is `Conditional` because nothing monitors the in-process job).
- **Status is behavioural, not structural.** A route or component existing is never enough for WORKING.
- Priority is business criticality of the feature, not of its defects: P0 = release blocker, P1 = major,
  P2 = normal, P3 = cosmetic.

---

## Feature Status Matrix

`W` = WORKING, `U` = UNVERIFIED, `P` = PARTIAL, `B` = BROKEN, `M` = MISSING, `N` = NEEDS_IMPROVEMENT.
Evidence is abbreviated; the module assessments in §5 give the full picture. `Last Verified` is the date the
listed evidence was actually executed, or `docs` when only documentation was reviewed.

| ID | Module | Feature | Status | Priority | Production Ready | Evidence | Last Verified |
|---|---|---|---|---|---|---|---|
| AUTH-001 | Authentication | First-run setup and initialization | WORKING | P0 | Yes | `test_setup.py` (4); live `/auth/setup/status` → initialized | 2026-10-23 |
| AUTH-002 | Authentication | Login by username or email + password | WORKING | P0 | Conditional | `uv run pytest tests/test_auth_sessions.py tests/test_auth_remember_me.py -q --disable-warnings`: 26 passed; isolated Playwright auth journeys: 4 passed; production HTTPS pending | 2026-10-24 |
| AUTH-003 | Authentication | Stable sessions, silent renewal, rotation, idle/absolute limits | WORKING | P0 | Conditional | `uv run pytest tests/test_auth_sessions.py tests/test_auth_remember_me.py -q --disable-warnings`: 26 passed; disposable `test_auth_postgres.py`: 1 passed; production HTTPS pending | 2026-10-24 |
| AUTH-004 | Authentication | Remember-me cookie persistence within finite session deadlines | WORKING | P2 | Conditional | `test_auth_remember_me.py`: 12 passed as part of 26-test auth run; server idle/absolute bounds apply to both cookie modes | 2026-10-24 |
| AUTH-005 | Authentication | Logout and immediate session/access revocation | WORKING | P0 | Conditional | `test_auth_sessions.py` + `test_auth_remember_me.py`: 26 passed; delayed renewal/logout coordinator and browser checks; HTTPS release check pending | 2026-10-24 |
| AUTH-006 | Authentication | Password reset with time-limited code | WORKING | P1 | Yes | `test_password_reset.py` (15) | 2026-10-23 |
| AUTH-007 | Authentication | Change password and forced password change | WORKING | P1 | Yes | `test_password_reset.py`; `tests/user-form-password.spec.ts` | 2026-10-23 |
| AUTH-008 | Authentication | Account lockout after failed attempts | WORKING | P0 | Yes | `test_lockout_policy.py` (4); `test_auth_rbac.py` | 2026-10-23 |
| AUTH-009 | Authentication | Request throttling / rate limiting | WORKING | P1 | Conditional | `test_rate_limit.py` (8); `test_redis_integration.py` (17) — depends on Redis | 2026-10-23 |
| AUTH-010 | Authentication | User create, update, status lifecycle | WORKING | P0 | Yes | `test_auth_rbac.py` (15); `test_workflows.py::test_user_create_*` | 2026-10-23 |
| AUTH-011 | Authentication | Profile and avatar | WORKING | P2 | Yes | `test_api_completeness.py::test_profile_avatar_persists` | 2026-10-23 |
| AUTH-012 | Authentication | User deletion | BROKEN | P1 | No | `audit/models.py` FK without `ondelete`; SQLite tests run FK-off; `docs/10` §7 | 2026-10-23 |
| AUTH-013 | Authentication | Password strength policy | WORKING | P1 | Yes | `test_password_policy.py` (20): length + uppercase + lowercase + number + special on setup, reset, change, admin reset and user creation; legacy weak login still succeeds; `tests/password-policy.spec.ts` + `tests/password-forms.spec.ts` (frontend mirror, 5 forms gated) | 2026-10-24 |
| AUTH-014 | Authentication | MFA for privileged users | MISSING | P2 | No | `docs/11` §18 (open risk) | docs |
| AUTH-015 | Authentication | Permission/role change effective without re-login | WORKING | P1 | Yes | `test_auth_rbac.py::test_permission_and_role_changes_take_effect_without_relogin`: a role grant/revoke flips `/users` 403↔200 on the live session; the enforcer reloads after every policy write | 2026-10-27 |
| RBAC-001 | Roles & permissions | Permission catalog and startup sync | WORKING | P0 | Yes | `test_role_permissions.py` (catalog uniqueness/classification, seeded grants); `ensure_permission_catalog` seeds 283 codes + 7 roles + their Casbin grants at startup; `/permissions/catalog` returns 39 pages and 81 modules | 2026-10-27 |
| RBAC-002 | Roles & permissions | Role CRUD, duplicate, search, pagination | WORKING | P0 | Yes | `test_role_permissions.py::test_creating_a_role_stores_policy_rows` plus the role lifecycle cases in `test_auth_rbac.py`; create/read over HTTP verified in `pytest` on this revision (2026-10-28) | 2026-10-28 |
| RBAC-003 | Roles & permissions | Role permission matrix UI and round-trip | UNVERIFIED | P1 | No | Matrix renders the backend `/permissions/catalog` pages and saves page codes (compile happens server-side); `pnpm lint`/`typecheck`/`test`/`i18n:check` pass but the page was not exercised in a browser | 2026-10-27 |
| RBAC-004 | Roles & permissions | Single-role assignment (one role per user, replacement semantics) | WORKING | P0 | Yes | `test_auth_rbac.py::test_a_user_holds_exactly_one_role_and_assignment_replaces_it` + `test_multiple_role_payloads_are_rejected`; `test_single_role_rbac.py::test_the_database_allows_only_one_role_per_user` (partial unique index); migration `b4c5d6e7f8a9` materializes legacy inheritance and aborts on unresolved multi-role users | 2026-10-28 |
| RBAC-005 | Roles & permissions | Page grant compiles to API permissions | WORKING | P0 | Yes | `test_role_permissions.py`: a configuration *view* page no longer grants write, a settings view no longer grants backup, untick/revoke drops the derived capabilities, one capability never grants an independent one, and compiling is idempotent for all 283 codes; `test_single_role_rbac.py::test_repeated_permission_saves_do_not_expand` proves repeated saves never widen the set | 2026-10-28 |
| RBAC-006 | Roles & permissions | Protected system administrator identity | WORKING | P0 | Yes | `test_auth_rbac.py`: stripping/ deactivating/deleting `SUPER_ADMIN` and mutating the built-in administrator are refused (403); last holder cannot be unassigned or deactivated; migration `a1b2c3d4e5f7` renamed `PLATFORM_ADMIN` → `SUPER_ADMIN` | 2026-10-27 |
| RBAC-007 | Roles & permissions | Delegation and privilege-escalation guard | WORKING | P0 | Yes | `test_auth_rbac.py::test_privilege_escalation_is_blocked`: a delegated role manager holding `role.manage` cannot grant a code it lacks, create a privileged role, or assign `SUPER_ADMIN` | 2026-10-28 |
| RBAC-008 | Roles & permissions | Server-side authorization (401/403) | WORKING | P0 | Yes | `test_auth_rbac.py::test_least_privilege_default_deny` (403 + `AUTHORIZATION_DENIED` row written by `record_denial`); compose stack 2026-10-27: anonymous `/users` → 401, `VIEWER` `/users` → 403, `/quotations` → 200 | 2026-10-27 |
| RBAC-009 | Roles & permissions | Role inheritance without cycles | MISSING | P1 | Yes | Intentionally removed (task 2026-10-28): no `parentRoles` field, no `/roles/{id}/inheritance` endpoints, the loader ignores legacy `role:`→`role:` edges, and migration `b4c5d6e7f8a9` materializes inherited grants as direct child-role grants before deleting the edges; covered by `test_role_permissions.py::test_role_permissions_are_direct_and_inheritance_is_gone` | 2026-10-28 |
| RBAC-010 | Roles & permissions | Redis policy synchronization and fail-closed reload | WORKING | P0 | Conditional | `cache.bump("auth")` + per-worker reload with the version read before the rows; `CASBIN_RELOAD_INTERVAL_SECONDS` backstop; a load failure drops the copy and answers `503`. Compose run 2026-10-27 (Redis up); the Redis-outage path was not exercised | 2026-10-27 |
| MASTER-001 | Master data | Business parties | WORKING | P0 | Yes | `test_workflows.py::test_business_party_roles`; business-parties pages | 2026-10-23 |
| MASTER-002 | Master data | Party roles and assignments | WORKING | P1 | Yes | `test_party_roles.py` (5) | 2026-10-23 |
| MASTER-003 | Master data | Place roles and route stops | WORKING | P1 | Yes | `test_place_roles.py` (6); `tests/place-roles.spec.ts` | 2026-10-23 |
| MASTER-004 | Master data | Trade directions | WORKING | P0 | Yes | `test_quotations.py::test_a_quotation_saves_for_each_configured_trade_direction` | 2026-10-23 |
| MASTER-005 | Master data | Container types (ISO dimensions) | WORKING | P1 | Yes | `test_container_types.py` (4); `tests/container-types.spec.ts` | 2026-10-23 |
| MASTER-006 | Master data | Transport types | WORKING | P0 | Yes | `test_quotations.py` transport-type tests | 2026-10-23 |
| MASTER-007 | Master data | Transport assets, identity vocabulary, capacity | WORKING | P1 | Yes | `test_transport_assets.py` (26); `tests/transport-assets.spec.ts` | 2026-10-23 |
| MASTER-008 | Master data | Fee types | WORKING | P1 | Yes | `test_posting_rules.py` fee-specific rule tests | 2026-10-23 |
| MASTER-009 | Master data | Currencies | WORKING | P0 | Yes | `test_currencies_and_fx.py` (4); `tests/removed-features.spec.ts` | 2026-10-23 |
| MASTER-010 | Master data | Currency exchange-rate store | PARTIAL | P1 | No | `test_multi_currency.py` (13); API-only, no screen by owner decision (`lcs-reference-modules.ts` §currency rates) | 2026-10-23 |
| MASTER-011 | Master data | Reference status and deactivation | WORKING | P1 | Yes | `test_record_status.py` (18) | 2026-10-23 |
| MASTER-012 | Master data | Delete guards and reference policy | WORKING | P0 | Yes | `test_deletion_policy.py` (8); `test_archive.py` | 2026-10-23 |
| MASTER-013 | Master data | Document Types master (custom labels over canonical accounting behaviours) | WORKING | P1 | Yes | `test_document_types.py` (7); `test_migration_chain.py` parity regression (26); migration `f6a7b8c9d0e1` applied live on the migrated DB — `select(DocumentType)` returns rows on PostgreSQL | 2026-10-24 |
| PLAT-006 | Platform | Excel Import & Export engine + Master Data import/export (Phase A/B) | WORKING | P1 | Yes | `test_excel_import_export.py` (46, incl. filter/status/search/date-range/CSV/invalid-filter/export-count guards plus zip-expansion, row-cap, export-escape, export-header round-trip and history-authz); `tests/export-dialog.spec.ts` (5) and `tests/excel-io.spec.ts`; full backend suite 692 passed / 5 skipped; frontend 91 files / 737 passed, typecheck, lint, i18n check green. The workspace list Export menu item opens the filter dialog (date range, Created/Updated By, status, keyword), shows the matching-record count via `GET /{module}/export-count`, and exports xlsx or csv with filters applied at the database query level | 2026-10-26 |
| MASTER-013 | Master data | Customer customs credentials | PARTIAL | P1 | No | Encrypted generic record tested (`test_workflows.py::test_generic_records_encrypt_credentials`); `customer_customs_accounts` + `customs_credential.retrieve` unused (`docs/10` §7) | 2026-10-23 |
| MASTER-014 | Master data | Legacy generic collections (companies, shipments, customs, documents, deliveries, payments) | PARTIAL | P2 | No | `master_data/service.py: GENERIC_COLLECTIONS`; no frontend page; `companies` still feeds search | 2026-10-23 |
| CFG-001 | Dynamic configuration | Component attribute catalog and data types | WORKING | P0 | Yes | `test_component_attributes.py` (20); inline-validation specs | 2026-10-23 |
| CFG-002 | Dynamic configuration | Component groups | WORKING | P1 | Yes | `test_component_layouts.py` (11) | 2026-10-23 |
| CFG-003 | Dynamic configuration | Component tabs, shared tabs, direction filtering | WORKING | P0 | Yes | `test_component_layouts.py`; `tests/component-layout.spec.ts` | 2026-10-23 |
| CFG-004 | Dynamic configuration | Configuration version publish/activate/rollback/retire | WORKING | P0 | Yes | `test_config_version_lifecycle.py` (9) | 2026-10-23 |
| CFG-005 | Dynamic configuration | Version compare and historical snapshot rendering | WORKING | P1 | Yes | `test_config_compare.py` (3); `test_config_version_lifecycle.py::test_historical_service_order_*` | 2026-10-23 |
| CFG-006 | Dynamic configuration | Snapshot validation | WORKING | P1 | Yes | `test_config_versions.py` (8); `config_versions.py::validate_snapshot` | 2026-10-23 |
| CFG-007 | Dynamic configuration | UI schema delivery (`/ui-schemas/{page}`) | UNVERIFIED | P2 | No | Route exists in `master_data/router.py`; no dedicated behavioural test found | docs |
| CFG-008 | Dynamic configuration | Keyboard-accessible catalog reordering | NEEDS_IMPROVEMENT | P3 | No | Move buttons only; `docs/10` §8 | docs |
| QUOT-001 | Quotations | Create and save a draft | WORKING | P0 | Yes | `test_quotations.py` (22) | 2026-10-23 |
| QUOT-002 | Quotations | Edit draft; issued revision immutable | WORKING | P0 | Yes | `test_quotation_versions.py::test_editing_an_issued_revision_opens_a_new_one_*` | 2026-10-23 |
| QUOT-003 | Quotations | Delete draft with conversion guard | WORKING | P1 | Yes | `test_quotations.py::test_delete_is_blocked_once_quotation_has_service_order` | 2026-10-23 |
| QUOT-004 | Quotations | Header and route validation (party, direction, dates, roles) | WORKING | P0 | Yes | `test_quotations.py` (22); `document-form-validation.spec.ts` | 2026-10-23 |
| QUOT-005 | Quotations | Pricing lines and authoritative totals | WORKING | P0 | Yes | `test_quotations.py::test_the_backend_recomputes_quotation_totals_*`; `document-calculations.spec.ts` | 2026-10-23 |
| QUOT-006 | Quotations | Container requirements on a revision | WORKING | P1 | Yes | `test_quotations.py::test_container_requirements_are_persisted_and_returned` (API round trip + `quotation_revision_containers` row) | 2026-10-23 |
| QUOT-007 | Quotations | Send revision | WORKING | P0 | Yes | `test_record_status.py::test_a_quotation_send_is_audited`; `test_quotation_versions.py` | 2026-10-23 |
| QUOT-008 | Quotations | Accept, reject, cancel | WORKING | P0 | Yes | `test_workflows.py::test_quotation_lifecycle_and_conversion`; `test_quotation_versions.py` | 2026-10-23 |
| QUOT-009 | Quotations | Convert accepted revision to service order (idempotent) | WORKING | P0 | Yes | `test_workflows.py`; `test_quotation_versions.py::test_a_converted_revision_cannot_be_converted_twice`; `test_quotations.py::{test_conversion_replays_the_same_idempotency_key,test_only_an_accepted_revision_can_be_converted}`; `test_quotation_postgres.py` (two concurrent conversions → one order, one 409) | 2026-10-23 |
| QUOT-010 | Quotations | Revision creation, copy and numbering | WORKING | P0 | Yes | `test_quotation_versions.py` (7) | 2026-10-23 |
| QUOT-011 | Quotations | Revision history UI | WORKING | P1 | Yes | `quotation-revisions.spec.ts` (5); revisions tab renders R01-style revision/status/grand total/creator/created/actions, newest first, read-only (no add row) | 2026-10-23 |
| QUOT-012 | Quotations | Side-by-side revision comparison UI | MISSING | P1 | No | Compare API + `test_compare_revisions_*` exist; the Compare Selected UI was removed at the owner's request | 2026-10-23 |
| QUOT-013 | Quotations | Re-quotation from a service order | WORKING | P2 | Yes | `test_quotations.py::test_requotation_from_a_service_order_creates_a_new_draft` (+3 sibling tests, route/containers/pricing asserted); `test_quotation_postgres.py::test_deleting_the_order_nulls_the_requotation_link`; `quotation-actions.spec.ts`; order header action in `DocumentView.vue` | 2026-10-23 |
| QUOT-014 | Quotations | Bilingual print preview | WORKING | P2 | Yes | `quotation-print.spec.ts`; `print-model.spec.ts`; visual output not machine-checked | 2026-10-23 |
| QUOT-015 | Quotations | Quotation permissions | WORKING | P0 | Yes | Casbin `p, role:<code>, quotation, <action>` policies + page compile (`compile_role_permissions`); `test_frontend_api_contract.py` keeps the route list honest | 2026-10-27 |
| ORDER-001 | Service orders | Create from quotation, list, detail | WORKING | P0 | Yes | `test_workflows.py::test_quotation_lifecycle_and_conversion` | 2026-10-23 |
| ORDER-002 | Service orders | Edit with source snapshots | WORKING | P0 | Yes | `test_workflows.py`; `operations/service.py` | 2026-10-23 |
| ORDER-003 | Service orders | ACTIVE/INACTIVE status policy | WORKING | P0 | Yes | `test_record_status.py`; `test_movements_and_milestones.py::test_inactive_service_orders_reject_operational_edits` | 2026-10-23 |
| ORDER-004 | Service orders | Actual containers and unique numbers | WORKING | P0 | Yes | `test_workflows.py::test_service_order_components_and_containers`, `test_conversion_prepares_pending_actual_containers`; `job-containers.spec.ts` | 2026-10-23 |
| ORDER-005 | Service orders | Gross weight ≥ net weight validation | UNVERIFIED | P1 | No | Implemented at `operations/service.py:543-549`; no test exercises it | docs |
| ORDER-006 | Service orders | Dynamic component tabs, rows, required-field validation | WORKING | P0 | Yes | `test_component_layouts.py`; `tests/job-component-tabs.spec.ts` | 2026-10-23 |
| ORDER-007 | Service orders | Movements / itinerary (API) | PARTIAL | P1 | No | `test_movements_and_milestones.py` (10) pass; no UI caller (`grep` finds only endpoint constants) | 2026-10-23 |
| ORDER-008 | Service orders | Milestones (API) | PARTIAL | P1 | No | Same as ORDER-007 | 2026-10-23 |
| ORDER-009 | Service orders | Attachments on order and components | WORKING | P1 | Yes | `test_attachments.py` (8); Files tab Note column edited in the cell (`attachment-note.spec.ts`) | 2026-10-23 |
| ORDER-010 | Service orders | Finish order (audited) | WORKING | P1 | Yes | `test_workflows.py::test_service_order_finish`; `test_record_status.py` | 2026-10-23 |
| ORDER-011 | Service orders | Bilingual print | WORKING | P2 | Yes | `job-print.spec.ts`; `print-model.spec.ts` | 2026-10-23 |
| ORDER-012 | Service orders | One idempotent invoice from order charges | WORKING | P0 | Yes | `test_reporting_values.py::test_order_invoice_endpoint_is_idempotent_*`; `test_workflows.py` | 2026-10-23 |
| CHG-001 | Service charges | Create, edit, delete draft charge | WORKING | P0 | Yes | `test_workflows.py`; `test_finance_automation.py` | 2026-10-23 |
| CHG-002 | Service charges | Fee lines with optional container / whole-order charge | WORKING | P0 | Yes | `test_workflows.py`; `job-component-line-table.spec.ts`; `job-containers.spec.ts` per-container expansion | 2026-10-23 |
| CHG-003 | Service charges | Totals and tax round trip | WORKING | P0 | Yes | `test_charge_tax_round_trip.py` (6) | 2026-10-23 |
| CHG-004 | Service charges | Issue action and issued immutability | WORKING | P0 | Yes | `test_finance_automation.py::test_service_charge_validation_and_issued_immutability` | 2026-10-23 |
| CHG-005 | Service charges | Convert to draft finance invoice (idempotent) | WORKING | P0 | Yes | `test_finance_automation.py::test_issued_charge_automatically_creates_one_draft_invoice` | 2026-10-23 |
| CHG-006 | Service charges | Issuing creates no journal | WORKING | P0 | Yes | `test_finance_automation.py`; invariant INV-005 in `docs/02` | 2026-10-23 |
| CHG-007 | Service charges | Bilingual print | WORKING | P2 | Yes | `charge-print.spec.ts` (5): whole charge, single line by index and by id, draft watermark; `Print All` order statement reuses the same builder | 2026-10-23 |
| FIN-001 | Finance | Chart of accounts (hierarchy, postable flag) | WORKING | P0 | Yes | `test_posting_rules.py` account tests; chart-of-accounts pages | 2026-10-23 |
| FIN-002 | Finance | Financial accounts (cash/bank/wallet) | WORKING | P1 | Yes | `test_api_completeness.py` admin detail/delete; financial-accounts pages | 2026-10-23 |
| FIN-003 | Finance | Accounting periods, closure and posting block | WORKING | P0 | Yes | `test_record_status.py::test_a_closed_period_blocks_posting_and_reopening_restores_it` | 2026-10-23 |
| FIN-004 | Finance | Document sequences by type and year | WORKING | P0 | Yes | `test_setup.py`; `tests/sequence-allocation.spec.ts` | 2026-10-23 |
| FIN-005 | Finance | Financial documents and all document types | WORKING | P0 | Yes | `test_financial_documents_module.py` (11) | 2026-10-23 |
| FIN-006 | Finance | Posting rule resolution, priority, ambiguity | WORKING | P0 | Yes | `test_posting_rules.py` (37) | 2026-10-23 |
| FIN-007 | Finance | Atomic balanced posting | WORKING | P0 | Yes | `test_posting_rules.py`; `test_financial_documents_module.py` | 2026-10-23 |
| FIN-008 | Finance | Reversal instead of edit/delete | WORKING | P0 | Yes | `test_workflows.py::test_document_reversal`; `test_posting_rules.py` | 2026-10-23 |
| FIN-009 | Finance | Payment allocation, partial payment, limits, FX difference | WORKING | P0 | Yes | `test_workflows.py`; `test_multi_currency.py` allocation test | 2026-10-23 |
| FIN-010 | Finance | Manual journal entries | WORKING | P1 | Yes | `test_finance_automation.py::test_manual_journal_rejects_two_sided_and_negative_lines` | 2026-10-23 |
| FIN-011 | Finance | Multi-currency posting with rate snapshot | WORKING | P0 | Yes | `test_multi_currency.py` (13) | 2026-10-23 |
| FIN-012 | Finance | PostgreSQL immutability/balance/allocation triggers | PARTIAL | P0 | No | `backend/tests/sql/integrity_guards.sql` exists; not run in CI; SQLite tests cannot exercise triggers (`docs/10` §6-§7) | docs |
| FIN-013 | Finance | Cross-currency allocation | MISSING | P2 | No | `docs/11` §18 — accepted limitation, needs reviewed FX design | docs |
| FIN-014 | Finance | Automated reconciliation | MISSING | P2 | No | `docs/10` §7 — reconciliation queries are manual, F6 open | docs |
| FIN-015 | Finance | Document tabs: lines, allocation, journal, traceability | WORKING | P1 | Yes | `financial-documents.spec.ts`; `job-finance.spec.ts` | 2026-10-23 |
| FIN-016 | Finance | Exact decimal API serialization | NEEDS_IMPROVEMENT | P2 | No | `finance/service.py:485-494` returns `float`; `core/serialization.py` `jsonable()` is unused | 2026-10-23 |
| REP-001 | Reports | Dashboard KPIs and charts | WORKING | P0 | Yes | `test_reports_dashboard.py` (2); `dashboard.spec.ts` | 2026-10-23 |
| REP-002 | Reports | Service order register and status | UNVERIFIED | P1 | No | Column contract tested (`operations-reports.spec.ts`); row values still unasserted | 2026-10-23 |
| REP-003 | Reports | Container register | WORKING | P2 | Yes | `test_reporting_values.py::test_container_register_*` | 2026-10-23 |
| REP-004 | Reports | Profitability (operational) | UNVERIFIED | P1 | No | Column contract tested (`operations-reports.spec.ts`); `/profitability` row values still unasserted | docs |
| REP-005 | Reports | Quotation performance | UNVERIFIED | P2 | No | Endpoint exists; no assertion test | docs |
| REP-006 | Reports | Trial balance | WORKING | P0 | Yes | `test_report_accounting.py` (13 independent-fixture assertions); `test_report_generation.py` (14); browser `e2e/reports-generate.spec.ts` (7) | 2026-10-27 |
| REP-007 | Reports | Profit & loss, balance sheet, cash flow | WORKING | P0 | Yes | Three `test_reporting_values.py` tests | 2026-10-23 |
| REP-008 | Reports | Receivables, payables, revenue and expense | WORKING | P0 | Yes | `test_workflows.py::test_payment_allocation_and_receivables`; P&L tests | 2026-10-23 |
| REP-009 | Reports | General ledger lines and financial summary | WORKING | P1 | Yes | `test_report_accounting.py` (opening/running balances, cross-account partition, voucher filters); `test_report_generation.py`; browser `e2e/reports-generate.spec.ts` | 2026-10-27 |
| REP-010 | Reports | Filters and CSV export | WORKING | P2 | Yes | Generate-on-demand filters are server-applied (`report-generation.spec.ts`, 8); full-result CSV export verified by `test_report_export.py` (9) and by a real browser download whose totals reconcile | 2026-10-27 |
| ADM-001 | Administration | Application info and branding | WORKING | P1 | Yes | `test_api_completeness.py::test_settings_app_info_and_app_config_roundtrip` | 2026-10-23 |
| ADM-002 | Administration | App configuration incl. email/Telegram test send | PARTIAL | P1 | No | Security lifetime settings validated in 26 passing auth tests; existing channel delivery limitations remain (`docs/10`) | 2026-10-24 |
| ADM-003 | Administration | Reset application data | WORKING | P1 | Conditional | `test_setup.py`; typed `RESET` confirmation in `settings/router.py` | 2026-10-23 |
| ADM-004 | Administration | Global search and ask | WORKING | P1 | Yes | `test_api_completeness.py::test_search_finds_business_party_and_answers`; layout search UI | 2026-10-23 |
| ADM-005 | Administration | Audit log viewer and filtering | WORKING | P1 | Yes | `tests/audit-logs.spec.ts` (5): newest-first list, pagination meta, entity/event filters, read-only status-policy gate, identifier formatting; `test_audit_logs.py` (5): API sort/page/filters, 403 without `audit_log.read`, no status policy for auditLogs; page opens without the 404 probe | 2026-10-24 |
| ADM-006 | Administration | Archive / recycle bin | WORKING | P1 | Yes | `test_archive.py` (9) | 2026-10-23 |
| ADM-007 | Administration | Localization settings (languages, formats) | WORKING | P1 | Yes | `test_localization_settings.py` (10); `pnpm i18n:check` | 2026-10-23 |
| ADM-008 | Administration | Audit trail for posting, roles, status, archive | WORKING | P0 | Yes | `test_posting_rules.py` audit tests; `test_record_status.py`; `test_archive.py` | 2026-10-23 |
| BAK-001 | Backup & restore | Manual Google Sheets backup | WORKING | P1 | Yes | `test_backup.py` (13); `backup-settings.spec.ts`; settings UI | 2026-10-23 |
| BAK-002 | Backup & restore | Scheduled in-process backup | WORKING | P1 | Conditional | `test_backup.py::test_scheduler_due_logic`; asyncio scheduler; no external monitor | 2026-10-23 |
| BAK-003 | Backup & restore | Restore from Sheets with typed confirmation | WORKING | P1 | Conditional | `test_backup.py::test_restore_*`; never exercised against PostgreSQL | 2026-10-23 |
| BAK-004 | Backup & restore | R2 object-storage mirror | WORKING | P2 | Conditional | R2 tests in `test_backup.py` (5) | 2026-10-23 |
| BAK-005 | Backup & restore | Off-host PostgreSQL backup and WAL archiving | PARTIAL | P0 | No | `docs/11` §11: pre-deploy dump only; off-host scheduling and WAL not automated | docs |
| BAK-006 | Backup & restore | Executed restore drill | UNVERIFIED | P0 | No | Procedure documented (`docs/11` §12); not executed in this audit | docs |
| PLAT-001 | Platform | API envelope, pagination, consistent errors | WORKING | P0 | Yes | `test_request_schemas.py` (15); `test_write_validation.py` (12) | 2026-10-23 |
| PLAT-002 | Platform | Health endpoints | WORKING | P0 | Yes | Live `/health` and `/api/v1/health` returned 200 | 2026-10-23 |
| PLAT-003 | Platform | OpenAPI contract exposure | WORKING | P2 | Yes | Live `/openapi.json` served 207 paths | 2026-10-23 |
| PLAT-004 | Platform | Schema DDL docs and drift check | WORKING | P0 | Yes | `uv run pytest tests/test_schema_docs.py tests/test_migration_chain.py -q --disable-warnings`: 29 passed; generated reference documents 70 model tables | 2026-10-24 |
| PLAT-005 | Platform | Linear Alembic chain with downgrades | WORKING | P0 | Conditional | `test_migration_chain.py` in 83-test passing run; `24ac57ef90bd` upgrade/downgrade/re-upgrade and row preservation in disposable `test_auth_postgres.py`: 1 passed | 2026-10-24 |
| PLAT-006 | Platform | Docker Compose stack | WORKING | P0 | Conditional | 5 containers healthy; image built before latest edits | 2026-10-23 |
| PLAT-007 | Platform | CI gate coverage | NEEDS_IMPROVEMENT | P0 | No | `dev-ci.yml` runs pytest/ruff/bandit/pip-audit/lint/typecheck/test/secrets/docker; no E2E, no PostgreSQL guards | 2026-10-23 |
| PLAT-008 | Platform | Production deploy and rollback | UNVERIFIED | P0 | No | `production.yml` + `docs/11` §13-§15 documented; not exercised in this audit | docs |
| PLAT-009 | Platform | Monitoring and alerting | MISSING | P0 | No | `docs/11` §14: no monitoring stack deployed | docs |
| PLAT-010 | Platform | Dependency and secret scanning | WORKING | P1 | Yes | `dev-ci.yml` bandit, pip-audit, pnpm audit, secret scan | 2026-10-23 |
| PLAT-011 | Platform | Multilingual UI (English/Khmer/Chinese) | WORKING | P1 | Yes | `pnpm i18n:check` passed, 3148 keys each | 2026-10-23 |
| PLAT-012 | Platform | Translation completeness | NEEDS_IMPROVEMENT | P2 | No | `pnpm i18n:check` reports 52 Khmer values identical to English | 2026-10-23 |
| PLAT-013 | Platform | Browser end-to-end coverage | PARTIAL | P1 | No | Isolated `pnpm exec playwright test e2e/auth-renewal.spec.ts --workers=1 --reporter=list`: 4 passed; normal smoke suite read-only; no authenticated CI gate | 2026-10-24 |
| PLAT-014 | Platform | Accessibility and responsive verification | UNVERIFIED | P2 | No | No automated a11y or viewport test; `docs/10` §7 | docs |
| PLAT-015 | Platform | Data import (CSV/XLSX) | PARTIAL | P2 | Yes | Master Data reference import is WORKING via `PLAT-006` (12 modules, .xlsx only). Service orders, configuration, finance setup, finance documents and report imports (Phases C–F) are not registered. No CSV support. | 2026-10-24 |
| PLAT-016 | Platform | CSV export | PARTIAL | P2 | No | Client-side export in `ReportsView.vue` and dashboard only; untested | 2026-10-23 |
| PLAT-017 | Platform | Redis cache, locks and integration | WORKING | P1 | Conditional | `test_redis_integration.py` (17); live Redis healthy | 2026-10-23 |
| PLAT-018 | Platform | Unsaved-changes guard on navigation | MISSING | P2 | No | `docs/10` §7: a dirty form can be lost | docs |
| PLAT-019 | Platform | Secret/key hygiene | NEEDS_IMPROVEMENT | P0 | No | `docs/lcssystem.pem` untracked but inside the working tree (`docs/11` §18, S1) | 2026-10-23 |

---

## Detailed Module Assessments

### 1. Authentication and users

- **Business purpose:** prove identity, protect every entry point, and let administrators manage accounts safely.
- **Expected behaviour:** login by username/email, rotating sessions, reset/change password, lockout, rate limits,
  disable users, revoke sessions, one protected administrator that cannot be removed.
- **Current implementation:** `backend/app/modules/auth/` (router, service, repository, schemas, models) plus
  `core/security.py`, `core/deps.py`, `core/locks.py`, `core/rate_limit.py`; six auth pages and the auth store.
- **Verified:** login, refresh rotation, remember-me, logout/revocation, reset codes, forced password change,
  lockout, throttling, user lifecycle, avatar, password policy, no-relogin permission refresh.
- **Missing / defects:** MFA is absent (`AUTH-014`); account deletion is broken on PostgreSQL (`AUTH-012`).
- **Improvement opportunities:** move the audit FK to `ON DELETE SET NULL` and test the deletion of a user with
  audit history on PostgreSQL; add MFA for privileged roles.
- **Frontend evidence:** `app/pages/auth/*`, `app/stores/auth.ts`, `app/middleware/*`.
- **Backend evidence:** `app/modules/auth/*`, `core/deps.py`, `core/security.py`.
- **Database evidence:** `users`, `user_credentials`, stable `user_sessions`, consumed `used_refresh_tokens`, `casbin_rule`, `audit_events`.
- **2026-10-24 verification:** 26 auth tests passed; disposable PostgreSQL rotation/replay/schema/rollback test passed; frontend auth/API tests (17) passed. Full backend rerun: `uv run pytest -q --disable-warnings` → 606 passed, 4 optional skips; `pnpm test` → 681 passed; lint/typecheck/i18n passed. Isolated Playwright auth journeys: 4 passed, including a Service Order draft save after silent refresh, reload, cross-tab rotation/logout and genuine idle expiry without losing the draft. Production HTTPS delivery remains a release check. See `docs/10_testing_and_quality.md` for exact commands and broader gate results.
- **Test evidence:** `test_auth_rbac.py`, `test_auth_remember_me.py`, `test_password_reset.py`,
  `test_lockout_policy.py`, `test_rate_limit.py`, `test_setup.py`; Vitest session/remember-me/password specs.
- **Security considerations:** tokens are HttpOnly-capable and rotated; denial paths are tested; the deletion bug
  is a data-lifecycle and operability risk rather than an auth bypass.
- **Dependencies:** PostgreSQL is authoritative for session rotation/revocation; existing optional Redis infrastructure still supports caching/rate limiting, and audit records security events.
- **Recommended next action:** fix `AUTH-012` first; it is small and removes a support dead end.

### 2. Roles and permissions (RBAC)

- **Business purpose:** least-privilege access for seven role templates without a per-tenant scope.
- **Expected behaviour:** multiple roles per user, role inheritance without cycles, page grants compiled into API
  capabilities at save time, protected super administrator, audited role changes, no privilege escalation,
  default deny, fail closed when the policy store is unreadable.
- **Current implementation:** PyCasbin over the `casbin_rule` table
  (`backend/app/core/authorization/`: `model.conf`, `models.py`, `service.py`); catalog, matrix pages, page→capability
  grants and the seven seeded roles in `core/permissions.py`; enforcement through
  `core/deps.py::require_permission`/`require_any_permission` and `RequestContext.has_permission`; administration
  endpoints in `modules/auth/`; matrix UI in `AppRolePermissionMatrix.vue` fed by `/permissions/catalog`.
- **Verified (2026-10-27):** `tests/test_role_permissions.py` (12 passed) and `tests/test_auth_rbac.py` (15 passed)
  cover the catalog, the page→capability compile (including the no-over-grant rules), policy persistence, inheritance
  and cycle refusal, deny-by-default with the `AUTHORIZATION_DENIED` row, escalation guards and revocation without
  re-login. Compose stack: Alembic upgrade → downgrade → upgrade, startup, seven roles (ADMIN 283, ACCOUNTANT 110,
  MANAGER 97, SALES 48, VIEWER 44, OPERATIONS 39, `SUPER_ADMIN` `*`), `VIEWER` login (33 page + 12 capability codes),
  `/users` 403, `/permissions/catalog` 403, `/quotations` 200. Frontend `lint`, `typecheck`, `test` (743 passed) and
  `i18n:check` pass; the SPA builds (`pnpm generate`).
- **Missing / defects:** the browser matrix was not exercised, and a grant written by an *older* compiler keeps its old
  capabilities until the role is saved again or `scripts/rebuild_role_permissions.py --apply` is run (documented in
  `docs/09` §9.1). Redis-unavailable reload and fail-closed behaviour were verified in an isolated probe, not on the
  compose stack.
- **Improvement opportunities:** a PostgreSQL rehearsal of the policy migration, and a browser pass over the matrix.
- **Frontend evidence:** `administration/roles/*`, `administration/users/*`, `components/common/AppRolePermissionMatrix.vue`,
  `composables/common/useRolePermissionCatalog.ts`, `utils/role/permissions.ts`.
- **Backend evidence:** `core/authorization/*`, `core/permissions.py`, `core/deps.py`, `core/context.py`,
  `auth/service.py` (role/user methods), `api/v1/router.py`.
- **Database evidence:** `roles`, `permissions`, `casbin_rule`.
- **Security considerations:** the denial path is enforced and audited at the API, not hidden in the UI; the protected
  super administrator is enforced by policy and identity, not by display name; policy-load failure denies rather than
  serving a stale copy.
- **Dependencies:** users table, audit, optional Redis (policy version broadcast; the reload interval is the fallback).
- **Recommended next action:** a browser pass over the role matrix; the route-inventory gate now protects new endpoints.

### 3. Master data

- **Business purpose:** keep the reference vocabulary that documents and finance depend on consistent.
- **Expected behaviour:** CRUD for 12 reference collections, active/inactive status, delete guards, option lists
  that exclude inactive records, seeded roles that administrators can extend.
- **Current implementation:** generic `SPECS` registry and handler registration in `master_data/router.py` +
  `service.py`, with dedicated `route_stops.py`, `currency_rates.py`, `status_*`; 14 pages under
  `master-data/` (including asset identity types and capacity units).
- **Verified:** party roles, place roles, container types, transport assets (26-test suite covering identity
  patterns, vocabulary changes, capacity pairing), status policy, delete guards, currencies and FX.
- **Missing / partial:** currency rates have no screen (`MASTER-010`); customs credential retrieval is not wired
  (`MASTER-013`); legacy generic collections have APIs but no pages (`MASTER-014`).
- **Improvement opportunities:** add a read-only currency-rate list to the Currencies screen; decide whether
  shipments/customs/documents/deliveries collections stay (they duplicate service-order concepts) or are removed.
- **Frontend evidence:** `pages/master-data/**`, `config/lcs-reference-modules.ts`, `components/freight/DynamicDataTable.vue`.
- **Backend evidence:** `modules/master_data/{router,service,repository,models,schemas}.py`, `status_service.py`.
- **Database evidence:** `business_parties`, `party_roles`, `business_party_roles`, `place_roles`,
  `trade_directions`, `container_types`, `transport_types`, `transport_assets`, `transport_asset_identity_types`,
  `capacity_units`, `fee_types`, `currencies`, `currency_rates`.
- **Test evidence:** `test_party_roles.py`, `test_place_roles.py`, `test_container_types.py`,
  `test_transport_assets.py`, `test_currencies_and_fx.py`, `test_record_status.py`, `test_deletion_policy.py`.
- **Security considerations:** reference writes require permission; customs credentials are encrypted and
  redacted from ordinary responses; retrieval has no audited workflow yet.
- **Dependencies:** document modules (quotations, orders, charges), finance posting.
- **Recommended next action:** close `MASTER-010` (UI) and `MASTER-013` (credential retrieval or remove the
  dead permission/table path).

### 4. Dynamic configuration (component tabs and versions)

- **Business purpose:** let administrators change the Service Order form without code, safely and reversibly.
- **Expected behaviour:** attributes with types/rules, groups, tabs, trade-direction filtering, published
  snapshots, activation/rollback, historical orders rendering the version they used.
- **Current implementation:** `component_config.py`, `component_tabs.py`, `config_versions.py`,
  `config_snapshot.py`, `config_compare.py`; four configuration pages plus the document renderers.
- **Verified:** 20 attribute-catalog tests, 11 layout tests, 9 lifecycle tests, 3 compare tests, 8 version tests.
- **Missing / defects:** `/ui-schemas/{page}` is untested (`CFG-007`); reordering lacks a keyboard-only path
  (`CFG-008`).
- **Live-data finding (2026-10-23):** the running database has zero `component_group_attributes` rows for the
  `cargo-information` and `transport-information` groups, and the published snapshot records the same empty
  `attributes` arrays. The "No columns configured" state is therefore accurate configuration, not a renderer or
  direction-filter defect; the fix is for an administrator to attach attributes, then publish a new version.
  Historical orders keep rendering their pinned snapshot by design.
- **Improvement opportunities:** the snapshot validator is a 67-complexity function; split it into per-section
  validators before adding more field types.
- **Frontend evidence:** `pages/configuration/**`, `components/document/AppDynamic*`, `Dynamic*Renderer`.
- **Backend evidence:** `modules/master_data/component_config.py`, `component_tabs.py`, `config_*.py`.
- **Database evidence:** `component_attribute_catalog`, `component_groups`, `component_group_attributes`,
  `component_tabs`, `component_tab_groups`, `configuration_versions`, `service_order_component_*`.
- **Test evidence:** `test_component_attributes.py`, `test_component_layouts.py`, `test_config_versions.py`,
  `test_config_version_lifecycle.py`, `test_config_compare.py`; six Vitest configuration specs.
- **Security considerations:** publishing is stricter than editing (`service_order_config.publish`), versions are
  immutable once published, and activation is audited with a reason for rollback.
- **Dependencies:** master data (trade directions), service orders.
- **Recommended next action:** verify `CFG-007` with a focused test, then leave the module alone.

### 5. Quotations

- **Business purpose:** price a shipment, negotiate revisions, and convert an accepted offer into an order.
- **Expected behaviour:** draft/sent/immutable revisions, server-authoritative totals, route validation,
  accept/reject/cancel, explicit idempotent conversion, history and print.
- **Current implementation:** full lifecycle in `modules/quotations/`, pages `quotations/{index,new,[id]}`, shared
  line tables and document tabs, bilingual print.
- **Verified:** 31 quotation tests and 7 revision tests cover party/direction/date rules, route roles, totals,
  container persistence, delete guard, send/accept/reject/cancel, conversion twice, revision numbering under
  concurrency, and the refusal to convert a draft. Four re-quotation tests cover the copy, the untouched order,
  an unknown order and the permission denial; one conversion replay test covers `Idempotency-Key`. Three
  PostgreSQL-only tests cover two simultaneous conversions (one order, one `409`), same-key retries (one order)
  and `ON DELETE SET NULL` for the re-quotation link.
- **Missing / defects:** no compare UI (`QUOT-012`). A re-quotation never updates the originating order's
  pricing — that stays a manual decision.
- **Improvement opportunities:** compare UI is a small read-only screen over an existing endpoint.
- **Frontend evidence:** `pages/quotations/**`, `utils/freight/document-tabs.ts`, `utils/freight/quotation-actions.ts`,
  `quotation-*.spec.ts` (4 files).
- **Backend evidence:** `modules/quotations/{router,service,repository,schemas,models}.py`.
- **Database evidence:** `quotations` (incl. `source_service_order_id`), `quotation_revisions`,
  `quotation_revision_containers`, `quotation_revision_places`, `quotation_revision_lines`,
  `quotation_conversions`.
- **Test evidence:** `test_quotations.py` (31), `test_quotation_versions.py` (7), `test_quotation_postgres.py` (3,
  PostgreSQL only), `test_workflows.py`.
- **Security considerations:** permissions are page-mapped; a converted quotation cannot be deleted; a sent
  revision cannot be edited.
- **Dependencies:** business parties, trade directions, place roles, transport types, fee types, attachments.
- **Recommended next action:** ship the compare UI and add the missing container-requirement test.

### 6. Service orders

- **Business purpose:** the operational record that carries containers, dynamic components, charges and finance.
- **Expected behaviour:** ACTIVE/INACTIVE lifecycle, snapshots from the source revision, unique containers,
  validated weights, dynamic tabs, attachments, finish action, one idempotent invoice.
- **Current implementation:** `modules/operations/` with `component_tabs.py` and `reference_options.py`; pages
  `service-orders/**` using `DocumentView`, `JobDetail`, `JobContainers`, `JobCharges`, `JobFinance`, `JobFiles`.
- **Verified:** creation from quotation, component/container round trip, inactive-order edit refusal, finish,
  attachments, invoice idempotency, print.
- **Missing / defects:** movements and milestones are API-only (`ORDER-007/008`); weight validation exists but is
  untested (`ORDER-005`).
- **Improvement opportunities:** add a compact itinerary/milestone panel to the order detail — the API is already
  done and tested, so this is UI-only work.
- **Frontend evidence:** `pages/service-orders/**`, `components/freight/Job*.vue`, `components/document/AppComponentTabs.vue`.
- **Backend evidence:** `modules/operations/{router,service,repository,component_tabs}.py`.
- **Database evidence:** `service_orders`, `service_order_containers`, `service_order_movements`,
  `service_order_milestones`, `service_order_components`, `service_charge` tables, `attachments`.
- **Test evidence:** `test_workflows.py` (15), `test_movements_and_milestones.py` (10), `test_attachments.py`,
  nine Vitest job specs.
- **Security considerations:** inactive orders reject operational edits; attachments are permission-gated and
  checksum-tracked; no authenticated E2E proves the page wiring.
- **Dependencies:** quotations, configuration versions, attachments, finance.
- **Recommended next action:** weigh a small itinerary UI; otherwise add the missing weight test.

### 7. Service charges

- **Business purpose:** present operational charges to the customer and hand them to finance when billing starts.
- **Expected behaviour:** charge under an order, fee lines, totals/tax, issue without accounting, explicit
  idempotent conversion into one draft invoice, print.
- **Current implementation:** charge endpoints inside `operations/` and dedicated pages `service-charges/**`.
- **Verified:** create/edit/issue, immutability after issue, tax round trip, no journal on issue, one draft
  invoice on repeat conversion, print.
- **Missing / defects:** none found.
- **Improvement opportunities:** the charge list and order charges overlap; confirm one navigation entry is
  enough for users.
- **Frontend evidence:** `pages/service-charges/**`, `components/freight/JobCharges.vue`, `charge-print.spec.ts`.
- **Backend evidence:** `operations/service.py` (`issue_charge`, `charge_to_invoice`), `finance/service.py`
  (`create_invoice_from_charge`).
- **Database evidence:** `service_charges`, `service_charge_lines`, `financial_documents` (draft).
- **Test evidence:** `test_charge_tax_round_trip.py` (6), `test_finance_automation.py` (4), `test_workflows.py`.
- **Security considerations:** issue and conversion are separate permissions; conversion never posts.
- **Dependencies:** service orders, fee types, containers, financial documents.
- **Recommended next action:** no work; keep the tax round-trip test as a guard.

### 8. Finance and accounting

- **Business purpose:** double-entry books that reconcile, with immutable posted history and auditable periods.
- **Expected behaviour:** chart of accounts, financial accounts, periods, sequences, documents, rule-driven
  posting, balanced and atomic journals, reversal, allocation, multi-currency snapshots, manual journals.
- **Current implementation:** `modules/finance/` split into `posting.py` (journal construction strategies),
  `posting_rules.py` (rule resolution), `service.py`, `repository.py`; five finance page groups.
- **Verified:** 37 posting-rule tests, 11 document-module tests, 13 multi-currency tests, reversal, allocation,
  period blocking, sequence allocation, trial balance/P&L/balance sheet/cash flow.
- **Missing / defects:** PostgreSQL triggers are unverified in CI (`FIN-012`); cross-currency allocation and
  automated reconciliation are missing (`FIN-013/014`); API amounts are serialized as `float` (`FIN-016`).
- **Improvement opportunities:** move `tests/sql/integrity_guards.sql` into a nightly PostgreSQL CI job; return
  money as strings or fixed-scale decimals; split `restore_from_sheets` (complexity 79) before extending it.
- **Frontend evidence:** `pages/finance/**`, `document/DocumentView.vue`, `job/JobFinance.vue`,
  `financial-documents.spec.ts`, `job-finance.spec.ts`.
- **Backend evidence:** `modules/finance/{posting,posting_rules,service,repository,router,schemas,models}.py`,
  `core/fx.py`, `core/sequences.py`.
- **Database evidence:** `chart_of_accounts`, `financial_accounts`, `accounting_periods`, `document_sequences`,
  `posting_rules`, `financial_documents`, `financial_document_lines`, `financial_document_postings`,
  `journal_entries`, `journal_entry_lines`, `payment_allocations`, reporting views.
- **Test evidence:** `test_posting_rules.py` (37), `test_financial_documents_module.py` (11),
  `test_multi_currency.py` (13), `test_reporting_values.py` (10), `test_workflows.py`, `test_posting_rules`.
- **Security considerations:** posted history is immutable at the service layer; triggers are the PostgreSQL
  backstop but are not executed in the default suite; allocations are guarded by uniqueness and service checks.
- **Dependencies:** service charges, orders, business parties, currencies, posting rules.
- **Recommended next action:** PostgreSQL guard CI is the highest-value engineering task in the project.

### 9. Reports and dashboard

- **Business purpose:** give operations and finance a read-only, posted-data view for decisions and reconciliation.
- **Expected behaviour:** 12 catalogued reports, filters by party/status/currency/date, statements reconcile,
  permissions per report area, and no report data on page load.
- **Current implementation:** `modules/reports/` (service + repository + on-demand generation engine:
  `engine.py`, `ledger_reports.py`, `schemas.py`, `csv_export.py`), `config/freight-reports.ts` (12 definitions),
  `ReportsView.vue`, `utils/freight/report-request.ts`, dashboard components.
- **Verified:** dashboard KPIs, trial balance, P&L, balance sheet, cash flow, container register, receivables via
  allocation tests; generated Trial Balance and General Ledger via `test_report_accounting.py` (13, independent
  fixed-date fixtures) and `test_report_generation.py` (14); full-result CSV export via `test_report_export.py` (9);
  the browser journeys in `e2e/reports-generate.spec.ts` (7) on a disposable compose stack, including the download.
- **Performance:** measured, not assumed — see `docs/10` §8 (200,000 ledger lines: Trial Balance 72–87 ms, General
  Ledger page 43 ms with an account filter and 474 ms unfiltered over 101,470 rows, exports 0.17 s / 3.69 s). No
  index was added because the plans do not support one; the next lever is a narrower window sort.
- **Missing / defects:** service-order register/status, profitability and quotation performance still have no direct
  row assertion (`REP-002/004/005`); the four statement reports still request the whole ledger
  (`/reports/ledger-lines`) instead of a paginated engine report; export is CSV only.
- **Improvement opportunities:** add one assertion per remaining endpoint; move the statements onto the engine; trim
  the window's projected columns to speed up an unfiltered ledger page.
- **Frontend evidence:** `pages/reports/**`, `config/freight-reports.ts`, `components/freight/ReportsView.vue`,
  `utils/freight/report-request.ts`, `utils/export/csv.ts`, `components/dashboard/**`, `report-access.spec.ts`,
  `report-generation.spec.ts`, `e2e/reports-generate.spec.ts`.
- **Backend evidence:** `modules/reports/{router,service,repository,engine,ledger_reports,schemas,csv_export}.py`,
  `core/pagination.py`, `scripts/verify_report_performance.py`.
- **Database evidence:** reporting views (`vw_*`), journal and document tables; reports read posted data only, and
  the generated reports read the same posted-ledger projection as the statements.
- **Test evidence:** `test_reports_dashboard.py` (2), `test_reporting_values.py` (10), `test_report_generation.py`
  (14), `test_report_accounting.py` (13), `test_report_export.py` (9), `test_workflows.py`, browser 7.
- **Security considerations:** each endpoint maps to a report page code plus `report.read`; the engine re-checks the
  registry permission before a byte is streamed; filters are parameterised server-side; period, account, party,
  voucher and currency filters never widen the posted-only scope; no report writes data; exported text cells are
  neutralised against spreadsheet formula injection.
- **Dependencies:** finance posting, service orders.
- **Recommended next action:** add the three missing endpoint assertions and move the statements onto the engine.

### 10. Administration, audit and archive

- **Business purpose:** operate the installation: settings, users, sequences, audit trail, recovery of deleted
  records, and global search.
- **Expected behaviour:** configurable localization/branding/email/Telegram, searchable audit events, archived
  records restorable, guarded hard delete, typed confirmations for destructive actions.
- **Current implementation:** `modules/settings/`, `audit/`, `archive/`; pages `administration/**`; settings tabs
  include backup and restore.
- **Verified:** app info/config round-trip, reset data confirmation, search/ask, archive/restore/hard delete,
  localization (10 tests), audit writes for posting/roles/status/archive.
- **Missing / defects:** audit-log filtering is untested (`ADM-005`); email/Telegram test-send is untested
  (`ADM-002`); import covers Master Data only (`PLAT-006`), not configuration or finance (`PLAT-015`).
- **Improvement opportunities:** one backend test for audit filters (actor/event/entity/result/date) would turn
  `ADM-005` green; validate the email/Telegram endpoints with a mocked transport.
- **Frontend evidence:** `pages/administration/**`, `components/document/SystemSettingsPage.vue`,
  `audit-logs.spec.ts`, `backup-settings.spec.ts`, `localization-composable.spec.ts`.
- **Backend evidence:** `modules/settings/*`, `modules/audit/*`, `modules/archive/*`.
- **Database evidence:** `app_settings`, `audit_events`, `archive_records`, `document_sequences`.
- **Test evidence:** `test_api_completeness.py`, `test_archive.py`, `test_localization_settings.py`,
  `test_record_status.py`.
- **Security considerations:** audit payloads must never include secrets (tested for backup config); hard delete
  requires a permission and reference checks; reset/restore require typed confirmation.
- **Dependencies:** every module emits audit events.
- **Recommended next action:** close the audit-filter and email/Telegram verification gaps.

- **2026-10-24 security verification:** access-token, idle and absolute lifetimes use the existing Security form and backend validation. The 26-test auth command in `docs/10` passed; other administration feature statuses are unchanged.

### 11. Backup and restore

- **Business purpose:** survive accidental data loss and satisfy recovery expectations.
- **Expected behaviour:** scheduled/manual Sheets mirror, R2 snapshot, restore with explicit confirmation,
  documented and drilled PostgreSQL backup.
- **Current implementation:** `modules/backup/` (service, sheets client, scheduler, repository, router); settings
  UI tab; production workflow takes a pre-deploy dump.
- **Verified:** backup idempotency (insert/update, no duplicates), restore recreates rows, confirmation required,
  R2 upload/connection, permission denial, scheduler due logic.
- **Missing / defects:** the Sheets mirror is not a database backup; off-host PostgreSQL backup/WAL is not
  automated (`BAK-005`); no restore drill was executed (`BAK-006`).
- **Improvement opportunities:** encrypted `pg_dump` to a separate account on a schedule, plus a quarterly restore
  drill with recorded evidence.
- **Frontend evidence:** `SystemSettingsPage.vue`, `backup-settings.spec.ts`.
- **Backend evidence:** `modules/backup/{service,scheduler,sheets,repository,router}.py`.
- **Database evidence:** `backup_runs`, `backup_logs` (excluded from export), audit.
- **Test evidence:** `test_backup.py` (13).
- **Security considerations:** secrets are redacted, restore needs `backup.manage` plus typed confirmation, and
  sensitive columns are never exported.
- **Dependencies:** Google Sheets credentials, optional R2, PostgreSQL.
- **Recommended next action:** automate off-host dumps before the first production release.

### 12. Platform, deployment and quality

- **Business purpose:** make the system installable, observable, upgradeable and safe to operate.
- **Expected behaviour:** container images, migrations on start, TLS, CI gates, versioned releases, rollback,
  monitoring, and a schema reference that never drifts.
- **Current implementation:** `infrastructure/` (compose + nginx), four GitHub workflows,
  generated schema docs, 52 backend test files and 74 frontend specs.
- **Verified:** compose stack healthy, health endpoints, 207 OpenAPI paths, schema docs current (76 tables), linear
  migration chain, frontend/backend gates, dependency and secret scans, CSV export in reports (client-side).
- **Missing / defects:** no monitoring/alerting (`PLAT-009`), no import outside Master Data (`PLAT-015`), no unsaved-changes guard
  (`PLAT-018`), production deploy/rollback unexercised (`PLAT-008`), stale `docs/lcssystem.pem` in the tree
  (`PLAT-019`), 52 untranslated Khmer strings (`PLAT-012`).
- **Improvement opportunities:** add a scheduled PostgreSQL job that runs `tests/sql/integrity_guards.sql`; add
  authenticated Playwright to CI; add a minimal metrics/alert path (5xx, posting failures, backup failures).
- **Frontend evidence:** `nuxt.config.ts`, `scripts/i18n.mjs`, `playwright.config.ts`, `e2e/*.spec.ts`.
- **Backend evidence:** `app/main.py`, `core/config.py`, `alembic/`, `scripts/generate_schema_docs.py`.
- **Database evidence:** 45 Alembic revisions; 76 tables; generated `docs/06_database_design.sql`.
- **Test evidence:** `test_schema_docs.py`, `test_schema_integrity.py`, `test_migration_chain.py`,
  `test_frontend_api_contract.py`, `test_redis_integration.py`; Vitest i18n/navigation/format specs.
- **Security considerations:** dev CI is read-only and never deploys; production is a separate manual workflow;
  the untracked private key is the top hygiene item.
- **Dependencies:** GHCR, EC2 runtime, TLS certificates, PostgreSQL, Redis, MinIO.
- **Recommended next action:** monitoring plus PostgreSQL guard CI, then exercise one rollback end to end.

---

## High-Priority Issues

Ordered by risk, as required.

1. **P0 — Private key inside the working tree.** `docs/lcssystem.pem` is untracked and gitignored but readable by
   any process in the repository. *Action:* move it outside the tree and rotate if exposure is possible. (S1 in
   `docs/11` §18.)
2. **P0 — PostgreSQL integrity guards are not executed by any gate.** The SQLite suite cannot see triggers; a
   trigger regression has already caused a posting outage. *Action:* run `backend/tests/sql/integrity_guards.sql`
   against a disposable PostgreSQL service in CI, nightly and pre-release.
3. **P1 — User deletion is broken on PostgreSQL (`AUTH-012`).** `audit_events.actor_user_id` has no
   `ON DELETE SET NULL`; deleting an audited user violates the FK. *Action:* additive migration with
   `ondelete="SET NULL"`, then a PostgreSQL test that deletes a user with audit history.
4. **P0 — No monitoring or alerting (`PLAT-009`).** Failed postings, lockouts and backup failures are silent.
   *Action:* minimal metrics plus alerts for 5xx, posting failures, auth-failure spikes, backup failures.
5. **P0 — Off-host PostgreSQL backup/restore is not automated (`BAK-005`, `BAK-006`).** The Sheets mirror and the
   pre-deploy dump are not disaster recovery. *Action:* scheduled encrypted dumps to a separate account, then a
   recorded restore drill.
6. **P1 — Movements and milestones are unreachable (`ORDER-007/008`).** Tested APIs, no UI. *Action:* add the
   itinerary/milestone panel to the order detail.
7. **P1 — Quotation revision comparison has no UI (`QUOT-012`).** *Action:* read-only compare screen using the
   existing endpoint.
8. **P1 — Currency-rate maintenance is API-only (`MASTER-010`).** *Action:* expose the rate list in the Currencies
   screen; keep approved-only semantics.
9. **P1 — Audit-log search is unverified (`ADM-005`)** and **three operational reports have no assertion tests
   (`REP-002/004/005`).** *Action:* one focused test each; cheap and removes ambiguity.
10. **P1 — Browser coverage stops at the login form (`PLAT-013`).** *Action:* run the authenticated Playwright
    journey in CI against the compose stack with a dedicated non-production account.
11. **P2 — API returns money as JSON floats (`FIN-016`).** Stored values stay `Decimal`, but clients receive
    binary floats. *Action:* serialize money as strings or fixed-scale decimals; keep tests numeric where they
    already are.
12. **P2 — Translation completeness and accessibility are unverified (`PLAT-012`, `PLAT-014`).** *Action:* fill the
    52 identical Khmer strings and add an automated a11y check on the three core forms.

---

## Production Readiness

Assessed separately from feature status. A feature marked WORKING may still be "Conditional" here when its
verification depends on SQLite-only behaviour, Redis, or an unexercised procedure.

| Area | Verdict | Evidence / reason |
|---|---|---|
| Core business workflows (quotation → order → charge → invoice → posting) | **Ready** | End-to-end path covered by `test_workflows.py`, `test_quotation_versions.py`, `test_finance_automation.py` |
| Authentication and authorization | **Ready with one defect** | 15 RBAC tests plus live 401; `AUTH-012` deletion bug must be fixed |
| Financial integrity | **Conditional** | Service-level invariants tested (37 posting-rule tests); PostgreSQL triggers not in CI (`FIN-012`) |
| Database migrations | **Conditional** | Linear chain, 37 revisions, schema docs current; full downgrade below the previous release is not supported (`docs/11` §18) |
| API integration | **Ready** | 207 paths, contract test, envelope/pagination/validation tests |
| Testing | **Conditional** | 531 backend + 606 frontend pass; one race-induced failure re-ran green; no PostgreSQL guard run, no authenticated E2E |
| Security | **Conditional** | Scans and RBAC are good; private key in tree, no MFA, no malware scan on uploads (`PLAT-019`, `AUTH-014`) |
| Backups and restoration | **Not ready** | Google Sheets mirror ≠ database backup; off-host dumps and drills missing (`BAK-005/006`) |
| Docker deployment | **Ready** | Five healthy containers; health via nginx documented; port exposure limited to frontend |
| Monitoring | **Not ready** | No metrics or alerts deployed (`PLAT-009`) |
| Rollback readiness | **Conditional** | Images are immutable and rollback is documented/automated; the rollback has not been exercised in this audit (`PLAT-008`) |

**Overall verdict: NO-GO for production as of 2026-10-23.** The blockers are operational, not architectural:
secret hygiene, PostgreSQL guard execution, monitoring, off-host backup, and the user-deletion defect. None of
them requires reworking the domain model.

---

## Recommended Development Backlog

| # | Feature ID | Description | Reason | Priority | Dependency | Acceptance criteria |
|---|---|---|---|---|---|---|
| 1 | PLAT-019 | Remove `docs/lcssystem.pem` from the working tree, rotate if needed, document the location | Live private key inside the repo | P0 | Owner decision | File gone; no reference in docs; rotation recorded |
| 2 | FIN-012 | Run `integrity_guards.sql` in a PostgreSQL CI service | Triggers are the financial backstop and are untested | P0 | CI PostgreSQL service | Job fails on a deliberately weakened trigger; passes on `dev` |
| 3 | AUTH-012 | Additive migration: `audit_events.actor_user_id` → `ON DELETE SET NULL` + test | User deletion currently fails on PostgreSQL | P1 | Migration + PostgreSQL test | Delete an audited user on PostgreSQL succeeds; audit row keeps a null actor |
| 4 | PLAT-009 | Minimal monitoring: 5xx rate, posting failures, auth failures, backup failures | Failures are silent today | P0 | Hosting/metrics choice | Alert fires on an induced failure in staging |
| 5 | BAK-005 | Scheduled encrypted `pg_dump` to off-host storage, retention policy | Current backup is not disaster recovery | P0 | Object storage credentials | A restore from the off-host dump recreates a staging database |
| 6 | BAK-006 | Execute and record a restore drill | Untested restore is a promise | P0 | BAK-005 | Drill log with timestamps and row counts in `docs/11` |
| 7 | ORDER-007/008 | Itinerary/milestone panel on the service order | Tested APIs, no user access | P1 | None | Create/edit/delete movement and milestone from the order page; Vitest + Playwright proof |
| 8 | QUOT-012 | Read-only revision compare screen | Endpoint exists; users cannot see differences | P1 | None | Compare two revisions side by side; identical revisions show no change |
| 9 | MASTER-010 | Currency-rate list on the Currencies screen | Rates can only be maintained by API | P1 | None | Approved rates visible and filterable; create/edit gated by permission |
| 10 | ADM-005 / REP-002/004/005 | Add one focused backend test per unverified screen | Removes three UNVERIFIED rows | P1 | None | Each endpoint asserts a known seeded value and a permission denial |
| 11 | PLAT-013 | Authenticated Playwright journey in CI | Login/navigation regressions can reach `dev` | P1 | Dedicated test account | Quotation → order navigation passes headlessly in CI |
| 12 | PLAT-012 / PLAT-014 | Complete 52 Khmer strings; add an a11y check on core forms | Quality and accessibility | P2 | Translation review | `i18n:check` reports 0 identical values; a11y spec passes |
| 13 | FIN-016 | Serialize money as strings/fixed-scale decimals | API precision contract | P2 | Frontend formatters | API contract test asserts exact string amounts; UI unchanged |
| 14 | PLAT-015 | CSV/XLSX import beyond Master Data (service orders, configuration, finance) | Master Data import shipped in Phase A/B (`PLAT-006`); the other domains have no registered module | P2 | Owner priority | Register a module per domain; keep preview, per-row errors and no partial write |

---

## Change History

Record only meaningful status transitions; do not add a row when nothing changed.

| Date | Change | Detail |
|---|---|---|
| 2026-10-28 | RBAC-004 redefined to single-role assignment; RBAC-009 WORKING → MISSING (inheritance removed by design) | Direct RBAC: each user holds exactly one role — request schemas take a single `roleCode` (a `roles`/`role_ids` array is refused with 422), `POST /users/{id}/role-assignments` now **replaces** the previous role, and a partial unique index `uq_casbin_rule_single_user_role` enforces one assignment per user at the database level. Role inheritance was removed: no `parentRoles` payload field, no `/roles/{id}/inheritance` endpoints, the policy loader ignores legacy `role:`→`role:` edges, and the Role Management UI lost the "Inherits from", "Inherited permissions" and "Effective permissions" fields; the Users form now uses a searchable single-select "Assigned Role" dropdown. New tests `test_single_role_rbac.py` (5) cover the constraint, roleless accounts, idempotent saves, audit events and the migration's multi-role conflict report; `test_auth_rbac.py`/`test_role_permissions.py` rewritten for the model. |
| 2026-10-27 | REP-010 NEEDS_IMPROVEMENT → WORKING; report exports and measurement; Casbin wildcard repaired | Trial Balance and General Ledger now export the whole filtered result as a streamed CSV (`POST /reports/<key>/export`, server-side cursor, footer totals equal `/generate`, formula-injection guard, read-only mode allowed). Independent accounting coverage added (`test_report_accounting.py`, 13) with fixed-date fixtures: opening/period/closing columns, debit-credit control, reversal policy, foreign-currency base amounts, four-decimal round-trip, fiscal-year boundaries, same-date ordering, P&L agreement. `test_report_export.py` (9) covers full-result rows, totals reconciliation, column selection, 403, read-only. Browser suite `e2e/reports-generate.spec.ts` (7) ran green on a disposable compose stack, including a downloaded CSV. Performance measured with `scripts/verify_report_performance.py` on 200,000 lines: TB 72–87 ms, GL page 43 ms (one account) / 474 ms (unfiltered 101k rows), exports 0.17 s / 3.69 s; no index added because the plans do not support one. Root cause of the failing working-tree suite fixed: `*` was stored as a two-token policy row, so the protected administrator held nothing; `split_code`/`join_code`/loader repaired and covered by `test_authorization_wildcard.py` (3). Stale test fixtures still naming removed roles (`AUDITOR`, `SALES_OFFICER`) updated to `VIEWER`/`SALES`. Combined working tree: backend **733 passed / 7 skipped**, frontend 91 files / 747 passed, ruff/lint/typecheck/i18n green. |
| 2026-10-27 | REP-009 UNVERIFIED → WORKING; reports generate on demand | Trial Balance and General Ledger moved behind a shared report engine (`engine.py` registry + `ledger_reports.py` calculations + `schemas.py` contracts) and two POST generate endpoints with server pagination; report pages load no rows until Generate and mark results stale on filter changes. `test_report_generation.py` (13) verifies opening/period split, imbalance reporting, draft exclusion, running balances across pages, voucher/account filters, read-only behaviour, 403 and 422; `report-generation.spec.ts` (6) pins the request body and the no-fetch rule. Backend suite 708 passed / 7 skipped on a clean HEAD worktree carrying these files; frontend 91 files / 743 passed, lint/typecheck/i18n green. |
| 2026-10-27 | Authorization engine replaced with Casbin | `role_permissions`/`user_role_assignments` dropped in favour of `casbin_rule`; multi-role, role inheritance, page→capability compile at save time, Redis-synced reload, fail-closed on policy load failure. Follow-up pass: the compile no longer loops capability→page→capability (a configuration viewer no longer inherited configuration write, a settings viewer no longer inherited `backup.manage`), `quotation.convert` and the attachment capabilities are reachable from the document pages, four dead codes (`excel.import/export`, `telegram.manage/view`) were removed (283 codes), the denial audit moved into the request session, and the enforcer reads the published version before the rows. `test_role_permissions.py` (12) and `test_auth_rbac.py` (15) were rewritten for the Casbin model and pass, together with `test_password_reset.py`, `test_repository_queries.py` and `test_migration_chain.py`; RBAC-003 (browser matrix) stays UNVERIFIED. |
| 2026-10-23 | Initial baseline | 138 features: 102 WORKING, 10 PARTIAL, 12 UNVERIFIED, 7 MISSING, 1 BROKEN, 6 NEEDS_IMPROVEMENT, 0 BLOCKED. Backend 531 pass / 1 stale-expectation failure (re-run green), frontend 606 pass, lint/typecheck/i18n/schema/ruff green. |
| 2026-10-23 | QUOT-013 UNVERIFIED → WORKING | `POST /quotations/from-service-order/{identifier}` now copies customer, direction, route, containers and priced lines into a new draft, records `source_service_order_id` (Alembic `c7e8f9a0b1c2`), and is reachable from the service-order header. QUOT-009 evidence extended with the `Idempotency-Key` replay test. Backend `pytest` 538 pass, frontend 609 pass. |
| 2026-10-23 | Verification pass; QUOT-006 UNVERIFIED → WORKING | Backend image rebuilt with `c7e8f9a0b1c2` and restarted against the existing database (`alembic current` = `c7e8f9a0b1c2 (head)`, health `ok`); a clean-database Alembic chain ran up → down → up. PostgreSQL: two concurrent conversions produced one order and one `409 DUPLICATE_CONVERSION`; two same-key retries produced one order; deleting the order nulled the re-quotation link. Container requirements now have a round-trip + child-row test. Backend 540 passed / 3 PostgreSQL-only skipped (no URL), focused 120 passed, ruff clean; browser suite 6 passed / 2 skipped (no credentials). |
| 2026-10-23 | ORDER-004 evidence extended; container/payment UI simplified | Conversion expands quotation requirements into pending `service_order_containers` rows (nullable number, Alembic `d8f9a0b1c2d3`); numbering updates the prepared row and a payment-referenced container cannot be deleted. Container payments are derived per actual container using the pricing line's `containerType`; shipment lines stay single. Service Charge and Finance grids keep review columns with a details/detail-page path. Focused backend 84 passed, frontend 616 passed, typecheck/lint/ruff/schema green. |
| 2026-10-23 | QUOT-011 evidence; ORDER-009 extended; attachment note | Revisions tab now has revision + status + grand total + creator + created + row actions (View only), newest first, with a short revision column; revision comparison UI was removed. Quotation list shows the seven business columns with R01 revisions and linked Service Order numbers; the party column/filter is labelled Business Party. Attachments gain a nullable `note` (Alembic `e9a0b1c2d3e4`) edited directly in the Note cell and saved through `PATCH /attachments/{id}`. Backend `pytest` focused 40 passed, ruff clean, schema docs regenerated (67 tables); frontend tests, lint/typecheck/i18n green. |
| 2026-10-23 | Line adjustments and fee-line printing | Quotation pricing, container payments, service charges and fee lines offer **Additional Details** (discount amount + tax rate) in the row menu; the values stay out of the columns, the server derives the tax (quotation lines now accept `taxRate`), and sheet-level totals fall back to line sums when a line carries an adjustment. Both service-charge tables show Fee Type / Description / Qty / Unit Price / Line Total; each row prints one fee line by stable id and **Print All** prints the whole charge or, on the order tab, a combined order statement. Backend quotation/charge tests and ruff green; frontend 78 files / 630 passed, typecheck/lint/i18n green. |
| 2026-10-23 | List columns | Service Orders list shows SO No. (data key stays `jobNo`), Business Party, Trade Direction, Containers, Quotation, Total Charges, Status and Created At; the list API now returns the source `quotationNo`. Quotation list gains a Created column. Backend `test_workflows.py` 16 passed, ruff clean; focused frontend specs 7 passed, typecheck/lint/i18n green. |
| 2026-10-23 | Service Charges list | Seven columns: SC No. (clickable), SO No. (clickable), Business Party, Grand Total, Invoice No. (links to the finance document when present), Status, Created At. The list mapping falls back to the linked service order's party when the charge carries no free-text company. Filters keep their parameters with SO No. / Business Party labels. Backend `test_workflows.py` 17 passed, ruff clean; focused frontend specs 3 passed, typecheck/lint/i18n green. |
| 2026-10-23 | Bidirectional document links | Quotation list starts Quotation No. → SO No.; Service Order list starts SO No. → Quotation No. Both numbers are links built from API ids (`serviceOrderId`, `quotationId`), not formatted numbers; unlinked rows show `—`. The order list now also returns the source `quotationId`. Backend `test_workflows.py` 17 passed, ruff clean; focused frontend specs 7 passed, typecheck/lint green. |
| 2026-10-23 | Creator attribution | Quotation, Service Order, Service Charge and Financial Document lists end with Created By then Created At. Names resolve from the stored `created_by_user_id` through one batched user query per page; the quotation shows its first revision's author so a later editor cannot replace it. Backend `test_created_by.py` (spoofing, edit immutability, all four lists) passed, ruff clean; frontend 80 files / 636 passed, typecheck/lint/i18n green. Business Parties and generic Master Data store no creator column and have no reliable creation audit event, so they keep no Created By column rather than showing a fabricated value. |
| 2026-10-23 | Operations reports | Register: SO No., Quotation No. (both linked by record id), Business Party, Trade Direction, Containers, Total Charges, Status, Created By, Created At. Status: SO No., Business Party, Trade Direction, Status, Days Open, Pending Components, Last Activity, Created By. Containers: Container No., Type, SO No., Business Party, Seal No., Status, Net/Gross Weight. Profitability: SO No., Business Party, Quoted, Service Charges, Revenue, Cost, Profit, Margin %. Counts format as integers; existing calculations untouched. Frontend 81 files / 641 passed, typecheck/lint/i18n green. |
| 2026-10-23 | Finance tables and reports | Financial documents: Document No., SO No., Type, Business Party, Document Date, Grand Total, Outstanding, Status, Created By, Created At. Financial accounts reordered and their unreliable balance column dropped; journals add SO No., Created By and a clickable Source Document; accounting periods and posting rules already matched. The eight finance reports now use SO No. / Business Party labels with the required columns, and invoice/bill, journal, source document and account codes link by real ids (ledger rows expose `journalId`, `sourceDocumentId`, `accountId`). Backend finance/report tests 15 passed, ruff clean; frontend 82 files / 650 passed, typecheck/lint/i18n green. |
| 2026-10-23 | Administration tables | Users: Username, Full Name, Email, Roles, Status, Last Login, Created By, Created At (creator resolved from the `USER_CREATED` audit event; legacy rows show `—`). Roles: name, description, permission/user counts, status, Created By (from `ROLE_CREATED`), Created At. Audit Logs: Date & Time, User, Action, Module, Record (linked to the record when accessible), Result. Document Sequences: Padding / Next Number labels kept as non-consuming previews. Configuration Versions: Description, Created By (= the publish/rollback actor that created the row), Created At, Published By, Published At. Backend auth/creator tests 33 passed, ruff clean; frontend 83 files / 655 passed, typecheck/lint/i18n green. No standalone Permissions or Login History page exists; audit logs already record login events. |
| 2026-10-23 | Master data lists | The eleven reference lists now end with Created By / Created At and show the compact required column sets (Business Parties, Party Roles, Place Roles, Trade Directions, Container Types, Transport Types, Transport Assets, Asset Identity Types, Capacity Units, Fee Types, Currencies). Creation writes one `MASTER_DATA_CREATED` audit event so new rows resolve their creator in a single batched query; legacy rows show `—`. Reference dropdowns, validation, unique codes and relationship rules untouched. Backend master-data/creator tests 66 passed, ruff clean; frontend 84 files / 657 passed, typecheck/lint/i18n green. |
| 2026-10-23 | Configuration tables | Configuration Versions already shows Version / Description / Status / Created By / Created At / Published By / Published At with the existing Compare/Publish/Rollback rules. The attribute grid now leads with Field Name, Field Key, Data Type, Required, Display Order and Status (read-only order/status), keeping the Choices / Master Data / Rules / Help Text editors and reorder control that the dynamic forms depend on. Tabs and Component Groups are master-detail builders, not list tables, and were left as-is; no separate Components page or configuration audit list exists. Frontend 84 files / 657 passed, typecheck/lint/i18n green. |
| 2026-10-23 | Settings verification | Server-side settings validation added for upload size, security, notification retries, pagination and channel requirements; settings updates now write a `SETTINGS_UPDATED` audit event; email/Telegram test endpoints no longer claim `connected` without a check (they return `not_verified`); system environment/cache/scheduler/version status is read from runtime instead of hardcoded values; unsupported Kanban option removed. Backend settings/localization/backup 36 passed, ruff clean; frontend 84 files / 657 passed, typecheck/lint/i18n green. Full report: `docs/FULL_SYSTEM_VERIFICATION.md`. General/Notifications/System tabs remain unrouted; notification engine and maintenance/read-only enforcement do not exist. |
| 2026-10-23 | Settings enforcement (Phase 1) | Maintenance mode now returns `503 MAINTENANCE_MODE` for ordinary access while login/refresh/logout/me/change-password and the administrator Settings endpoint remain available; read-only mode rejects unsafe methods with `409 READ_ONLY_MODE` and keeps reads; session timeout is enforced as an absolute window on access tokens and refresh rotation; password expiry and the one-shot global require-password-change policy block all routes except the safe change/recovery paths. Existing login-attempt and lock-duration logic untouched. `test_access_enforcement.py` (7) and 78 focused backend tests passed, plus the full suite 560 passed / 3 skipped, ruff clean. PostgreSQL behaviour remains unverified. |
| 2026-10-23 | Service Order Finance tab | The tab is now a manual financial-entry workspace: rows are financial documents linked to the current order (`serviceOrderId`, legacy `jobNo` fallback) and the table shows Type, Date, Description, Business Party, Amount, Status only. Add Entry creates a draft through `POST /financial-documents` for the six supported types (Customer Charge/Receipt, Supplier Expense/Payment, Other Income/Expense) with an active-posting-rule warning; View/Edit Draft/Post/Reverse/Delete and Allocate (posted receipts/payments) use the existing finance services. Service Charges, quotation lines and job `expenses` are no longer projected into the table. Backend manual-entry validation rejects a missing order/party, empty lines and a non-positive total. `test_job_finance_entries.py` (4) and `finance-tab.spec.ts` passed; frontend 85 files / 660 passed, typecheck/lint/i18n green. |
| 2026-10-23 | Document Types master | New administrator-managed `document_types` master (Alembic `f0b1c2d3e4f5`, seeded with the ten canonical accounting behaviours): custom types must reference a canonical behaviour, canonical codes keep their behaviour and cannot be deleted. The Service Order Finance tab and Financial Documents form now take their type options from this master (`availableIn` filtered), and posting rules select canonical behaviours only. A financial document created with `documentTypeId` persists the canonical code as `documentType` and stores `documentTypeId/Code/Name` in its `data` payload echo. Backend `test_document_types.py` (7), full suite green, ruff clean; frontend typecheck/lint/i18n green; `docs/06` regenerated (68 tables). |
| 2026-10-24 | Excel Import & Export (Phase A/B) | Centralized, allowlisted engine (`app/modules/excel_io/`): registry of 12 Master Data modules derived from the master-data specs, backend-driven .xlsx templates (Instructions/Examples/reference sheets with dropdowns for lists ≤ 200), upload → validate → preview (per Excel row + column errors, workbook duplicate detection, reference and business-rule checks through the service pipeline), durable import sessions in PostgreSQL (`import_sessions`) bound to user + checksum + mode + expiry with a single-use atomic claim, single-use atomic commit with commit-time revalidation, downloadable XLSX error report, authorized export (all filtered rows or selected ids, header frozen, auto-filter, formula-injection escape), and `import_jobs` history (Alembic `12ab34cd56ef`). Import/Export actions appear on eligible list pages only with the module's manage permission. Stabilization pass (2026-10-24): the archive guard now reads *uncompressed* sizes (the previous compress-size check could never reject a zip bomb), the Data sheet is streamed instead of materialized so the 2 000-row cap applies before allocation, an oversized declared `Content-Length` is refused before the body is buffered, export escapes a formula prefix hidden behind leading whitespace, and unscoped import history now requires `master.reference.view`. Backend `test_excel_import_export.py` (33) green, ruff clean; frontend typecheck/lint green, 88 files / 679 passed, i18n keys added to all three locales. Phases C–F (service-order operations, configuration, finance setup, finance documents, report exports) are not registered yet. |
| 2026-10-24 | Excel Import & Export (Phase A/B) — browser verification | The compose stack was exercised end to end as a dedicated `PLATFORM_ADMIN` account. Four defects were found and fixed: the dialog only loaded the module catalog inside `show()`, so the disabled Import button could never be clicked (now loads on mount); `exportRows` sent a JSON body without `Content-Type: application/json`, so every export returned `422 VALIDATION_ERROR` (FastAPI read a `text/plain` string); the export header list appended `status` a second time for modules that already export it (duplicate column, broken header/template parity); and `lcs.common.close` was a missing i18n key, rendered literally by the result step (added to all three locales). The import parser also strips the export-time `'` quote so a copied `+855 …` phone number round-trips unchanged. Verified live: template download, CREATE preview/commit, list refresh, CREATE_AND_UPDATE preview/commit, invalid workbook (three field errors, Confirm disabled, no toast), discard confirmation, error-report download, filtered export download. Backend `test_excel_import_export.py` (35), ruff clean; frontend `tests/excel-io.spec.ts` (6). Test party and import jobs removed from the dev database; the temporary browser account keeps its (append-only) audit rows, so it was retired (`INACTIVE`, credentials deleted) rather than dropped. |
| 2026-10-24 | Excel Phase A/B hardening | Import gating: `ImportExportDialog` now also disables the Import trigger without the module's manage permission (`canManageImport`); Export stays view-permission-gated for view-only users, backend 403s unchanged. `scripts/verify_excel_postgres.py` is rerunnable: the default disposable `verify` database is schema-reset and re-migrated at the start of each run (custom `VERIFY_DATABASE_URL` only wiped with `VERIFY_RESET=1`), so reruns no longer fail on leftover rows. Redis `auth` namespace is bumped after permission-catalog sync (`ensure_permission_catalog`) and on `update_app_config`, so security-sensitive changes are no longer subject to the 300s identity-cache TTL. Backend focused: `test_setup.py`+`test_settings_validation.py`+`test_excel_import_export.py` 45 passed, ruff clean; frontend `tests/excel-io.spec.ts` (7) passed. Authenticated browser re-verification not run in this pass (no E2E credentials configured). |
| 2026-10-24 | Document Types soft-delete attribution fix | The Audit Logs page 500'd because its reference fetch of `/documentTypes` crashed on PostgreSQL: the `DocumentType` model carries `SoftDeleteMixin` but migration `f0b1c2d3e4f5` created the table without `deleted_by_user_id` (and without the two soft-delete indexes), so every ORM select raised `UndefinedColumnError`; SQLite tests build the schema with `create_all` and never saw the drift. Fix: additive migration `f6a7b8c9d0e1` (column + FK `ON DELETE SET NULL` + indexes, reversible), a static chain-vs-model parity regression in `test_migration_chain.py` (fails without the migration, 26 passed with it), `docs/11` head reference updated, `docs/06` regenerated. Migration applied live on the compose DB (`Running upgrade b2c3d4e5f6a7b8 -> f6a7b8c9d0e1`); the exact failing ORM query now returns rows against the migrated database; `audit_events` history untouched (46 rows). |
| 2026-10-24 | Strong password policy | One rule now applies to every new password — at least 8 characters plus one uppercase letter, one lowercase letter, one number and one special character — added to `validate_password_strength`, which setup, forgot-password reset, self-service change, administrator reset and user creation already called before hashing. Login does not apply it, so existing accounts are not locked out (test inserts a legacy weak credential and signs in). Confirm-password mismatch is now also refused server-side on the administrator reset endpoint. The frontend mirrors the policy in `validatePasswordStrength`/`passwordRequirements`, and a new `CommonAppPasswordRequirements` checklist with a disabled submit gate is wired into setup, change-password, reset-password, the profile dialog, the administrator password dialog and the create-user form; the previously broken `freight.users.password.*` keys (labels lived at `users.password.*`) are fixed. Settings → Security has no complexity setting, so nothing was made configurable; `PASSWORD_MIN_LENGTH` keeps its startup floor of 8. `test_password_policy.py` (20) and the full backend suite, `password-policy.spec.ts` + `password-forms.spec.ts`, 90 frontend files / 724 tests, typecheck, lint and i18n check all pass. |
| 2026-10-24 | Audit Logs page errors | Two independent defects. (1) `WorkspaceView` starts the shared status manager for every module, so the read-only Audit Logs page requested `GET /auditLogs/status-policy`, which the backend answers 404 by design (no lifecycle for history) — the toast appeared on every load. `supportsStatusPolicy` now skips read-only modules and modules without a `status` value, so the request is never made there; the repository also marks a policy 404 as an expected answer so a similar probe (a writable collection without a policy) stays silent. No `auditLogs` policy was invented, and Jobs/Quotations/Users/Roles policies are unchanged (tested). (2) `useApi` raised the "Could not reach the server" toast for any ofetch `FetchError`, which includes HTTP 404/500 answers, duplicating the API-error toast with a misleading cause; `isNetworkFailure` now requires the absence of a status, so only real transport failures toast. The "Record" column also formatted `entityId` through the number formatter (`46` → `46.00`); identifiers now render as integer labels, while amounts keep money formatting. Tests: `test_audit_logs.py` (5), `audit-logs.spec.ts`, `record-status.spec.ts`; frontend 90 files / 730 tests, typecheck, lint green. |
| 2026-10-24 | List page header actions | Import/Export moved off the table toolbar into the page-header ⋯ menu on every eligible list page; the primary New/Create header button stays where it was and the empty-state create action is unchanged. Import is offered only with the module's manage permission, Export with its view permission. The `ImportExportDialog` no longer renders its own trigger (the page opens it through `v-model:open`) and loads the import history when opened; the shared header component only shows its field-picker Export item when the page supplies export fields, so pages without one no longer show a dead item. `tests/excel-io.spec.ts` (8), frontend 90 files / 732 tests, typecheck, lint, i18n check green. |
| 2026-10-26 | Export filter dialog | The workspace list Export menu item (one action, no separate "by filter" entry) now opens the shared `CommonAppExportDialog` instead of downloading directly. The dialog adds export filters — date range, Updated By (only where the module tracks attribution), status — plus file format (xlsx/csv), the existing scope choices (all matching / current page / selected rows), a Reset Filters button, a debounced matching-record count from the new `GET /api/v1/excel/{module}/export-count` (Export disabled at zero), and it closes on success. Backend: `POST /{module}/export` accepts optional `format` and `filters` (`dateFrom`, `dateTo`, `createdBy`, `updatedBy`, `status`, `search`), validates them (422 on invalid dates/users/formats or a user filter on an unsupported module, unknown users refused), applies filters at the database query level inside the existing permission, rate-limit and row-cap guards, and CSV keeps the exact template columns (UTF-8 BOM). Existing export path (ids, all-authorized, xlsx) is unchanged; import untouched. New i18n keys in all three locales. Backend `test_excel_import_export.py` (46) and full suite 692 passed / 5 skipped, ruff clean; frontend lint, typecheck, 91 files / 737 tests, i18n check green. Live browser verification not run in this pass (no E2E credentials configured). |
| 2026-10-26 | Export dialog: Created By and Search removed | The Created By dropdown and Search keyword field were removed from the Export dialog per product decision; the backend export API still accepts `created_by`/`search` filters (documented, validated, unused by the UI), so the shared contract is unchanged. Remaining dialog filters: date range, Updated By (where supported), status, format, scope. Backend untouched; `docs/07` API surface unchanged. Frontend lint, typecheck, 91 files / 737 tests, i18n check green on this revision. |

---

## Incremental Audit: Change Mapping

This table is the machine-readable map used by `scripts/feature-status.mjs`. Paths are globs relative to the
repository root. A change under a prefix means "review these feature rows", not "the feature changed status".

<!-- feature-map:start -->
| Prefix | Paths |
|---|---|
| AUTH | `backend/app/modules/auth/**`, `backend/app/core/security.py`, `backend/app/core/deps.py`, `backend/app/core/rate_limit.py`, `backend/app/core/locks.py`, `frontend/app/pages/auth/**`, `frontend/app/stores/auth.ts`, `frontend/app/middleware/**` |
| RBAC | `backend/app/core/permissions.py`, `frontend/app/pages/administration/roles/**`, `frontend/app/pages/administration/users/**` |
| MASTER | `backend/app/modules/master_data/service.py`, `backend/app/modules/master_data/models.py`, `backend/app/modules/master_data/router.py`, `backend/app/modules/master_data/schemas.py`, `backend/app/modules/master_data/route_stops.py`, `backend/app/modules/master_data/currency_rates.py`, `backend/app/modules/master_data/status_*.py`, `frontend/app/pages/master-data/**`, `frontend/app/config/lcs-reference-modules.ts` |
| CFG | `backend/app/modules/master_data/component_config.py`, `backend/app/modules/master_data/component_tabs.py`, `backend/app/modules/master_data/config_versions.py`, `backend/app/modules/master_data/config_snapshot.py`, `backend/app/modules/master_data/config_compare.py`, `frontend/app/pages/configuration/**`, `frontend/app/components/document/AppDynamic*.vue`, `frontend/app/components/document/Dynamic*.vue` |
| QUOT | `backend/app/modules/quotations/**`, `frontend/app/pages/quotations/**`, `frontend/app/utils/freight/document-tabs.ts` |
| ORDER | `backend/app/modules/operations/**`, `frontend/app/pages/service-orders/**`, `frontend/app/components/freight/Job*.vue` |
| CHG | `frontend/app/pages/service-charges/**`, `frontend/app/components/freight/JobCharges.vue` |
| FIN | `backend/app/modules/finance/**`, `backend/app/core/fx.py`, `backend/app/core/sequences.py`, `frontend/app/pages/finance/**`, `frontend/app/components/freight/JobFinance.vue` |
| REP | `backend/app/modules/reports/**`, `frontend/app/config/freight-reports.ts`, `frontend/app/components/freight/ReportsView.vue`, `frontend/app/components/dashboard/**` |
| ADM | `backend/app/modules/settings/**`, `backend/app/modules/audit/**`, `backend/app/modules/archive/**`, `frontend/app/pages/administration/**`, `frontend/app/components/document/SystemSettingsPage.vue` |
| BAK | `backend/app/modules/backup/**`, `frontend/app/repositories/http/backup.ts`, `frontend/app/composables/settings/**` |
| PLAT | `backend/app/main.py`, `backend/app/core/**`, `backend/app/api/**`, `backend/alembic/**`, `backend/scripts/**`, `infrastructure/**`, `deploy/**`, `.github/**`, `frontend/nuxt.config.ts`, `frontend/package.json`, `frontend/playwright.config.ts`, `frontend/scripts/**`, `backend/pyproject.toml`, `docs/06_database_design.sql` |
<!-- feature-map:end -->

### How an incremental audit runs

```bash
# from the repository root; prints the affected prefixes and the matching files
node scripts/feature-status.mjs --base origin/dev
```

Then, for each reported prefix: read the current row(s), run the focused test for the changed behaviour, and
update **only** those rows and the matching module assessment. If a row's status changed, add one Change History
line. If nothing was verified, the row stays UNVERIFIED and the reason is recorded; the script itself never
edits the report, and no CI job rewrites statuses.

A deterministic auto-writer was considered and rejected: tests prove behaviour only for what they cover, and a
generator would either invent statuses or overwrite reviewed judgements. The examined alternative — deriving
status solely from passing test files — is not sound for this repository because several suites test behaviour
without asserting the full user journey (for example, movements and milestones pass while the UI is unreachable).

---

## Status Definitions

| Status | Meaning in this report |
|---|---|
| WORKING | Implemented and verified by a test or live check that was actually run on this revision |
| UNVERIFIED | Implementation exists, but no executed evidence covers the stated behaviour |
| PARTIAL | Some required behaviour exists; a named part is missing or unreachable |
| BROKEN | Executed or static evidence demonstrates a functional failure |
| MISSING | Required behaviour is not implemented |
| NEEDS_IMPROVEMENT | Functional, but quality, security, performance or usability is below the acceptance bar |
| BLOCKED | Verification could not be completed because an external dependency or environment is unavailable |
| NOT_APPLICABLE | Requirement does not apply to the feature |

No feature is marked `NOT_APPLICABLE` in this report: removed organization/branch requirements are recorded in
`docs/02` as removed and are not part of the inventory.
