---
name: lcs-quality
description: Select and run focused LCS validation for a scoped change, diagnose regressions and distinguish inspection from executed acceptance.
---

# lcs-quality

Purpose: choose evidence appropriate to risk; do not generate broad suites automatically.
Required context: task-owned changed paths (separate preexisting dirty work), acceptance and
[test policy](../../../docs/03-development/testing-guide.md). The policy owns FAST/STANDARD/DEEP.

Workflow: identify changed behavior and its closest existing regression. Ordinary UI/CRUD uses
focused lint/types and a short manual journey; add useful tests for logic/refusal changes.
Documentation uses links/frontmatter/path checks. DEEP money/security/integrity still requires
success, denial, rollback/idempotency/concurrency where applicable, regression and independent
read-only review. Keep API contract/route-authorization coverage when affected.

Run from the owning backend/ or frontend/ directory using existing uv/pnpm tools. Batch
independent test selectors once. Do not rerun a passing suite without edits/new evidence.
No new test framework. No automatic full suite, build, Docker or browser. SQLite fixtures do
not prove PostgreSQL triggers/locks; Vitest node tests do not mount Vue/Nuxt. Browser journeys
use an isolated safe target. Never weaken assertions or authorization to obtain a pass.

Complete with exact commands, observed counts/results, skipped gates and why, a short manual
checklist and remaining limits. Stop after applicable checks; update only affected evidence.
