---
name: lcs-documentation
description: Maintain LCS canonical docs, task handoffs and concise agent context without duplicating requirements or promoting unverified implementation.
---

# lcs-documentation

Purpose/modules: docs, agent context, task trackers and tool guidance. Read the owning topic
via [docs index](../../../docs/README.md),
[documentation policy](../../../docs/03-development/documentation-standards.md) and current task.

Workflow: search before reading; retain docs/00-project, 01-architecture, 02-business,
03-development, 04-implementation and archive. Edit the canonical owner and link to it from
context/skills. Record decision ID, source, status and verification date; distinguish approved
requirements, inspected code and executed tests. Update only affected map rows/task/Handoff.
Memory never outranks newer source/approved docs. No logs, code snapshots or customer secrets.
Review content and dependencies before removal; retain withheld/unreviewed history untouched.

Validation: changed Markdown local links/anchors, named source paths and skill frontmatter;
node scripts/feature-status.mjs for routing only. No backend/frontend runtime suite for prose.
Generated SQL changes only through the existing generator when schema really changes.

Complete with files, structural checks and semantic limits. Documentation or setup completion
does not complete an ERP phase, certify production readiness or authorize the next task.
