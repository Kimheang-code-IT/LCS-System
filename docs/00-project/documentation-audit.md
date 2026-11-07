# Documentation modernization audit

Current layout: see the folder-layout migration section below. Earlier sections retain the
previous modernization audit snapshot; their old counts/structure decisions are historical.

Audit date: 2026-11-04 (Asia/Bangkok). Scope: documentation, requirements, architecture review and planning only.
Baseline: branch `dev`, HEAD `a219a8c` (2026-11-01); the working tree is the source snapshot, not HEAD alone.

## Safety and review evidence

Before documentation edits, `git status --short`, branch, HEAD, documentation timestamps and a
SHA-256 manifest of 840 existing non-secret tracked/untracked files were captured outside the
repository. Existing backend/frontend changes, three untracked migrations, test changes,
generated SQL, modified documentation and deleted tooling/QA files are other work. Preserve them.
No reset, clean, restore, stage, commit, application write or migration execution is authorized here.
Private keys and environment files are excluded. Hash comparisons establish task-only changes.

During the task the hash comparison detected concurrent writes to
backend/alembic/versions/a8c0e2e4b6d8_accounting_period_management.py,
backend/tests/sql/integrity_guards.sql and backend/tests/test_record_status.py.
The documentation tools did not edit those files. They were preserved and reported separately;
therefore no claim is made that the shared working tree's application files stayed globally
unchanged while this task ran. Source findings remain a time-bounded review snapshot.

This audit inventories every file currently under docs except private-key material: 26 Markdown
files and one generated SQL reference. It is a structural and targeted semantic audit, not a
claim that every line of every legacy report has been verified. Two legacy guides were withheld
by the context gateway (`secret.redacted, redaction.incomplete`); they must not be bypassed or
deleted. No legacy file qualifies for safe deletion in this pass. The old inventory in
[documentation standards](../03-development/documentation-standards.md) is historical, not today's filesystem.

## Current-file disposition

All paths below are relative to docs. Dates of prior claims are historical evidence; the last
meaningful business update is not reliably determinable from filesystem times or commit date
in this dirty checkout. The baseline retains exact modification timestamps. UPDATE means a
documentation correction/addition in this task; KEEP may include a future review recommendation.

