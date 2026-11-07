# Smart Settings and Integration Architecture

Status: DOCUMENTED TARGET, 2026-11-04. This is a source-reviewed design, not implementation
or provider acceptance. Preserve FastAPI/SQLAlchemy/PostgreSQL, the Nuxt static SPA, Casbin,
existing workers/storage and all 44 pages. The current request authorizes documentation only.

## Reading and ownership

- [Settings, email and security](../03-development/settings-and-provider-configuration.md)
  owns field contracts, secrets, password recovery and provider costs.
- [Notifications](../02-business/notification-requirements.md) owns routing/events/delivery.
- [Backup and recovery](../02-business/backup-and-recovery.md) owns recovery-set integrity.
- [Import/export](../02-business/import-export-requirements.md) owns module eligibility.
- [A–G implementation plan](../04-implementation/plans/PLAN-0005-settings-integrations.md)
  owns small tasks, dependencies and acceptance. Existing P03/P04/P14/P16 remain package owners.

## Current implementation inventory

Classification is against this request's target: COMPLETE requires executed acceptance;
PARTIAL = relevant implementation exists but target/gates unfinished; MISSING = no owning
implementation found in scoped sources; NEEDS_REVIEW = ambiguity or a demonstrated risk.
No runtime/provider test ran in this documentation task. A code comment or old test count
is not acceptance. Thus none of the integration features is newly declared COMPLETE.

| Area / status | Inspected source and existing behavior | Gap / next evidence |
|---|---|---|
| Settings shell — PARTIAL | frontend/app/components/document/SystemSettingsPage.vue; frontend/app/config/settings-schemas.ts select Localization/Email/Telegram/Security/Backup; shared header/validation/repositories | Preserve five tabs. Save submits whole model; tests can save a section then reload whole form. No local unsaved-change handler found; verify parent behavior and prevent stale cross-tab overwrite |
| Settings persistence — NEEDS_REVIEW | backend/app/modules/settings/service.py: deep_merge, keyed app_settings, redaction, blank-secret preservation, SETTINGS_UPDATED group audit | update_app_config loops merged groups, not just changed groups. Comment about independent writes does not prove concurrent safety. Need group revision/allowlist and caller privilege checks |
| Telegram transport/private/admin — PARTIAL | backend/app/modules/telegram/{service,client,outbox,worker,models}.py; verified pairing, encrypted token, claims, unique dedup keys, bounded retry | Currently PRIVATE/ADMIN destinations, one adminGroupId. No separate Operations destination; additive routing/constraint migration required |
| SO event notifications — MISSING | backend/app/modules/operations/service.py and router.py have lifecycle/audit; no Telegram enqueue producer found | Add after-commit delivery using transactionally enqueued actual events, not every Save |
| Developer alerts — PARTIAL | telegram/monitor.py samples incidents, audit, backup, API, DB and capacity; cooldown/recovery state exists | Separate Developer route and object-storage coverage; external observer needed for complete process/host outage. DB-down direct send is cached best effort, not durable |
| Email delivery — MISSING | Settings SMTP fields/validation exist. settings/router.py email test/send-test call connection_result; no SMTP/Resend sender found | Do not report connected/sent. Add actual provider adapter and tested failures; preserve SMTP configuration |
| Password recovery — PARTIAL | auth/service.py request/verify/reset: token_urlsafe(32), hash, 15-minute expiry, per-user lock, conditional consumption, revoke sessions; Telegram PRIVATE encrypted outbox | Real recovery already exists via verified Telegram link, not email. Add email without tying email tokens to Telegram state; preserve private-channel controls |
| Session/security — PARTIAL | auth/service.py, core/deps.py, settings/service.py enforce idle/absolute/access, password change and lockout | Neutral login refusal needs review: locked/inactive wording differs. Verify concurrent failures, settings propagation and complete browser renewal acceptance |
| R2 backup — PARTIAL | backup/service.py build_r2_storage uses S3Storage ensure_bucket=False; gzip latest BackupRecord JSON, put then exists; backup runs/logs | Not pg_dump, authenticated encryption, full file/config set or checksum-readback verification. Existence alone is insufficient |
| Google Sheets legacy — PARTIAL | backup/sheets.py and service.py versioned row mirror, restore_from_sheets | Preserve separately. Sheets is not Google Drive file backup or complete disaster recovery |
| Google Drive archives — MISSING | No Drive archive/OAuth adapter found in backup module | Reuse installed Google API libraries; add encrypted-file upload, OAuth refresh/revoke and checksum verification |
| Scheduling/history — PARTIAL | backup/scheduler.py asyncio tick, intervalHours, advisory lock; BackupRun/Record/State/Log | Calendar/timezone/DST, durable missed-run/lease recovery, one active cloud provider and retention protections missing/unverified |
| Complete restore — NEEDS_REVIEW | Sheets restore inserts/updates and commits per table; backup/router.py accepts confirmation; deployment-guide describes pg_dump/isolated scripts | This is not atomic complete restore; no R2 archive restore found. Require isolated staged recovery set and gated cutover |
| Upload storage — DONE | storage module: CloudflareR2Provider / GoogleDriveProvider, cloud-only, configured in Settings → Storage & Backup | No MinIO, no local-disk provider, no upload volume; uploads streamed to the selected provider |
| Master import/export — PARTIAL | excel_io registry/service/router; twelve master collections, XLSX preview/atomic confirm, CSV/XLSX exports, formula escaping, jobs/history | CSV import absent; identity types match name, requiring review. Current broad master permissions and audit completeness need scoped acceptance |
| Configuration bulk IO — MISSING | Attributes/groups/tabs/version APIs exist in master_data; absent from Excel registry | Add dependency-aware draft graph import using owning validators, no published-history overwrite |
| Permissions/audit — PARTIAL | core/permissions.py, module guards and audit/service.py | Settings update and backup.manage are coarse; design granular capabilities through existing Casbin catalog/page compiler |

