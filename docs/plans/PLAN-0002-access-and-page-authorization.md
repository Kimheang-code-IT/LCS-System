# PLAN-0002 — Access and Page Authorization

## Metadata

Slice: S01 — Login and Page Authorization
Status: In Progress
Last updated: 2026-10-31
Execution: Backend verification started 2026-10-31 (E09 in the checklist: 149 backend tests
passed incl. a new page-collection deny matrix); E10 disposable PostgreSQL and E11 all-page
browser matrix executed 2026-10-31; E12 MOD-024/030/031 permission alignment (explicit route
maps, per-action in-browser gating, status-policy fix, first-permitted-page landing fallback)
executed 2026-10-31. Per-page action gating for the remaining pages and the renewal journey remain.
Task level: DEEP when security implementation/verification begins

## Objective and requirement IDs

Verify login/session/logout and all 44 pages' existing page/action/API permissions, fixing
only demonstrated defects. Preserve Casbin semantics and the protected Super Administrator.
Requirements: LCS-001, LCS-002, LCS-009, LCS-013; LCS-011 for localized auth/refusal behavior.
Related stable IDs: FR-176–181 in the canonical API specification and INV-001/002 in the
data-model traceability table; detailed security/permission catalog remains linked below.

## Dependencies and current implementation evidence