| Current path | Purpose / unique contents | Accuracy, overlap or missing information | Action and destination / dependency |
|---|---|---|---|
| 00-agent-handbook.md | Reading order, task levels, DoD, resume | Sound; linked handoff directory absent | UPDATE link to existing plan Handoff; retain agent entry point |
| 01-system-architecture.md | Canonical module/dependency architecture | Stack matches manifests; versions and reusable boundaries need detail | UPDATE; retain detailed architecture cross-reference |
| 02-data-model.md | Canonical integrity/migration rules and entity groups | Quotation-only-once legacy invariants outdated; SQL is generated | UPDATE quotation invariants and period limitations; no SQL edit |
| 03-security-access-control.md | Session/Casbin, threat and audit requirements | Detailed permission catalog is supplementary; no new engine needed | KEEP; closing target inherits backend permission rules |
| 04-record-workflow-lifecycle.md | Canonical transitions, retry semantics | One-order restriction and Active/Inactive-only SO contradict dirty current code and new request | UPDATE authoritative quotation/SO/period rules |
| 04_functional_design.md | Detailed use cases, error/transaction catalog, ER/process/data-flow diagrams | Old Send/Accept, prepared containers and duplicate conversion conflict | KEEP unique detail; canonical lifecycle overrides legacy examples; full reconciliation pending |
| 05-api-specification.md | Canonical endpoint/session/error catalog | Static historical count is stale; new custom-period and Finish contracts need delta evidence | UPDATE reviewed contract delta; retain complete older catalog |
| 05_solution_architecture.md | Detailed layering, posting strategies, hardcoded configuration register | Overlaps 01 but retains unique mappings and migration references | KEEP; 01 owns decisions, this file implementation detail |
| 06-operations-runbook.md | Deployment/recovery/incident requirements | Does not prove daily backup or actual recovery; detailed guide retained | KEEP; operational changes excluded |
| 06_database_design.sql | Generated table/column/constraint SQL | Already modified before task; generated, not migration execution proof | KEEP unchanged; generator/test_schema_docs.py dependency |
| 07-adr-log.md | Accepted decision index | Links absent decisions directory | UPDATE to record detail inline until a real ADR file is needed |
| 07_api_documentation.md | Compatibility pointer to 05 | Already consolidated; no competing catalog | KEEP; retained inbound legacy references |
| 08-app-flow.md | Canonical business journeys and retained SOP | Send/Accept, prepared actual rows, no Finish, retry wording stale | UPDATE journey and SOP to lifecycle authority |
| 08_frontend_and_ui_design.md | Detailed components, routes, validation, reporting UI | Historical route guard table incomplete/stale; excludes newer reference pages | KEEP; feature inventory owns current page verification; no claim this table is current |
| 09-design-brief.md | Approved 44 pages, stable LCS/BR/FR/NFR IDs | BR-005/006 outdated; proposed closing page would increase count | UPDATE requirements; specify closing within existing period page; standalone page proposed only |
| 09_roles_and_permissions.md | Detailed Casbin compilation/payload catalog/history | Must compare current permissions.py before future endpoint work | KEEP; source/test dependencies require exact path |
| 10-coding-conventions.md | Canonical stack, errors, shared validation, tooling | Blanket read-only E2E statement conflicts with mutating workflow specs | UPDATE safe isolated test guidance; retain current patterns |
| 10_testing_and_quality.md | Detailed historical quality/risk evidence | Gateway withheld content; not exhaustively reviewed | KEEP unchanged; no acceptance promoted from historical claims |
| 11-testing-and-quality.md | Canonical focused-first gates | Existing link from standards targets removed section | UPDATE documentation validation section and evidence |
| 11_deployment_and_security.md | Detailed deploy/hardening/recovery instructions | Already modified; gateway withheld content | KEEP unchanged; owner must provide sanitized reviewable content for complete reconciliation |
| 12-documentation-standards.md | Ownership, prior consolidation inventory | References absent source prompt, reports/directories and old validation anchor | UPDATE navigation/authority; retain old disposition table explicitly as history |
| 12_feature_status.md | Tool-required feature evidence and change-prefix map | Historical implementation percentages cannot establish current acceptance | KEEP unchanged; scripts/feature-status.mjs requires exact file and markers |
| 13-git-workflow.md | Branch/commit/PR/release policy | Links absent handoff convention | UPDATE to current plan Handoff convention; commits remain explicit |
| plans/MASTER-ROADMAP.md | S01–S13 execution sequence | Says both executed and not started; stale closure/reuse expectations | UPDATE; preserve sequence and active S01 pointer |
| plans/PLAN-0001-template.md | Reusable implementation slice template | Valid; later detailed task packages supplement it | KEEP |
| plans/PLAN-0002-access-and-page-authorization.md | Active S01 evidence/Handoff | E09–E21 historical; next-action Send/Accept examples stale | UPDATE documentation handoff note only; no new runtime result |
| plans/PROJECT-STATUS-CHECKLIST.md | Extensive per-page verification index | Existing edits and evidence; not read wholesale per AGENTS | KEEP unchanged; inventory supplements requirements, does not overwrite status evidence |

## Consolidation and safe preservation

No files were moved, archived or deleted by this task. This is deliberate: the earlier cleanup
already consolidated the API pointer and foundation duplicates, while remaining files contain
unique implementation/history or required inbound references. Creating the suggested four
parallel numbered directory trees would duplicate the established canonical docs/00–13.
The requested architecture/business/development topics therefore stay with those owners.

New, nonempty documents have distinct purposes:

- [README](../README.md): navigation and focused agent reading.
- [Feature inventory](feature-inventory.md): all 44 page contracts, evidence boundaries and acceptance.
- [Smart ERP requirements](../02-business/accounting-and-posting.md): deterministic automation, target closing and report semantics.
- [Modernization planning index](../04-implementation/planning-guide.md): package-to-slice mapping and execution instructions.
- [Phase tracker](../04-implementation/phase-tracker.md), [dependency map](../04-implementation/dependency-map.md),
  [acceptance matrix](../04-implementation/acceptance-criteria.md), and seventeen bounded phase packages.
  These are planning detail explicitly requested now, not seventeen active implementation plans.

