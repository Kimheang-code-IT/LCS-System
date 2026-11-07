# PLAN-0005 — Smart Settings and Integrations

Last updated: 2026-11-04. Status: DOCUMENTATION COMPLETE; implementation NOT_STARTED.
This is a dependency-aware planning package for the current explicit documentation request,
not a second active implementation plan. S01/PLAN-0002 remains the resume pointer. No new
business page, deployment, production access, provider account, message send or migration is
authorized by this document. Source baseline is the current dirty working tree, not HEAD.

## Goal and shared implementation contract

Complete the requested Settings/notification/email/security/cloud recovery/bulk IO behavior
inside existing modules. Canonical details are linked below; do not duplicate them in each task.

| Required plan dimension | Owning specification / shared rule |
|---|---|
| Current implementation / missing features | [inspected inventory](../../01-architecture/integration-architecture.md#current-implementation-inventory), status meanings and source paths; none newly declared runtime COMPLETE |
| Business / UI requirements | SET-001/002, REC-001, SEC-001 in [settings spec](../../03-development/settings-and-provider-configuration.md); five tabs/header/shared validation; notification, backup and IO IDs below |
| Backend / reuse | [shared architecture](../../01-architecture/integration-architecture.md#reuse-and-boundaries); existing settings/auth/Telegram/outbox/backup/excel_io/audit; no duplicate engine/broker |
| Database | [proposed extensions](../../01-architecture/integration-architecture.md#database-changes-to-plan-not-execute); only justified additive migrations with current head, downgrade/recovery and generated docs review |
| API | [existing/proposed boundaries](../../01-architecture/integration-architecture.md#existing-versus-proposed-api-boundaries); proposals are not existing routes; preserve envelopes/legacy clients |
| Provider configuration / cost | [dated official sources and field contracts](../../03-development/settings-and-provider-configuration.md); no live probe or paid activation without authorization |
| Security / permissions / audit | [capabilities and audit](../../01-architecture/integration-architecture.md#permissions-and-audit-contract); Casbin only; group-level all-or-nothing checks; write-only encryption; no credential logs |
| Validation / error handling | Linked business specs plus existing field errors; 409 stale config/preview, explicit job state/retry/unknown outcomes, rollback and no false success |
| Dependencies | Existing S01/P02 UI/access; P03/P04 validators where needed; P14 administration; S12/P16 isolated recovery/release; graph below |
| Verification | Scoped existing tests, necessary added regressions, disposable PostgreSQL for locks/races, provider mocks, synthetic UI; DEEP reviewer for changed protected contracts |
| Manual testing | Phase-specific journeys below, executed only later in authorized safe environments; not evidence from this docs task |
| Out of scope | New sidebar/pages, stack/provider rewrites, production data, blind generic financial import, automatic restore/purge, new brokers/Redis/MinIO, commits/deploys |

## Dependencies and recommended order

Planning audit A is complete. Later implementation: A → D1/D2 access+secret+group-write
foundation → B and C (independent after foundation) → E with B Developer alert path; F may
proceed independently after A/foundation and relevant P03/P04 validators; G joins B/C/D/E/F.
D3 session/login policy can be verified alongside B/C without weakening current S01 work.

Explicit task edges: A1→A2; A2→D1→D2; D2→B1→B2→B3→B4;
D2→C1→C2→C3; D2→D3; D2+B4→E1→E2→E3→E4→E5;
A2+D1+P03/P04-required-subset→F1→F2→F3; B4+C3+D3+E5+F3→G1→G2.
Existing roadmap sequence still governs activated slices. This graph identifies prerequisites;
it does not start a future phase or imply all P03/P04/S01 work must be reimplemented.

## Phase A — Settings audit

Status: COMPLETE for documentation/source inspection only; no runtime feature acceptance.
Goal: establish truthful current state/reuse/gaps without touching functionality.
Current: five Settings tabs, keyed config, encrypted Telegram private/admin delivery, password
reset primitives, R2 JSON/Sheets backup, scheduler and twelve-master Excel engine exist.
Missing/risks: two-group SO routing, real email/Drive/complete DR, configuration IO, granularity,
secret at-rest and stale-save behavior; evidence is in the inventory, not guessed from UI.

| Task | Scope and source | Acceptance / evidence |
|---|---|---|
| A1 | Inspect Settings/schema/repositories, auth/users/Casbin, Telegram worker/monitor, backup/storage/Compose, Excel/config and current docs | Paths and actual behavior inventoried; no secret values read or provider called |
| A2 | Define canonical specs/IDs, proposed contracts, A–G dependencies and current-state classifications | Complete linked specs and structural validation; task records no application change |

Manual review: follow one Settings tab's view→repository→router→service and each existing
provider path; distinguish a placeholder connection result, redacted mirror and full recovery.
No commands that send, deploy, restore or mutate credentials are part of A.

## Phase B — Telegram

Status: NOT_STARTED (existing private/admin transport PARTIAL against target).
Goal: NOT-001–005, one bot/two distinct verified groups with isolated Ops/Developer delivery.
Canonical scope: [notifications](../../02-business/notification-requirements.md). UI/backend/
DB/API/security/provider rules inherit the shared contract, including recovery constraints.

| Task | Small change / existing owner | Measurable acceptance |
|---|---|---|
| B1 | Telegram destination settings/verification and additive outbox destination constraints; preserve legacy admin/private links | Legacy candidate migrates to Developer only, Ops stays disabled; invalid/public/same-group destinations refused; recovery never routes to a group |
| B2 | Operation service transition producers + existing outbox, source/event/version IDs and dedup handling | Committed creation/Finish/important transition queues one logical event; rollback/minor Save/replay queues none; provider outage cannot fail SO save |
| B3 | Worker policy/revision/lease/429 retry and history by destination | Concurrent claims/restarts bounded; stale config cancels safely; no technical Ops payload; unknown send window documented rather than fake exactly-once |
| B4 | Monitor Developer routing, incident recovery and selected-group tests | Cooldown/one recovery verified; backup/storage/DB/scheduler errors sanitized; full-host outage limitation explicit; tests require explicit action |

Focused candidates: backend/tests/test_telegram.py, test_telegram_client.py,
test_telegram_outbox.py, test_telegram_monitor.py, test_telegram_postgres.py,
test_telegram_recovery.py; operation producer regression and affected contract/denial tests.
Manual: enable/verify only a synthetic private group pair, inspect events/test/history, disable
one destination and confirm no reroute. External sends require separate permission.
Done: NOT acceptance passes, old private recovery works, no duplicate business writes; update
P14.2/S11 + operational lifecycle topic only for implemented behavior.

## Phase C — Email and password recovery

Status: NOT_STARTED (SMTP fields exist; real sender MISSING; Telegram recovery PARTIAL reuse).
Goal: SET-002/MAIL-001/REC-001 using Resend with SMTP preserved and secure neutral recovery.
Canonical scope: [email/recovery/security spec](../../03-development/settings-and-provider-configuration.md).

| Task | Small change / existing owner | Measurable acceptance |
|---|---|---|
| C1 | Real email adapter, provider selection, sender verification, explicit test/send and durable channel; replace placeholder diagnostics honestly | Mocked Resend/SMTP accepted/permanent/transient/quota errors accurate; old SMTP config retained; no secrets returned; no sends on Save |
| C2 | Channel-independent recovery issuance/consumption and compatibility migration in auth/outbox | Hashed random expiring single-use tokens; email independent of Telegram state; known/unknown/disabled equal public response; no raw token logs/links in groups |
| C3 | Existing auth forms + link hygiene, confirmations and session invalidation | GET/scanner cannot consume, replay/races fail, shared password policy, atomic password+token update, ALL old sessions revoked; confirmation failure cannot undo reset |

Candidates: backend/tests/test_password_reset.py, test_password_policy.py, test_auth_sessions.py,
test_auth_postgres.py, existing Telegram recovery regressions; frontend/tests/password-forms.spec.ts,
password-policy.spec.ts, auth-api.spec.ts. Provider mocks first; no dependency installed before
reuse check. Manual: sender setup, test recipient, neutral forgot flow, expired/used token,
provider outage and old-session rejection on isolated users. Done: secure email path works,
Telegram compatibility retained and existing S01 acceptance remains accurately scoped.

## Phase D — Security settings and shared foundation

Status: NOT_STARTED for this package; existing enforcement PARTIAL, sensitive writes NEEDS_REVIEW.
Goal: SET-001/SEC-001 plus integration secret/capability contracts, preserving S01 guards.

| Task | Small change / existing owner | Measurable acceptance |
|---|---|---|
| D1 | Casbin catalog/page grants and per-group request/read projections; high-privilege test/run/download/restore distinctions | All mixed-group requirements checked before mutation; no coarse-grant escalation, protected admin intact; 401/403 per operation and revoked grant tested |
| D2 | Settings service/group revisions, only changed-group writes, encrypted secret migration and dirty draft-safe UI | Two-tab/two-admin writes preserve unrelated config; stale same-group 409; omitted/blank preserves, explicit remove audited; no plaintext/ciphertext API/log leak |
| D3 | Existing idle/absolute/refresh/logout/password/lockout behavior and neutral public refusals | Every configured field has enforced timing/effect; changed policy converges within documented cache bound; replay/expiry/lockout/concurrent failures verified; no second timeout engine |

Candidates: backend/tests/test_settings_validation.py, test_localization_settings.py,
test_auth_rbac.py, test_auth_sessions.py, test_auth_postgres.py, test_role_permissions.py,
test_route_authorization.py and test_frontend_api_contract.py (affected subset);
frontend/tests/session.spec.ts, auth-renewal.spec.ts and password-policy.spec.ts.
Manual: view-only versus each manage role; stale/dirty Save/Refresh, explicit secret removal,
reauth confirmation, shortened absolute lifetime and safe logout. Done: secret/grant/write
foundation is verified before provider activation; do not reinterpret it as full S01 completion.

## Phase E — Cloud backup and restore

Status: NOT_STARTED; existing R2 snapshot/Sheets scheduler PARTIAL, complete DR/Drive MISSING.
Goal: BAK-001–008; canonical [backup/recovery spec](../../02-business/backup-and-recovery.md).
Keep existing upload storage and legacy mirrors. Implement a recovery set, not a renamed JSON file.

| Task | Small change / existing owner | Measurable acceptance |
|---|---|---|
| E1 | Reuse run/history/scheduler, durable occurrence/lease and one recovery-set builder | Consistent PostgreSQL+file+config cutoff, complete manifest/compatibility, stream/bounds; no overlap across replicas; restart/missed-slot/DST states verified |
| E2 | Authenticated encryption/key references and direct R2 adapter with multipart/checksum/readback | No MinIO target dependency; private scoped bucket; wrong key/corruption/interrupted upload fail; verified content digest and complete manifest, not exists-only success |
| E3 | Optional Drive OAuth/file adapter through same builder | State/PKCE/least scope, encrypted refresh/revoke, shared-drive limitations, resumable binary encrypted archives and independent old-provider history verified |
| E4 | Retention/protected last-good, downloadable tickets, verification/overdue and Developer alerts | Wrong namespace/last-good/restore-in-use deletions refused; permission rechecked; no signed URLs/secrets in Telegram; no paid activation without authorization |
| E5 | Staged asynchronous restore plan, reauth/confirmation/control runner and isolated drill | Verified compatibility/digest/nonce, maintenance outside target DB, pre-restore set, DB/files coordinated, ledger/allocations/attachments/sequence checks, token/job quarantine; failed stage never exposes mixed data |

Reuse backend/tests/test_backup.py and frontend/tests/backup-settings.spec.ts, adding only
necessary archive/provider/scheduler/restore regressions. Real PostgreSQL/synthetic object
storage proves locks and full recovery; providers mocked until explicitly authorized sandbox
checks. Manual: configure/test, queue run/history/download/verify, corrupt sample refusal,
stale restore nonce, failed stage recovery and authorized isolated complete restore. Done:
record measured RPO/RTO and verified contents/keys; no actual production restore or provider
migration implicit in implementation acceptance. S12/P16 gate remains independent.

## Phase F — Data Import/Export

Status: NOT_STARTED for extensions; twelve-master XLSX engine PARTIAL, configuration/CSV import MISSING.
Goal: IO-001–007; canonical [IO spec](../../02-business/import-export-requirements.md).

| Task | Small change / existing owner | Measurable acceptance |
|---|---|---|
| F1 | Audit existing master templates/modes, stable identities, group grants, file limits, audit and CSV adapter | All twelve keys explicit; ambiguous name-update refused; no target records before confirm; CSV/XLSX same validation; protected/system rows safe |
| F2 | Existing registry/dialog plus dependency-aware draft configuration graph adapters | Attributes→groups→tabs→draft version with ID remap/revision checks; atomic rollback; published version/SO snapshot unchanged; activation is separate |
| F3 | Safe filtered/all-authorized export, job/audit counts, failed-row reports and eligibility UI | All 44 page policies explicit; formula/Unicode/Decimal/permission safe, no arbitrary ledger import, retry/foreign session/stale preview denied without duplicate writes |

Candidates: backend/tests/test_excel_import_export.py and configuration lifecycle tests;
frontend/tests/excel-io.spec.ts and export-dialog.spec.ts. Test atomicity/concurrent identity
updates on disposable PostgreSQL; do not generate unrelated fixtures or another framework.
Manual: master template/invalid preview/errors/cancel/one confirm/export; config graph import
stays DRAFT, explicit activation, old SO unchanged; export-only pages show no import.
Done: P03.3/P04 captured subset verified; no whole-package completion inferred.

## Phase G — Integration review

Status: NOT_STARTED. Goal: coherent privilege/config/job/recovery behavior across B–F.

| Task | Small review / acceptance | Evidence |
|---|---|---|
| G1 | Cross-feature fault/permission/upgrade/secret review and regressions | Restore cannot replay notifications/resets, provider rotation cannot resurrect secrets/jobs, import cannot bypass guards, stale config/token/journal invariants preserved; DEEP independent review |
| G2 | Safe manual journeys, recovery drill and requirements/evidence reconciliation | Record environment/revision/commands/provider mocks/skips, measured recovery, all open decisions and authorized business acceptance; no release claim from docs/unit tests alone |

Use [testing policy](../../03-development/testing-guide.md); full suites/build/cross-browser only
when release/shared impact requires them. Browser only for actual Settings/auth/IO/restore
interaction; no runtime tests for this prose task. Done only after named acceptance/recovery
owners approve operational policy and required isolated tests succeed. No automatic deploy.

## Open decisions before activation

Owner approval needed for trusted recovery-email proof; sender/domain and Drive account/folder;
role/capability migration; event materiality/payload visibility/cooldowns and incident responders;
RPO/RTO, retention/protected sets and schedule/grace; archive size/streaming crypto/runner/key
escrow/rotation; provider budget/quotas; CSV/template conflict policy and stable identity type
update key. Safe defaults in the specs are proposals, not hidden production configuration. Telegram
accepted-send/acknowledgment ambiguity also requires explicit acceptance if strict external
zero-duplicate delivery is a business requirement.

## Documentation verification and Handoff

- Completed: scoped source inspection, existing/gap classification, five owning specifications,
  A–G plan/dependencies, package/roadmap links and requirements/API/security navigation.
- Remaining implementation: B–G and runtime acceptance; all NOT_STARTED. A completed only
  documentation inventory. S01/PLAN-0002 remains unfinished and is not executed by this task.
- Exact next action: when implementation is explicitly requested, re-read current AGENTS,
  roadmap/Handoff and select the authorized foundation task (D1/D2) after current S01 needs.
- Verification: structural/source-path/link/coverage and baseline checks recorded below after run;
  no application/provider test, cloud connection, message, backup/restore or paid account here.
- Commit status: uncommitted; no commit/deployment authorized. Other sessions' dirty work retained.

## Executed documentation verification (2026-11-04)

| Check | Observed result / limit |
|---|---|
| Targeted source/config inspection via lean-ctx | Settings frontend/schema/Telegram panel, settings/auth/user/security guards, Telegram client/outbox/worker/monitor/models, backup/Sheets/scheduler/storage, Excel registry/validation/confirm/export, configuration and Compose inspected. No secrets/provider calls |
| Node REPL structural validation | 21 task docs: 192 local links, 28 anchors, seven A–G phases; zero link/anchor/whitespace errors before this evidence section |
| Task/dependency/requirements coverage | 22 task IDs, 27 directed edges, acyclic; 25 distinct SET/MAIL/REC/SEC/NOT/BAK/IO headings; explicit IO policy covers 44 MOD IDs |
| Candidate source/test validation | 18 named backend test candidates and 14 concrete source file paths exist; candidates are NOT executed tests |
| git diff --check -- docs | Exit 0; new files separately checked for whitespace |
| node scripts/feature-status.mjs --self-test | Passed; 12 mapped groups |
| node scripts/feature-status.mjs | Read-only routing completed; output includes preexisting code/migration work. No feature-status implementation row promoted for prose |
| Resumed SHA-256 preservation check | 842 selected non-secret existing files; 15 intended existing-document edits, no unexpected changes/deletions; all application/infra/schema/agent-tooling files in that snapshot unchanged |

Six new documents: integration-architecture.md; notification-requirements.md;
backup-and-recovery.md; import-export-requirements.md; settings-and-provider-configuration.md;
this PLAN-0005. Fifteen existing documents updated: docs/README.md; 00-project README/requirements;
01-architecture system/API/security/permission catalog; 03-development deployment guide;
04-implementation master plan, tracker, dependency map and P03/P04/P14/P16 packages. No existing
document was deleted or replaced by a duplicate phase document.

Preservation evidence is scoped: the final hash comparison starts after resumption with the six
new draft specifications already present. The initial pre-draft inspection recorded 837 files,
but its in-memory receipt was not retained across the interrupted chat; no full-span hash claim
is made. Every performed file mutation was documentation-only. Other sessions' preexisting
dirty/untracked application work was preserved; the overall Git diff is not this task's delta.

Official provider/security references were checked on 2026-11-04 and linked beside claims in
the settings/provider specification. No account entitlement, actual pricing bill, SMTP/Resend/
Telegram/R2/Drive connection, message delivery, backup, restore, runtime test, build, generated
SQL, deployment or paid signup was executed/claimed. Existing archived review limits remain
untouched. Implementation B–G and operational owners/targets remain open, not COMPLETE.
