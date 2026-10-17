# AGENTS.md

Modular-monolith freight forwarding + double-entry finance system. Three top-level
trees: `backend/` (FastAPI), `frontend/` (Nuxt static SPA), `infrastructure/`
(compose + nginx). `docs/` holds the authoritative business/architecture specs.

## Agent tooling

- **Project config:** `opencode.jsonc` at the repo root. It sets no model or
  provider (those stay in your global config) and adds two things: secret
  protection (`read`/`edit` denied for `*.pem`, `*.key`, `**/.env`, kept out of
  model context and off disk) and approval prompts for irreversible commands
  (`git push`, `alembic downgrade`, `DROP DATABASE`, `down -v`, `rm -rf`).
- **Skills:** `.opencode/skills/<id>/SKILL.md`, auto-discovered. `lcs-development`
  is the umbrella working agreement; load the focused skill for the area you are
  touching (`database-migration`, `fastapi-backend`, `nuxt-frontend`,
  `dynamic-ui-configuration`, `quotation-management`, `finance-accounting`,
  `security-rbac`, `testing-qa`, `deployment-devops`, `project-analysis`). They
  carry the detailed workflow and acceptance criteria — this file stays an index.
- **Read the whole `docs/17_repository_analysis.md` and
  `docs/18_implementation_checklist.md` before starting a non-trivial change** so
  you inherit the verified feature status instead of re-deriving it.
- If another session is editing a tree, check `LastWriteTime` first and do not race
  it. Uncommitted edits are user work, never abandoned work.

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
uv run python scripts/generate_schema_docs.py   # regenerate docs/06b (add --check to verify)
uv run python scripts/generate_schema_dump.py   # regenerate docs/06  (add --check to verify)

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
`alembic upgrade head` on start. The DB ships empty; first login is `/auth/setup`
(`POST /api/v1/auth/setup/initialize`, gated on no users existing), which provisions
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
- **i18n (`@nuxtjs/i18n` v10, `strategy: no_prefix`):** English, Khmer and
  Simplified Chinese. Message bundles live in `i18n/locales/<code>.json` and
  **must stay structurally identical to `en.json`**. Add a language in one place —
  `app/utils/constants/app-languages.ts` (single registry for codes, names and
  BCP-47 locales) — then mirror the entry in `nuxt.config.ts` `i18n.locales`, add
  the script font in `fonts.families` + `html[lang]` rules in
  `app/assets/css/main.css`, and add the code to `SUPPORTED_LANGUAGES` /
  `_LANGUAGE_LOCALES` in `backend/app/core/localization.py`. Never hardcode a
  `'en' | 'km'` union; derive from the registry.
  Run `pnpm i18n:check` (parity + placeholder audit; also enforced by
  `tests/i18n-locales.spec.ts`). Manage keys with
  `node scripts/i18n.mjs add <locale> '<json>'`.
- **Label resolution:** never add a per-language parallel field (`labelKm`) for
  copy shipped in code — `useFreightLabel().fieldLabel()` resolves
  `labelKey` -> `freight.modules.<collection>.fields.<key>` -> `freight.fields.<key>`
  -> the English `label`, and warns in dev when a label has no key. The
  `labelKm` column that remains is *admin-managed data* (user-defined component
  attributes / dynamic-table columns) and is looked up per active locale via
  `STORED_LABEL_FIELDS`.
- **Print output is deliberately bilingual English + Khmer** (Cambodian tax
  invoice requirement) via `composables/print/usePrintBilingual.ts`, independent
  of the active UI language.
- **Form validation is one shared pipeline — never per page.** Use
  `composables/common/useFormValidation.ts` with the leaf rules in
  `app/utils/validation/` (`field-rules`, `record-validation`,
  `component-rules`, `error-paths`, `api-error`, `messages`, `focus`). A form
  supplies only its field `order`, a `label` resolver and a `reveal` callback
  that opens the owning tab/section; it never writes its own validation logic.
  Rules come from the existing module config (`required`, plus the new optional
  `rule` on `FreightField` / `FreightLineColumn`) and, for Service Order dynamic
  tabs, from the attribute's admin-managed `validationRules` blob.
  - Errors are addressed by a canonical camelCase model path; repeatable rows use
    `table.<rowIndex>.<column>`. Tag any new input with `data-field-key="<path>"`
    so first-invalid-field navigation can reach it.
  - `:error` on `UFormField` supplies `aria-invalid` / `aria-describedby`; render
    everything else through `CommonAppFormErrorSummary`.
  - **Notification policy:** validation errors and business-rule refusals are
    never toasts — they go on the field, or into a persistent form/page-level
    message. A toast is only for a confirmed success. `useApi` deliberately
    suppresses its own toast for 400/409/422 because the form renders those.
    `tests/validation-notification-policy.spec.ts` scans every toast call and
    fails the build if the rule is broken.
  - `validation.<code>` keys must exist in all three locale bundles;
    `tests/validation-messages.spec.ts` fails on a referenced-but-missing key.
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
- **No editor/Tiptap deps:** `frontend/.pnpmfile.cjs` strips `@tiptap/*` from
  `@nuxt/ui` at install time (no `UEditor*` component is used anywhere). The
  lockfile pins the hook via `pnpmfileChecksum`, and CI/Docker install with
  `--frozen-lockfile` need the file present. If Nuxt UI's editor is ever adopted,
  delete the hook and run `pnpm install --no-frozen-lockfile`.
