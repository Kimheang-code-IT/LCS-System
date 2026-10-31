# Agent Handbook

## Reading order

Start with [AGENTS.md](../AGENTS.md), [master roadmap](plans/MASTER-ROADMAP.md),
the active plan and Handoff, then [design brief](09-design-brief.md).
Load the relevant architecture, data, security, lifecycle, API, coding, testing,
operations, documentation, and Git references linked from AGENTS.md.
Read the retained detailed specification only for the affected topic.

## Decision hierarchy

Explicit current user instructions and approved decisions govern scope; foundation documents
record those decisions. Detailed legacy specifications supply linked technical detail where
consistent. Code is evidence of implementation, not proof of acceptance or permission to
discard a requirement. Surface conflicts rather than silently choosing an interpretation.
See [documentation standards](12-documentation-standards.md) for source ownership.

## Task lifecycle

Understand → plan → implement → test → document → validate → report.
Inspect code/tests and timestamps first. Define a testable outcome and dependencies;
implement only demonstrated gaps; collect exact evidence and update the active Handoff.
Existing correct behavior can complete a slice through verification without rewriting it.

## Task levels

Name the level in one line when it is not obvious, then follow it. Escalate when a change
turns out to touch finance, auth, schema, shared contracts or infrastructure; never downgrade.

**FAST** — copy or label, styling, a table column, one simple field, a local UI or logic bug.
1. Locate the file or symbol. 2. Read only what the edit needs. 3. Implement.
4. Run the focused check for that file (`pnpm vitest run tests/<spec>`,
`uv run pytest tests/<file>`, `pnpm lint`, `pnpm typecheck`). 5. Stop.

FAST does not use a plan, a subagent, Context7, Playwright MCP, a Docker rebuild, a full
test suite or unrelated backend/frontend/database gates.

**STANDARD** — CRUD page, FastAPI endpoint, master-data configuration, form wired to the API,
business validation.
1. Locate the owning modules. 2. Load the matching skill. 3. Implement across the layers the
feature actually needs. 4. Run focused backend and frontend tests. 5. Update the affected
doc section. 6. Stop when those pass.

**DEEP** — Alembic migrations, auth and permissions, finance/accounting, quotation →
service-order transactions, shared API contracts, deployment, infrastructure security.
1. Read the relevant `docs/` requirements. 2. Load the specialized skill. 3. Check impacted
callers before editing. 4. Plan before implementing. 5. Implement in controlled steps.
6. Run integration, regression and permission-denial tests. 7. Use the reviewer agent.
8. Update the docs. 9. Report remaining risks.

DEEP verification is never reduced, and never traded for tokens or speed.

Common to every level: `git diff --name-only` plus untracked files shows what the change
actually touches — gate the stacks it touches, not every gate "just in case". If another
session is editing a tree, check `LastWriteTime` first; uncommitted edits are user work,
never abandoned work.

The foundation's plan-mode rule applies to qualifying STANDARD work as well as DEEP work.
For DEEP implementation read the relevant specialized skill and use the read-only reviewer
defined in `.opencode/agents/reviewer.md`. Documentation-only foundation work does not
execute implementation gates or start a security/finance slice.

## Definition of Done

1. The slice's approved outcome is reachable and acceptance criteria are met.
2. Backend authorization and denial tests cover protected behavior.
3. Existing layers are respected; no duplicate service, repository, store, or endpoint.
4. Schema changes use additive Alembic revisions with working downgrade and regenerated SQL.
5. Financial paths preserve Decimal, balance, atomicity, immutability, and settlement limits.
6. Relevant success, refusal, boundary, concurrency, and regression checks pass; none weakened.
7. Applicable gates in [testing](11-testing-and-quality.md) pass with exact evidence.
8. Affected docs, roadmap, plan, Handoff, and behavior-status evidence reflect reality.
9. No secret, debug output, or throwaway artifact is introduced.
10. Report files changed, commands/results, limitations, and unresolved risks.

An unmet applicable criterion is reported explicitly. Documentation completion never implies
application acceptance or production readiness.

## Continue development

When the user says “Continue development”, “continue”, or “resume”:

1. Read AGENTS.md.
2. Read docs/plans/MASTER-ROADMAP.md.
3. Find the active plan: status `In Progress`, latest `Last updated`.
4. Read its Handoff section.
5. Continue only remaining work.
6. Do not repeat completed work.
7. Do not expand scope.
8. Ask if scope is unclear; if no active plan exists, do not invent one.
9. Run validation before completion.
10. Update plan status and Handoff after meaningful progress.

If equally current active plans conflict, ask before choosing. A blocked active plan is not
permission to start another slice. Current user restrictions continue to apply.

## Handoff rules

Follow [handoff convention](handoff/README.md). Stop implementation before recording status,
completed/remaining work, exact next action, files/commands, and blockers. Commit only when
explicitly authorized; otherwise leave work uncommitted and state that in Handoff.
