# Agent Handbook

## Reading order

Start with [AGENTS.md](../../AGENTS.md) and the short
[project context](../../.agents/context/project-context.md). For implementation/resume read
[roadmap](../04-implementation/master-plan.md), selected active Handoff and relevant task only.
Use [module map](../../.agents/context/module-map.md) and [docs index](../README.md) to load
owning requirements and source ranges. Do not reread all docs or the full checklist.
[Tooling](agent-tooling.md) owns skill discovery, optional MCP status and context strategy.

## Decision hierarchy

Explicit current user instructions and approved decisions govern scope; foundation documents
record those decisions. Detailed legacy specifications supply linked technical detail where
consistent. Code is evidence of implementation, not proof of acceptance or permission to
discard a requirement. Surface conflicts rather than silently choosing an interpretation.
See [documentation standards](documentation-standards.md) for source ownership.

## Task lifecycle

Understand → plan → implement → test → document → validate → report.
Inspect code/tests and timestamps first. Define a testable outcome and dependencies;
implement only demonstrated gaps; collect exact evidence and update the active Handoff.
Existing correct behavior can complete a slice through verification without rewriting it.

## Task levels

Use the single [risk-based testing policy](testing-guide.md#mandatory-gates-by-change-size).
FAST / STANDARD / DEEP remain the names; classify the current task-owned delta, not unrelated
preexisting dirty changes. Escalate financial/security/schema/shared-contract/infrastructure
work to DEEP. Do not reduce integrity checks for token or time savings.

Plan before architectural, multi-file API/data/security/workflow edits. Use host plan mode if
available; otherwise a brief written plan with scope, acceptance and checks. One coding agent
is the default. DEEP implementation uses the read-only reviewer defined in
.opencode/agents/reviewer.md (or a supported independent read-only review in another host);
if unavailable, report the missing gate. Do not spawn agents just because six skills exist.
Documentation/configuration-instruction edits do not run runtime finance/security gates.

Inspect status, untracked files and timestamps before edits; preserve other sessions' work.
Load only relevant skills/source, run focused checks once, update owning docs/Handoff and stop.

## Definition of Done

1. The slice's approved outcome is reachable and acceptance criteria are met.
2. Backend authorization and denial tests cover protected behavior.
3. Existing layers are respected; no duplicate service, repository, store, or endpoint.
4. Schema changes use additive Alembic revisions with working downgrade and regenerated SQL.
5. Financial paths preserve Decimal, balance, atomicity, immutability, and settlement limits.
6. Relevant success, refusal, boundary, concurrency, and regression checks pass; none weakened.
7. Applicable gates in [testing](testing-guide.md) pass with exact evidence.
8. Affected docs, roadmap, plan, Handoff, and behavior-status evidence reflect reality.
9. No secret, debug output, or throwaway artifact is introduced.
10. Report files changed, commands/results, limitations, and unresolved risks.

An unmet applicable criterion is reported explicitly. Documentation completion never implies
application acceptance or production readiness.

## Continue development

When the user says “Continue development”, “continue”, or “resume”:

1. Read AGENTS.md.
2. Read docs/04-implementation/master-plan.md.
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

Use the active plan's Handoff section, following the fields in
[plan template](../04-implementation/plan-template.md#handoff). Stop implementation before recording status,
completed/remaining work, exact next action, files/commands, and blockers. Commit only when
explicitly authorized; otherwise leave work uncommitted and state that in Handoff.