- `pnpm-workspace.yaml` only lists `ignoredBuiltDependencies` — this is **not** a
  monorepo.

## Reference docs

`docs/05_solution_architecture.md`, `docs/06_database_design.sql`,
`docs/06b_database_design_annotated.sql`,
`docs/07_entity_relationship_diagram.mmd`, `docs/11_permissions_matrix.md`,
`docs/12_deployment_runbook.md`, and the root `README.md`.

`docs/17_repository_analysis.md` is the authoritative statement of **what is
actually implemented** (each feature classified as implemented-and-tested,
implemented-but-unverified, partial, missing, or obsolete) plus the hardcoded
configuration register and the security/financial risk lists.
`docs/18_implementation_checklist.md` tracks per-feature status and remaining work.
`docs/14`–`docs/16` cover the database migration analysis, the apply/rollback
procedure, and the upgrade summary with its outstanding risks.

`docs/06b_database_design_annotated.sql` is **generated** — it carries the same
DDL as `docs/06_database_design.sql` plus a description for every table and
column, as both inline `--` comments and executable `COMMENT ON` statements.
Its prose lives in `backend/scripts/schema_descriptions.py`; after changing a
model or a description, run `uv run python scripts/generate_schema_docs.py`
from `backend/`. `tests/test_schema_docs.py` fails if the file is stale, if a
column is undocumented, or if it drifts from `docs/06_database_design.sql`.

`docs/06_database_design.sql` is generated too, by
`backend/scripts/generate_schema_dump.py` — the un-annotated half of the pair.
Whenever a model changes, regenerate **both** files; the pair must always be
consistent, because the drift test compares their DDL structurally.

## Financial data integrity

Non-negotiable, regardless of the task:

- **Debit equals credit** for every journal. A posting is atomic: journal, lines,
  posting link, and document status commit together or not at all.
- **Posted history is immutable.** Corrections use `reverse_document`, never an
  edit or a delete. Enforced in the service layer *and* by PostgreSQL triggers
  (`fn_guard_journal_entry`, `fn_guard_journal_line`).
- **Closed periods reject new postings**; entries must fall inside an `OPEN`
  period, checked by the deferred constraint trigger `fn_validate_journal_post`.
- **No duplicate posting and no over-allocation** — unique
  `financial_document_postings` and the `fn_guard_allocation` guard.
- **Money is `NUMERIC`, decoded as `Decimal`.** Never `float`.
- **Historical rates are preserved.** A posting snapshots its own
  `exchange_rate` and stores `base_debit_amount` / `base_credit_amount`; never
  recompute a posted amount from a newer rate.
- **Posting rules come from `posting_rules`**, resolved per
  `(document_type, fee_type_id)` with a NULL-fee default and the highest
  `priority` winning within a tier. `DEFAULT_ACCOUNTS` in `finance/service.py` is
  a last-resort fallback, not the configuration. `PostingRuleResolver`
  (`finance/posting_rules.py`) answers *which accounts*; `AccountingPostingService`
  (`finance/posting.py`) answers *what journal* from the `STRATEGIES` table. No
  account id belongs in either file — add the type to `STRATEGIES` and
  `DOCUMENT_TYPE_LABELS` instead of special-casing a document type.
- **Reports read posted data only** and must be reconciled before being called
  correct (trial balance nets to zero; AR/AP match their control accounts).

Treat any change touching postings, allocations, periods, or account mapping as
high risk: load the `finance-accounting` skill and add regression tests.

## Documentation update rules

- Update the existing document; do not create a parallel one with a conflicting
  requirement. New documents are only for genuinely uncovered topics.
- Generated files are never hand-edited: `docs/06`, `docs/06b` come from
  `backend/scripts/`; descriptions come from `backend/scripts/schema_descriptions.py`.
- When a model, endpoint, permission, or report changes, update the matching doc in
  the same change and refresh its implementation status.
- Never label an unverified feature as complete. Record it in
  `docs/18_implementation_checklist.md` with the missing work named.
- Replace superseded text instead of appending a contradictory paragraph.

## Definition of Done

A change is complete only when all of these hold, and any that does not is
reported explicitly rather than glossed over:

1. The requested behaviour exists and is reachable from the UI or the API.
2. Authorization is enforced on the backend and a test proves the denial path.
3. Existing architecture and conventions are respected; no duplicate service,
   repository, endpoint, component, or store was introduced.
4. Database changes are additive Alembic revisions with a working `downgrade()`,
   and both generated schema documents are regenerated.
5. Money paths keep debit/credit balance and `Decimal` arithmetic, with a test.
6. Tests cover the new behaviour, its failure modes, and the boundary cases; no
   failing test was deleted, skipped, or weakened.
7. Gates pass: backend `pytest` + `ruff`; frontend `lint` + `typecheck` + `test` +
   `i18n:check`; plus the schema/migration checks when the schema changed.
8. Documentation reflects reality, including the new implementation status.
9. No secret, credential, debug print, or throwaway file was added.
10. The result is reported with the exact commands run and their observed
    outcomes, and every unverified claim is named as such.

