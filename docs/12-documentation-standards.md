# Documentation Standards

## Authority and migration

[Source prompt](system-design-prompt.md) defines foundation paths/content. Approved discovery
decisions are recorded in [design brief](09-design-brief.md), architecture and ADR index.
The numbered hyphenated docs/00–13 are the canonical documentation structure.
The full named 44-page inventory and stable requirement IDs now live in the design brief
and topic-specific traceability tables. Generated SQL remains the schema authority;
`docs/12_feature_status.md` remains the tooling-required evidence/status record.
Reviewed duplicate drafts are consolidated and removed; there is no second foundation index.
The inventory below records retained compatibility, dependency and review exceptions.
Those references preserve implementation/evidence detail, not competing product requirements.

## When to update each document

| File/topic | Update trigger |
|---|---|
| AGENTS / CLAUDE | Agent entry rules or reading paths; CLAUDE remains thin |
| README | Setup, commands or documentation navigation |
| 00 handbook | Task lifecycle, DoD or resume behavior |
| 01 architecture | Module boundaries, dependency or architecture change |
| 02 data | Model/migration/invariant change; regenerate SQL separately |
| 03 security | Authentication, permissions, audit or threat changes |
| 04 lifecycle | State/transition/guard change; retain in reading order |
| 05 API | Endpoint/envelope/error/client-contract change; update canonical catalog |
| 06 operations | Deployment/configuration/monitoring/backup/recovery change |
| 07 ADR | Significant approved decision or supersession |
| 08 flow | User/system journey change |
| 09 brief | Approved scope, priorities, acceptance or open requirements |
| 10 coding | Naming, layout, errors, dependencies or tooling convention |
| 11 testing | Test architecture, gates, verified gaps or acceptance strategy |
| 12 standards | Source ownership, update policy or migration resolution |
| 13 Git | Branch, commit, PR or release rules |
| Roadmap / active plan | Meaningful progress, evidence, blockers and Handoff |

Follow the Documentation Policy in AGENTS.md. Change only affected sections; FAST needs docs
when behavior or a documented requirement changes. Do not create speculative feature/user-guide/
release-note/template directories. Preserve history and use Markdown links to canonical detail.

## Ownership and writing rules

The change author maintains affected docs; named module/operations owners are TBD, not invented.
Proposed acceptance roles are in the brief. Separate approved requirement, proposed target,
implementation evidence, executed verification and business acceptance. Use stable IDs and
exact paths; replace superseded instructions rather than appending contradictory rules.
Never include secret values or read private keys. Read complete existing targets before edits,
check timestamps, preserve concurrent edits, and report unresolved/destructive conflicts.

## Feature-status maintenance

Run `node scripts/feature-status.mjs` (or `--base <ref>`) after a change; it reports affected
prefixes/files without editing status. Update only affected rows/module assessments with exact
evidence and Last Verified; add history only when status changes. Documentation-only changes
do not update feature rows or imply runtime completion.
Never hand-edit `docs/06_database_design.sql`; use the generation/check commands in data model.

## Migration decisions and unresolved conflicts

- 41 pages was a counting error; approved scope is 44. Supporting routes are excluded.
- Localization/bilingual printing are Must; Telegram improvements Should; Sheets enhancements Could.
- README setup/organization/branch statements are corrected to current single-tenant bootstrap.
- Hostinger is intended baseline; EC2 wording in preserved legacy files is historical.
- Service orders use ACTIVE/INACTIVE, not a new closure lifecycle.
- Source inspection resolves same-key replay versus duplicate conflict; S02 still needs runtime evidence.
- Existing local 30-day backup cleanup is implementation detail, not approved retention.
- Superseded finance planning content is consolidated into roadmap history; duplicate plan removed without claiming completion.
- Legacy audit assertions of verification are historical claims; use executed revision evidence.
- Legacy testing/deployment content withheld by the context gateway remains unreviewed.

## Validation policy

Check exact required paths/sections, local Markdown links, AGENTS <200 lines, thin CLAUDE,
roadmap/active-plan/Handoff links, and preservation of existing work. For documentation-only
work verify no application/database/deployment files changed during the task. Record limitations
without claiming application gates were run. Do not commit without authorization.

## Documentation cleanup inventory

Scope: 93 project-owned Markdown/document/reference files before cleanup, including 56 under
`docs/`. Classifications are content/dependency based; every project-owned file is listed below.
The `.opencode` resources, SQL test fixtures and served robots file are tooling/application
dependencies, not extra foundation documents. Vendor environments, caches and generated test/
graph output are classified separately below. No private-key contents were read.

Phase A classifications precede removal; MERGE/DELETE CANDIDATE rows are removed only after
canonical coverage, stable-ID, page-route, link and inbound-reference checks pass.
Retained review/dependency rows are intentional exceptions; full consolidation of them remains
incomplete and is not hidden by a filename-count target.

