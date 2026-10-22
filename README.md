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

Authentication uses JWT: the access token is short-lived
(`ACCESS_TOKEN_EXPIRE_MINUTES`, 15 in Docker and capped at 30 in production) and
is delivered in a Secure HttpOnly cookie; refresh tokens rotate a persisted
server-side session and are never readable from JavaScript. The login page's
**Remember me** option controls persistence: when checked, the refresh session
lasts `REFRESH_TOKEN_EXPIRE_DAYS` (30 days) with persistent cookies; when
unchecked, cookies are browser-session cookies and the server enforces
`SESSION_REFRESH_TOKEN_EXPIRE_HOURS` (12 hours). Change the durations via the env
vars without rebuilding.

The **local development** backend container waits for PostgreSQL, Redis and MinIO
to become healthy, then runs `alembic upgrade head`. Production images start
Uvicorn only: the production workflow runs Alembic explicitly with the new image
while the old stack is still serving. **No data is seeded** - the database starts
empty, so the first login requires a user to be provisioned (see below).

The frontend is a static SPA served by nginx, which also reverse-proxies `/api/`
to the backend, so the browser uses a single origin (no CORS, no Node runtime).
Only nginx, the FastAPI backend and the datastores run in production; this is
sized for small internal teams (well under ~15 concurrent users).

### Empty database / first login

Because all seeding was removed, a freshly migrated database has no users. Open
the app and it redirects to the **first-run setup page** (`/auth/setup`), where you
create the first organization and administrator in the browser. The setup page
provisions the permission catalog, roles, organization, head-office branch,
admin user/credential and a minimal finance baseline (chart of accounts, posting
rules, financial accounts, sequences, current periods) so the system is usable
immediately. Setup is accepted only while no user exists (guarded by
`GET /api/v1/auth/setup/status` / `POST /api/v1/auth/setup/initialize`).

### Reset business data

An administrator (permission `settings.manage`) can clear business and
configuration records from **System Settings → Reset all data** (type `RESET`
to confirm). The API is `POST /api/v1/settings/reset-data` with body
`{"confirm": "RESET"}`. Security identities are deliberately preserved:
users, credentials, roles, permissions, role assignments, sessions, and audit
history are not deleted, so the protected System Administrator remains usable
and first-run setup is not reopened.

Attachments are stored in MinIO (`STORAGE_PROVIDER=s3`); the backend signs
uploads/downloads with the public endpoint (`S3_PUBLIC_ENDPOINT_URL`) so the
browser can open files at `http://localhost:9000/...`. Set
`STORAGE_PROVIDER=local` to fall back to the `freight_uploads` volume.

## Modules

```text
backend/app/modules/
├── auth/          users, roles, permissions, sessions, single-role RBAC
├── master_data/   business parties, places, types, currencies/FX, component/tab configuration, configuration versions
├── quotations/    quotations, immutable revisions, comparison, conversion
├── operations/    service orders, containers, movements, milestones, dynamic tabs, charges, files
├── finance/       financial documents, posting, allocation, journals, accounts, periods
├── reports/       server-side dashboard, operational, accounting and financial-statement reports
├── settings/      branding, localization, app config, global search, reset-all-data
├── setup/         first-run admin/finance provisioning
├── backup/        Google Sheets replication and its scheduler
├── archive/       soft-delete tombstones, restore, guarded hard delete
└── audit/         append-only audit trail
```

## Documentation map

| Document | Read it for |
|---|---|
| `AGENTS.md` | Commands, conventions, financial-integrity rules, Definition of Done |
| `docs/01_business_requirements.md` | Business goals, scope, actors, requirements |
| `docs/02_software_requirements.md` | Functional and non-functional requirements |
| `docs/03_business_process_and_sop.md` | Operational procedures and controls |
| `docs/04_functional_design.md` | Use cases, posting rules, error catalogue, and Mermaid diagrams |
| `docs/05_solution_architecture.md` | Architecture, layering, module boundaries |
| `docs/06_database_design.sql` | Generated schema: DDL with a description for every table and column |
| `docs/07_api_documentation.md` | API conventions, endpoint catalogue, dynamic collections, errors |
| `docs/08_frontend_and_ui_design.md` | Routes, metadata-driven pages, forms, validation, i18n |
| `docs/09_roles_and_permissions.md` | Permission catalog, role templates, page mapping, enforcement |
| `docs/10_testing_and_quality.md` | Test architecture, gates, coverage gaps, status, open risks |
| `docs/11_deployment_and_security.md` | Deploy, CI/CD, migrations, backup/restore, rollback, hardening |

Reusable agent workflows live in `.opencode/skills/` (`lcs-development` is the
umbrella; `database-migration`, `fastapi-backend`, `nuxt-frontend`,
`dynamic-ui-configuration`, `quotation-management`, `finance-accounting`,
`security-rbac`, `testing-qa`, `deployment-devops`, `project-analysis` are the
focused ones). Reusable slash commands live in `.opencode/commands/` and the
read-only review subagent in `.opencode/agents/reviewer.md`.

`docs/lcssystem.pem` is an untracked private key. It must never be committed,
copied into an image, or exposed; its relocation is an open owner decision.

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
