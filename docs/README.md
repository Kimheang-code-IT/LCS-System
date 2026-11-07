# LCS documentation

## Current documentation tree

The documentation is organized by responsibility. Start with
[Project documentation](00-project/README.md), then read only the topic needed for the task.

```text
docs/
  README.md
  00-project/
    README.md
    project-overview.md
    requirements.md
    feature-inventory.md
    feature-status.md
    documentation-audit.md
  01-architecture/
    system-architecture.md
    integration-architecture.md
    database-design.md
    database-design.sql
    api-design.md
    security-and-permissions.md
    architecture-decisions.md
    implementation-reference.md
    permission-catalog.md
  02-business/
    business-rules.md
    workflows.md
    accounting-and-posting.md
    notification-requirements.md
    backup-and-recovery.md
    import-export-requirements.md
    ui-ux-standards.md
    functional-reference.md
  03-development/
    ai-agent-guidelines.md
    agent-tooling.md
    coding-standards.md
    testing-guide.md
    deployment-guide.md
    settings-and-provider-configuration.md
    documentation-standards.md
    git-workflow.md
  04-implementation/
    master-plan.md
    phase-tracker.md
    acceptance-criteria.md
    dependency-map.md
    planning-guide.md
    plan-template.md
    project-status-checklist.md
    plans/
      PLAN-0002-access-and-page-authorization.md
      PLAN-0004-financial-printing.md
      PLAN-0005-settings-integrations.md
    phases/
      P00-documentation.md ... P16-final-review.md
  archive/
    README.md
    api-compatibility-reference.md
    testing-quality-history.md
    deployment-security-history.md
```

Agent setup: [short context](../.agents/context/project-context.md),
[module map](../.agents/context/module-map.md), [skills/MCP workflow](03-development/agent-tooling.md).

## Where to find things

| Topic | Authoritative document |
|---|---|
| Purpose, stack and module map | [Project overview](00-project/project-overview.md) |
| Approved scope, priorities and stable requirement IDs | [Requirements](00-project/requirements.md) |
| All 44 page contracts | [Feature inventory](00-project/feature-inventory.md) |
| Implementation verification history | [Feature status](00-project/feature-status.md); [verification checklist](04-implementation/project-status-checklist.md) |
| Architecture and accepted decisions | [System architecture](01-architecture/system-architecture.md); [ADR log](01-architecture/architecture-decisions.md) |
| Entities, invariants and generated schema | [Database design](01-architecture/database-design.md); [generated SQL](01-architecture/database-design.sql) |
| HTTP contracts and access controls | [API design](01-architecture/api-design.md); [security](01-architecture/security-and-permissions.md) |
| Transitions, retry behavior and journeys | [Business rules](02-business/business-rules.md); [workflows](02-business/workflows.md) |
| Automation, accounting, reporting and closing targets | [Accounting and posting](02-business/accounting-and-posting.md) |
| Shared UI, forms and rendering | [UI/UX standards](02-business/ui-ux-standards.md) |
| Development, testing and operational guidance | [Coding](03-development/coding-standards.md); [testing](03-development/testing-guide.md); [deployment](03-development/deployment-guide.md) |
| Execution sequence and phase tasks | [Master plan](04-implementation/master-plan.md); [planning guide](04-implementation/planning-guide.md) |
| Dependencies, acceptance and progress | [Dependency map](04-implementation/dependency-map.md); [acceptance](04-implementation/acceptance-criteria.md); [tracker](04-implementation/phase-tracker.md) |
| Ownership and migration history | [Documentation standards](03-development/documentation-standards.md); [audit](00-project/documentation-audit.md) |

## Smart Settings and Integrations

The documentation-first 2026-11-04 request is specified in
[integration architecture/current inventory](01-architecture/integration-architecture.md),
[notifications](02-business/notification-requirements.md),
[backup/recovery](02-business/backup-and-recovery.md),
[import/export](02-business/import-export-requirements.md) and
[settings/provider configuration](03-development/settings-and-provider-configuration.md).
[PLAN-0005 A–G](04-implementation/plans/PLAN-0005-settings-integrations.md) links these to existing
packages. Documentation is complete; implementation remains NOT_STARTED. S01 stays the unfinished
resume pointer; no integrations are activated by these documents.

## Agent reading and updates

Read [AGENTS](../AGENTS.md), [agent guidelines](03-development/ai-agent-guidelines.md),
the master plan and active [S01 Handoff](04-implementation/plans/PLAN-0002-access-and-page-authorization.md#handoff).
Then load only relevant requirements, page contracts, phase tasks, source and tests.
Preserve current working-tree edits. Verify implemented behavior before fixing a demonstrated gap.

After scoped work, update its owning document and plan/Handoff, and record exact validation.
Requirement changes and runtime evidence are separate. Documentation does not certify feature
delivery or production readiness. Do not automatically start another implementation phase.

## Retained references and archive

Implementation/permission/functional references preserve unique technical detail and history;
current requirements and business rules override obsolete examples. Archive contains superseded
navigation and older guides, not discarded information. Two archived guides remain byte-preserved
pending sanitized review; their internal historical links were not rewritten. The
[audit](00-project/documentation-audit.md#folder-layout-migration) maps every old path to its new
location, including references embedded in immutable historical migrations.