| Original file | Classification | Content/dependency disposition |
|---|---|---|
| `CLAUDE.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/00-agent-handbook.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/01-system-architecture.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/02-data-model.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/03-security-access-control.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/04-record-workflow-lifecycle.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/05-api-specification.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/06-operations-runbook.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/07-adr-log.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/08-app-flow.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/09-design-brief.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/10-coding-conventions.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/11-testing-and-quality.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/12-documentation-standards.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/13-git-workflow.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/decisions/README.md` | REQUIRED DEPENDENCY | Retain: legitimate ADR-directory index required by canonical ADR log; no decision record deleted. |
| `docs/engineering/api-specification.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/05-api-specification.md`. |
| `docs/engineering/coding-conventions.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/10-coding-conventions.md`. |
| `docs/engineering/documentation-standards.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/12-documentation-standards.md`. |
| `docs/engineering/git-workflow.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/13-git-workflow.md`. |
| `docs/engineering/operations-runbook.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/06-operations-runbook.md`. |
| `docs/engineering/record-workflow-lifecycle.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/04-record-workflow-lifecycle.md`. |
| `docs/engineering/security-access-control.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/03-security-access-control.md`. |
| `docs/engineering/testing-quality.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/11-testing-and-quality.md`. |
| `docs/foundation/DOCUMENTATION_AUDIT.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/12-documentation-standards.md`. |
| `docs/foundation/README.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/12-documentation-standards.md`. |
| `docs/foundation/agent-handbook.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/00-agent-handbook.md`. |
| `docs/foundation/application-flow.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/08-app-flow.md`. |
| `docs/foundation/approved-pages.md` | MERGE | Consolidate into `docs/09-design-brief.md#approved-44-page-inventory`; remove after identifier/content/link checks. |
| `docs/foundation/data-flow.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/08-app-flow.md`. |
| `docs/foundation/database-schema.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/02-data-model.md`. |
| `docs/foundation/design-brief.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/09-design-brief.md`. |
| `docs/foundation/implementation-plan.md` | MERGE | Consolidate into `docs/plans/MASTER-ROADMAP.md`; remove after identifier/content/link checks. |
| `docs/foundation/module-requirements.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/01-system-architecture.md`. |
| `docs/foundation/prd.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/09-design-brief.md`. |
| `docs/foundation/product-requirements.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/09-design-brief.md`. |
| `docs/foundation/system-architecture.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/01-system-architecture.md`. |
| `docs/foundation/technical-requirements.md` | DELETE CANDIDATE | Reviewed duplicate/superseded draft; canonical coverage: `docs/10-coding-conventions.md`. |
| `docs/handoff/README.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/plans/MASTER-ROADMAP.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/plans/PLAN-0001-template.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/plans/PLAN-0002-access-and-page-authorization.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `docs/plans/PLAN-0002-first-slice.md` | MERGE | Consolidate into `docs/plans/MASTER-ROADMAP.md#superseded-finance-verification-proposal`; remove after identifier/content/link checks. |
| `docs/system-design-prompt.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `.opencode/agents/reviewer.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/build-fast.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/check.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/debug.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/docs-check.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/project-audit.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/test-backend.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/test-fast.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/test-frontend.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/token-report.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/commands/verify.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/database-migration/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/deployment-devops/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/dynamic-ui-configuration/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/fastapi-backend/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/finance-accounting/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/add-watch.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/exports.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/extraction-spec.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/github-and-merge.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/hooks.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/query.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/transcribe.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/graphify/references/update.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/lcs-development/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/nuxt-frontend/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/project-analysis/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/quotation-management/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/security-rbac/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `.opencode/skills/testing-qa/SKILL.md` | REQUIRED DEPENDENCY | Agent skill/command/reviewer resource; preserve tool entry point, not a competing product specification. |
| `AGENTS.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `README.md` | KEEP | Required canonical foundation, active plan, handoff, or approved source reference. |
| `backend/tests/sql/integrity_guards.sql` | REQUIRED DEPENDENCY | Executable test/reconciliation fixture; outside documentation deletion scope. |
| `backend/tests/sql/pre_migration_counts.sql` | REQUIRED DEPENDENCY | Executable test/reconciliation fixture; outside documentation deletion scope. |
| `docs/01_business_requirements.md` | MERGE | Consolidate into `docs/09-design-brief.md`; remove after identifier/content/link checks. |
| `docs/02_software_requirements.md` | MERGE | Consolidate into `docs/09-design-brief.md#legacy-requirement-traceability`; remove after identifier/content/link checks. |
| `docs/03_business_process_and_sop.md` | MERGE | Consolidate into `docs/08-app-flow.md#operating-procedures`; remove after identifier/content/link checks. |
| `docs/04_functional_design.md` | REVIEW REQUIRED | Retain: unique use cases, error catalogue and ER/process/data-flow diagrams; full accuracy review incomplete. |
| `docs/05_solution_architecture.md` | REQUIRED DEPENDENCY | Retain: immutable migration e6f7a8b9c0d1 and status_policy.py reference it; unique hardcoded-configuration register. |
| `docs/06_database_design.sql` | GENERATED | Retain unchanged: generator and test_schema_docs.py require this exact single SQL path. |
| `docs/07_api_documentation.md` | REQUIRED DEPENDENCY | Catalog consolidated into 05-api-specification; retain compatibility pointer for unmodified deployment/architecture references. |
| `docs/08_frontend_and_ui_design.md` | REVIEW REQUIRED | Retain unchanged: pre-existing user edits and unique current UI details require complete review before consolidation. |
| `docs/09_roles_and_permissions.md` | REQUIRED DEPENDENCY | Retain: test_migration_chain.py references Casbin history; unique detailed permission/payload catalog. |
| `docs/10_testing_and_quality.md` | REVIEW REQUIRED | Retain unchanged: gateway withheld content; reports/service.py and skills reference its risk/evidence records. |
| `docs/11_deployment_and_security.md` | REVIEW REQUIRED | Retain unchanged: gateway withheld content; migration/test/deployment references and recovery knowledge must survive. |
| `docs/12_feature_status.md` | REQUIRED DEPENDENCY | Retain unchanged: scripts/feature-status.mjs REPORT path; pre-existing edits and unique evidence/history. |
| `docs/FULL_SYSTEM_VERIFICATION.md` | REVIEW REQUIRED | Retain: historical exact test/settings evidence; not reproduced or fully reconciled in this cleanup. |
| `frontend/public/robots.txt` | REQUIRED DEPENDENCY | Served application asset; no behavior changes authorized. |