## Material findings and risk register

| ID | Evidence / issue | Consequence and planned verification |
|---|---|---|
| DOC-01 | quotations/service.py convert_revision permits repeated distinct orders, deduplicates same key | Old one-order requirement superseded by requested reuse; test revision snapshots, retry payload identity and concurrent same-key requests in S02 |
| DOC-02 | operations/service.py save_service_order / finish_service_order; models have finish metadata | Finish is operational, never ledger posting; UI config still lists ACTIVE_STATUS; verify all list/action/denial paths |
| DOC-03 | finance/service.py create_period derives year/month; models retain unique year/month | Two disjoint custom periods starting in same month may still conflict; additive schema decision only after test evidence |
| DOC-04 | finance/service.py resolve_period creates an OPEN calendar month if no period matches | Missing-period policy and custom-range overlap race require explicit target validation; no silent accounting-policy acceptance |
| DOC-05 | finance/service.py update_period accepts status; close_period commits directly | Test generic update cannot bypass close permission/review; test concurrent close vs posting and audit atomicity before acceptance |
| DOC-06 | close_period has no review checklist in inspected body; engine.REPORTS has GL/TB only | Rich Period Closing is MISSING; accounting-period management PARTIAL; other report registry entries must not be invented |
| DOC-07 | docs/README absent; links to deleted source prompt, decisions and handoff dirs | Repair navigation using existing canonical documents; do not restore speculative empty directories |
| DOC-08 | Legacy functional/UI architecture overlap remains | Preserve unique registers/diagrams; current lifecycle, scope and source evidence win over obsolete examples |
| DOC-09 | Two legacy guides withheld; checklist deliberately read only by relevant section | Exhaustive semantic reconciliation remains incomplete; record NEEDS_REVIEW, never claim a full audit pass |
| DOC-10 | Existing code and untracked migrations are not runtime-verified here | PARTIAL/NEEDS_REVIEW statuses; migration presence is not deployed schema evidence |
| DOC-11 | Twelve report definitions do not imply identical filter/export implementations | Reconcile each handler, date basis, currency and control totals in S09/S10 |

## Completion and validation record

