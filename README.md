# LCS Freight Forwarding Platform

Modular-monolith freight forwarding, operations and double-entry finance system.

- **Frontend:** Nuxt 4 static SPA (`frontend/`) — built with `nuxt generate`, served by nginx.
- **Backend:** FastAPI + SQLAlchemy 2.x + Alembic (`backend/`).
- **Database and authorization:** PostgreSQL with Casbin RBAC and session-bound authentication.
- **Storage:** MinIO (S3-compatible) for attachments.
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

Attachments use the existing S3-compatible storage interface, configured for MinIO in
Compose. Upload/download behavior follows the configured provider and authorization path;
production disables presigned uploads. Local storage remains an existing alternative.
See the operations and security references before changing storage configuration.

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

The approved foundation follows [system-design-prompt.md](docs/system-design-prompt.md).
Scope: exactly **44 business pages**, with supporting routes excluded.

- [00-agent-handbook.md](docs/00-agent-handbook.md)
- [01-system-architecture.md](docs/01-system-architecture.md)
- [02-data-model.md](docs/02-data-model.md)
- [03-security-access-control.md](docs/03-security-access-control.md)
- [04-record-workflow-lifecycle.md](docs/04-record-workflow-lifecycle.md)
- [05-api-specification.md](docs/05-api-specification.md)
- [06-operations-runbook.md](docs/06-operations-runbook.md)
- [07-adr-log.md](docs/07-adr-log.md)
- [08-app-flow.md](docs/08-app-flow.md)
- [09-design-brief.md](docs/09-design-brief.md)
- [10-coding-conventions.md](docs/10-coding-conventions.md)
- [11-testing-and-quality.md](docs/11-testing-and-quality.md)
- [12-documentation-standards.md](docs/12-documentation-standards.md)
- [13-git-workflow.md](docs/13-git-workflow.md)

- [Master roadmap](docs/plans/MASTER-ROADMAP.md)
- [Plan template](docs/plans/PLAN-0001-template.md)
- [Active S01 plan](docs/plans/PLAN-0002-access-and-page-authorization.md)
- [Handoff guide](docs/handoff/README.md)

The [44-page inventory](docs/09-design-brief.md#approved-44-page-inventory) and stable requirements
are consolidated into the canonical foundation. [Feature status](docs/12_feature_status.md)
and [generated schema](docs/06_database_design.sql) remain required tooling references.
The [cleanup inventory](docs/12-documentation-standards.md#documentation-cleanup-inventory)
lists retained dependency/review exceptions, not competing requirement authorities.
S01 is planned only; this foundation does not establish production readiness.

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
cd ../frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm i18n:check && pnpm generate
```
