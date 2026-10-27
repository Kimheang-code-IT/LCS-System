# LCS Freight Forwarding — Full System Verification

Date: 2026-10-23 · Branch: `dev` · Working tree: uncommitted changes from multiple sessions preserved.

This report records what was **executed** in this verification pass. Anything that needs a live
PostgreSQL instance, a browser session, or external credentials is marked `NOT VERIFIED`, never
`PASS`.

## Method

- Repository is the source of truth; `docs/` was cross-checked against code.
- Frontend: Vitest, `pnpm typecheck`, `pnpm lint`, `pnpm i18n:check`.
- Backend: focused `pytest`, `ruff`, API contract tests.
- Database: Alembic head and schema-doc checks only; no live database queries were made in this
  pass, and no migration was run against the working database.
- Browser: Playwright was **not** executed (no credentials/stack run in this pass).

## Verification summary

| Module | Feature | Frontend | Backend | Database | Business Logic | Tests | Result | Notes |
|---|---|---|---|---|---|---|---|---|
| Shared lists | Column configs, Created By/At, document links | `WorkspaceView.vue`, module configs | list payloads expose ids/creator names | columns exist in models | creator resolved from stored field/audit | frontend 84 files / 657 passed | PASS | Rows verified by unit/API tests; visual rendering not browser-verified |
| Quotations | List, revisions, compare, conversion, re-quotation | `DocumentView.vue`, `quotation-revisions.ts` | `quotations/service.py` | `quotations`, `quotation_revisions` | Draft→Accepted→Converted, idempotent conversion | `test_quotations.py` 32 passed | PASS | Compare UI removed by owner request; API remains |
| Service Orders | List, containers, re-quotation, charges | `WorkspaceView`, `JobContainers` | `operations/service.py` | `service_orders`, `service_order_containers` | conversion copies data, pending containers allowed | `test_workflows.py` 17 passed | PASS | — |
| Service Charges | List, fee lines, line adjustments, printing | `JobCharges.vue`, `AppLineTable.vue` | `operations/service.py`, `charge-print.ts` | `service_order_charges`, `..._charge_lines` | line discount/tax, draft watermark | `test_charge_tax_round_trip`, `charge-print.spec.ts` | PASS | Print output not visually verified |
| Finance documents | List, posting, allocation | `WorkspaceView`, `DocumentView` | `finance/service.py` | `financial_documents`, `..._lines` | Decimal amounts, posting guards | `test_finance_automation.py` | PASS | Outstanding hidden for non-invoice types |
| Finance modules | CoA, financial accounts, journals, periods, posting rules | reference module configs | `finance/service.py` | `chart_of_accounts`, `journal_entries`, `accounting_periods`, `posting_rules` | debit=credit preserved | `test_reporting_values.py`, `test_created_by.py` | PASS | Chart-of-accounts list rows are not hyperlinked |
| Operations reports | Register, status, containers, profitability | `freight-reports.ts`, `ReportsView.vue` | `/api/v1/reports/*` | posted rows + order data | integers for counts, existing money logic | `operations-reports.spec.ts` | PASS | Report **row values** for REP-002/REP-004 remain unasserted |
| Financial reports | 8 reports | `freight-reports.ts`, `ReportsView.vue` | `reports/service.py` | posted ledger rows | statements preserved, −/debit/credit untouched | `finance-lists.spec.ts`, `test_reporting_values.py` | PASS | Statement totals covered by existing backend tests |
| Master data | 11 reference lists | `lcs-reference-modules.ts` | `master_data/service.py` | reference tables | dynamic dropdowns untouched | `master-data-tables.spec.ts`, 66 backend tests | PASS | Creator only for records created after the audit write |
| Master data | Document Types master (custom types over canonical behaviours) | `/master-data/document-types` page; finance + posting-rule selectors read the master | `master_data/service.py` documentTypes spec; `finance/service.py` resolves `documentTypeId` | `document_types` (Alembic `f0b1c2d3e4f5`, seeded canonical rows) | canonical code keeps its behaviour; custom type must reference a canonical behaviour; `documentType` stays canonical | `test_document_types.py` (7) | PASS | Migration not applied to the live stack (image predates the revision); POST behaviour verified on SQLite |
| Configuration | Versions, tabs, groups, attributes | version page + builders | `config_versions.py`, `component_config.py` | `configuration_versions`, component tables | publish/rollback unchanged | `component-config-tables.spec.ts`, 66 backend tests | PARTIAL | Tabs/Groups are builders, not list tables; no separate Components page |
| Administration | Users, roles, audit, sequences, versions | module configs, versions page | `auth/service.py`, `audit` | `users`, `roles`, `audit_events` | permissions unchanged | `test_auth_rbac.py`, `test_role_permissions.py`, 33 passed | PASS | No standalone Permissions/Login-history page |
| Settings | 8 configured tabs | `settings-schemas.ts`, `SystemSettingsPage.vue` | `settings/service.py`, `router.py` | `app_settings` (JSON per group) | see Settings section | `test_settings_validation.py` + 36 focused backend tests | FIXED | 5 of 8 tabs are rendered; see below |

