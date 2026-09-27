# LCS Freight Forwarding Platform

Modular-monolith freight forwarding, operations and double-entry finance system.

- **Frontend:** Nuxt 4 static SPA (`frontend/`) — built with `nuxt generate`, served by nginx.
- **Backend:** FastAPI + SQLAlchemy 2.x + Alembic (`backend/`).
- **Storage:** MinIO (S3-compatible) for attachments.
- **Infrastructure:** Compose, env files and nginx config (`infrastructure/`).

## Current version

- **Reports & dashboard are backend-driven** — dashboard KPIs and all report
  tables are served by `/api/v1/reports/*` instead of being computed in the
  browser from cached store data.
- **First-run setup** — an empty database redirects to `/setup`, which
  provisions the organization, administrator and a minimal finance baseline.
- **Simplified navigation** — the Organizations, Branches and Posting Rules
  screens were removed from the UI, and the role form now captures only name and
  permissions (no code/status/scope/level).
- **Standard host ports** — backend `8000`, frontend `80`, PostgreSQL `5432`,
  Redis `6379`, MinIO `9000` / `9001`.

## Run (Docker Compose)

All infrastructure lives in `infrastructure/` (compose file and env files). Run
Compose from the repository root, or `cd infrastructure` and drop the `-f` flag.

```bash
docker compose -f infrastructure/docker-compose.yml up -d --build
docker compose -f infrastructure/docker-compose.yml ps
docker compose -f infrastructure/docker-compose.yml logs -f backend
docker compose -f infrastructure/docker-compose.yml down    # keeps volumes/data
```

| Service | From your computer | Inside Docker |
|---|---|---|
| Frontend (nginx) | http://localhost (port 80) | `frontend:80` |
| Backend / API docs | http://localhost:8000 · http://localhost:8000/docs | `backend:8000` |
| PostgreSQL | `localhost:5432` | `postgres:5432` |
| Redis | `localhost:6379` | `redis:6379` |
| MinIO API / Console | http://localhost:9000 · http://localhost:9001 | `minio:9000` / `9001` |

Health: `http://localhost:8000/health`, `http://localhost:8000/health/ready`.

Host ports are env-driven (see `infrastructure/.env` / `infrastructure/.env.example`):
`FRONTEND_HOST_PORT` (default `80`), `BACKEND_HOST_PORT` (default `8000`),
`POSTGRES_HOST_PORT` (default `5432`), `REDIS_HOST_PORT` (default `6379`),
`MINIO_HOST_PORT` (default `9000`), `MINIO_CONSOLE_HOST_PORT` (default `9001`).

Authentication uses JWT: the access token lasts **a full day** by default
(`ACCESS_TOKEN_EXPIRE_MINUTES=1440`) and is sent as `Authorization: Bearer`;
refresh tokens rotate a persisted server-side session and last 30 days
(`REFRESH_TOKEN_EXPIRE_DAYS`). HttpOnly cookies are also set as a same-origin
fallback. Change the durations via the env vars without rebuilding.

The backend container waits for PostgreSQL, Redis and MinIO to become healthy,
then runs `alembic upgrade head`. **No data is seeded** — the database starts
empty, so the first login requires a user to be provisioned (see below).

The frontend is a static SPA served by nginx, which also reverse-proxies `/api/`
to the backend, so the browser uses a single origin (no CORS, no Node runtime).
Only nginx, the FastAPI backend and the datastores run in production; this is
sized for small internal teams (well under ~15 concurrent users).

### Empty database / first login

Because all seeding was removed, a freshly migrated database has no users. Open
the app and it redirects to the **first-run setup page** (`/setup`), where you
create the first organization and administrator in the browser. The setup page
provisions the permission catalog, roles, organization, head-office branch,
admin user/credential and a minimal finance baseline (chart of accounts, posting
rules, financial accounts, sequences, current periods) so the system is usable
immediately. Setup is accepted only while no user exists (guarded by
`GET /api/v1/setup/status` / `POST /api/v1/setup/initialize`).

The same provisioning is available headlessly (idempotent — re-run to reset the
password):

```bash
# Local venv
cd backend && uv run python -m app.create_admin --email admin@example.com --password 'Passw0rd!'

# Running Docker stack
docker compose -f infrastructure/docker-compose.yml exec backend \
  python -m app.create_admin --email admin@example.com --password 'Passw0rd!'
```

Options: `--username`, `--name`, `--org-code`, `--org-name`, `--branch-code`,
`--role` (`PLATFORM_ADMIN` default, or `ORGANIZATION_ADMIN`, …), `--country`,
`--currency`, `--timezone`.

### Reset all data

An administrator (permission `settings.manage`) can wipe every record and return
the system to first-run setup from **System Settings → Reset all data** (type
`RESET` to confirm). The API is `POST /api/v1/settings/reset-data` with body
`{"confirm": "RESET"}`. After a reset you are signed out and returned to
`/setup`.

Attachments are stored in MinIO (`STORAGE_PROVIDER=s3`); the backend signs
uploads/downloads with the public endpoint (`S3_PUBLIC_ENDPOINT_URL`) so the
browser can open files at `http://localhost:9000/...`. Set
`STORAGE_PROVIDER=local` to fall back to the `freight_uploads` volume.

## Modules

```text
backend/app/modules/
├── auth/          users, roles, permissions, sessions, org/branch context
├── master_data/   business parties, places, types, component/tab configuration
├── quotations/    quotations, immutable revisions, conversion
├── operations/    service orders, containers, dynamic tabs, charges, files
├── finance/       financial documents, posting, allocation, journals, accounts
├── reports/       server-side dashboard, operational and accounting reports
├── settings/      branding, localization, global search, reset-all-data
├── setup/         first-run organization/admin/finance provisioning
└── audit/         immutable audit trail
```

## Backend package manager — uv

The backend is managed with [uv](https://docs.astral.sh/uv/) (`uv.lock` is committed).
The Docker image installs from the lockfile with `uv sync --frozen`.

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Frontend ↔ API

The frontend talks only to the real `/api/v1` API: auth (bearer token + cookie),
all master-data/config collections, quotations, service orders (including the
dynamic configurable tabs), finance, reports and audit. There is **no mock data
layer** — the legacy seeds, mock repositories and mock accounts have been
removed. All HTTP access goes through `app/repositories/http/` and the Pinia
`useFreightStore`, and the static bundle calls the backend same-origin through
nginx.

## Quality gates

```bash
cd backend && uv run alembic upgrade head && uv run pytest -q && uv run ruff check .
cd ../frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm generate
```
