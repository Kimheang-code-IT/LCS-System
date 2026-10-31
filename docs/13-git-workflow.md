# Git Workflow

## Branch naming

`dev` is integration; `main` is protected production. Use a scoped feature/fix/docs branch
following existing repository practice, e.g. `docs/foundation` or `fix/plan-s01-session`.
Examples are conventions, not branches created by this task. Preserve other worktree edits.

## Commit conventions

Use focused descriptive commits (`docs:`, `fix:`, `feat:` as appropriate).
Handoff convention: `wip: <plan-id> <short status>`.
The user must explicitly authorize every commit; handoff alone does not authorize one.
Never stage all dirty work blindly. Inspect diff/untracked files and stage only authorized
paths. Never stage private keys, secret env files, generated local graphs or unrelated work.

## PR expectations

Describe the final behavior/problem, scope, applicable requirement/plan, exact validation,
known limitations and remaining risks. Keep the change focused; no unrelated refactors.
DEEP implementation uses the read-only reviewer. Preserve failing tests and denial checks.
Keep roadmap, plan/Handoff and affected documentation current without inventing evidence.

## Release rules

Preserve Dev CI and the existing production workflow; `dev-ci.yml` does not deploy.
Protected main requires PR/required checks according to repository policy; actual remote
branch-protection settings were not verified in foundation work.
Production migration, health checks, immutable-image rollback and recovery follow
[operations runbook](06-operations-runbook.md). No deploy, CI modification or provider move
is authorized by foundation creation. Business/finance/technical approval and final owner
acceptance are distinct from a green CI run.