### Document Types master (added in this pass)

- New `document_types` table (Alembic `f0b1c2d3e4f5`), seeded with the ten canonical accounting
  behaviours; `/master-data/document-types` page, menu entry and page-access mapping added.
- Selectors driven by the master: Financial Documents form (`financeDocumentTypeFilter`),
  posting-rules type selector (`postingRuleDocumentTypeFilter` — canonical behaviours only) and
  the Service Order Finance tab (behaviour vocabulary + `availableIn service_order_finance`).
- `POST /financial-documents` accepts `documentTypeId`, resolves the canonical behaviour as
  `documentType`, and stores `documentTypeId/Code/Name` in the payload `data` echo.

### Excel Import & Export engine — Phase A/B (added 2026-10-24)

- New module `backend/app/modules/excel_io/`: registry (12 Master Data modules, derived from
  the master-data specs — no duplicated validation), template generation, upload/validate/
  preview/confirm pipeline, XLSX error report, export, history model.
- New `import_jobs` table (Alembic `12ab34cd56ef`; preserved by administrative reset) and
  `import_sessions` (Alembic `b2c3d4e5f6a7b8`) for durable pending previews.
- Endpoints under `/api/v1/excel/*` (see `docs/07`); per-user, per-action rate limits in a
  60 s window (20 template / 10 validate / 10 commit / 20 export / 60 history), 10 MB /
  2 000 rows cap, `.xlsx`-only, formula cells and stale templates refused, archive
  expansion capped at 100 MB uncompressed / 2 000 entries / 100× ratio, formula-injection
  escape on export (including behind leading whitespace).
- Frontend: `useExcelIo` client + shared `ImportExportDialog` wired into `WorkspaceView`;
  actions hidden unless the backend catalog lists the module and the caller holds the
  module's manage permission.
- Tests: backend `test_excel_import_export.py` (35) green; frontend `excel-io.spec.ts` (6);
  full frontend suite 89 files / 692 passed; typecheck/lint/i18n green.
- Browser verification on the compose stack (2026-10-24): template download, validate/preview,
  CREATE commit, list refresh, CREATE_AND_UPDATE commit, invalid workbook (field errors, Confirm
  disabled, no toast), discard confirmation, error-report download and filtered export download.
  Fixed on the way: the Import button never enabled (catalog was only loaded inside `show()`),
  export returned `422` (JSON body sent as `text/plain`), the export header list repeated
  `status`, and `lcs.common.close` was missing from the locale bundles. Exported `'`-quoted
  values are unquoted again on import.

## Settings verification

Rendered tabs: **Localization, Email, Telegram, Security, Backup** (`systemSettingsTabs`).
General, Notifications and System are defined in `appConfigTabs` but are **not reachable from any
route** — reported, not invented.