Source list is repository-relative. These are inspected paths, not new proposed services.
Revalidate changed symbols before implementation because other sessions have dirty work.

## Reuse and boundaries

Reuse frontend/app/components/document/AppDocumentPage.vue and TelegramSettingsPanel.vue;
the latter already provides admin-group pairing/rules/history controls. Extend it rather than
rebuilding private/admin setup. Reuse frontend/app/components/excel/ImportExportDialog.vue for IO.

Settings page → settings schema/fields → existing repository contracts/HTTP → settings router
→ settings service/secret helpers → keyed app_settings. Extend the shared secret input,
field errors, confirmation and history controls; do not create another Settings sidebar page.

Business command → owning service transaction + notification_outbox INSERT → COMMIT →
existing worker claims → Telegram or email provider → conditional status update/audit.
No network request belongs inside an SO transaction. Keep notification failures independent
of a committed business result. Do not introduce another broker, Redis instance or worker fleet.

Backup orchestration → one recovery-set builder → authenticated encryption → selected cloud
adapter (R2 OR Drive) → remote verification → backup metadata → guarded retention.
Reuse backup runs/logs/scheduler and S3Storage; provider adapters own only storage/OAuth,
not database extraction, retention decisions or restore authority. Existing Storage Protocol
lacks streaming/stat/checksum/multipart primitives; extend only proven needs, preserving uploads.

Import dialog → existing excel_io registry/session validation → preview → explicit confirmation
→ owning master/config services in one transaction → durable result/audit. Never bulk insert
around normal reference/status/finance rules. Reuse openpyxl/csv/httpx/boto3/Google libraries;
no new package before checking installed capabilities.

## Shared settings and secret contract (proposed)

Schema allowlist each tab/group; server rejects unknown/server-owned keys and unauthorized
mixed-group patches before any mutation. Client sends dirty fields for one group, with a
per-group revision/If-Match equivalent; server locks and checks that revision, returns 409
on stale input, preserves unrelated groups and invalidates only affected caches. Diagnostic
status updates carry the tested credential revision and cannot overwrite newer configuration.

Secrets are write-only: omission or blank = preserve, explicit remove = remove after separate
confirmation, nonblank = validate and encrypt server-side. Return only configured/masked state,
never stored ciphertext, SMTP password, provider/API key, refresh token or service JSON.
Use core/crypto.py consistently with a dedicated encryption key; its current JWT-secret fallback
needs an authorized transition/key-recovery plan. Do not embed that key in the database archive.
Migrate legacy secret copies (including module_records) idempotently; do not silently lose
settings or make queued encrypted recovery payloads undecryptable during rotation.

Expose localization alone to ordinary authenticated users; restrict integration metadata/history
to the appropriate capability. Existing get-app-config strips Telegram detail for non-viewers
but returns other redacted groups; review this surface rather than assuming least privilege.

## Database changes to plan, not execute

| Existing owner | Smallest proposed extension / invariant |
|---|---|
| app_settings + legacy module_records | Group revision, schema/provider version, encrypted secret fields/references; one authority; compatibility migration retires plaintext copies only after verification |
| notification_outbox | Channel + explicit OPERATIONS/DEVELOPER/PRIVATE/USER_EMAIL destinations and revision; event/source/aggregate version; unique environment+event+destination; safe provider ID; preserve recovery-private/email-only constraints |
| notification_incidents | Reuse sustained condition/cooldown/recovery episode state; recovery transition distinct from severity |
| PasswordResetToken | Reuse hashes/expiry/used-at; add channel/purpose/credential-version or equivalent needed to separate email eligibility from Telegram eligibility |
| BackupRun/Log/State | Provider/config revision, durable job key/lease/checkpoint, verification/manifest/checksum/key-ID/compatibility metadata, retention protection, restore job reference |
| ImportSession/ImportJob | Reuse ownership/TTL/claim/results; template/graph versions, mode/checksum, conflict revisions and export history where absent |

