---
description: Check whether documentation is stale or missing for the current change
---

Scope: the uncommitted diff plus what it changes in behaviour.

1. Generated files — never hand-edit. Regenerate and verify from `backend/`:
   `uv run python scripts/generate_schema_docs.py --check --strict`. Prose for table and
   column descriptions lives in `backend/scripts/schema_descriptions.py`.
2. Status and risk — `docs/10_testing_and_quality.md` (verified implementation status,
   coverage gaps, open risks). Update the entry the change touches; never mark
   unverified work complete.
3. Permissions — a new endpoint or permission code updates `docs/09_roles_and_permissions.md`
   and `app/core/permissions.py` together.
4. Architecture — layering, module boundary, or a new module updates
   `docs/05_solution_architecture.md`.
5. Deploy — a new env var, service, or migration step updates
   `docs/11_deployment_and_security.md` and `infrastructure/.env.example`.
6. Commands — a new or changed command updates the command list in `AGENTS.md` and
   `README.md` only if the documented invocation changed.
7. Reference check — every path and symbol the docs name must still exist. Report dead
   references instead of silently deleting surrounding text.

Report: files updated, files that still need updating and why, and anything that cannot be
verified in this environment.
