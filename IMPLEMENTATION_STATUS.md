# Implementation Status

| Area | Database | API | Tests | Frontend | Status |
|---|---|---|---|---|---|
| Core | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| Auth | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| Master Data | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| Quotations | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| Operations | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| Finance | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| Reports | COMPLETE | COMPLETE | COMPLETE | IN PROGRESS | IN PROGRESS |
| Audit | COMPLETE | COMPLETE | COMPLETE | COMPLETE | COMPLETE |

## Notes

- **Core** — config, async SQLAlchemy 2.x, Redis (optional), JWT, ERP permissions,
  consistent error payloads, pagination, Alembic migration, Docker + Compose.
- **Auth** — bearer and HttpOnly-cookie sessions, refresh rotation, forgot/reset
  password, users, roles, permissions, organization/branch scope.
- **Master Data** — one shared business-party model with multi-role mapping,
  places, trade directions, container/transport/fee types, transport assets,
  component groups/templates/attributes and trade-direction component config.
- **Quotations** — quotation aggregate with immutable sent revisions, explicit
  send/accept/convert actions, accepted-revision-only conversion with source link.
- **Operations** — service orders created from quotations, container requirements
  vs actual containers, versioned dynamic components with typed values, movements,
  milestones, informational service charges, attachment uploads.
- **Service Order dynamic tabs** — configurable operational tabs (Invoice, Packing
  List, Shipment Registration No., Bill, Customs, Transport + any admin-defined
  tab) render as editable multi-row tables driven by tab/column configuration
  (`service_order_tab_configs`, `service_order_column_configs`) and row JSONB
  (`service_order_tab_rows`). Adding a tab or column requires no frontend change
  and no new migration. Config is managed at Settings → Service Order Tabs
  (`/configuration/service-order-tabs`); APIs live in `master_data` (config) and
  `operations` (rows), with per-column type/reference/required validation.
- **Finance** — reusable financial documents, double-entry posting engine
  (balanced journals enforced in a transaction), payment allocation with balance
  validation, reversal, chart of accounts, financial accounts, periods, sequences,
  posting rules.
- **Reports** — server-side service-order, quotation, receivable, payable, income,
  expense, profitability and financial-summary queries.
- **Audit** — append-only event log written on login, quotation, component,
  service-charge, posting, allocation, reversal and period-closure actions.
- **Reports frontend** — the report pages are still rendered from the existing
  Nuxt routing; backend endpoints are ready and wired where the frontend already
  calls the API.

## Docker / infrastructure

- Compose project `freight_forwarding`: `frontend` (nginx), `backend`, `postgres`,
  `redis`, `minio`. Custom host ports (18080 / 18081 / 15432 / 16379 / 19000 /
  19001), project-scoped named volumes, bridge network, service DNS
  (`postgres:5432`, `redis:6379`, `minio:9000`), healthchecks for every service.
- Frontend image is a multi-stage build: `nuxt generate` (static SPA) then nginx.
  nginx serves the static bundle and reverse-proxies `/api/` to `backend:8000`
  (config mounted from `infrastructure/nginx/default.conf`).
- Backend entrypoint: `alembic upgrade head` then Uvicorn. **No seeding.**
- Attachments use MinIO via the `app/core/storage.py` abstraction
  (`STORAGE_PROVIDER=s3`); local filesystem remains available for dev.
- Existing unrelated Docker containers/projects are untouched.

## Maintenance / reset

Reset the database to an empty schema at any time (keeps volumes):

```bash
docker compose -f infrastructure/docker-compose.yml stop backend frontend
docker compose -f infrastructure/docker-compose.yml run --rm --no-deps backend alembic downgrade base
docker compose -f infrastructure/docker-compose.yml run --rm --no-deps backend alembic upgrade head
docker compose -f infrastructure/docker-compose.yml up -d
```

After a reset the database is empty (no users, roles, master data or
transactions). The MinIO bucket can be emptied with
`mc rm --recursive --force freight/freight-attachments` inside the MinIO container.

Removed code: backend seeding (`app/seed.py`, `SEED_ON_STARTUP`) and the whole
frontend mock layer — `app/repositories/mock/`, `app/mocks/`,
`app/utils/auth/mock-login.ts`, `app/config/freight-seed.ts`,
`app/config/lcs-seed.ts`, `app/config/lcs-tenant.ts`, the `NUXT_PUBLIC_USE_MOCK_DATA`
flag, the Vercel deploy files, plus earlier dead-code cleanups
(`types/freight/records.ts`, unused `/api/v2` auth endpoints, unused Google-login
i18n keys, unused exports). Seed data now exists only as test fixtures under
`frontend/tests/fixtures/`.

## Verification

```bash
cd backend
alembic upgrade head     # OK (2 revisions)
pytest -q                # 12 passed
ruff check .             # All checks passed

cd ../frontend
pnpm exec nuxt typecheck # clean
pnpm exec vitest run     # 33 files / 176 tests passed
pnpm exec eslint <files> # All checks passed
pnpm exec nuxt generate  # static SPA -> .output/public

# Running stack
docker compose -f infrastructure/docker-compose.yml ps   # all healthy
curl http://localhost:18080/health/ready      # {"status":"ready"} (via nginx)
# Comprehensive E2E suite against the running stack: 99/99 checks passed
# (auth, permissions, master-data CRUD, quotations lifecycle, operations,
# dynamic tabs, service charges, finance posting/allocation/reversal,
# reports, audit, MinIO presign). Full business flow also OK.
```

## Frontend ↔ API integration

- The frontend is **API-only**; the mock data layer, seed files and mock login
  accounts have been removed (`app/repositories/mock/`, `app/mocks/`,
  `app/utils/auth/mock-login.ts`, `app/config/*-seed.ts`). Seed fixtures live
  only under `frontend/tests/fixtures/` for the unit tests.
- Auth is real: `useAuth` calls `/api/v1/auth/*`; tokens are stored and attached
  as `Authorization: Bearer` by `useApi` (cookie + `credentials: include` also
  supported).
- `useFreightStore` is a remote-backed reactive cache:
  `list/get/save/create/remove/reload/related/dashboardSummary` map to the API
  (see `app/utils/api/freight-remote.ts`). It fetches on the client, so all
  existing detail/dashboard/report components read real backend data.
- The frontend is built as a static SPA (`nuxt generate`, `ssr: false`) and
  served by nginx, which reverse-proxies `/api/` to the backend. `apiBase` is
  empty so the browser calls the same origin.
- Backend is managed with **uv** (`uv.lock`, Docker `uv sync --frozen`).
- The backend no longer seeds on startup (`SEED_ON_STARTUP` removed; `app/seed.py`
  deleted). The database is empty after migrations.

### Environment

| Setting | Value |
|---|---|
| Frontend API base | same origin (`/api` via nginx) |
| Frontend delivery | static SPA (`nuxt generate`) behind nginx |
| Backend package manager | uv (`uv.lock`) |
| Storage | MinIO (`STORAGE_PROVIDER=s3`) |
| Seed data | none (empty database) |
