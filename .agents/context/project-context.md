# LCS project context

Source-inspected 2026-11-04; working-tree facts, not release acceptance. Recheck the
changed manifest/source. This summary routes context; canonical docs own requirements.

## Verified stack and boundaries

| Area | Evidence / implementation |
|---|---|
| Frontend | Nuxt 4 / Vue 3 / TypeScript; Nuxt UI 4, Tailwind 4, Pinia; frontend/package.json |
| Runtime | Static SPA, ssr:false, nuxt generate; nginx serves .output/public and proxies /api/; frontend/nuxt.config.ts and frontend/Dockerfile |
| Backend | Python >=3.12, FastAPI, async SQLAlchemy 2, Pydantic 2, Alembic; backend/pyproject.toml |
| Data/services | PostgreSQL 16, Redis 7, MinIO/S3 storage; infrastructure/docker-compose.yml |
| Auth | Session-bound JWT access, rotating refresh cookies; backend/app/modules/auth/ and backend/app/core/authorization/ (Casbin) |
| Tests | Pytest/pytest-asyncio with SQLite fixtures; isolated PostgreSQL for locking/triggers. Vitest node tests; separate Playwright E2E |

Backend: backend/app/api/v1/router.py registers modules under /api/v1. Router → service →
repository/models; business rules/transactions stay server-side. Success envelope {data:...};
shared error envelope and field keys are client contracts.
Frontend: thin app/pages → views/composables → repository contracts/HTTP → Pinia.
Metadata: app/config/freight-modules.ts, lcs-reference-modules.ts, freight-reports.ts.
Registries: app/utils/constants/api-v1-endpoints.ts and app/utils/api/freight-remote.ts.
Reuse shared form validation/errors and English/Khmer/Chinese bundles.

## Commands — select by risk, do not run all

| Directory | Command / purpose |
|---|---|
| backend/ | uv run --no-sync pytest -q tests/<file>.py — focused existing environment; frozen sync only if setup is needed |
| backend/ | uv run --no-sync ruff check <changed-paths>; uv run --no-sync alembic heads for chain work |
| backend/ | uv run --no-sync python scripts/generate_schema_docs.py --check --strict — schema changes only |
| frontend/ | pnpm exec vitest run tests/<file>.spec.ts; pnpm exec eslint <changed-files>; pnpm typecheck for component/type changes |
| frontend/ | pnpm i18n:check for locales; pnpm generate for build-affecting changes; pnpm test:e2e only for relevant safe browser scenarios |
| root | node scripts/feature-status.mjs — read-only routing; includes preexisting dirty files, never promotes status |

Full suites are deliberate broad-regression/release checks, not ordinary defaults.
Use available lean-ctx for reads/search/shell; recover exact slices when compression omits
needed details. Respect restrictions. No browser/server/database for setup-only work.

## Rules, progress and limits

- [Decisions](decisions.md) separates approved rules, inspected facts and gaps.
- [Module map](module-map.md) routes all 44 pages to source owners.
- [Roadmap](../../docs/04-implementation/master-plan.md) owns S01–S13 sequence;
  [tracker](../../docs/04-implementation/phase-tracker.md) owns P00–P16 tasks.
  S01 / PLAN-0002 is the unfinished resume pointer; PLAN-0004 printing is completed only
  in its recorded scope. Re-read the current Handoff instead of trusting this dated pointer.
- Rich period-closing review/reconciliation is planned, despite existing custom periods and
  basic close/reopen. A page's existence does not prove its requirements complete.
- Historical evidence, SQLite and Chromium PDF checks do not prove current production
  readiness, PostgreSQL concurrency or cross-browser acceptance.
- No private keys, secret env values or customer financial data in memory. No new stack,
  business page, financial engine or automatic next-phase execution.
