# ERP package tracker

Last updated: 2026-11-04. [Execution roadmap](master-plan.md) owns slice status;
this file owns topic-package/task planning status only.

NOT_STARTED = no package acceptance execution recorded; IN_PROGRESS = active scoped work;
BLOCKED = cannot proceed without required prerequisite/decision; NEEDS_REVIEW = incomplete or
conflicting evidence; COMPLETED = all task acceptance and required checks recorded.
Do not change a whole phase to COMPLETED because one subtask or historical test passed.

| Phase | Priority | Status | Dependencies | Verification | Notes |
|---|---|---|---|---|---|
| [P00 Documentation Audit and Cleanup](phases/P00-documentation.md) | High | NEEDS_REVIEW | None; preserve dirty-worktree baseline | Documentation checks in testing reference; no runtime gates | Written deliverables present; exhaustive sanitized legacy review open |
| [P01 Architecture and Codebase Audit](phases/P01-architecture-audit.md) | High | NOT_STARTED | P00 | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P02 Shared UI and UX Components](phases/P02-shared-ui.md) | High | NOT_STARTED | P01 | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P03 Master Data](phases/P03-master-data.md) | High | NOT_STARTED | P01,P02 | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P04 Dynamic Configuration](phases/P04-configuration.md) | High | NOT_STARTED | P03 prerequisite catalogs; P02 | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| P05 | [P05 Quotations](phases/P05-quotations.md) | High | COMPLETED | P03,P04 prerequisites; S01 | PLAN-0006: 56 backend + 3 PG concurrency + 4 browser journey tests (2026-11-04) | Defects fixed: create-save label, silent line seeding; Chromium-only limits recorded |
| [P06 Service Orders](phases/P06-service-orders.md) | High | NOT_STARTED | P05; P04 operational snapshot prerequisite; S01 | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P07 Service Charges](phases/P07-service-charges.md) | High | NOT_STARTED | P06; P09 accounting setup subset before conversion | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P08 Financial Documents](phases/P08-financial-documents.md) | High | IN_PROGRESS | P07; P09 account/rule/open-period prerequisite; S01 | Scoped printing verified in PLAN-0004 | Posting/settlement/package acceptance remains open |
| [P09 Accounting and Posting Rules](phases/P09-accounting.md) | High | NOT_STARTED | P03 finance references; P14.1 identity/numbering prerequisite; S01 | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P10 Smart Accounting Period Closing](phases/P10-period-closing.md) | High | NOT_STARTED | P09; P11.1 GL/TB/AR/AP reconciliation baseline | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P11 Financial Reports](phases/P11-financial-reports.md) | High | NOT_STARTED | P09; P08 scoped posted/settlement fixture for full verification | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P12 Operations Reports](phases/P12-operations-reports.md) | High | NOT_STARTED | P06,P07; P08 posted comparison fixture | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P13 Dashboard](phases/P13-dashboard.md) | Medium after correctness prerequisites | NOT_STARTED | P11,P12; S01 | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P14 Administration](phases/P14-administration.md) | High prerequisites; remaining Medium | NOT_STARTED | P01,P02; P03 for referenced vocabularies | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P15 Cross-Module Integration](phases/P15-integration.md) | High | NOT_STARTED | Relevant P03–P14 accepted subsets; S01–S11 verification | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |
| [P16 Final Quality and Production-Readiness Review](phases/P16-final-review.md) | High release gate | NOT_STARTED | P15; S12 authorized isolated recovery; S01–S12 acceptance | No fresh package acceptance run | Existing implementation may satisfy portions; verify first |

## Scoped agent setup (2026-11-04)

