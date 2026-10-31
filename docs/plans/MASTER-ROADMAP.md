# Master Roadmap

Last updated: 2026-10-31

## Approved milestones and ordered vertical slices

This is the approved S01–S13 mandatory-release roadmap for the existing application.
Statuses indicate slice verification/delivery, not absence of existing implementation.
S01 is the active resume pointer; verification is executed against the running app on
2026-10-31 (see PLAN-0002's evidence table: E09 backend deny matrix, E10 disposable PostgreSQL,
E11 all-page browser matrix, E12 per-page action gating for MOD-024/030/031). Remaining S01
work is recorded in PLAN-0002's Handoff.
Foundation creation did not start its execution.

| Slice | Milestone | Outcome area | Dependencies | Requirements | Status | Testable acceptance outcome |
|---|---|---|---|---|---|---|
| S01 | Secure Access | Login and Page Authorization | Existing auth/Casbin and 44-page inventory | LCS-001,002,009,013 | In Progress — verification executed (E09–E12; per-page action gating for remaining pages open) | Permitted login/pages/actions; denied API access and logout invalidation |
| S02 | Operational Continuity | Quotation to Service Order | S01; reference/config prerequisites | LCS-003,014 | Not Started | One source-linked order, preserved required snapshots, safe repeated conversion |
| S03 | Operational Continuity | Operational Execution | S02 | LCS-004,010 | Not Started | Actual containers, dynamic data and authorized attachments persist correctly |
| S04 | Operational Continuity | Service Charge to Financial Draft | S03; finance setup | LCS-004,005 | Not Started | Charge issue has no ledger effect; explicit conversion yields one draft |
| S05 | Accounting Integrity | Customer Invoice Posting | S04; accounts/rules/open period | LCS-005,006 | Not Started | Atomic unique balanced posting with source and rate snapshots |
| S06 | Accounting Integrity | Customer Receipt and Settlement | S05 | LCS-006,007 | Not Started | Partial/full allocation reconciles; excess allocation denied |
| S07 | Accounting Integrity | Supplier Bill and Payment | S05 | LCS-005,006,007 | Not Started | Supplier posting/payment/settlement reconcile with AP control |
| S08 | Accounting Integrity | Corrections and Accounting Period Controls | S05–S07 | LCS-006,009 | Not Started | Reversal preserves history; balanced manual journals; closed-period denial |
| S09 | Reliable Reporting | Operational Reporting | S02–S07 | LCS-008 | Not Started | Approved operational reports distinguish quoted/issued/draft/posted values |
| S10 | Reliable Reporting | Financial Reconciliation | S05–S08 | LCS-006,008 | Not Started | GL/TB/AR/AP/P&L/Balance Sheet/Cash Flow reconcile |
| S11 | Complete Business Functionality | Remaining Approved Page Workflows | S01; reference setup verified as needed earlier | LCS-001,009,014 | Not Started | Required remaining CRUD/config/admin/archive/audit actions verified |
| S12 | Recoverability | Isolated Recovery Drill | Representative earlier-slice data; approved safe recovery controls | LCS-012 | Not Started | Coordinated DB/files/config recovery passes integrity and measured-time checks |
| S13 | Release Acceptance | Cross-browser, Performance, Accessibility, and Business Acceptance | S01–S12; approved datasets/targets | LCS-010,011,013,015,016,019 | Not Started | Required browser/print/localization checks and authorized acceptance evidence |

## Active implementation plan

[Project status checklist](PROJECT-STATUS-CHECKLIST.md) is the verification index for requirements,
all 44 pages, technical evidence and remaining gaps. This roadmap controls sequence; the active
plan controls implementation scope. Checklist completion never authorizes unrelated work.

[PLAN-0002 — Access and Page Authorization](PLAN-0002-access-and-page-authorization.md)
is `In Progress` for planning only, with execution not started. Read its Handoff before work.
[PLAN-0001 template](PLAN-0001-template.md) defines future plan contents; only S01 is planned
in detail now. Create later plans when their slice starts and has a real need.
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

Apply [canonical DoD](../00-agent-handbook.md#definition-of-done) and per-plan acceptance.
Require exact executed evidence, meaningful failure/boundary tests, relevant PostgreSQL
financial guards, reconciled reports and safe recovery validation. Update status only after
verification. Critical/high defects and unresolved critical finance/security/integrity/
recovery/operational/legal issues block production; noncritical TBDs require explicit acceptance.
Capacity, performance, RPO/RTO, budget, WCAG target, retention/legal and named owners remain
open as recorded in [design brief](../09-design-brief.md).

## Optional backlog

Supporting audit: [PLAN-0003 — Codebase cleanup baseline](PLAN-0003-codebase-cleanup-baseline.md)
records the separately requested audit and two completed bounded cleanup batches (Excel dead
helper removal and global-search lifecycle fixes). Broader cleanup remains open; see its Handoff.
It does not replace S01, reorder S01–S13, or authorize broader refactors/database changes.

Should: Telegram delivery/monitoring improvements, nonblocking usability, additional safely
anonymized business scenarios; tablet and essential mobile viewing remain Should.
Could: Google Sheets mirror enhancements, optional integrations, advanced nonessential features.
Preserve existing functionality. Optional improvements are not release blockers unless needed
for a Must or explicitly committed. No extra business pages or speculative plans are authorized.

## History

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
