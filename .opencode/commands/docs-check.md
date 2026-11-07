---
description: Check changed documentation, skill and context references
---

Read docs/03-development/documentation-standards.md; inspect only task-changed prose/config.

- Check relative local links/anchors, named source paths, skill frontmatter/name uniqueness
  and discovery locations. Read required content withheld by tools only if access permits;
  otherwise preserve it and report the semantic limit.
- Canonical owners: requirements/architecture/business rules/API, current feature-status and
  affected task/Handoff. Archive is history, not a second status authority.
- Context/skills link to those owners; no duplicated requirement sets, stale decisions,
  token-savings claims, credentials or logs. Preserve docs folder structure and useful history.
- Run generated-schema check only if schema/model/descriptions changed; never hand-edit SQL.
- Permissions/API changes update the current catalog; deployment changes update the current
  deployment guide. Neither is implied by prose-only changes.
- Run node scripts/feature-status.mjs for routing; do not promote ERP status for setup prose.

Report exact structural checks, changed files, unresolved references/semantic limitations.
No runtime/backend/frontend/full-suite/browser/database gate for documentation-only work.
