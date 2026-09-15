# LCS Freight Forwarding Platform

Modular-monolith freight forwarding, operations and double-entry finance system.

- **Frontend:** Nuxt 4 static SPA (`frontend/`) — built with `nuxt generate`, served by nginx.
- **Backend:** FastAPI + SQLAlchemy 2.x + Alembic (`backend/`).
- **Storage:** MinIO (S3-compatible) for attachments.
- **Infrastructure:** Compose, env files and nginx config (`infrastructure/`).

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
| Frontend (nginx) | http://localhost:18080 | `frontend:80` |
| Backend / API docs | http://localhost:18081 · http://localhost:18081/docs | `backend:8000` |
| PostgreSQL | `localhost:15432` | `postgres:5432` |
| Redis | `localhost:16379` | `redis:6379` |
| MinIO API / Console | http://localhost:19000 · http://localhost:19001 | `minio:9000` / `9001` |

Health: `http://localhost:18081/health`, `http://localhost:18081/health/ready`.

Host ports are env-driven (see `infrastructure/.env` / `infrastructure/.env.example`):
`FRONTEND_HOST_PORT`, `BACKEND_HOST_PORT`, `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`,
`MINIO_HOST_PORT`, `MINIO_CONSOLE_HOST_PORT`.

The backend container waits for PostgreSQL, Redis and MinIO to become healthy,
then runs `alembic upgrade head`. **No data is seeded** — the database starts
empty, so the first login requires a user to be provisioned (see below).

The frontend is a static SPA served by nginx, which also reverse-proxies `/api/`
to the backend, so the browser uses a single origin (no CORS, no Node runtime).
Only nginx, the FastAPI backend and the datastores run in production; this is
sized for small internal teams (well under ~15 concurrent users).

### Empty database / first login

Because all seeding was removed, a freshly migrated database has no users. To
sign in you must create an organization, a role, a user and a credential. Ask
for a `create-admin` management command if you want this automated, or insert
them directly with `psql` against the `freight` database.

Attachments are stored in MinIO (`STORAGE_PROVIDER=s3`); the backend signs
uploads/downloads with the public endpoint (`S3_PUBLIC_ENDPOINT_URL`) so the
browser can open files at `http://localhost:19000/...`. Set
`STORAGE_PROVIDER=local` to fall back to the `freight_uploads` volume.

## Modules

```text
backend/app/modules/
├── auth/          users, roles, permissions, sessions, org/branch context
├── master_data/   business parties, places, types, component/tab configuration
├── quotations/    quotations, immutable revisions, conversion
├── operations/    service orders, containers, dynamic tabs, charges, files
├── finance/       financial documents, posting, allocation, journals, accounts
├── reports/       server-side operational and accounting reports
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
