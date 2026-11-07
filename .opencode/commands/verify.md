---
description: Verify the requested change using risk-based Definition-of-Done gates
---

Scope is the current task delta, not all preexisting dirty files. Read the handbook DoD
and docs/03-development/testing-guide.md. Derive acceptance, touched layers and risk first.

1. Review status/diff/untracked paths and timestamps; preserve other sessions' edits.
2. FAST documentation: /docs-check only; simple UI: focused review/manual check.
3. STANDARD code: scoped lint/types and relevant behavior tests/manual journey. Use existing
   selectors; add meaningful missing regressions, not broad fixtures.
4. DEEP: affected integration/regression/denial/boundary and transaction/rollback/retry/race
   checks as applicable, plus independent read-only review. Include backend API-contract
   and route-authorization tests for protected/shared-contract changes. PostgreSQL behavior
   requires an isolated disposable target; SQLite is insufficient for triggers/locks.
5. Schema: additive migration/downgrade review and existing generator --check --strict only
   when schema actually changes. No live migration/reset by this verification command.
6. Build/browser/Docker/full suites only for demonstrated shared/build/visual/release impact
   or explicit request. No blanket trigger from every models.py/core/UI edit.
7. Update affected docs, task evidence and Handoff. Never weaken a failing gate.

If a required gate fails, fix only in scope or report it incomplete; do not claim completion.
Report changed files, exact commands/results, manual checks and limitations; stop.
