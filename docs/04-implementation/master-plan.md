# Master Roadmap

Last updated: 2026-11-05

## Approved milestones and ordered vertical slices

This is the approved S01–S13 mandatory-release roadmap for the existing application.
Statuses indicate slice verification/delivery, not absence of existing implementation.
S01 completed 2026-11-04 (evidence E09–E24 in the checklist: E23 per-page action gating,
E24 renewal/expiry on a disposable stack). Remaining S01 limits are recorded in
PLAN-0002's Handoff. S02 completed the same day (PLAN-0006). S03 completed 2026-11-05
(PLAN-0007/E26 files batch + PLAN-0008/E27 remaining acceptance), and S04 completed the
same day (PLAN-0009–0012/E28–E31); deferred items carry recorded owners.
Foundation creation did not start its execution.

| Slice | Milestone | Outcome area | Dependencies | Requirements | Status | Testable acceptance outcome |
|---|---|---|---|---|---|---|
| S01 | Secure Access | Login and Page Authorization | Existing auth/Casbin and 44-page inventory | LCS-001,002,009,013 | Completed 2026-11-04 (E09–E24: deny matrix, disposable PostgreSQL, 44-page browser matrix, action gating + renewal/expiry on disposable stack; limits: Chromium-only, cross-browser→NT02/S13) | Permitted login/pages/actions; denied API access and logout invalidation |
| S02 | Operational Continuity | Quotation to Service Order | Completed S01 + reference/config prerequisites | LCS-003,014 | Completed 2026-11-04 (PLAN-0006: reuse/replay backend 56 passed, PG concurrency 3 passed on disposable DB, browser journey 4 passed; AppLineTable silent-seeding + save-label defects fixed) | Multiple intentional source-linked SOs may reuse an offer; each keyed command creates one order with preserved independent snapshots |
| S03 | Operational Continuity | Operational Execution | S02 | LCS-004,010 | Completed 2026-11-05 (PLAN-0007 files/attachments E26 + PLAN-0008 acceptance E27: API-level journeys for movements/milestones/required values/INACTIVE-FINISHED guards, containers separation + deleted-refs refusal, conversion transfers routes/requirements/boxes/snapshots, config snapshot pinned; movement-sequence unique constraint added via migration c0d1e2f3a4b5 verified on PG. Deferred: storage recovery drill →S12, DATA-011 catalog scope →S11, movements browser journey →NT02) | Actual containers, dynamic data and authorized files persist; Save/Finish protect operations without posting |
| S04 | Operational Continuity | Service Charge to Financial Draft | S03; finance setup | LCS-004,005 | Completed 2026-11-05 (PLAN-0009/E28 map + PLAN-0010/E29 issue isolation + PLAN-0011/E30 bill-once concurrency + PLAN-0012/E31 profit layers: issue → no document/journal, explicit convert → one draft (PG race-proven, DB backstop b7c8d9e0f1a2), posted layers ledger-true base sums, mixed currencies grouped; deferred: per-currency report redesign → S09/S10, container-level P&L has no source (documented absent)) | Charge issue has no ledger effect; explicit conversion yields one draft |
| S05 | Accounting Integrity | Customer Invoice Posting | S04; accounts/rules/open period | LCS-005,006 | Completed 2026-11-05 (PLAN-0013/E32 posting contract + PG post race; PLAN-0014/E33 receipt allocation + AR reconcile + PG allocation race; PLAN-0015/E34 supplier flow + AP reconcile/race; PLAN-0016/E35 reversals/allocation-undo/permission isolation + acceptance review. Deferred: allocation period-gate → S06/S08, audit split → S06+, presentation → S09/S10) | Atomic unique balanced posting with source and rate snapshots |
| S06 | Accounting Integrity | Customer Receipt and Settlement | S05 | LCS-006,007 | Not Started | Partial/full allocation reconciles; excess allocation denied |
| S07 | Accounting Integrity | Supplier Bill and Payment | S05 | LCS-005,006,007 | Not Started | Supplier posting/payment/settlement reconcile with AP control |
| S08 | Accounting Integrity | Corrections and Accounting Period Controls | S05–S07 | LCS-006,009 | Partly 2026-11-05 (PLAN-0017/E36: Period Closing feature — validation pipeline, atomic period-row-locked close shared with posting (PG race), reasoned reopen; authorized /finance/period-closing page. 10.4 remaining: closing-report evidence retention + reopening dependency checks (S09/S10 baseline); corrections ledger work follows S06/S07) | Preserved reversal; balanced journals; custom dates; backend review/close/reopen with audit and closed-period denial (P10 uses verified report baseline) |
| S09 | Reliable Reporting | Operational Reporting | S02–S07 | LCS-008 | Not Started | Approved operational reports distinguish quoted/issued/draft/posted values |
| S10 | Reliable Reporting | Financial Reconciliation | S05–S08 | LCS-006,008 | Not Started | GL/TB/AR/AP/P&L/Balance Sheet/Cash Flow reconcile |
| S11 | Complete Business Functionality | Remaining Approved Page Workflows | S01; reference setup verified as needed earlier | LCS-001,009,014 | Not Started | Required remaining CRUD/config/admin/archive/audit actions verified |
| S12 | Recoverability | Isolated Recovery Drill | Representative earlier-slice data; approved safe recovery controls | LCS-012 | Not Started | Coordinated DB/files/config recovery passes integrity and measured-time checks |
| S13 | Release Acceptance | Cross-browser, Performance, Accessibility, and Business Acceptance | S01–S12; approved datasets/targets | LCS-010,011,013,015,016,019 | Not Started | Required browser/print/localization checks and authorized acceptance evidence |