Task output: 25 new Markdown files and 16 existing Markdown files updated (including root
README/AGENTS). No files moved/archived/removed by this task; the 27 existing docs/reference
paths remain. The [actual tree](../README.md#current-documentation-tree) lists the result.

See [documentation validation](../03-development/testing-guide.md#documentation-modernization-validation)
for executed checks and limits. Application verification and production readiness are not
established by this task. Remaining sanitized legacy review is a documentation gap, not
authorization to implement S01 or another slice.

Observed final structural results: 44 unique page records/routes, 17 packages with all nine
required sections, 68 task rows, 504 checked local links/anchors with no failures, no trailing
whitespace, and no task deletions. Two withheld guides are excluded from link/content review.
Preservation comparison found 821 unchanged baseline files, 16 task-modified Markdown files,
25 added Markdown files and the three separately reported concurrent non-document writes.


## Folder layout migration

On 2026-11-04 the user explicitly requested the folder structure shown in their reference.
This supersedes the earlier decision to retain flat docs/00–13 paths. Sections above record
that earlier audit snapshot; the table below is the current location map. All 51 existing
non-index documentation/reference files were moved, not discarded. Root docs/README.md is
now navigation; 00-project/README.md, project-overview.md and archive/README.md add focused
entry points. The master plan, active S01 Handoff, 44 pages and 17 packages/68 tasks remain.

Two gateway-withheld guides were moved to archive without reading/reworking their content.
Their hashes match the starting files; internal historical links remain unreviewed. Immutable
Alembic migrations keep original documentation paths in historical comments; resolve them
using this table rather than editing migration history. The private key was not moved/read.

Schema-generator/test and feature-status paths were updated to the new locations. Generated
SQL was regenerated through its generator, never hand-edited; no DDL/model/migration change
was introduced by this folder migration. Other non-document edits are documentation-path
references/comments only. Existing user edits were retained before mechanical replacements.

| Former path | Current location |
|---|---|
| `docs/00-agent-handbook.md` | [docs/03-development/ai-agent-guidelines.md](../03-development/ai-agent-guidelines.md) |
| `docs/01-system-architecture.md` | [docs/01-architecture/system-architecture.md](../01-architecture/system-architecture.md) |
| `docs/02-data-model.md` | [docs/01-architecture/database-design.md](../01-architecture/database-design.md) |
| `docs/03-security-access-control.md` | [docs/01-architecture/security-and-permissions.md](../01-architecture/security-and-permissions.md) |
| `docs/04-record-workflow-lifecycle.md` | [docs/02-business/business-rules.md](../02-business/business-rules.md) |
| `docs/04_functional_design.md` | [docs/02-business/functional-reference.md](../02-business/functional-reference.md) |
| `docs/05-api-specification.md` | [docs/01-architecture/api-design.md](../01-architecture/api-design.md) |
| `docs/05_solution_architecture.md` | [docs/01-architecture/implementation-reference.md](../01-architecture/implementation-reference.md) |
| `docs/06-operations-runbook.md` | [docs/03-development/deployment-guide.md](../03-development/deployment-guide.md) |
| `docs/06_database_design.sql` | [docs/01-architecture/database-design.sql](../01-architecture/database-design.sql) |
| `docs/07-adr-log.md` | [docs/01-architecture/architecture-decisions.md](../01-architecture/architecture-decisions.md) |
| `docs/07_api_documentation.md` | [docs/archive/api-compatibility-reference.md](../archive/api-compatibility-reference.md) |
| `docs/08-app-flow.md` | [docs/02-business/workflows.md](../02-business/workflows.md) |
| `docs/08_frontend_and_ui_design.md` | [docs/02-business/ui-ux-standards.md](../02-business/ui-ux-standards.md) |
| `docs/09-design-brief.md` | [docs/00-project/requirements.md](../00-project/requirements.md) |
| `docs/09_roles_and_permissions.md` | [docs/01-architecture/permission-catalog.md](../01-architecture/permission-catalog.md) |
| `docs/10-coding-conventions.md` | [docs/03-development/coding-standards.md](../03-development/coding-standards.md) |
| `docs/10_testing_and_quality.md` | [docs/archive/testing-quality-history.md](../archive/testing-quality-history.md) |
| `docs/11-testing-and-quality.md` | [docs/03-development/testing-guide.md](../03-development/testing-guide.md) |
| `docs/11_deployment_and_security.md` | [docs/archive/deployment-security-history.md](../archive/deployment-security-history.md) |
| `docs/12-documentation-standards.md` | [docs/03-development/documentation-standards.md](../03-development/documentation-standards.md) |
| `docs/12_feature_status.md` | [docs/00-project/feature-status.md](../00-project/feature-status.md) |
| `docs/13-git-workflow.md` | [docs/03-development/git-workflow.md](../03-development/git-workflow.md) |
| `docs/documentation-audit.md` | [docs/00-project/documentation-audit.md](../00-project/documentation-audit.md) |
| `docs/feature-inventory.md` | [docs/00-project/feature-inventory.md](../00-project/feature-inventory.md) |
| `docs/smart-erp-requirements.md` | [docs/02-business/accounting-and-posting.md](../02-business/accounting-and-posting.md) |
| `docs/plans/MASTER-ROADMAP.md` | [docs/04-implementation/master-plan.md](../04-implementation/master-plan.md) |
| `docs/plans/PLAN-0001-template.md` | [docs/04-implementation/plan-template.md](../04-implementation/plan-template.md) |
| `docs/plans/PLAN-0002-access-and-page-authorization.md` | [docs/04-implementation/plans/PLAN-0002-access-and-page-authorization.md](../04-implementation/plans/PLAN-0002-access-and-page-authorization.md) |
| `docs/plans/PROJECT-STATUS-CHECKLIST.md` | [docs/04-implementation/project-status-checklist.md](../04-implementation/project-status-checklist.md) |
| `docs/plans/ERP-MODERNIZATION.md` | [docs/04-implementation/planning-guide.md](../04-implementation/planning-guide.md) |
| `docs/plans/ERP-PHASE-TRACKER.md` | [docs/04-implementation/phase-tracker.md](../04-implementation/phase-tracker.md) |
| `docs/plans/ERP-DEPENDENCIES.md` | [docs/04-implementation/dependency-map.md](../04-implementation/dependency-map.md) |
| `docs/plans/ERP-ACCEPTANCE.md` | [docs/04-implementation/acceptance-criteria.md](../04-implementation/acceptance-criteria.md) |
| `docs/plans/phases/P00-documentation.md` | [docs/04-implementation/phases/P00-documentation.md](../04-implementation/phases/P00-documentation.md) |
| `docs/plans/phases/P01-architecture-audit.md` | [docs/04-implementation/phases/P01-architecture-audit.md](../04-implementation/phases/P01-architecture-audit.md) |
| `docs/plans/phases/P02-shared-ui.md` | [docs/04-implementation/phases/P02-shared-ui.md](../04-implementation/phases/P02-shared-ui.md) |
| `docs/plans/phases/P03-master-data.md` | [docs/04-implementation/phases/P03-master-data.md](../04-implementation/phases/P03-master-data.md) |
| `docs/plans/phases/P04-configuration.md` | [docs/04-implementation/phases/P04-configuration.md](../04-implementation/phases/P04-configuration.md) |
| `docs/plans/phases/P05-quotations.md` | [docs/04-implementation/phases/P05-quotations.md](../04-implementation/phases/P05-quotations.md) |
| `docs/plans/phases/P06-service-orders.md` | [docs/04-implementation/phases/P06-service-orders.md](../04-implementation/phases/P06-service-orders.md) |
| `docs/plans/phases/P07-service-charges.md` | [docs/04-implementation/phases/P07-service-charges.md](../04-implementation/phases/P07-service-charges.md) |
| `docs/plans/phases/P08-financial-documents.md` | [docs/04-implementation/phases/P08-financial-documents.md](../04-implementation/phases/P08-financial-documents.md) |
| `docs/plans/phases/P09-accounting.md` | [docs/04-implementation/phases/P09-accounting.md](../04-implementation/phases/P09-accounting.md) |
| `docs/plans/phases/P10-period-closing.md` | [docs/04-implementation/phases/P10-period-closing.md](../04-implementation/phases/P10-period-closing.md) |
| `docs/plans/phases/P11-financial-reports.md` | [docs/04-implementation/phases/P11-financial-reports.md](../04-implementation/phases/P11-financial-reports.md) |
| `docs/plans/phases/P12-operations-reports.md` | [docs/04-implementation/phases/P12-operations-reports.md](../04-implementation/phases/P12-operations-reports.md) |
| `docs/plans/phases/P13-dashboard.md` | [docs/04-implementation/phases/P13-dashboard.md](../04-implementation/phases/P13-dashboard.md) |
| `docs/plans/phases/P14-administration.md` | [docs/04-implementation/phases/P14-administration.md](../04-implementation/phases/P14-administration.md) |
| `docs/plans/phases/P15-integration.md` | [docs/04-implementation/phases/P15-integration.md](../04-implementation/phases/P15-integration.md) |
| `docs/plans/phases/P16-final-review.md` | [docs/04-implementation/phases/P16-final-review.md](../04-implementation/phases/P16-final-review.md) |

Validation: recorded in the current testing guide's Folder layout validation section. No
business feature implementation or commit is authorized by this reorganization.

Final layout checks: 51 moved files present at their mapped destinations; 562 project-owned
local Markdown links/anchors resolve; 44 unique page contracts, 17 packages/68 tasks retained;
schema-documentation tests 7 passed; generator/test lint and feature-status self-test passed.
The two archived withheld guides preserve their starting hashes and are excluded from internal
link/content scanning. A dependency README caught by the first overly broad scan was restored
to its exact starting hash; vendor files are excluded from project documentation scope.
