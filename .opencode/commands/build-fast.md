---
description: Build only the artefacts the current change can break
---

Skip anything the diff cannot affect, and say what you skipped.

1. Backend Python: nothing to compile. `uv run python -c "import app.main"` from
   `backend/` is enough to prove imports resolve.
2. Frontend: only for `frontend/**` changes — from `frontend/` `pnpm generate`
   (`nuxt generate`; this is the production SPA build). A dev-server check is
   `pnpm dev`, not a build.
3. Docker: only when a Dockerfile, dependency manifest, `infrastructure/**` or
   `infrastructure/docker-compose.prod.yml` changed. Rebuild one service, not the stack:
   `docker compose -f infrastructure/docker-compose.yml build backend` (or `frontend`).
4. Do not run `--no-cache`, do not prune, and do not run `docker compose down -v`.
   Layer caches are the point: `uv sync --frozen` and `pnpm install --frozen-lockfile`
   are cached in the image and only invalidate when the lockfile changes.
5. Never rebuild the image just to re-run a test — the backend test suite runs from the
   host with `uv`.

Report per artefact: built / skipped (with reason) / failed.