Use additive Alembic migrations, current-head inspection, downgrade/recovery review and generated
schema docs only in an authorized implementation task. Do not add a speculative table per
concept or update generated SQL for this documentation-only task.

## Permissions and audit contract

Existing guards: settings.app_config.view/update or configuration.manage; backup.read/manage;
Excel module view/manage permissions, currently broad master.reference.view/manage for registry
entries. These are existing capabilities, not sufficient proof of desired separation.

Proposed capabilities (not registered yet): settings.localization.update, settings.email.manage,
settings.telegram.manage, settings.security.manage, settings.backup.manage, backup.run,
backup.download, backup.verify, backup.restore; import/export use existing page action codes
with explicit module-specific import management grants. Maintain existing backup.read and
read-history policy. Do not introduce a parallel role map or automatically grant new rights
through configuration.manage. Define compatibility/grant migration and protect Super Administrator.

Every mixed settings request must satisfy ALL affected group capabilities. Read/test does not
authorize save/send/restore. Restore requires backup.restore, recent reauthentication, typed
backup/environment confirmation, a short-lived plan nonce and approved execution target.
Run/download/import/restore must recheck authorization at execution as well as submission.
Use existing catalog + PAGE_PERMISSION_GRANTS; action-level Settings controls stay on MOD-042.

Audit actor, action, source/module, job/event ID, environment, config revision, counts, sanitized
result/error and correlation ID. Log changed field names, never secret values/tokens, reset
URLs, raw provider responses, customer rows or full import files. Durable job history supports
reconciliation but does not replace Audit Logs. Recovery audit must survive database cutover.

## Existing versus proposed API boundaries

All paths below are relative to /api/v1. Existing route schemas/errors remain the compatibility
baseline; additions are proposals until implementation updates the canonical API catalog.

| Existing | Target extension / refusal |
|---|---|
| GET/PATCH /settings/app-config | Group-scoped dirty patch + revision and server group privileges; read projections |
| POST /settings/app-config/email/test-connection and /email/send-test | Real transport verification; send-test separately explicit/authorized, never fake success |
| POST /settings/app-config/telegram/test-connection; /telegram/send-test; /telegram/* pairing/history | Preserve bot/private linking; explicit destination selection and verified group test; no free chat/token proxy |
| POST /auth/forgot-password, /verify, /resend, /reset | Preserve existing clients; token remains opaque code compatibility argument; neutral response and channel-independent email eligibility |
| GET /backup/status, /backup/runs, /backup/runs/{id}; POST /backup/run, /restore, /test-connection | Preserve legacy semantics explicitly; new archive jobs return 202 + ID, never relabel Sheets restore as complete DR |
| /excel/modules, /excel/{module}/template, /validate, /export, /export-count; /excel/imports/{token}/* | Extend registry/format/mode with compatibility; enforce permission, owner, expiry, revalidation |

Proposed new operation shapes: POST /backup/runs/{id}/verify, /download-ticket,
POST /backup/restore-plans then POST /backup/restore-plans/{id}/execute; GET /backup/jobs/{id};
GET /settings/backup/drive/oauth/start and /callback plus POST /disconnect (callback state-bound,
no public config write); POST /settings/app-config/telegram/destinations/{kind}/test.
Finalize exact names in the implementing slice; do not pretend these routes exist now.
No arbitrary path, endpoint, SQL, command or browser-supplied database URL may reach a restore.

Common envelope: data; persistent field errors for input, 401/403 denial, 404 inaccessible
job/record as appropriate, 409 stale/replay conflict, 422 invalid provider/file/relationship,
429 throttled, and sanitized retryable dependency failures. Public recovery responses remain
neutral regardless of account/provider state. Unknown outcomes remain explicit; no false success.

## Delivery, cost and release boundary

Use existing in-process asyncio workers + PostgreSQL locks/leases first. Persist durable state,
reclaim expired leases, bound execution, and cancel stale credential/destination work. Long
backup/restore/export work cannot run inside a normal request; controlled execution may later
need a narrowly privileged recovery runner in existing infrastructure. Never grant broad shell
or database-owner powers to the public API. A dead host cannot send its own outage alert.

Provider costs/limits are dated reference values in settings/provider documentation, not code
constants. No account creation, external message/test, provider installation, cloud upload,
retention deletion, backup drill or Compose modification is performed by this task.
