---
name: project-analysis
description: Use when analysing the LCS repository, classifying feature implementation status, comparing code against requirements and docs, inventorying hardcoded configuration, or producing an implementation plan before starting work.
---

# Project analysis

Produce a fact-based assessment of the LCS Freight Forwarding System: what exists,
what is only partially built, what is missing, and where the code and the
documentation disagree. The output is an implementation plan, not code.

## When to use

- Starting a new phase of work and needing to know the true starting point.
- A requirement is claimed as done but has not been verified.
- Deciding whether to extend or replace an existing implementation.
- Producing `docs/17_repository_analysis.md` or refreshing it.

## Required inputs

1. The requirement source: the task brief, `docs/01`–`docs/04`, or a specific request.
2. The area to analyse. Never analyse "everything" in one pass — scope by module.
3. Any prior analysis in `docs/14`–`docs/17` so findings are not duplicated.

## Project references

| Document | Use it for |
|---|---|
| `AGENTS.md` | Commands, architecture rules, enforced conventions |
| `docs/05_solution_architecture.md` | Intended architecture and layering |
| `docs/06_database_design.sql`, `docs/06b_database_design_annotated.sql` | Actual schema (generated from models) |
| `docs/11_permissions_matrix.md` | Permission catalog and page mapping |
| `docs/14_47_table_migration_analysis.md` | Old→new table mapping and deliberate non-adoptions |
| `docs/16_upgrade_summary_and_risks.md` | Known risks and outstanding work |
| `docs/17_repository_analysis.md` | The most recent classification of every feature |
| `docs/18_implementation_checklist.md` | Live per-feature status and missing work |

## Workflow

1. **Inventory the surfaces.** List backend modules (`backend/app/modules/*`), API
   routes (`backend/app/api/v1/router.py` plus each module `router.py`), frontend
   pages (`frontend/app/pages/**`), and tests (`backend/tests/`, `frontend/tests/`).
2. **Verify, never assume.** A table, a model, a route, or a doc section is not
   evidence that a feature works. Trace page → repository → endpoint → service →
   model, and confirm each hop exists.
3. **Classify every feature** into exactly one bucket:
   - `Implemented and tested` — a test exercises it and passes.
   - `Implemented but not verified` — code exists, no test covers the behaviour.
   - `Partially implemented` — state the missing part concretely.
   - `Missing` — required but absent.
   - `Deprecated or obsolete` — superseded; say what replaced it.
4. **Find the drift.** Compare each doc against the code. Report contradictions
   with file paths, not opinions.
5. **Inventory hardcoded business configuration** and, for each item, state whether
   a database row can override it at runtime. Use `docs/17` §"Hardcoded configuration"
   as the register and extend it rather than starting over.
6. **Report risk** in two separate lists: security risk and financial-correctness
   risk. Rank by blast radius, not by ease of fixing.
7. **Write the plan.** Order work so each step is independently verifiable, and
   mark which steps are destructive or irreversible so they can be approved
   before execution.

## Evidence rules

- Cite `path:line` for every claim about current behaviour.
- Prefer a runnable check over a reading: `pytest`, `ruff`, a `grep`, or a query.
- Distinguish "not implemented" from "not reachable" (dead code that exists but is
  never called is a different finding from a missing feature).
- When measuring a database, query the live schema, not the migration files:
  `information_schema` reflects what actually exists.
- Timestamps matter: a file modified in the last few minutes may be another
  session's in-flight work. Check `LastWriteTime` before editing, and never treat
  uncommitted concurrent edits as abandoned.

## Security and safety requirements

- Never print secret values. For `docs/lcssystem.pem` and any `.env`, report only
  existence, path, and whether it is git-tracked or ignored.
- Redact connection strings when quoting logs.
- Do not run destructive commands (`DROP`, `downgrade`, `down -v`) during analysis.

## Testing

Analysis is verified by reproducing its claims:

```bash
cd backend && uv run python -m pytest -q --no-header
cd backend && uv run ruff check .
cd frontend && pnpm lint && pnpm typecheck && pnpm test
cd backend && uv run python -m alembic heads        # single head?
cd backend && uv run python scripts/generate_schema_docs.py --check --strict
```

Record the exact command and its observed result. A claim with no command behind it
is an assumption and must be labelled as one.

## Acceptance criteria

- Every feature in scope carries a bucket and `path:line` evidence.
- Each doc drift is listed with the doc location and the contradicting code.
- The hardcoded-configuration register states DB-overridable or code-only per item.
- Security and financial risks are separate, ranked lists.
- The plan marks destructive steps explicitly.
- No claim about passing tests that was not executed in this session.

## Expected outputs

- `docs/17_repository_analysis.md` — inventory, classification, drift, risks.
- An updated `docs/18_implementation_checklist.md` row per affected feature.
- A short plan: ordered steps, each with its verification command.