| Tab | Field/Feature | Frontend | Backend | Persistence | Validation | Security | Result | Notes |
|---|---|---|---|---|---|---|---|---|
| General | Default landing/page size/record view, upload size, comments/sharing/export | schema only, no route | merged from `DEFAULT_APP_CONFIG`; `maxUploadSizeMb` read by upload policy | `app_settings.general` JSON | now server-validated (`maxUploadSizeMb` 1–100) | requires `settings.app_config.update` | PARTIAL | Toggles `enableComments/Sharing/Export` and `defaultLandingPage/PageSize/RecordView` are **not consumed** by any page; Kanban option removed as unsupported |
| Localization | Language, available languages, timezone, formats, currency | `AppDynamicFieldRenderer` language toggles; static option lists | `normalize_localization`, `validate_localization_patch` | `app_settings.localization` JSON | strict language/timezone/format checks; timestamps stay UTC in DB | authenticated read; update permission | PARTIAL | Currency list is static (`SUPPORTED_CURRENCIES`), not driven by Currency master data; formatting is applied through `useAppLocalization` |
| Email | Enabled, host, port, user, password, encryption | `SystemSettingsPage` + settings rules | JSON group; secrets redacted | `app_settings.email` | **FIXED**: enabled requires host + valid port; encryption vocabulary checked | password never returned; blank keeps stored value | FIXED | No SMTP client exists in backend, so no delivery |
| Email | Test connection | menu action | `POST /settings/app-config/email/test-connection` | no state written | — | permission-gated | FIXED | Endpoint previously returned **“connected” without any call**; now returns `not_verified` with an explicit message |
| Telegram | Enabled, bot name/token/username, language, organization, destinations | `__telegramConnection`, destinations editor | JSON group; token redacted | `app_settings.telegram` | **FIXED**: enabled requires a stored token; language clamped | token never returned; blank keeps stored value | FIXED | No Telegram client/sender exists; destination JSON persists |
| Telegram | Test connection / test message | menu action | same endpoints | no state written | — | permission-gated | FIXED | Now `not_verified`, never a fabricated “connected” |
| Notifications | In-app/email/telegram, retries, rules | schema only, no route | defaults stored | `app_settings.notifications` | **FIXED**: retries 0–10 validated server-side | update permission | FAIL | No notification delivery/retry engine exists; rules are stored but not executed |
| Security | Session timeout, max attempts, lock minutes, password expiry, require change | numeric inputs + client bounds | `security` group + `get_access_policy` | `app_settings.security` | **FIXED**: numeric bounds server-side | update permission; values not exposed publicly | FIXED | **Session timeout is absolute** from token issuance (and caps refresh rotation) via `get_current_context` / `rotate_refresh_token`; password expiry and the one-shot global `requirePasswordChange` block all routes except me/refresh/logout/change-password; max-login/lockout behaviour unchanged |
| Backup | Enabled, interval, R2 fields, legacy Sheets | `SystemSettingsPage` | `_validate_backup_config`, R2/Sheets clients, in-process scheduler | `app_settings.backup` JSON | interval 1–720; R2 completeness/endpoint/prefix; destination required when enabled | R2/Sheets secrets redacted; blank keeps stored value | PASS | Restore was **not** executed against the working DB |
| System | Maintenance, read-only, pagination, version/env/cache/job status | schema only, no route | `system` group + `core/access_modes.py` | `app_settings.system` JSON | **FIXED**: pagination validated | update permission | FIXED | **Maintenance** now returns `503 MAINTENANCE_MODE` for ordinary access, while login/refresh/logout/me/change-password and the admin Settings endpoint stay open. **Read-only** returns `409 READ_ONLY_MODE` for POST/PUT/PATCH/DELETE, keeps reads and the admin Settings endpoint. Status is runtime-derived (environment, cache configured state, backup scheduler, published version) |
| Settings | Audit history | none | **FIXED**: writes `SETTINGS_UPDATED` audit event (group names only) | `audit_events` | — | no secret values recorded | FIXED | No dedicated settings-history UI; events appear in Audit Logs |
| Settings | One-row-per-group persistence | form sends full model | `_upsert_setting` merges per group | `app_settings` | 422 field errors map to inputs | per-tab RBAC | PASS | Verified by API tests |

### Confirmed defects fixed in this pass

1. Settings API accepted out-of-range security/notification/upload values that the UI rejected.
   Server now validates the merged configuration (`security.*`, `notifications.deliveryRetries`,
   `general.maxUploadSizeMb`, channel requirements).
2. Email/Telegram “Test connection” returned `connected` without performing any check. It now
   returns `not_verified` and the UI shows a warning, not a success.
3. System status fields were hardcoded (`healthy`, `idle`, `production`, `1.0.0`). They now come
   from runtime settings, cache configuration, the backup scheduler and the published configuration
   version.
4. Settings changes wrote only `updated_by_user_id`; they now also create an audit event.
5. The unsupported Kanban record-view option was removed from the settings schema.

### Phase 1 — critical enforcement (this pass)

| Gap | Implementation | Files | Result |
|---|---|---|---|
| Maintenance mode | `core/access_modes.py`, called from `get_current_context`; `503 MAINTENANCE_MODE`; auth + admin Settings exempt | `core/access_modes.py`, `core/deps.py` | FIXED |
| Read-only mode | Same module; unsafe methods get `409 READ_ONLY_MODE`; GET/HEAD/OPTIONS and admin Settings exempt | `core/access_modes.py`, `core/deps.py` | FIXED |
| Session timeout | Absolute timeout from access-token `iat`; refresh rotation refused once `user_sessions.created_at + timeout` passed | `core/deps.py`, `auth/service.py` | FIXED |
| Password expiry | `passwordExpiryDays` checked against `user_credentials.password_changed_at`; flags the credential and refuses all routes except me/refresh/logout/change-password | `core/deps.py` | FIXED |
| Require password change | One-shot marker `requirePasswordChangeSince` written when the policy is switched on; users whose password predates it must change it; cleared when turned off | `settings/service.py`, `core/deps.py` | FIXED |
| Max login attempts / lock minutes | Existing clamping and lockout logic left untouched | — | PASS (regression test) |

