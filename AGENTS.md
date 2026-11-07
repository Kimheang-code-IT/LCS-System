# LCS agent working agreement

LCS is an existing single-tenant freight-forwarding ERP with double-entry finance.
Preserve FastAPI / SQLAlchemy / PostgreSQL, the Nuxt 4 static SPA, Casbin and exactly
44 approved business pages. Supporting routes add no pages.

## Load context progressively

1. Read this file and [project context](.agents/context/project-context.md).
2. For implementation/resume, read the [roadmap](docs/04-implementation/master-plan.md),
   selected plan's Handoff and relevant phase/task only. An active plan is a resume pointer,
   not authorization to bypass this request. S01 remains unfinished.
3. Use [module map](.agents/context/module-map.md) to find the owner; open its row and only
   needed [documentation](docs/README.md) sections. The [handbook](docs/03-development/ai-agent-guidelines.md)
   owns lifecycle/resume details. [Tooling](docs/03-development/agent-tooling.md) owns skill/MCP setup.
4. Search filenames/symbols/imports before reading source; inspect the smallest sufficient
   range plus relevant callers/tests. Reuse unchanged context; do not re-audit the repository.
   Load only the relevant skill. Respect lean-ctx read/search/shell rules when available.

## Work within scope

- Check Git status, untracked files and LastWriteTime before edits; preserve other sessions'
  work. Verify behavior that already meets acceptance; implement only demonstrated gaps.
- Reuse existing components, services, repositories, contracts and calculators. Keep functions
  clear, types consistent, errors explicit and dependencies minimal; no unrelated refactors.
- Follow [coding standards](docs/03-development/coding-standards.md) and approved requirements.
  Source proves implementation, not acceptance. Surface conflicting/outdated requirements.
- Classify FAST / STANDARD / DEEP using [testing policy](docs/03-development/testing-guide.md).
  Plan architectural, multi-file API/data/security/workflow work before edits; use host plan
  mode when available, otherwise a brief written plan. Work one testable slice at a time.
- Default to one coding agent. Skills do not imply subagents. Use read-only review for DEEP
  changes; delegate other independent work only when useful, supported and authorized.

## Protect data and access

- Casbin is the sole authorization engine; backend checks are mandatory. Preserve protected
  Super Administrator/current role semantics; add no parallel permission map.
- Apply [financial invariants](docs/01-architecture/database-design.md#financial-data-integrity--canonical-invariants):
  Decimal, balanced/atomic/idempotent posting, settlement bounds, immutable posted history,
  source/rate snapshots. Printing never writes or allocates numbers.
- Preserve historical records/relationships. Use additive Alembic migrations; never hand-edit
  generated SQL. Remove obsolete docs only after content and dependency review.
- Never read/copy/expose/stage/commit docs/lcssystem.pem, private keys or secrets; report
  configuration presence only. No production data use, deployment, provider/infrastructure
  changes, destructive reset or Git commit without appropriate explicit authorization.

## Verify, record and stop

- Run risk-based checks for changed behavior only. No automatic full suites, browser, build
  or database work for prose/simple UI. Do not repeat passing suites without a new reason.
  Essential finance/security/integrity checks and DEEP review remain mandatory; never weaken
  validation, accounting protections, authorization or assertions for a pass.
- Record exact commands/results/limits. Update only owning docs, affected decisions, phase/task
  and Handoff; follow [documentation standards](docs/03-development/documentation-standards.md).
  Context is a navigation aid; canonical docs remain authoritative. No secret/log dumps.
- On continue/resume follow the handbook and unfinished Handoff only. On handoff/context
  exhaustion stop implementation and record completed/remaining work and exact next step.
- Report changes, actual verification and risks. Stop at requested scope; no automatic next
  phase. No Git commit without explicit user authorization.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