## Agent setup completion (2026-11-04)

The explicit agent-configuration task added concise .agents context and six on-demand skills,
reconciled existing OpenCode instructions and documented optional MCPs. It changes no ERP
business behavior or slice acceptance. [Setup evidence](../03-development/agent-tooling.md#setup-verification-record)
records validation; S01/PLAN-0002 remains the unfinished resume pointer. No next phase started.

## Smart Settings documentation package (2026-11-04)

[PLAN-0005 A–G](plans/PLAN-0005-settings-integrations.md) specifies Settings/notifications,
email/recovery/security, encrypted cloud backup/restore and reusable bulk IO. Documentation is
complete; runtime tasks are NOT_STARTED. P14 owns administration, P03/P04 bulk IO, P06 SO event
producers, P15 integration and S12/P16 recovery/release evidence. S01/PLAN-0002 remains the
unfinished active pointer. No new pages, provider activation or execution authorization follows.

## Active implementation plan

The explicit 2026-11-04 printing request is tracked separately in
[PLAN-0004](plans/PLAN-0004-financial-printing.md), a bounded read-only financial-printing
change. Its scoped verification does not complete S02 or activate the remaining P08 work.

S01's [PLAN-0002](plans/PLAN-0002-access-and-page-authorization.md) closed 2026-11-04,
S02 the same day, S03 closed 2026-11-05 (PLAN-0007/0008), S04 the same day
(PLAN-0009–0012, evidence E28–E31), and S05 closed the same day
(PLAN-0013–0016, evidence E32–E35). S06 is the next open slice
([P08 financial documents](phases/P08-financial-documents.md) owns S05–S07, one
document/settlement slice at a time).

[Project status checklist](project-status-checklist.md) is the verification index for requirements,
all 44 pages, technical evidence and remaining gaps. This roadmap controls sequence; the active
plan controls implementation scope. Checklist completion never authorizes unrelated work.

[PLAN-0002 — Access and Page Authorization](plans/PLAN-0002-access-and-page-authorization.md)
is `Completed` (2026-11-04) with executed backend/browser evidence E09–E24 and two read-only
reviewer passes. Read its Handoff before touching auth/Casbin behavior.
[PLAN-0001 template](plan-template.md) defines future plan contents; an S02 plan is created
only when that slice starts. The current documentation master task also explicitly
requests detailed future topic packages: see [ERP modernization planning](planning-guide.md),
[tracker](phase-tracker.md), [dependencies](dependency-map.md) and
[acceptance](acceptance-criteria.md). P00–P16 are planning detail mapped to these S01–S13 slices,
not additional active plans or permission to start implementation. Create later active plans
only when their slice starts and has a real need.
The superseded finance-verification proposal is preserved in the history section below;
it is not an active plan or a completed verification.

## Execution rules and dependencies

Verify existing behavior first and fix only demonstrated gaps, one independently testable
slice at a time. Preserve protected admin/permission semantics and working integrations.
Verify necessary master data/configuration before dependent slices; S11 is remaining coverage,
not permission to defer prerequisite configuration. Recovery planning stays active in parallel;
live infrastructure changes need separate authorization. Include localization, validation,
applicable printing, audit and denial checks in each relevant slice.

## Definition of Done and release blockers

Apply [canonical DoD](../03-development/ai-agent-guidelines.md#definition-of-done) and per-plan acceptance.
Require exact executed evidence, meaningful failure/boundary tests, relevant PostgreSQL
financial guards, reconciled reports and safe recovery validation. Update status only after
verification. Critical/high defects and unresolved critical finance/security/integrity/
recovery/operational/legal issues block production; noncritical TBDs require explicit acceptance.
Capacity, performance, RPO/RTO, budget, WCAG target, retention/legal and named owners remain
open as recorded in [design brief](../00-project/requirements.md).

## Optional backlog

Supporting audit: the former PLAN-0003 codebase-cleanup audit (removed 2026-11-04, consolidated
here) completed two bounded batches: dead Excel-registry helper/constant removal
(`excel_io/registry.py`, with before/after API regression) and global-search lifecycle fixes
(21-regression suite in `frontend/tests/global-search.spec.ts`). The completed fixes remain in
the codebase; do not reimplement them. Broader cleanup remains open: on an explicit separate
cleanup request, prove dynamic/import/re-export reachability before removing
`COMPONENT_DISPLAY_MODES`. It does not replace S01, reorder S01–S13, or authorize broader
refactors/database changes.

Should: Telegram delivery/monitoring improvements, nonblocking usability, additional safely
anonymized business scenarios; tablet and essential mobile viewing remain Should.
Could: Google Sheets mirror enhancements, optional integrations, advanced nonessential features.
Preserve existing functionality. Optional improvements are not release blockers unless needed
for a Must or explicitly committed. No extra business page is approved. Rich Period Closing
is planned within Accounting Periods; a standalone navigation page remains proposed.
Explicitly requested future package planning does not authorize feature implementation.

## History

### Compact Settings UI follow-up — 2026-11-04

User clarified the compact maintenance editor also belongs in the existing Backup tab and
Telegram should simplify existing controls only. STANDARD UI scope; backend guards, permissions,
verification API and database schema were unchanged. Maintenance now renders only toggle/Reason,
saves through the existing document header, and shares one editor state across both tabs.
Hidden settings/revisions are preserved; an existing schedule survives a Reason-only edit.
Reopening still requires prior backend recovery verification through the authorized API.
Telegram rules now update the parent draft and use header Save; connection/pairing remain,
rules/history collapse, and history loads on first opening. Fixed its demonstrated invalid
empty select option and passed interpolation parameters to the existing validation translator.

Files: `SystemSettingsPage.vue`, `MaintenanceSettingsPanel.vue`, `TelegramSettingsPanel.vue`,
`TelegramDeliveryHistory.vue`, new `composables/settings/useMaintenanceSettings.ts`,
`utils/settings/maintenance.ts`, `tests/maintenance-settings.spec.ts`; UI standards and operator
instructions updated. Save targets the current tab's changed settings group; Backup saves its
changes before maintenance activation, or reopens first if backend verification permits it.
Separate API writes are not atomic; failed requests keep the remaining draft and show errors.

Evidence: `pnpm exec vitest run tests/maintenance-settings.spec.ts tests/maintenance.spec.ts`
→ **5 passed**; scoped ESLint on seven changed frontend files → pass; `pnpm typecheck` → pass.
Synthetic browser checks on 127.0.0.1:3018 observed shared drafts across Maintenance/Backup,
header-only maintenance persistence, Telegram invalid-rule refusal, successful header rule save
and delivery-history rendering without its select error. Screenshots:
`output/browser/maintenance-compact.png`, `output/browser/telegram-compact.png`.
Existing missing translation/dev-environment warnings and a blocked synthetic avatar request
were not resolved. No real Telegram send/backend deployment test was run; browser/server stopped.
No commit or automatic next phase. Prior production/PostgreSQL acceptance limits remain.

### Scoped maintenance implementation — 2026-11-04

The explicit maintenance request was implemented independently of unfinished S01. It does
not complete S01, PLAN-0005 integrations, full disaster recovery, or release acceptance.
No migration: existing `app_settings`, `audit_events` and `notification_outbox` are reused.
No deployment, real provider send, production data operation or Git commit was performed.

Changed runtime owners: backend `app/modules/settings/{maintenance.py,router.py,service.py}`,
`app/core/{access_modes.py,config.py}`, `app/api/v1/router.py`, `app/main.py`,
`app/modules/backup/scheduler.py`, `app/modules/telegram/{worker.py,outbox.py,monitor.py}`;
frontend `app/components/document/{MaintenanceSettingsPanel.vue,SystemSettingsPage.vue}`,
`app/components/layout/MaintenanceNotice.vue`, `app/pages/maintenance.vue`,
`app/layouts/{default.vue,maintenance.vue}`, `app/composables/useApi.ts`,
`app/middleware/auth.global.ts`, `app/repositories/http/maintenance.ts`,
`app/types/maintenance.ts`, `app/utils/auth/maintenance.ts`,
`app/utils/constants/api-v1-endpoints.ts`, `app/config/settings-schemas.ts`, and en/km/zh locales.
Tests: new `backend/tests/test_maintenance.py`, updated `test_access_enforcement.py` and
`test_route_authorization.py`; new `frontend/tests/maintenance.spec.ts`.
Owning API/security/deployment docs describe the contracts and operator recovery boundary.
Preexisting dirty work was preserved; baseline hashes/times were captured before edits.

Executed evidence (existing environments, focused only):

- Backend: `uv run --no-sync pytest -q tests/test_maintenance.py tests/test_telegram.py tests/test_backup.py tests/test_access_enforcement.py tests/test_auth_sessions.py tests/test_route_authorization.py tests/test_frontend_api_contract.py --disable-warnings`
  → **54 passed**, 38 existing/deprecation/schema/OpenAPI warnings, 59.64s.
  Covers activation/confirmation/denial, stale revisions, blocked financial/public integration
  writes, preserved session records, persisted/scheduled state, no end-time reopening, failed
  backup/deployment, CSRF, notification routing/retry/consent and emergency DB-down status.
- Frontend: `pnpm exec vitest run tests/maintenance.spec.ts tests/auth-session.spec.ts`
  → **2 passed** in the new maintenance spec; `auth-session.spec.ts` does not exist and was
  not run. Corrected regression selection
  `pnpm exec vitest run tests/session.spec.ts tests/auth-renewal.spec.ts` → **13 passed**.
  Total executed frontend checks: **15 passed** across three actual specs.
- Scoped `uv run --no-sync ruff check` on the 14 touched Python files and scoped
  `pnpm exec eslint` on the 14 touched frontend source/test files → pass.
  `pnpm typecheck` → pass. `pnpm i18n:check` → pass, 3386 keys per locale.
  Scoped `git diff --check` → pass; 27 local links in the four affected docs resolve.
- Browser e2e runs with an isolated frontend on 127.0.0.1:3018 and synthetic API responses:
  desktop/mobile public page, administrator direct recovery/settings tab despite ancillary
  503s, hidden generic Save on Maintenance, and field validation/input preservation observed.
  Screenshots: `output/browser/maintenance-{desktop,mobile,settings-validation}.png`.
  Initial browser interception mistakenly matched a Vite dependency; corrected to API paths.
  One initial CLI inspection timed out; a fresh isolated browser completed recovery checks.
  Existing dev dependency scan warnings, missing `common.moreActions`, and deliberately
  refused synthetic branding/avatar requests are not claimed resolved. Browser/server stopped.
- Independent read-only DEEP review: recovery redirect, bounded/canonical group IDs, shared
  Save and system-notification opt-out issues fixed; fresh review reports no blocking issues.

Handoff: implementation complete in this scope; operational acceptance remains **unverified**.
Exact next step for an authorized release owner: follow the
[maintenance deployment/recovery procedure](../03-development/deployment-guide.md#maintenance-deployment-and-emergency-recovery)
on an isolated PostgreSQL stack, prove concurrent replica admission/revision behavior and
request drain, then exercise the actual backup/restore/deployment and Telegram destinations.
SQLite is not PostgreSQL-lock evidence. Reopening checks are operator attestations; no automatic
backup/deployment/drain verification was added. Emergency server configuration provides DB-independent
lockdown/status, not database repair or an auth bypass. No automatic next phase is authorized.

- 2026-11-04 folder-layout request: moved documentation into 00-project, 01-architecture,
  02-business, 03-development, 04-implementation and archive; updated navigation, generator,
  status-tool and reference paths. This changes no implementation status or S01–S13 order.

- 2026-11-04 documentation master task: added 44-page detail, Smart ERP targets and seventeen
  dependency-aware topic packages; corrected reusable-quotation/Finish expectations and stale
  S01 execution wording. No implementation status or historical test evidence was promoted.

- 2026-11-04: Removed PLAN-0003 and docs/qa on user request; completed cleanup outcomes are
  summarized in the Optional backlog. Updated the testing reference to focused-first gates.
- 2026-10-31: Reviewed draft documentation consolidated; the superseded finance plan is
  preserved in the proposal history below. S01 references now use the canonical inventory
  and requirement tables. Slice statuses and execution scope are unchanged.
- 2026-10-30: Approved discovery roadmap S01–S13 replaces the earlier verification scaffold.
  Prior milestone intentions are represented by secure access, configuration/operations,
  finance/reporting, UI/localization, integration/recovery and production acceptance above.
  Earlier first-slice finance proposal is summarized below as superseded.

## Superseded finance verification proposal

The old `PLAN-0002-first-slice.md` and draft implementation plan were reviewed and consolidated
here, then removed to eliminate the duplicate PLAN-0002 identity. Their proposal was to verify
financial_documents/posting and trial-balance reconciliation, map finance/report endpoints,
inspect targeted finance/report tests and `test_frontend_api_contract.py`, and record gaps.
Relevant source areas: `finance/service.py`, `posting.py`, `posting_rules.py`, reports engine
and ledger reports. SQLite cannot prove PostgreSQL triggers/locking; use separate safe
PostgreSQL evidence. No tests were executed by those draft plans and no finance slice was
completed. Their former next action is deferred to S05/S10; S01 remains first.
The old oversized quote-to-trial-balance slice is now split across S02–S10; configuration
comparison/rollback fits S03/S11, exports S09/S10, denial S01 and every applicable slice.
