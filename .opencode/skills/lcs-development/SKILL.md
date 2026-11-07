---
name: lcs-development
description: Route an LCS change to the existing domain and implementation guidance when ownership is unclear.
---

# LCS development routing

Read AGENTS.md and .agents/context/project-context.md, then the selected module-map row,
phase/Handoff and source only. Do not load every skill or re-audit unchanged code.

| Need | Existing skill |
|---|---|
| Boundaries/reuse | .agents/skills/lcs-architecture/SKILL.md |
| Quotation/SO/actual containers/charges | .agents/skills/lcs-operations/SKILL.md |
| Posting, allocation, periods and finance reports | .agents/skills/lcs-finance/SKILL.md |
| Shared UI/printing | .agents/skills/lcs-ui/SKILL.md |
| Focused verification | .agents/skills/lcs-quality/SKILL.md |
| Canonical docs/context | .agents/skills/lcs-documentation/SKILL.md |
| Backend implementation | .opencode/skills/fastapi-backend/SKILL.md |
| Nuxt implementation | .opencode/skills/nuxt-frontend/SKILL.md |
| Schema/migrations | .opencode/skills/database-migration/SKILL.md |
| Auth/Casbin | .opencode/skills/security-rbac/SKILL.md |

Paths in this table are repository-relative. Load only the row(s) this task needs.
Preserve module relationships, backend calculation/transaction ownership, storage abstraction,
configuration/quotation snapshots and historic records. No duplicate layer or broad refactor.
For removals inspect dynamic imports, metadata, callers and database dependencies first.
Follow the single risk policy in docs/03-development/testing-guide.md and report actual
checks/limits. Stop at authorized scope; no automatic next phase or Git commit.
