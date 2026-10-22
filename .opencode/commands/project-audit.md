---
description: Audit the OpenCode, LeanCTX and project tooling setup
---

Read-only audit. Report findings by expected benefit, and apply only changes that are
safe and reversible.

1. Effective config: `opencode debug config` (sources and merged values) and
   `opencode debug agents` / `opencode debug paths`.
2. MCP: `opencode mcp list` — every connected server costs tool descriptions in every
   session; flag any that is unused or `needs authentication`.
3. Extensions: list `.opencode/skills/*/SKILL.md` (name + description + line count),
   `.opencode/commands/*.md`, `.opencode/agents/*.md` and the global `skills/`, `commands/`,
   `agents/` directories. Flag duplicates that answer the same question.
4. Instructions: `AGENTS.md` (root and global) — duplicated rules, stale commands, claims
   that no longer match the code, and anything that belongs in a skill instead.
5. Toolchain: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm i18n:check`,
   `uv run pytest -q`, `uv run ruff check .` — report what runs and how long it takes.
6. Docs: broken references, generated docs out of date, status documents that disagree
   with the code.
7. LeanCTX health: `ctx_quality` (or lean-ctx health) if available, and note any command
   blocked by the shell allowlist.

Never change the default model, provider credentials, proxy routing, production secrets or
Git history. Do not delete a document or skill without approval — mark it superseded first.
