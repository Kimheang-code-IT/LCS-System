# Smart ERP modernization planning

Last updated: 2026-11-04. Documentation and planning only.

## Authority and execution model

[MASTER-ROADMAP](master-plan.md) remains the sole execution sequence: S01–S13.
The seventeen P00–P16 packages below organize the requested ERP topic coverage; they are
detailed backlog specifications, not seventeen active plans or permission to bypass S01.
This is the master index for these packages, not a replacement roadmap or duplicate PRD.

Only [PLAN-0002](plans/PLAN-0002-access-and-page-authorization.md#handoff) is active. Historical E09–E21
evidence exists, but remaining action gating/session journey and final review stay open.
No application implementation, migration, deployment or new business page is authorized by
this documentation task. A later implementation request selects the smallest remaining
approved slice and activates only the required package tasks.

## Package index and completion requirements

| Package | Topic / objective | Priority | Dependencies | Owning execution slice |
|---|---|---|---|---|
| [P00](phases/P00-documentation.md) | Documentation Audit and Cleanup: One navigable authority map, preserved unique history and explicit review limitations. | High | None; preserve dirty-worktree baseline | Documentation only |
| [P01](phases/P01-architecture-audit.md) | Architecture and Codebase Audit: A revision-specific route→guard→service→entity→test map and bounded gap list. | High | P00 | S01 baseline and owning later slices |
| [P02](phases/P02-shared-ui.md) | Shared UI and UX Components: Consistent, permission-aware forms/tables with no duplicated page framework. | High | P01 | Cross-cutting within each approved slice |
| [P03](phases/P03-master-data.md) | Master Data: Required reference data usable and safe under inactive, duplicate, archive and import cases. | High | P01,P02 | Prerequisite subsets before S02/S05; remaining S11 |
| [P04](phases/P04-configuration.md) | Dynamic Configuration: Valid published configurations and stable historical SO rendering. | High | P03 prerequisite catalogs; P02 | S03 prerequisites and remaining S11 |
| [P05](phases/P05-quotations.md) | Quotations: Reusable versioned offers, explicit commands and safe request deduplication. | High | P03,P04 prerequisites; S01 | S02 |
| [P06](phases/P06-service-orders.md) | Service Orders: Operational booking, editable copied pricing and controlled Finish without accounting effects. | High | P05; P04 operational snapshot prerequisite; S01 | S02–S03 |
| [P07](phases/P07-service-charges.md) | Service Charges: Valid revenue/cost visibility and once-only source-linked draft billing. | High | P06; P09 accounting setup subset before conversion | S04 |
| [P08](phases/P08-financial-documents.md) | Financial Documents: Atomic documents and partial/full customer/supplier settlement with reliable balances. | High | P07; P09 account/rule/open-period prerequisite; S01 | S05–S07, one document/settlement slice at a time |
| [P09](phases/P09-accounting.md) | Accounting and Posting Rules: Stable account mappings, balanced immutable journals and custom-date OPEN-period controls. | High | P03 finance references; P14.1 identity/numbering prerequisite; S01 | Setup before S05; corrections/custom periods in S08 |
| [P10](phases/P10-period-closing.md) | Smart Accounting Period Closing: Authorized review→confirm→lock and reasoned reopen preserving historical evidence. | High | P09; P11.1 GL/TB/AR/AP reconciliation baseline | S08 control work with S10 reconciliation evidence |
| [P11](phases/P11-financial-reports.md) | Financial Reports: Reconciled posted reports with explicit date/currency/sign/whole-export semantics. | High | P09; P08 scoped posted/settlement fixture for full verification | S10 |
| [P12](phases/P12-operations-reports.md) | Operations Reports: Accurate SO register/status/physical-container/profitability views. | High | P06,P07; P08 posted comparison fixture | S09 |
| [P13](phases/P13-dashboard.md) | Dashboard: Source-defined permitted KPIs with consistent interval/as-of/currency. | Medium after correctness prerequisites | P11,P12; S01 | S09–S10 aggregates; S13 presentation acceptance |
| [P14](phases/P14-administration.md) | Administration: Safe identities/numbering/configuration and preserved searchable history. | High prerequisites; remaining Medium | P01,P02; P03 for referenced vocabularies | S01 auth prerequisite; S02–S08 numbering; remaining S11 |
| [P15](phases/P15-integration.md) | Cross-Module Integration: Repeatable source-linked quotation→SO→charge→invoice→settlement→reports journey plus supplier/correction/closing branches. | High | Relevant P03–P14 accepted subsets; S01–S11 verification | S02–S11 integration, final scenarios before S13 |
| [P16](phases/P16-final-review.md) | Final Quality and Production-Readiness Review: Evidence-based release decision with explicit business/security/finance/recovery sign-off. | High release gate | P15; S12 authorized isolated recovery; S01–S12 acceptance | S13 |

Each package includes current evidence, requirements, layer/permission scope, four numbered
tasks with dependency/change/validation/acceptance, error handling, testing, DoD and exclusions.
There are 68 bounded tasks. [Dependencies](dependency-map.md) defines prerequisite subsets;
[tracker](phase-tracker.md) records status; [acceptance](acceptance-criteria.md) links requirements
to code/test discovery. Acceptance never follows from a package's existence.

## How one future session executes

1. Read AGENTS, handbook, roadmap and active Handoff; current user scope controls.
2. Read only relevant inventory/profile/requirement/package and source/tests.
3. Record branch/dirty paths/timestamps and select one testable task; name FAST/STANDARD/DEEP.
4. State existing behavior and demonstrated gap. If tests meet acceptance, verify without rewrite.
5. Plan actual layer/API/schema/permission changes first; preserve current callers/history.
6. Implement the bounded gap using existing components/services, without new dependencies unless justified.
7. Run applicable focused gates; DEEP requires integration/regression/denial, PostgreSQL where
   relevant and reviewer. Browser/print/localization evidence is distinct from node/SQLite tests.
8. Update owning docs and evidence, task status, active Handoff and exact next action. Stop.

Do not repeatedly scan all docs for a small change, activate P08/P09 as one giant accounting
rewrite, or wait until S11 to validate prerequisites already needed by S02–S08.
No new feature/user-guide/release-note documents are needed until a real feature/release needs them.

## Shared acceptance and evidence record

A completed task records: requirement/page/task IDs; source revision and dirty-state caveat;
exact command and cwd; safe environment and data; expected/observed outcome; pass/fail/skip counts;
refusal/concurrency/rollback evidence where applicable; remaining limitations; reviewer findings.
A test file's existence is not passing evidence. Business sign-off and production readiness
remain distinct from automated checks.

## Open design decisions

- Period Closing workspace inside MOD-013 preserves 44 pages; a standalone page requires scope approval.
- Missing-period policy: current resolver auto-creates OPEN month; decide explicit setup/refusal
  vs approved creation before S08 acceptance. No frontend Year requirement.
- Two disjoint custom periods with the same start month conflict with retained year/month key;
  prove with tests before proposing additive constraint changes.
- Closing cutoff/materiality/reconciliation ownership and reproducible report preservation need
  finance/operations decisions. Structural integrity blockers are not optional.
- Precision mismatch (currency 0–6 vs NUMERIC(19,4), quotation two-decimal rounding) needs a
  compatible policy, with historical amounts preserved.
- Capacity/performance/RPO/RTO/retention/WCAG compliance targets and named owners remain unapproved.
- Sanitized legacy testing/deployment guides are required for exhaustive documentation reconciliation.

## Handoff

Status: documentation modernization written and validated as recorded in
[testing](../03-development/testing-guide.md#documentation-modernization-validation);
P00 remains NEEDS_REVIEW for the withheld-guide/full legacy reconciliation limit.
Completed: navigation, current-file audit, 44-page specification, target business rules and
17 packages/68 tasks; existing S01–S13 roadmap preserved.
No feature implementation or current application acceptance is claimed.
Next implementation task: remaining S01 per-page action-button gating and isolated
renewal/expiry journey, following PLAN-0002; source actions now follow current lifecycle,
not the old Send/Accept examples. Start no later slice automatically.
Documentation follow-up: sanitized review of the two withheld guides and complete detailed
legacy/UI/source reconciliation before retiring any retained file.
Commit status: uncommitted; no commit authorized.