COMPLETED: instruction/context/skill setup only; see
[setup verification](../03-development/agent-tooling.md#setup-verification-record).
P00/P01/P02 and S01 acceptance are not promoted by this environment task. Existing P00
semantic-review gaps and all unfinished ERP task rows remain open. Resume S01 only on request.

## Smart Settings planning package (2026-11-04)

[PLAN-0005](plans/PLAN-0005-settings-integrations.md) refines existing package subsets, not new
P17+ phases. A is source/documentation audit only; existing package/slice status is preserved.

| Scoped phase | Owner | Status | Remaining evidence |
|---|---|---|---|
| A Audit/specifications | P00/P01/P14 | COMPLETED (documentation only) | Structural evidence in PLAN-0005; no runtime pass |
| B Telegram/SO/Developer alerts | P06/P14/P15; S03/S11 | NOT_STARTED | NOT-001–005; preserve private recovery |
| C Email/password recovery | P14/S01/S11 | NOT_STARTED | SET-002/MAIL-001/REC-001 and migration |
| D Settings/security foundation | P14/S01 | NOT_STARTED | Grants, secrets, concurrency and SEC-001 |
| E R2/Drive backup/restore | P14; S12 | NOT_STARTED | BAK-001–008, isolated recovery/measured targets |
| F Master/Configuration IO | P03.3/P04; S11 | NOT_STARTED | IO-001–007, draft graphs and audit |
| G Integration review | P15/P16; S12/S13 | NOT_STARTED | Fault/denial/recovery/owner evidence |

## P05 execution (2026-11-04, PLAN-0006)

| Task | Status | Evidence / remaining work |
|---|---|---|
| 05.1 | COMPLETED | Lifecycle/revisions verified: 56 backend tests incl. revision history, SUBMITTED round trip, legacy SENT/ACCEPTED readable/convertible; no Send/Accept UI |
| 05.2 | COMPLETED | One quotation → many independent orders (backend + journey copy assertions) |
| 05.3 | COMPLETED | Same-key replay returns the same order (API + PG barrier); unrelated keys convert independently; deleted order nulls the re-quotation link (PG) |
| 05.4 | COMPLETED | Conversion gates hold: conflicting quantities/missing quotation 422, delete-with-SO 409, FINISHED lock 409; PG concurrency evidence fresh on disposable DB; defects fixed (save label, silent line seeding) |

S02 Completed. Next slice S03 (P06 operational execution).

## P06 authorized files batch (2026-11-05, PLAN-0007)

| Task | Status | Evidence / remaining work |
|---|---|---|
| 06.2 (files portion) | COMPLETED | Authorized files upload/preview/delete through the Files tab, viewer refusal (e2e/attachments.spec.ts 2 passed, E26); defects fixed: relative-URL preview drop, missing file-table Delete action, late-attachment repopulation |

## P06 remaining acceptance batch (2026-11-05, PLAN-0008)

| Task | Status | Evidence / remaining work |
|---|---|---|
| 06.1 | COMPLETED | Source selection + saved overrides verified by the conversion/reuse suites (quotation mandatory, partial-save merge, per-order snapshots; E25 PG race not repeated) — E27 |
| 06.2 | COMPLETED | Physical boxes normalized/duplicated-refused, payment-linked deletion refused, required dynamic component values enforced, authorized files verified in PLAN-0007 — E27/E26 |
| 06.3 | COMPLETED | Finish idempotent + audited, FINISHED lock on every operational write path (`_ensure_order_editing`), reopen clears the stamp, delete conflicts refused, movements/milestones inactive refusal; no journal on save/finish — E27 |
| 06.4 | COMPLETED | One demonstrated integrity gap fixed: movement-sequence unique constraint (migration c0d1e2f3a4b5, verified apply/downgrade/upgrade on dev PG); no other mismatch found by the executed suites |

S03 Completed 2026-11-05. Deferred: storage recovery drill → S12; DATA-011 catalog scope → S11;
movements/milestones browser tab journey → NT02. Next slice S04 (P07 service charges).

> S04 closed 2026-11-05 (all four P07 tasks; PLAN-0009–0012, E28–E31). Deferred: per-currency
> report presentation → S09/S10. Next slice S05 (customer invoice posting; P08 task table).

## P08 posting-contract batch (2026-11-05, PLAN-0013)

| Task | Status | Evidence / remaining work |
|---|---|---|
| 08.1 | COMPLETED | Posting contract verified read-only + defect fixed (audit-replay duplication) + PG race: two simultaneous posts → one journal one posting link (Dr=Cr=500); replay idempotent; E32 |
| 08.2 | COMPLETED | Settlement/allocation closed (PLAN-0014/E33): partial/full/unapplied verified; cross-party allocation now refused (`PARTY_MISMATCH`); replay audits once; PG race: two simultaneous allocations → one accepted + one typed refusal, no negative balances; AR control nets 0 == receivables |
| 08.3 | COMPLETED | Supplier flow closed (PLAN-0015/E34, tests-only): bill Dr 5010/Cr 2010 + payment Dr 2010/Cr 1020 via shared services; 300 bill partial(100)+full(200), expense once, AP 2010 nets 0 == payables; cross-supplier refused; PG race (lcs_verify8) one accepted + one refusal |
## P10 period closing feature batch (2026-11-05, PLAN-0017/E36)

| Task | Status | Evidence / remaining work |
|---|---|---|
| 10.1 | COMPLETED | Check result/evidence contract (code/name/PASS-WARNING-BLOCKED-NOT_AVAILABLE/severity/message/count/recommended action) in finance/period_closing.py |
| 10.2 | COMPLETED | Bounded read-only review: 8 checks reusing the report/repository services + period financial summary + audit history |
| 10.3 | COMPLETED | Atomic close: period-row FOR UPDATE + in-lock blocking re-validation; posting/reversal join the same serialization; backdated refusals; PG race evidence |
| 10.4 | OPEN | Closing-report evidence retention, stale-review acknowledgments, reopening dependency checks (S09/S10 baseline dependency) |

S05 CLOSED 2026-11-05 (PLAN-0016/E35: 08.1–08.4 COMPLETED; deferred: allocation
period-gate → S06/S08, audit split → S06+, per-currency presentation → S09/S10).
Next slice S06 (customer receipt/settlement; FLOW-010).

> S05 closed 2026-11-05 (PLAN-0016/E35 acceptance review: 08.1–08.4 COMPLETED; deferred:
> allocation period-gate → S06/S08, audit split → S06+, per-currency presentation → S09/S10).
> Next slice S06 (customer receipt/settlement; FLOW-010).

## P07 charge-map batch (2026-11-05, PLAN-0009)

| Task | Status | Evidence / remaining work |
|---|---|---|
| 07.1 | COMPLETED | Calculation/pricing-source/override/issue-boundary/bill-once maps recorded (charge schema Numeric(19,4)/12,3, backend-authoritative Decimal, manual-only pricing, rate snapshot at invoice, containers by id); `tests/test_charge_tax_round_trip.py + test_finance_automation.py + test_job_finance_entries.py` 14 passed; demonstrated mismatch recorded: issue auto-creates the finance draft vs workflows.md §9 → 07.2 |
| 07.2 | COMPLETED | Issue isolation fixed (PLAN-0010/E29): auto-draft removed from `issue_charge`; ISSUED + audit only; explicit `create-finance-invoice` (convert code) is the sole conversion path; Issue button gate → `service_charge.submit`; 82 focused backend tests + frontend gates + 825 unit pass |
| 07.3, 07.4 | 07.3 COMPLETED | Bill-once closed (PLAN-0011/E30): charge-row lock covers check-and-create; DB backstop partial unique index `uq_fin_doc_source_charge` (migration b7c8d9e0f1a2, rehearsed on disposable DB with downgrade/re-upgrade); conversion `idempotency_key` replay/conflict; PG race fixture 4 passed (two simultaneous converts → one draft, different keys → one draft, same-key concurrent → one result, DB refuses dup link); SQLite 114 passed |
| 07.4 | COMPLETED | Profit layers closed (PLAN-0012/E31): finance layers = base-currency ledger sums (rate snapshots, GL precedent), charge layers grouped per document currency with explicit mixed-currency flags, uninvoiced attributed by source links (converted charge → 0, never double-counted); read-only report (no journal writes); deferred: per-currency presentation + container-level P&L → S09/S10 (no cost/allocation source in schema). S04 COMPLETE 2026-11-05 |

Remaining S04 risks: report mixed-currency sums (S09/S10 owner), ignored `Idempotency-Key` on charge issue/convert (07.3), caller-supplied duplicate charge_no → 500 (note only).

## Task tracking rule

The four task rows in each package are the stable task IDs (00.1–16.4).
At creation P00 writing/navigation tasks have documentation evidence, but exhaustive review
and final semantic reconciliation remain open; all implementation tasks are unexecuted here.
When activating a task, add its status/evidence reference below without duplicating requirements.

| Task | Status | Evidence / remaining work |
|---|---|---|
| 00.1 | NEEDS_REVIEW | All 27 current documentation/reference paths classified; two guides withheld; targeted rather than exhaustive semantic review |
| 00.2 | NEEDS_REVIEW | Current navigation and canonical workflow conflicts repaired; retained detailed references require further reconciliation |
| 00.3 | COMPLETED | 44 MOD records, 17 nonempty packages and 68 task rows; see recorded structural checks |
| 00.4 | NEEDS_REVIEW | Structural/task-only validation recorded; exhaustive semantic pass cannot be claimed |
| P08 printing subset | COMPLETED | [PLAN-0004](plans/PLAN-0004-financial-printing.md): stored scope, actual containers, denial/read-only tests and Chromium A4 PDFs; no claim of full P08 acceptance |
| P02/P16 printing checks | NEEDS_REVIEW | Shared print components and Chromium output verified in PLAN-0004; cross-browser and whole-package acceptance remain open |

The folder migration changes no implementation status in project-status-checklist.md or
00-project/feature-status.md; only locations/references are updated.
S01 is COMPLETED 2026-11-04 (PLAN-0002 closed; evidence E09–E24 in the checklist; limits in
its Handoff). S02 is COMPLETED (PLAN-0006). S03 is COMPLETED 2026-11-05 (PLAN-0007 E26 +
PLAN-0008 E27; deferred items carry recorded owners). S04 is COMPLETED 2026-11-05
(PLAN-0009–0012, E28–E31; per-currency presentation deferred to S09/S10). S05 is
COMPLETED 2026-11-05 (PLAN-0013–0016, E32–E35; deferred debts carry owners). S06 is the
next slice; no P package is a second active implementation plan.

