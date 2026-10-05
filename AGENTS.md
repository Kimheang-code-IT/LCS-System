# AGENTS.md

Modular-monolith freight forwarding + double-entry finance system. Three top-level
trees: `backend/` (FastAPI), `frontend/` (Nuxt static SPA), `infrastructure/`
(compose + nginx). `docs/` holds the authoritative business/architecture specs.

## Commands

Each toolchain must run from its own directory (relative `.env`, `alembic.ini`,
`script_location`, and test paths all assume this).

```bash
# backend (from backend/)
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest -q                      # single: uv run pytest tests/test_workflows.py
uv run ruff check .

# frontend (from frontend/)
pnpm install
pnpm dev                              # dev server; pnpm generate builds the SPA
pnpm lint && pnpm typecheck && pnpm test
pnpm vitest run tests/format.spec.ts  # single test file
```

Quality gate order: `lint -> typecheck -> test` (frontend), `pytest -> ruff` (backend).
Two long-lived branches: `dev` (integration) and `main` (protected production).
`.github/workflows/dev-ci.yml` runs the gates plus Docker build validation on
pushes to `dev` and on PRs targeting `main`; it never deploys. `.github/workflows/production.yml`
runs only on `main` (or manual dispatch): validate, build immutable `sha-<short>`
images, push to GHCR, back up the database, then deploy to the AWS host. EC2 is a
runtime-only host — the Git repository is NOT cloned there; the workflow
transfers just `deploy/compose.yml` → `/opt/lcs/compose.yml` and
`infrastructure/nginx/production.conf` → `/opt/lcs/nginx/production.conf`, and
generates `/opt/lcs/.env` from the **production** environment secrets/vars (no
GHCR login; the images are public). Protect `main` with a ruleset requiring a
pull request and the **`Dev CI`** status check.

## Run stack

```bash
docker compose -f infrastructure/docker-compose.yml up -d --build   # from repo root
```

Host ports: frontend 80, backend 8000, Postgres 5432, Redis 6379, MinIO 9000/9001
(all env-driven in `infrastructure/.env`). The backend container runs
`alembic upgrade head` on start. The DB ships empty; first login is `/setup`
(`POST /api/v1/setup/initialize`, gated on no users existing), which provisions
the admin plus default document sequences (current year) and the default app
info/config — no finance or business data. Admin CLI:
`uv run python -m app.create_admin --email ... --password ...` (same baseline).

## Backend

- Python 3.12, async SQLAlchemy 2.x, Pydantic settings, `uv.lock` committed.
- Modules under `app/modules/<name>/` (`router.py`, `service.py`, `models.py`).
  Register new routers in `app/api/v1/router.py`.
- **API envelope:** successful payloads are `{"data": ...}`. List endpoints return
  `{"data": {"items": [...], "meta": {page, page_size, total}}}` (`core/pagination.py`).
  Errors are `{code, message, request_id, field_errors}` (see `app/main.py` handlers).
- Permission catalog + role mapping are **code-defined** in `app/core/permissions.py`
  and synced on startup; page/commercial codes here must be updated when adding
  endpoints.
- Migrations live in `alembic/versions/`. `alembic/env.py` explicitly imports every
  model module — add new ones there, and to `reset_all_data` in `app/core/bootstrap.py`
  (also referenced when wiping data via `POST /api/v1/settings/reset-data`).
- Ruff: line-length 120, `select = [E,F,I,UP,B]`, ignores `B008`, `E501`.
- Auth: JWT access token (default 24h) + rotating refresh token, sent as
  `Authorization: Bearer` or HttpOnly cookie. Config in `app/core/config.py`.
- Backup module runs an **in-process asyncio scheduler** (Google Sheets, no separate
  worker). Toggle via `BACKUP_SCHEDULER_ENABLED`; config stored per-install.

### Tests

- `backend/tests/` uses **in-memory SQLite** (`aiosqlite`), not Postgres; `conftest.py`
  overrides `get_session` and builds the schema with `Base.metadata.create_all`.
- `backend/tests/seed.py` is **test-only**, not used by the app. Default test login
  is `admin` / `Passw0rd!`.
- Fixtures: `client` (seeded AsyncClient), `login()` for auth headers.
- **Cross-stack contract test:** `tests/test_frontend_api_contract.py` statically
  reads frontend sources (`app/utils/constants/api-*.ts`,
  `app/utils/api/freight-remote.ts`, `app/config/freight-modules.ts`) and asserts
  every referenced `/api/v1/...` path and collection verb exists on the FastAPI app.
  Adding a frontend endpoint without the matching backend route (or vice versa)
  fails this test, not the browser.
- **Docker-only fallback (when `uv` is not on PATH):** run the backend test suite
  from the repo root against the built backend image, mounting the whole repo so
  the contract test can read `frontend/app` (the image ships no tests/dev deps):

  ```powershell
  docker run --rm -v "<repo>:/repo" -w /repo/backend freight_forwarding-backend:latest `
    sh -c "uv sync --frozen --extra dev && uv run pytest tests/test_frontend_api_contract.py -q"
  ```

  Drop the path argument to run the full suite. Verify the live API from the
  running stack with `docker exec ff-api curl -fsS http://localhost:8000/health`.

## Frontend

- Nuxt 4, `ssr: false`, built with `nuxt generate` and served by nginx; nginx also
  reverse-proxies `/api/` so the browser is same-origin.
- No mock data layer. All HTTP goes through `app/repositories/http/` behind the
  `app/repositories/index.ts` factories; Pinia stores in `app/stores/` (primary:
  `useFreightStore`). Register paths in `app/utils/constants/api-v1-endpoints.ts`
  (and `api-endpoints.ts`) plus `app/utils/api/freight-remote.ts`
  (`REMOTE_ENDPOINTS`) rather than calling `fetch` ad hoc — the backend contract
  test (above) reads these exact files.
- `app/utils/**` is auto-imported (`imports.dirs`); components/layouts/composables use
  Nuxt defaults. Use `~` for `app/`.
- **Icon gotcha:** `nuxt.config.ts` `icon.clientBundle.scan` only globs
  `app/components/**/*.{vue,ts}`, `app/composables/**/*.ts`, `app/config/**/*.ts`,
  `app/layouts/**/*.vue`, `app/pages/**/*.vue`. Icons referenced only in `app/utils`,
  `app/types` or `.json` won't be bundled — add the reference to a scanned file.
- Frontend tests are plain Vitest (`environment: node`, `import.meta.client = false`,
  alias `~ -> app`); only `tests/**/*.spec.ts`. They do not mount the Nuxt runtime.
- `pnpm-workspace.yaml` only lists `ignoredBuiltDependencies` — this is **not** a
  monorepo.

## Reference docs

`docs/05_solution_architecture.md`, `docs/06_database_design.sql`,
`docs/07_entity_relationship_diagram.mmd`, `docs/11_permissions_matrix.md`,
`docs/12_deployment_runbook.md`, and the root `README.md`.