Policy decisions:
- **Session timeout is absolute from token issuance**, not idle. A refresh cannot extend the session beyond the configured window. This also applies to `remember_me` sessions; that is a deliberate security trade-off.
- Turning on **Require Password Change** affects existing passwords created before the toggle. Turning it off clears the marker. No account is deleted and no password is reset.
- Maintenance/read-only are checked in the backend on every authenticated request; disabled frontend buttons are not relied on. The policy read is cached per engine for one second and invalidated immediately when settings are saved.
- Background jobs are not HTTP requests: the in-process backup scheduler keeps its documented schedule; read-only mode does not cancel an already-running backup.

Files changed:
- `backend/app/core/access_modes.py` (new): maintenance/read-only decisions and recovery allow-list.
- `backend/app/core/deps.py`: session age, password expiry/require-change enforcement, access-mode call.
- `backend/app/modules/auth/service.py`: refresh rotation stops at the configured session age.
- `backend/app/modules/settings/service.py`: `get_access_policy` with a 1-second per-engine cache, invalidation on update, one-shot `requirePasswordChangeSince`.
- `backend/app/modules/master_data/service.py`: creation audit uses `master_data:<collection>` so it cannot collide with status-history queries.
- `backend/tests/test_access_enforcement.py` (new, 7 tests); updated `test_setup.py`, `test_api_completeness.py` for runtime environment.
- `docs/FULL_SYSTEM_VERIFICATION.md`, `docs/12_feature_status.md`, `docs/11_deployment_and_security.md`.

### Not verified / limitations

- Live PostgreSQL persistence and reload were exercised through the API tests on SQLite only; no
  live database inspection was performed in this pass.
- SMTP/Telegram delivery and their true connectivity cannot be verified: no client or credentials
  exist in this build.
- Notification retry/rules engine is missing; its stored settings are validated but unused.
- General/Notifications/System tabs have no route; the backend policies above are nevertheless
  enforced through the stored `system`/`security` groups.
- Email/Telegram delivery and true connectivity cannot be verified: no client or credentials exist.
- Backup scheduler/restore and R2 integration are covered by existing backend tests, but no live
  restore was attempted.
- Browser E2E (Playwright) was not run.
- PostgreSQL-specific behaviour (triggers, deferred constraints, session/refresh concurrency) was
  **not verified**; backend tests run on SQLite.

## Tests executed

| Command | Result |
|---|---|
| `uv run pytest tests/test_settings_validation.py tests/test_localization_settings.py tests/test_backup.py -q` | **36 passed** |
| `uv run pytest tests/test_settings_validation.py tests/test_localization_settings.py tests/test_backup.py tests/test_setup.py tests/test_api_completeness.py -q` | **46 passed** |
| `uv run pytest tests/test_access_enforcement.py -q` | **7 passed** (maintenance, read-only, access-token timeout, refresh timeout, expiry, require-change, lockout regression) |
| `uv run pytest tests/test_access_enforcement.py tests/test_settings_validation.py tests/test_localization_settings.py tests/test_backup.py tests/test_auth_rbac.py tests/test_workflows.py tests/test_api_completeness.py tests/test_setup.py -q` | **78 passed** |
| `uv run pytest -q` (full backend suite, SQLite) | **560 passed, 3 skipped** |
| `uv run ruff check .` | clean |
| `uv run pytest -q` (full suite, after fixing `document_types` column docs) | **573 passed / 0 failed**, 4 skipped |
| `uv run pytest tests/test_created_by.py tests/test_reporting_values.py tests/test_finance_automation.py -q` (earlier) | 15 passed |
| `uv run pytest tests/test_workflows.py -q` (earlier) | 17 passed |
| `uv run pytest tests/test_auth_rbac.py tests/test_role_permissions.py -q` (earlier) | 33 passed |
| `pnpm test` | **88 files / 680 passed** |
| `pnpm typecheck` | 0 errors |
| `pnpm lint` | 0 errors |
| `pnpm i18n:check` | passed (3158 keys per locale) |
| `uv run pytest -q` (full backend suite, 2026-10-24 Excel verification pass) | **653 passed, 5 skipped** |
| `pnpm test` (2026-10-24) | **89 files / 692 passed** |
| `pnpm i18n:check` (2026-10-24) | passed (3275 keys per locale) |
| `uv run python scripts/generate_schema_docs.py --check --strict` | passed (76 tables, up to date) |
| `uv run pytest tests/test_excel_import_export.py -q` (final tree) | **35 passed** |

## Remaining blockers

- The 2026-10-24 Excel pass did use a live PostgreSQL 16 database
  (`scripts/verify_excel_postgres.py`, 20/20) and a browser session on the compose stack for
  that feature only. Everything outside it still depends on SQLite-level tests.
- Visual rendering, responsive layout and accessibility were not reviewed beyond the Excel
  dialog journey.
- Do not treat this report as production readiness.