### Generated, vendor and security exclusions

- `graphify-out/`: GENERATED local graph; no deletion. AST/source index is not authored requirements.
- `test-results/`, `frontend/test-results/`, `frontend/playwright-report/`: GENERATED browser
  reports/traces/screenshots; no cleanup of runtime/test artifacts authorized here.
- `frontend/node_modules/`, `backend/.venv/`, `.nuxt/`, `.output/`, caches and `.git/`:
  third-party/generated/internal content; excluded from project-authored documentation counts.
  Package README files are dependency material, not duplicate LCS specifications.
- `docs/lcssystem.pem`: outside document inventory; untracked and ignored. Private-key material
  remains a local repository/workspace exposure risk; not opened, copied, deleted or rotated.

### Consolidation evidence and exceptions

BR/FR/NFR/INV/UR identifiers remain traceable without renumbering. FR-032–042 stay retired.
Historical advanced credential requirements remain explicitly unverified and do not add scope.
The 44 named routes are preserved without the draft's unverified permission guesses.
SOP single-role, sent-revision immutability, order status and retry wording were reconciled
against inspected bootstrap, permission, quotation and operations source.
No CC measurements, old “implemented” assertions, unapproved priorities, EC2 assumptions,
new tax workflows or invented numerical targets were promoted to approved requirements.
Old audit gaps are either addressed by current foundation/ADR/API coverage or remain open:
monitoring ownership, safe restore evidence, and detailed legacy consistency review.
Historical test/settings verification reports and dirty frontend/status documents remain intact.

The legacy API filename remains a compatibility pointer because the untouched detailed
deployment guide and architecture reference name it. Repointing gateway-withheld guide contents
without review would violate safe removal. Architecture/RBAC files remain for immutable
migration/test references and unique registers; no source/test/comment change was made.
Legacy functional design and historical verification evidence need full review before removal.
Gateway-withheld testing/deployment contents remain unreviewed; this prevents claiming that all
legacy documentation has been removed or exhaustively reconciled.

### Cleanup outcome and remaining work

Phase C projected checks passed before Phase D removed 26 reviewed documents: all 14 old
foundation drafts, all eight engineering drafts, the separate business requirements, SRS,
SOP and superseded duplicate-ID finance plan. Their unique scoped requirements, 44-page
inventory, operational/API instructions and plan history are consolidated above and in the
linked canonical topics. The original inventory is retained as the disposition record.
No legitimate active plan, ADR, generated schema or implementation evidence report was deleted.
Project-owned documents/references: 93 before, 67 after; under docs: 56 before, 30 after.
The private key and vendor/generated outputs are excluded from these counts.

Final checks and command limitations are recorded in
[testing and quality](11-testing-and-quality.md#documentation-cleanup-checks--2026-10-31).
Nine legacy reference/evidence paths remain intentional dependency/review exceptions; this
cleanup does not claim the directory now contains only the canonical files. Complete review
of functional/UI detail, historical evidence, gateway-withheld guides and immutable-reference
migration is necessary before considering those files for further consolidation/removal.
Do not modify application/migration/test/tool paths merely to force the desired file count.
