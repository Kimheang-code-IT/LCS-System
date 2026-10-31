# AGENTS.md

LCS is an existing single-tenant freight-forwarding modular monolith with double-entry finance.
Preserve its FastAPI backend, Nuxt 4 static SPA, PostgreSQL, Casbin, and accounting engine.
Exactly 44 business pages are approved; supporting routes do not increase this count.

## Repository and required reading order

1. Read this file and [agent handbook](docs/00-agent-handbook.md).
2. Read [master roadmap](docs/plans/MASTER-ROADMAP.md), the active plan, and its Handoff.
3. Read [design brief](docs/09-design-brief.md) for approved scope and requirement IDs.
4. Read only relevant [architecture](docs/01-system-architecture.md),
   [data](docs/02-data-model.md), [security](docs/03-security-access-control.md),
   [record lifecycle](docs/04-record-workflow-lifecycle.md), and [API](docs/05-api-specification.md) sections.
5. Follow [coding](docs/10-coding-conventions.md), [testing](docs/11-testing-and-quality.md),
   [documentation](docs/12-documentation-standards.md), and [Git](docs/13-git-workflow.md) standards.
6. Read [operations](docs/06-operations-runbook.md) before operational work.

`backend/`: FastAPI modules, tests, Alembic. `frontend/`: Nuxt app, Vitest, Playwright.
`infrastructure/`: Compose/nginx/scripts. `docs/`: approved foundation and retained detailed references.
`.opencode/`: project skills, commands, and reviewer instructions.

## Implementation and validation rules

- Classify FAST / STANDARD / DEEP using the handbook; escalate for finance, auth, schema,
  shared contracts, or infrastructure. Never reduce DEEP verification.
- Use plan mode for architectural, multi-file, API, data-model, security, or workflow changes.
- Build one independently testable vertical slice at a time; follow approved dependencies.
- Inspect existing code and tests first. If behavior already meets acceptance, verify it;
  do not rewrite it. Implement only demonstrated defects or missing requirements.
- Follow existing patterns; preserve working functionality and permission semantics.
- Add/update meaningful tests for changed behavior. Never weaken authorization, validation,
  accounting protections, error handling, or tests to obtain a pass.
- Gate touched stacks with available lint, typecheck, and tests; use the testing reference
  for scope and order. Report exact commands, observed output, and unverified claims.
- Do not refactor unrelated code or add dependencies without justification.
- Check status, untracked files, and LastWriteTime before edits; preserve other sessions' work.
- Use the project tooling rules in coding conventions; load only relevant skills.
- Search before reading: locate with lean-ctx/ripgrep, then read only the needed ranges.
  Do not re-read unchanged files or re-run a suite already run in this session.

## Security, finance, and restricted areas

- Casbin is the only authorization decision engine; backend checks are mandatory.
- Preserve the protected Super Administrator role; add no parallel role-permission mapping.
- Follow accounting invariants in the data-model reference for every financial change.
- Never read, copy, expose, stage, or commit `docs/lcssystem.pem`, private keys, or secrets.
- Never print secret environment values; report configuration presence only.
- Remove obsolete documentation only after content review, consolidation and dependency checks; never purge historical business records automatically.
- Do not hand-edit generated schema SQL. Follow additive Alembic and schema-doc rules.
- No production data use, deployment, provider migration, infrastructure changes, destructive
  reset, or Git commit without the appropriate explicit authorization.
- Foundation authorization permits documentation only; S01 implementation has not started.

## Documentation Policy

- Maintain the master roadmap and active plan.
- Update docs/00–13 when their area changes, including the conditional lifecycle document.
- Create feature documentation when a new feature starts and its need is established.
- Create user guides and release notes only for user-facing releases.
- Create templates only when a document type is needed repeatedly.
- Do not create speculative files or competing authoritative requirements.
- Update only directly affected documentation; follow canonical ownership and legacy precedence
  in the documentation standards. Use the [project status checklist](docs/plans/PROJECT-STATUS-CHECKLIST.md)
  as the verification index; read only the section the task touches, never the whole
  file; preserve the tooling-required feature report and its evidence.

## Continue development and handoff

On “Continue development”, “continue”, or “resume”, read this file, the master roadmap,
and the active plan's Handoff. Follow the complete resume algorithm in the handbook:
continue unfinished work only, preserve scope, validate, and update status/Handoff.
On “handoff” or nearing the context limit, stop implementation and update Handoff before
ending. Follow the handoff guide, including its resume prompt and conditional WIP convention.
Never make a Git commit without the user's explicit authorization.
An active plan is a resume pointer, not permission to bypass the user's current task scope.
