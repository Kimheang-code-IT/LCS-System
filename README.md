# LCS Freight Forwarding Platform

Modular-monolith freight forwarding, operations and double-entry finance system.

- **Frontend:** Nuxt 4 static SPA (`frontend/`) — built with `nuxt generate`, served by nginx.
- **Backend:** FastAPI + SQLAlchemy 2.x + Alembic (`backend/`).
- **Database and authorization:** PostgreSQL with Casbin RBAC and session-bound authentication.
- **Storage:** Cloudflare R2 / Google Drive for file attachments, configured in Settings → Storage & Backup.
- **Infrastructure:** Compose, env files and nginx config (`infrastructure/`).

## Current version

- **Reports & dashboard are backend-driven** — dashboard KPIs and all report
  tables are served by `/api/v1/reports/*` instead of being computed in the
  browser from cached store data.
- **First-run setup** — an empty database redirects to `/auth/setup`, which
  provisions the administrator and baseline reference/configuration records.
- **Approved navigation** — 44 business pages, including Posting Rules. Organizations
  and Branches are outside the current single-tenant scope.
- **Standard host ports** — backend `8000`, frontend `80`, PostgreSQL `5432`,
  Redis `6379`.

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

Health: `http://localhost:8000/health`, `http://localhost:8000/health/ready`.

Host ports are env-driven (see `infrastructure/.env` / `infrastructure/.env.example`):
`FRONTEND_HOST_PORT` (default `80`), `BACKEND_HOST_PORT` (default `8000`),
`POSTGRES_HOST_PORT` (default `5432`), `REDIS_HOST_PORT` (default `6379`).

Authentication uses JWT: the access token is short-lived
(`ACCESS_TOKEN_EXPIRE_MINUTES`, 15 in Docker and capped at 30 in production) and
is delivered in a Secure HttpOnly cookie; refresh tokens rotate a persisted
server-side session and are never readable from JavaScript. The login page's
**Remember me** option controls persistence: when checked, the refresh session
lasts `REFRESH_TOKEN_EXPIRE_DAYS` (30 days) with persistent cookies; when
unchecked, cookies are browser-session cookies and the server enforces
`SESSION_REFRESH_TOKEN_EXPIRE_HOURS` (12 hours). Change the durations via the env
vars without rebuilding.

The **local development** backend container waits for PostgreSQL and Redis
to become healthy, then runs `alembic upgrade head`. Production images start
Uvicorn only: the production workflow runs Alembic explicitly with the new image
while the old stack is still serving. A fresh database requires first-run administrator
setup (see below); setup creates baseline configuration, not business transactions.

The frontend is a static SPA served by nginx, which also reverse-proxies `/api/`
to the backend, so the browser uses a single origin (no CORS, no Node runtime).
Only nginx, the FastAPI backend and the datastores run in production; this is
intended for a small-to-medium business. Capacity is unverified; 10–30 concurrent users is a preliminary planning assumption only.

### Empty database / first login

A freshly migrated database has no users. Open
the app and it redirects to the **first-run setup page** (`/auth/setup`), where you
create the first administrator in the browser. The setup page
provisions the permission catalog, protected system role, administrator and baseline
reference/configuration records, including currencies, role vocabularies and current-year
document sequences. It does not seed business transactions, accounts or accounting periods.
Setup is accepted only while no user exists (guarded by
`GET /api/v1/auth/setup/status` / `POST /api/v1/auth/setup/initialize`).

### Reset business data

An administrator (permission `settings.manage`) can clear business and
configuration records from **System Settings → Reset all data** (type `RESET`
to confirm). The API is `POST /api/v1/settings/reset-data` with body
`{"confirm": "RESET"}`. Security identities are deliberately preserved:
users, credentials, roles, permissions, role assignments, sessions, and audit
history are not deleted, so the protected System Administrator remains usable
and first-run setup is not reopened.

File attachments use Cloudflare R2 or Google Drive, configured in
Settings → Storage & Backup. Upload/download behavior follows the configured
provider and authorization path; MinIO is no longer part of the stack and there
is no object-storage environment configuration. See the operations and security
references before changing storage configuration.

## Modules

```text
backend/app/modules/
├── auth/          users, roles, permissions, sessions, single-role RBAC
├── master_data/   business parties, role vocabularies, types, currencies/FX, component/tab configuration, versions
├── quotations/    quotations, immutable revisions, comparison, conversion
├── operations/    service orders, containers, movements, milestones, dynamic tabs, charges, files
├── finance/       financial documents, posting, allocation, journals, accounts, periods
├── reports/       server-side dashboard, operational, accounting and financial-statement reports
├── settings/      branding, localization, app config, global search, reset-all-data
├── backup/        Google Sheets replication and its scheduler
├── archive/       soft-delete tombstones, restore, guarded hard delete
└── audit/         append-only audit trail
```

## Documentation map

Start with [docs/README.md](docs/README.md). Documentation is grouped for easier maintenance:

- [Project](docs/00-project/README.md): overview, requirements, 44-page inventory, status and audit.
- [Architecture](docs/01-architecture/system-architecture.md): system, database, API, security and decisions.
- [Business](docs/02-business/workflows.md): lifecycle rules, workflows, accounting/posting and UI standards.
- [Development](docs/03-development/ai-agent-guidelines.md): coding, tests, deployment and Git guidance.
- [Implementation](docs/04-implementation/master-plan.md): master plan, tracker, dependencies, acceptance and phases.
- [Archive](docs/archive/README.md): preserved older references with explicit review limits.

The [active S01 Handoff](docs/04-implementation/plans/PLAN-0002-access-and-page-authorization.md#handoff)
controls unfinished implementation scope. Folder reorganization does not promote application
acceptance or production readiness. The [feature-status report](docs/00-project/feature-status.md)
and [generated schema](docs/01-architecture/database-design.sql) retain their tooling support.
Agent workflows and commands remain in .opencode/; read AGENTS.md before making changes.

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

Use [focused-first gates](docs/03-development/testing-guide.md) for the changed behavior and stack.
Run commands from backend/ or frontend/ as appropriate. Schema generation/migrations,
full suites, i18n, browser and build checks depend on scope; do not run database upgrades as
a generic documentation gate. Record exact executed evidence and skips in the active plan.
