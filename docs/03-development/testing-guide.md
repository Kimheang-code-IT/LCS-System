# Testing and Quality

Focused verification follows changed behavior and risk. Use existing tools and manual checks
for ordinary workflows; do not manufacture a large test suite. Never weaken assertions,
authorization, validation or financial protections to obtain a pass.

## Mandatory gates by change size

Classify the task-owned delta, separating unrelated preexisting work. These are the single
FAST / STANDARD / DEEP definitions used by AGENTS, skills and OpenCode commands.

| Level | Examples | Required evidence |
|---|---|---|
| FAST / Level 1 | Documentation, instructions, simple labels/style | Review diff; relevant link/path/frontmatter or visual/manual check. No runtime suite for prose; lint/typecheck only where executable code can be affected |
| STANDARD / Level 2 | Ordinary forms/dropdowns/CRUD, local logic/validation | Scoped lint and available typecheck for touched code; short manual journey; focused existing/new regression where logic, boundary/refusal or integration behavior changes. No broad fixtures/suite by default |
| DEEP / Level 3 | Finance, allocations, numbering, currencies, auth/security, schema/integrity, quotation→SO transactions, shared API contracts, infrastructure | Focused automated correctness, success/refusal/denial/boundary and regression; transaction/rollback/idempotency/concurrency where relevant; affected contracts/route authorization; lint/types for touched stacks; independent read-only reviewer |

A narrow source-only/UI task needs no server, database, browser or build. A real browser is
appropriate when interaction/layout/print behavior needs observation; manual instructions
alone are not executed verification. Label unrun checks explicitly. Ordinary API changes
still test relevant validation/refusals; permission changes escalate to DEEP.

For real PostgreSQL triggers/locks use an explicitly isolated disposable target. Never infer
those properties from SQLite. No production data, implicit migrations/resets or weakened
checks. The DEEP gate is not optional; report an unavailable required reviewer/target.

Run only the smallest sufficient selectors from backend/ or frontend/. Combine independent
selectors in one run. Do not rerun passing unchanged suites unless a new failure, changed
code or unresolved concern justifies it. Full suites, Docker rebuilds and production builds
require shared-impact, release or explicit user justification; no blanket all-suite rule.
Use the existing uv/pnpm environment; no new test framework for setup or routine changes.

## Test architecture (what tests rely on)

- Backend: in-memory SQLite/aiosqlite via `get_session` overrides; `backend/tests/seed.py`
  supplies fixture credentials only. PostgreSQL trigger/locking behavior is proven only by the
  explicitly configured disposable-PostgreSQL tests (skipped without that target).
- The API contract test statically reads frontend endpoint registrations — do not move it or
  the route-authorization test out of the DEEP gate.
- Frontend Vitest: node environment, `import.meta.client=false`, alias `~` → app,
  `tests/**/*.spec.ts`. Browser acceptance is manual on the compose stack; no automated
  browser suite runs as a gate.
- i18n is not an automatic gate; run it when translations change. Manual browser testing
  on the compose stack is the default acceptance path for UI work.

## Standard command inventory (reference, not routine requirements)

```bash
# backend/
uv run pytest -q tests/<file>.py
uv run ruff check app tests scripts
uv run alembic heads
# frontend/
pnpm vitest run tests/<spec>.spec.ts
pnpm lint
pnpm typecheck
```

Build or regenerate (schema docs, Docker image) only when the related files changed.

## Evidence

For DEEP work and slice acceptance, record in the active plan: exact command, result, skipped
cases and limitations. Never mark a feature WORKING merely because a test file exists.
Pre-existing failures are reported as such, not suppressed. Historical run/timing evidence from
former QA/audit documents is preserved in Git history only; treat it as stale, not current.

## Documentation modernization validation

2026-11-04 documentation task: application implementation and runtime test gates are out of
scope. Existing dirty code/tests/migrations and feature-status evidence are preserved.
Structural validation covers relative local links/anchors in task-changed Markdown, source
links, all 44 unique MOD page contracts, 17 phase files with sections A–I and 68 task rows,
dependency acyclicity at prerequisite-subset level, and file hashes against the pre-edit
snapshot. The validator is a temporary local script, not a new project dependency/tool.

| Executed command (repository root unless stated) | Observed result | Limits |
|---|---|---|
| python "C:/Users/Moeng Kimheang/AppData/Local/Temp/lcs_docs_validate.py" | Exit 0: 44 unique page contracts/routes; 17 A–I packages; 68 tasks; 21-node prerequisite-subset graph acyclic; 497 task-document local links/anchors + 7 retained-doc links resolve; 0 trailing-whitespace errors | Temporary validator; two gateway-withheld guides excluded; no runtime acceptance; initial run required UTF-8 reader correction |
| git diff --check -- '*.md' | Exit 0; no whitespace errors; CRLF→LF normalization warnings | Diff includes pre-existing Markdown edits; added files checked by the validator |
| node scripts/feature-status.mjs | Reported affected groups for 123 working-tree files at that point; no report mutation | Includes other sessions' code/deletions; no feature rows promoted for prose |
| Baseline SHA-256 comparison | 840 starting files; 16 existing Markdown files changed by task, 25 new Markdown files; 0 task deletions; 821 starting files unchanged | Three concurrent non-document writes detected/reported separately; not a globally unchanged working tree |

No runtime/backend/frontend/database/browser pass is claimed. Exhaustive semantic reconciliation is still NEEDS_REVIEW:
the context gateway withheld legacy 10_testing_and_quality.md and
11_deployment_and_security.md; other large legacy references received structural/topic review
rather than full current acceptance verification. Do not bypass withheld content or delete it.

## Folder layout validation

2026-11-04 follow-up: documentation was moved to the user-requested folder layout. Tooling
changes are path references plus recursive discovery of the one generated SQL file. SQL was
regenerated with the existing generator; its hash matches the starting schema after reversing
only the generated preamble's documentation path. Historical migrations remain unchanged.

| Command / owning directory | Observed result |
|---|---|
| uv run --no-sync python scripts/generate_schema_docs.py --check --strict (backend, before move) | Up to date; all 77 tables and columns documented |
| uv run --no-sync python scripts/generate_schema_docs.py (backend, after move) | Wrote docs/01-architecture/database-design.sql, 4423 lines; all 77 tables documented |
| uv run --no-sync pytest -q tests/test_schema_docs.py (backend) | 7 passed, 3 existing SQLAlchemy FK-cycle warnings, 4.29 s |
| uv run --no-sync ruff check scripts/generate_schema_docs.py tests/test_schema_docs.py (backend) | All checks passed |
| node --check ../scripts/feature-status.mjs (backend) | Exit 0 |
| node scripts/feature-status.mjs --self-test (repository root) | Passed; 12 mapped feature groups |
| python "C:/Users/Moeng Kimheang/AppData/Local/Temp/lcs_docs_layout_validate.py" (repository root) | Exit 0: all 51 moved files present; 562 local links/anchors, 0 errors; 44 unique pages, 17 packages/68 tasks, one recursive SQL; generated preamble-only change and archived-guide hashes verified |

The FK-cycle warning was present before moving the schema; no schema/relationship fix belongs
to this task. The two archived gateway-withheld guides are excluded from content/link scanning
and retain exact original bytes. Project-owned files only are validated; an accidentally
included dependency README was restored to its exact baseline SHA-256. No runtime finance,
auth, migration or browser acceptance is inferred from these documentation/tool checks.
