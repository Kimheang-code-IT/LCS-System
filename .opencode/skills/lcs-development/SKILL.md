---
name: lcs-development
description: Use as the umbrella working agreement for any LCS Freight Forwarding System change that does not clearly match a more specific skill - covering repository conventions, safe-change workflow, and validation gates.
---

# LCS System Development Skill

## Purpose

Working agreement for any change in the LCS Freight Forwarding Platform: make safe,
consistent, production-quality changes without breaking business logic, database
integrity, API contracts, permissions, finance logic or deployment.

Detailed rules are **not** restated here. `AGENTS.md` is authoritative for architecture,
conventions, command invocations, financial integrity and Definition of Done; each area's
rules, acceptance criteria and expected outputs live in the focused skill below.

## Companion skills

| Task | Skill |
|---|---|
| Inventorying the repo, classifying implementation status, producing a plan | `project-analysis` |
| Schema, SQLAlchemy models, Alembic revisions, backfills, rollback | `database-migration` |
| FastAPI routers, services, repositories, validation, pagination, errors | `fastapi-backend` |
| Nuxt pages, components, composables, repositories, inline validation, i18n | `nuxt-frontend` |
| Tabs, groups, attributes, field config, trade-direction scoping, config versions | `dynamic-ui-configuration` |
| Quotation revisions, pricing, send/accept/reject, conversion | `quotation-management` |
| Posting rules, journals, periods, payments, allocations, reversals, reports | `finance-accounting` |
| Auth, permissions, single-role, sessions, audit, secrets | `security-rbac` |
| Writing or running tests, interpreting a failing suite, gate commands | `testing-qa` |
| Compose, CI/CD, environments, backups, restore drills, release verification | `deployment-devops` |

A task that spans areas loads each relevant skill. Slash commands cover the routine runs
(`/check`, `/test-fast`, `/test-backend`, `/test-frontend`, `/verify`, `/docs-check`,
`/debug`, `/build-fast`).

## Before coding

Non-trivial task → locate the owning module and the existing implementation first
(`ctx_compose`), then plan with these impact axes: database, API, permissions, business
logic, frontend contract, tests, documentation. A trivial self-contained edit goes straight
to implementation.

Prefer extending the existing architecture over introducing a pattern. Never create a
duplicate service, repository, endpoint, schema, store, helper or component when an
equivalent exists.

## Cross-cutting rules (not owned by a focused skill)

- **Module coupling is real.** A change to quotations, service orders, containers, charges,
  dynamic tabs or configuration versions can affect master data, finance and reports.
  Inspect the relationships; do not assume a module is isolated.
- **One authoritative calculation.** Reports, dashboard KPIs and pricing totals are computed
  once (backend) and read everywhere else. Never re-derive a business figure in the browser,
  and never persist a derived total without an explicit consistency design.
- **File storage goes through the storage abstraction** (MinIO/S3 in normal deployments,
  local fallback). No hard-coded local paths and no bypassing upload/download/signed URLs.
- **Documents and configuration are versioned data.** Quotation revisions and configuration
  versions are immutable snapshots: create a new version, never rewrite an existing one.
- **Deletion is the last option.** Search references, dynamic imports, configuration,
  tests, API consumers and database dependencies before removing code; never drop a column
  or table because static search finds no reference.
- **Refactoring preserves behaviour** unless a behaviour change was requested, and it stays
  inside the change's scope.

## Bug fix workflow

1. Reproduce the failure or identify it precisely (test, HTTP response, traceback).
2. Find the root cause; do not patch the visible symptom.
3. Check whether the same defect exists elsewhere in that pattern.
4. Apply the smallest safe fix, then add a regression test where practical.
5. Re-run the affected selector, then the gates for the touched stack.
6. Do not change unrelated behaviour while fixing a bug.

## Completion

Report, briefly: what changed, files, database/API/permission impact, tests added or
updated, commands executed with their observed results, and remaining risks. Name anything
unverified. Never claim a command or test passed unless it was actually executed.