Read [security](../03-security-access-control.md), [permission mappings](../09_roles_and_permissions.md),
[approved pages](../09-design-brief.md#approved-44-page-inventory) and relevant code before any change.
`backend/app/core/authorization/service.py` builds/enforces Casbin; `model.conf` defines the model.
`backend/app/core/permissions.py` defines vocabulary/compilation.
`frontend/app/composables/layout/useMenu.ts` builds navigation;
`frontend/app/utils/freight/page-access.ts` maps page access.
These paths were inspected structurally, not verified as passing acceptance.
Use an isolated test environment and dedicated synthetic identities; no production mutations.

## Scope and planned changes

Inventory each page, existing supporting routes, action controls and API capabilities in
verification evidence within this plan. Check all 44 pages; do not copy draft permission labels
as truth. Inspect existing tests first. No code change is predetermined; record correct behavior
and complete the slice without rewrites when evidence meets acceptance.
No new pages, authorization system, role semantics, approval engine or infrastructure.

## Backend tasks

Inspect authentication/session/dependency code and tests; trace login, refresh, idle/absolute
expiry, revoked sessions, logout and stale authorization. Check every scoped protected API's
existing guard and verify permitted/denied requests. Test protected system-role safeguards.
Implement only reproduced defects; review impacted callers and use security-rbac/testing skills.

## Frontend tasks

Trace page middleware, menu, action gates and direct-route access; verify no privilege from
hidden buttons alone. Confirm logout clears visible session state and invalid credentials
produce understandable persistent errors. Cover all approved pages in a safe browser target.

## Database and API tasks

No schema or API contract change is planned. Inspect session/Casbin persistence and endpoint
guards. If a demonstrated fix needs shared contracts, escalate impact analysis and preserve
compatibility with additive migration/docs/contract gates where applicable.

## Security and RBAC scenarios

Test unauthenticated rejection, valid session/allowed action, logged-in insufficient permission,
direct URL and direct API bypass, expired/revoked session, refresh rotation/replay, logout and
post-logout token rejection according to existing semantics. Verify disabled role/account and
permission changes where supported. Preserve protected Super Administrator behavior.
Page grants and capability codes are related by existing compilation, not a new mapping.

## Financial integrity

No business financial mutation is part of this slice. Verify finance action authorization using
isolated test fixtures; denial must leave business records unchanged. Full posting/reconciliation
proof belongs to S05–S10, not inferred from permission tests.

## Localization and printing

Check relevant login/navigation/action/refusal/validation labels in en/km/zh, including language
switching and no exposed translation keys. Verify print access permissions where applicable;
full bilingual document rendering remains in the producing business slices.

## Test scenarios and boundaries

Use dedicated synthetic allowed/denied accounts; the protected admin is a separate control case.
Cover each page's applicable create/read/update/delete and business actions, not invented CRUD.
Capture expected permission, actual backend result, UI result, and evidence for each page.
Check invalid login/input, session boundaries and authorization refresh across existing clients.
Do not weaken/skip tests to satisfy acceptance.

## Candidate commands and exact test results

Run from owning directories after inspecting tests/environment; these are candidates, not executed results.

```bash
# backend/
uv run pytest -q tests/test_auth_rbac.py tests/test_auth_sessions.py tests/test_auth_remember_me.py tests/test_route_authorization.py tests/test_authorization_wildcard.py
uv run pytest -q tests/test_frontend_api_contract.py
uv run ruff check .
# frontend/
pnpm lint
pnpm typecheck
pnpm vitest run tests/page-access.spec.ts tests/report-access.spec.ts
pnpm test
pnpm i18n:check
```

Inspect `tests/test_auth_postgres.py` for its environment prerequisites before running it;
include applicable PostgreSQL session/invalidation coverage and dedicated browser scenarios.
Existing Chromium-only config and read-only/skipped browser tests do not prove all acceptance.

| Validation | Result | Limits |
|---|---|---|
| Auth/RBAC/security backend tests | Run 2026-10-31: 149 passed / 0 failed (checklist E09, incl. new page-collection deny matrix) | SQLite in-memory only |
| MOD-024/030/031 permission alignment | Run 2026-10-31 (checklist E12): backend 86 passed (incl. new `tests/test_master_data_permissions.py`) + scoped ruff clean; browser 58 passed incl. per-action action-button gating, direct-API denial and CSRF-header replay; landing fallback covered by unit + browser tests | Rebuilt local dev compose stack; disposable synthetic accounts; no production data touched |
| Disposable PostgreSQL NT01 set | Run 2026-10-31 (checklist E10): 7 passed / 0 failed across auth rotation/replay/revocation, quotation conversion concurrency, places migration and telegram outbox/claims | Local dev-container PostgreSQL with disposable DBs, dropped after; no cross-browser/production evidence |
| All-page browser/action matrix | Run 2026-10-31 (checklist E11): 57 Chromium tests passed against the local dev compose stack — 44 anonymous redirect denials, two complementary 44-page allow/deny matrices (broad MANAGER + narrow catalog-code account) from the actual `/auth/me` page codes, sidebar filtering, viewer/anonymous API 403/401, sign-out | Per-page in-browser action-button gating still open; Firefox/Edge/Safari and cross-tab renewal remain (NT02) |
| Source inspection | Paths identified; guard/catalog semantics confirmed against tests | Not a substitute for runtime acceptance |

### Backend authorization verification matrix (2026-10-31)

Derived only from the existing catalog (`backend/app/core/permissions.py` `MATRIX_PAGES`),
`frontend/app/utils/freight/page-access.ts` and page `definePageMeta` — no permissions were
invented. Backend evidence column is identical for every page: the deny-matrix test
(`tests/test_page_api_integration.py::test_page_collections_deny_without_authentication_or_role`)
proved anonymous → 401, roleless → 403 and admin → 200 on every page collection list endpoint,
and E09's RBAC suites proved deny-by-default, least-privilege, wildcard, catalog compile and
protected-admin behavior. Page-open/browser behavior is not yet exercised.

| MOD | Page | Route | Page permission (canonical) | Status | Remaining |
|---|---|---|---|---|---|
| MOD-001 | Dashboard | `/` | `dashboard.view` | PARTIAL | Browser open/denial |
| MOD-002 | Quotations | `/quotations` | `sales.quotations.view` | PARTIAL | Browser open/denial |
| MOD-003 | Service Orders | `/service-orders` | `operations.service_orders.view` | PARTIAL | Browser open/denial |
| MOD-004 | Service Charges | `/service-charges` | `finance.service_charges.view` | PARTIAL | Browser open/denial |
| MOD-005 | Service Order Register | `/reports/operations/service-orders` | `reports.service_order_register.view` | PARTIAL | Browser open/denial |
| MOD-006 | Service Order Status | `/reports/operations/service-order-status` | `reports.service_order_status.view` | PARTIAL | Browser open/denial |
| MOD-007 | Containers | `/reports/operations/containers` | `reports.service_order_containers.view` | PARTIAL | Browser open/denial |
| MOD-008 | Profitability | `/reports/operations/profitability` | `reports.service_order_profitability.view` | PARTIAL | Browser open/denial |
| MOD-009 | Financial Documents | `/finance/documents` | `finance.financial_documents.view` | PARTIAL | Browser open/denial |
| MOD-010 | Chart of Accounts | `/finance/chart-of-accounts` | `finance.chart_of_accounts.view` | PARTIAL | Browser open/denial |
| MOD-011 | Financial Accounts | `/finance/financial-accounts` | `finance.financial_accounts.view` | PARTIAL | Browser open/denial |
| MOD-012 | Journal Entries | `/finance/journals` | `finance.journal_entries.view` | PARTIAL | Browser open/denial |
| MOD-013 | Accounting Periods | `/finance/accounting-periods` | `finance.accounting_periods.view` | PARTIAL | Browser open/denial |
| MOD-014 | Posting Rules | `/finance/posting-rules` | `finance.posting_rules.view` | PARTIAL | Browser open/denial |
| MOD-015 | Revenue & Expense | `/reports/finance/revenue-expense` | `reports.revenue_expense.view` | PARTIAL | Browser open/denial |
| MOD-016 | Accounts Receivable | `/reports/finance/accounts-receivable` | `reports.accounts_receivable.view` | PARTIAL | Browser open/denial |
| MOD-017 | Accounts Payable | `/reports/finance/accounts-payable` | `reports.accounts_payable.view` | PARTIAL | Browser open/denial |
| MOD-018 | General Ledger | `/reports/finance/general-ledger` | `reports.general_ledger.view` | PARTIAL | Browser open/denial |
| MOD-019 | Trial Balance | `/reports/finance/trial-balance` | `reports.trial_balance.view` | PARTIAL | Browser open/denial |
| MOD-020 | Profit & Loss | `/reports/finance/profit-loss` | `reports.profit_loss.view` | PARTIAL | Browser open/denial |
| MOD-021 | Balance Sheet | `/reports/finance/balance-sheet` | `reports.balance_sheet.view` | PARTIAL | Browser open/denial |
| MOD-022 | Cash Flow | `/reports/finance/cash-flow` | `reports.cash_flow.view` | PARTIAL | Browser open/denial |
| MOD-023 | Business Parties | `/master-data/business-parties` | `master.business_parties.view` | PARTIAL | Browser open/denial |
| MOD-024 | Party Roles | `/master-data/party-roles` | `master.party_roles.view` (route map + page meta; legacy `master.reference.view` accepted) | COMPLETE | Full page journey (E2E) |
| MOD-025 | Place Roles | `/master-data/place-roles` | `master.place_roles.view` | PARTIAL | Browser open/denial |
| MOD-026 | Trade Directions | `/master-data/trade-directions` | `master.trade_directions.view` (+ legacy `master.reference.view` accepted) | PARTIAL | Browser open/denial |
| MOD-027 | Container Types | `/master-data/container-types` | `master.container_types.view` | PARTIAL | Browser open/denial |
| MOD-028 | Transport Types | `/master-data/transport-types` | `master.transport_types.view` | PARTIAL | Browser open/denial |
| MOD-029 | Transport Assets | `/master-data/transport-assets` | `master.transport_assets.view` | PARTIAL | Browser open/denial |
| MOD-030 | Asset Identity Types | `/master-data/asset-identity-types` | `master.transport_assets.view` (E12: explicit route map + meta; legacy `master.reference.view` accepted) | COMPLETE | Full page journey (E2E) |
| MOD-031 | Capacity Units | `/master-data/capacity-units` | `master.transport_assets.view` (E12: explicit route map + meta; legacy `master.reference.view` accepted) | COMPLETE | Full page journey (E2E) |
| MOD-032 | Fee Types | `/master-data/fee-types` | `master.fee_types.view` | PARTIAL | Browser open/denial |
| MOD-033 | Currencies | `/master-data/currencies` | `master.currencies.view` | PARTIAL | Browser open/denial |
| MOD-034 | Document Types | `/master-data/document-types` | `master.reference.view` | PARTIAL | Browser open/denial |
| MOD-035 | Component Attributes | `/configuration/component-attributes` | `configuration.view` | PARTIAL | Browser open/denial |
| MOD-036 | Component Groups | `/configuration/component-groups` | `configuration.view` | PARTIAL | Browser open/denial |
| MOD-037 | Component Tabs | `/configuration/component-tabs` | `configuration.view` | PARTIAL | Browser open/denial |
| MOD-038 | Configuration Versions | `/configuration/versions` | `configuration.view` | PARTIAL | Browser open/denial |
| MOD-039 | Users | `/administration/users` | `admin.users.view` | PARTIAL | Browser open/denial |
| MOD-040 | Roles & Permissions | `/administration/roles` | `admin.roles.view` | PARTIAL | Browser open/denial |
| MOD-041 | Document Sequences | `/administration/document-sequences` | `admin.document_sequences.view` | PARTIAL | Browser open/denial |
| MOD-042 | Settings | `/administration/system-settings` | `settings.app_config.view` | PARTIAL | Browser open/denial |
| MOD-043 | Archive | `/administration/archive` | `admin.archive.view` | PARTIAL | Browser open/denial |
| MOD-044 | Audit Logs | `/administration/audit-logs` | `admin.audit_logs.view` | PARTIAL | Browser open/denial |

Permission mapping review (2026-10-31) — resolved without changes:
`/master-data/party-roles`, Asset Identity Types and Capacity Units are absent from
`PAGE_ROUTE_PERMISSIONS` but are guarded by their `definePageMeta` permission
(`master.party_roles.view` / legacy `master.reference.view`), which the middleware uses as
the documented fallback; the backend enforces the same codes. Denial and allow behavior was
browser-verified for all three (E11). The legacy fallback is correct as designed and is now
covered by `frontend/e2e/page-authorization.spec.ts`; no Casbin semantics changed.

Second permission pass (2026-10-31, E12) — after the per-action review of MOD-024/030/031 the
mappings were made explicit, changing no Casbin semantics and no deny behavior:

1. `PAGE_ROUTE_PERMISSIONS` now lists the three routes (party roles →
   `master.party_roles.view`; asset identity types and capacity units →
   `master.transport_assets.view`, mirroring the backend collection guard
   `master_data/router.py::_COLLECTION_PAGE_PREFIX`). The derived legacy
   `master.reference.view` fallback keeps old sessions accepted. This aligned the
   frontend with the backend for MANAGER-class roles (which hold the per-screen
   transport-assets code and were previously denied the two vocabulary pages the
   API and the matrix intend them to cover) and fixed the party-roles sidebar
   entry, which was previously not permission-filtered at all.
2. Action buttons previously required the aggregate `master.reference.manage` for
   every master page; narrow matrix roles holding per-screen codes (e.g.
   `master.party_roles.update`, no aggregate) had backend-allowed writes with no
   visible controls. The workspace list and document form now derive the per-page
   action codes through the existing `pageActionPermission` helper and keep the
   aggregate accepted, and the bulk Deactivate button requires the update code.
3. Backend status policy followed the collection guards: the deactivate/activate
   transition for `transportAssetIdentityTypes`/`capacityUnits` already accepted
   the coarse codes but not `master.transport_assets.update` (party roles already
   had the per-page pattern). `ASSET_VOCABULARY_WRITE` in
   `master_data/status_policy.py` closes that gap; regression-covered in
   `backend/tests/test_master_data_permissions.py`.
4. Demonstrated defect fixed with regression coverage: an account whose permitted
   pages are outside the hard-coded landing list (e.g. only master-data pages) was
   stranded on the login screen after sign-in; `auth.global.ts` now falls back to
   `firstPermittedPagePath` (pure, unit-covered helper) before clearing the session.

Demonstrated defect found by the browser matrix (fixed same day, regression-covered): a
signed-in account whose first permitted page is not `/` — e.g. a role granted only
administration/configuration pages — was stranded on the login screen after signing in,
because the middleware's denial branch called `abortNavigation()` for any matched `from`
page, including the login page itself, before the landing redirect could run.
`frontend/app/middleware/auth.global.ts` now aborts in-app denial navigation only when the
current page is itself authorized; a public `from` falls through to the authorized landing
(or clears the session when the account has no usable page). Verified: the narrow catalog
account previously stuck now lands correctly, and the denied-navigation abort still keeps
authorized pages (E11 57 passed; frontend lint/typecheck/unit/i18n gates exit 0).

## Acceptance criteria

1. Exactly 44 pages accounted for, with supporting routes separated and no deletions.
2. Login/session/refresh/logout behave according to the existing approved security contract.
3. Allowed page/actions work and insufficient/unauthenticated direct API access is denied.
4. Backend permissions remain authoritative; protected Super Administrator is preserved.
5. Refusals do not mutate business data; localized messages remain usable.
6. Relevant checks pass with exact revision/environment/results and meaningful denial evidence.
7. Demonstrated gaps are fixed and reviewed; otherwise no rewrite. Remaining limits explicit.

## Definition of Done

Meet [canonical DoD](../00-agent-handbook.md#definition-of-done), all criteria above, DEEP
integration/regression/denial checks and read-only reviewer assessment. Update only relevant
security/testing docs, verified feature rows, roadmap and Handoff. No commit without approval.

## Risks and blockers

The approved inventory names pages/routes; actual compiled API capabilities still need verification. Session/database
behavior needs actual execution. Safe browser accounts and isolated test environment must be
confirmed before mutation. No runtime acceptance evidence has been produced by foundation work.

## Handoff

- Current status: Backend and browser verification executed; S01 remains `In Progress` until
  the remaining pages' per-page action-button gating and the remaining acceptance items close.
- Completed work: E09 (149 backend tests incl. page-collection deny matrix), E10 (7 disposable
  PostgreSQL tests), E11 (57 Chromium browser tests), E12 (MOD-024/030/031: explicit route maps,
  per-action in-browser gating, backend status-policy alignment, first-permitted-page landing
  fallback; backend 86 passed, browser 58 passed, frontend unit 796 passed, typecheck/lint/i18n
  exit 0), E13 (operations reports auto-load defect fixed; frontend unit 802 passed, browser 6
  passed), E14 (MOD-034 Document Types: `documentTypes` added to the shared status policy so the
  row `...` menu carries Deactivate/Activate with a `STATUS_CHANGED` audit event and a backend
  403 for view-only callers; seeded canonical rows report `System` in Created By, API-created rows
  the actor, unattributed rows stay em dash; backend 39 passed across
  `test_document_types`/`test_record_status`/`test_master_data_creator`/`test_deletion_policy`/
  `test_created_by`, scoped ruff exit 0), E15 (Archive coverage: `documentTypes` added to the
  archive entity registry so a deactivated custom type archives into the central archive with an
  `ARCHIVE` audit event, refuses duplicate archive (`ALREADY_ARCHIVED`), restores with lifecycle
  status preserved and unique-code revalidation (`RESTORE_CONFLICT`); canonical types stay
  non-archivable (`SYSTEM_DOCUMENT_TYPE`) and the frontend hides their archive action
  (`isProtectedManagementRecord`, unit-covered); `tests/test_document_types.py` +
  `tests/test_archive.py` 21 passed, scoped ruff exit 0, frontend
  `tests/protected-system-records.spec.ts` 3 passed; no migration — document types already carry
  soft-delete columns, and finance/operations/configuration entities remain non-archivable —
  see the archive coverage matrix produced with this batch). Checklist rows: MOD-024/030/031-AUTH
  COMPLETE, their READ/CREATE/EDIT/DELETE/TEST PARTIAL (E12); MOD-034 READ/EDIT/DELETE/VALIDATE/
  AUTH/TEST PARTIAL (E14/E15), MOD-034-E2E still UNVERIFIED (no browser run); MOD-043
  API/READ/DELETE/SEARCH/VALIDATE/AUTH/TEST PARTIAL (E15), MOD-043-E2E UNVERIFIED; FLOW-017
  PARTIAL (E15). Demonstrated defects fixed with regression coverage: narrow-grant accounts
  stranded on the login screen (`auth.global.ts`, E11), per-action accounts stranded likewise
  (`firstPermittedPagePath` fallback, E12), reports page auto-load TDZ crash (`ReportsView.vue`,
  E13), document types rejected with "This entity type is not supported by the archive."
  (registry gap, E15), and quotations Save a silent no-op after the `canSave` refactor
  (header Save/“Save changes” never fired; `canRunSave` vs `canSave` split, E16), and
  actual-container rows are corrected to be user-added physical containers only: the
  pricing-line carry-forward attempt was rolled back, conversion leaves Actual Containers
  empty, and container numbers are normalized (uppercase) with case-insensitive duplicate
  refusal (E17), and the quotation workflow is simplified to DRAFT → SUBMITTED → CONVERTED
  with exactly Save Changes / Submit / Convert / Re-Quotation: submit targets `SUBMITTED`
  (idempotent, `QUOTATION_SUBMITTED` audit), conversion runs from SUBMITTED with legacy
  SENT/ACCEPTED kept readable and convertible, no historical record rewritten, and no new
  Send or Accept action is exposed (E18).
- Remaining work: (1) per-page in-browser action-button gating for the pages E12 did not cover —
  the "action" half of each MOD-*-AUTH row (E12 pattern: `WorkspaceView`/`DocumentView`
  per-page action codes + one browser scenario per page; next the document pages'
  create/send/accept/convert buttons, and MOD-034's Activate/Deactivate row action); (2)
  browser-silent renewal/expiry journey
  (`e2e/auth-renewal.spec.ts` requires `LCS_AUTH_E2E_ISOLATED=1` + disposable auth stack);
  (3) close PARTIAL rows or mark N/A where actions do not exist; (4) final DEEP review before
  marking S01 complete.
- Exact next action: Build the per-page action-button authorization browser evidence for the
  remaining MOD pages (extend `e2e/page-authorization.spec.ts` following the MOD-024/030/031
  model, starting with the document pages' create/send/accept/convert buttons) using the
  synthetic accounts already in the dev database (s01.e2e.full / s01.e2e.viewer /
  s01.e2e.pages / s01.e2e.actions, all password `Passw0rd!`, the repo's standard test-fixture
  password; browser sign-in uses the accounts' email addresses because the login form validates
  an email-shaped value).
- Relevant files and commands: Evidence E09–E18 in the checklist; the spec above; the matrix
  table in this plan; frontend gates `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm i18n:check`;
  browser requires the local dev compose stack (`docker compose up -d --build postgres redis
  backend frontend` from infrastructure/ — rebuild backend/frontend when their source changes)
  and Playwright Chromium.
- Open blockers: Browser-silent renewal/expiry e2e needs the disposable auth stack flag
  (LCS_AUTH_E2E_ISOLATED) with its own disposable database; reports-generate/telegram e2e
  suites not run (separate fixtures needed).
- Commit status: Uncommitted; no commit authorized.
