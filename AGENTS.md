# AGENTS.md

Modular-monolith freight forwarding + double-entry finance system. Three top-level
trees: `backend/` (FastAPI), `frontend/` (Nuxt static SPA), `infrastructure/`
(compose + nginx). `docs/` holds the authoritative business/architecture specs.

## Agent tooling

- **Project config:** `opencode.jsonc` (permissions, watcher; no model, so developers keep
  their own). **Commands:** `/check`, `/test-fast`, `/test-backend`, `/test-frontend`,
  `/verify`, `/debug`, `/docs-check`, `/build-fast`, `/project-audit`, `/token-report`
  (`.opencode/commands/`). **Reviewer:** `.opencode/agents/reviewer.md`, read-only
  subagent; use it for a second pass on changes touching finance, auth or schema.
- **Skills:** `.opencode/skills/<id>/SKILL.md`, auto-discovered. `lcs-development` is the
  umbrella working agreement; also load the focused skill for the area you touch:
  `database-migration`, `fastapi-backend`, `nuxt-frontend`, `dynamic-ui-configuration`,
  `quotation-management`, `finance-accounting`, `security-rbac`, `testing-qa`,
  `deployment-devops`, `project-analysis`.
- **Consult before a non-trivial change:** `docs/10_testing_and_quality.md` (verified
  feature status, coverage gaps, open risks) and `docs/11_deployment_and_security.md`
  (deployment, backup, security controls, open production risks). Read the relevant
  section, not the whole file.
- **Context tooling:** LeanCTX MCP (`ctx_*`) is available in this workspace.
  `ctx_compose` first for "where/how is X"; `ctx_tree` / `ctx_glob` (one pattern per call;
  brace expansion silently matches nothing) for shape and discovery; `ctx_search` scoped
  with `path`; `ctx_read` with `mode=map|signatures` or `lines:N-M`; `ctx_shell` for
  build/test output; `ctx_callgraph` when a shared service, schema or permission constant
  changes. Fall back to native `read`/`grep`/`glob`/`shell` when a path is outside its
  roots, when it is blocked by its shell allowlist, or when an edit needs exact bytes.
  It is read-only: all changes go through the normal edit tools.
- **Token discipline:** one discovery pass per task; reuse results instead of repeating a
  search or re-reading an unchanged file. Never save tokens on validation, authorization,
  error handling, tests or schema documentation.
- If another session is editing a tree, check `LastWriteTime` first. Uncommitted edits are
  user work, never abandoned work.

## Change workflow

1. Understand the request. A trivial, self-contained edit goes straight to
   implementation — no plan, no exploration pass.
2. Locate the owning module (`ctx_compose`); add `ctx_search`/`ctx_glob` only if it did not
   answer.
3. Read only the symbols, signatures or line ranges involved.
4. Check impact before editing shared code: other callers, `tests/test_frontend_api_contract.py`,
   `app/core/permissions.py`, generated schema docs.
5. Implement through the edit tools, matching the module layering
   (router → service → repository → schema) and reusing existing helpers.
6. Run the focused check for what changed (`/test-fast`, `/check`), then the
   Definition-of-Done gates; fix everything the change broke.
7. Report changed files, commands run, and observed results — briefly.

## Commands

Each toolchain runs from its own directory (relative `.env`, `alembic.ini`,
`script_location` and test paths assume it).

```bash
# backend (from backend/)
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest -q                      # single: uv run pytest tests/test_workflows.py
uv run ruff check .
uv run python scripts/generate_schema_docs.py   # regenerate docs/06_database_design.sql (add --check to verify)
uv run python scripts/generate_schema_dump.py   # compatibility wrapper for the same file

# frontend (from frontend/)
pnpm install
pnpm dev                              # dev server; pnpm generate builds the SPA
pnpm lint && pnpm typecheck && pnpm test && pnpm i18n:check
pnpm vitest run tests/format.spec.ts  # single test file
```

Gate order: frontend `lint -> typecheck -> test` (plus `i18n:check`), backend
`pytest -> ruff`. Branches: `dev` (integration), `main` (protected production).
`.github/workflows/dev-ci.yml` runs the gates plus a Docker build on pushes to `dev` and
PRs into `main`, and never deploys; `.github/workflows/production.yml` runs on `main`,
builds immutable `sha-<short>` images to GHCR, backs up the database, then deploys to the
AWS host. EC2 is runtime-only: the repo is not cloned there — the workflow transfers
`deploy/compose.yml`, `infrastructure/nginx/production.conf` and a generated `/opt/lcs/.env`.
Protect `main` with a ruleset requiring a PR and the `Dev CI` check.

## Run stack

```bash
docker compose -f infrastructure/docker-compose.yml up -d --build   # from repo root
```

Host ports: frontend 80, backend 8000, Postgres 5432, Redis 6379, MinIO 9000/9001 (all
env-driven in `infrastructure/.env`). The backend container runs `alembic upgrade head` on
start. The DB ships empty; first login is `/auth/setup`
(`POST /api/v1/auth/setup/initialize`, gated on no users existing), which provisions the
admin, default document sequences (current year) and default app info/config — no finance
or business data.

## Backend

- Python 3.12, async SQLAlchemy 2.x, Pydantic settings, `uv.lock` committed.
- Modules under `app/modules/<name>/` (`router.py`, `service.py`, `models.py`); register new
  routers in `app/api/v1/router.py`.
- **API envelope:** success is `{"data": ...}`. Lists return
  `{"data": {"items": [...], "meta": {page, page_size, total}}}` (`core/pagination.py`).
  Errors are `{code, message, request_id, field_errors}` (`app/main.py` handlers).
- Permission catalog and role mapping are **code-defined** in `app/core/permissions.py`,
  synced on startup; update it (and `docs/09_roles_and_permissions.md`) with any new endpoint.
- Migrations live in `alembic/versions/`. `alembic/env.py` imports every model module — add
  new ones there and to `reset_all_data` in `app/core/bootstrap.py`.
- Ruff: line-length 120, `select = [E,F,I,UP,B]`, ignores `B008`, `E501`.
- Auth: JWT access token (default 24h) + rotating refresh token, as `Authorization: Bearer`
  or HttpOnly cookie. Config in `app/core/config.py`.
- Backup module runs an **in-process asyncio scheduler** (Google Sheets, no worker);
  `BACKUP_SCHEDULER_ENABLED` toggles it, config is per-install.

### Tests

- `backend/tests/` uses **in-memory SQLite** (`aiosqlite`), not Postgres; `conftest.py`
  overrides `get_session` and builds the schema with `Base.metadata.create_all`.
- `backend/tests/seed.py` is **test-only**. Default test login `admin` / `Passw0rd!`.
  Fixtures: `client` (seeded AsyncClient), `login()` for auth headers.
- **Cross-stack contract test:** `tests/test_frontend_api_contract.py` statically reads
  `app/utils/constants/api-*.ts`, `app/utils/api/freight-remote.ts` and
  `app/config/freight-modules.ts` and asserts every referenced `/api/v1/...` path and
  collection verb exists on the FastAPI app. Adding a frontend endpoint without the backend
  route (or the reverse) fails here, not in the browser.
- **Docker-only fallback (no `uv` on PATH):** mount the repo so the contract test can read
  `frontend/app` (the image ships no tests or dev deps):

  ```powershell
  docker run --rm -v "<repo>:/repo" -w /repo/backend freight_forwarding-backend:latest `
    sh -c "uv sync --frozen --extra dev && uv run pytest tests/test_frontend_api_contract.py -q"
  ```

  Drop the path to run the full suite. Verify the live API with
  `docker exec ff-api curl -fsS http://localhost:8000/health`.

## Frontend

- Nuxt 4, `ssr: false`, built with `nuxt generate`, served by nginx, which also
  reverse-proxies `/api/` so the browser is same-origin.
- **i18n (`@nuxtjs/i18n` v10, `strategy: no_prefix`):** English, Khmer, Simplified Chinese.
  `i18n/locales/<code>.json` must stay structurally identical to `en.json`. A new language
  is added in one place — `app/utils/constants/app-languages.ts` — then mirrored in
  `nuxt.config.ts` `i18n.locales`, the script font in `fonts.families` + `html[lang]` rules
  in `app/assets/css/main.css`, and `SUPPORTED_LANGUAGES` / `_LANGUAGE_LOCALES` in
  `backend/app/core/localization.py`. Never hardcode an `'en' | 'km'` union.
  `pnpm i18n:check` (also `tests/i18n-locales.spec.ts`).
- **Label resolution:** never add a per-language parallel field (`labelKm`) for copy shipped
  in code — `useFreightLabel().fieldLabel()` resolves
  `labelKey` -> `freight.modules.<collection>.fields.<key>` -> `freight.fields.<key>` ->
  English `label`. The `labelKm` column that remains is *admin-managed data* (user-defined
  attributes / dynamic-table columns), resolved per locale via `STORED_LABEL_FIELDS`.
- **Print output is deliberately bilingual English + Khmer** (Cambodian tax invoice
  requirement) via `composables/print/usePrintBilingual.ts`, independent of the UI language.
- **Form validation is one shared pipeline — never per page:** `useFormValidation` with leaf
  rules in `app/utils/validation/`. A form supplies only its field `order`, a `label`
  resolver and a `reveal` callback. Rules come from module config (`required`, optional
  `rule`) and, for Service Order dynamic tabs, the attribute's `validationRules`.
  - Errors use a canonical camelCase model path; repeatable rows use `table.<row>.<column>`.
    Tag new inputs with `data-field-key="<path>"`.
  - `:error` on `UFormField` supplies `aria-invalid` / `aria-describedby`; a field error is
    reported **only** there. `CommonAppFormErrorSummary` renders just the messages that
    belong to no field, and every form producing `formErrors` renders it.
  - **Notification policy:** validation errors and business refusals are never toasts — on
    the field, or in a persistent form/page message. A toast is only for confirmed success;
    `useApi` suppresses its own toast for 400/409/422. Enforced by
    `tests/validation-notification-policy.spec.ts`.
  - `validation.<code>` keys must exist in all three bundles
    (`tests/validation-messages.spec.ts`).
- No mock data layer. All HTTP goes through `app/repositories/http/` behind the
  `app/repositories/index.ts` factories; Pinia stores in `app/stores/` (primary
  `useFreightStore`). Register paths in `app/utils/constants/api-v1-endpoints.ts` (and
  `api-endpoints.ts`) plus `app/utils/api/freight-remote.ts` (`REMOTE_ENDPOINTS`) rather than
  calling `fetch` ad hoc — the contract test reads those exact files.
- `app/utils/**` is auto-imported (`imports.dirs`); components/layouts/composables use Nuxt
  defaults. `~` maps to `app/`.
- **Icon gotcha:** `icon.clientBundle.scan` only globs `app/components/**`, `app/composables/**`,
  `app/config/**`, `app/layouts/**`, `app/pages/**`. Icons referenced only in `app/utils`,
  `app/types` or `.json` are not bundled — add the reference to a scanned file.
- Tests are plain Vitest (`environment: node`, `import.meta.client = false`, alias
  `~ -> app`); only `tests/**/*.spec.ts`; no Nuxt runtime and **no browser suite**.
- **No editor/Tiptap deps:** `frontend/.pnpmfile.cjs` strips `@tiptap/*` from `@nuxt/ui`.
  The lockfile pins the hook via `pnpmfileChecksum`, so CI and Docker (`--frozen-lockfile`)
  need the file present. Adopting Nuxt UI's editor means deleting the hook and running
  `pnpm install --no-frozen-lockfile`.
- `pnpm-workspace.yaml` only lists `ignoredBuiltDependencies` — this is **not** a monorepo.

## Reference docs

The `docs/` tree is the authoritative documentation set. It contains exactly eleven
documents (ten Markdown files plus one SQL schema reference) and one untracked
private key, `docs/lcssystem.pem`; never read, copy, commit or expose that key.

| File | Contents |
|---|---|
| `docs/01_business_requirements.md` | Business goals, scope, actors, requirements |
| `docs/02_software_requirements.md` | Functional and non-functional requirements |
| `docs/03_business_process_and_sop.md` | Operational procedures and controls |
| `docs/04_functional_design.md` | Use cases, posting rules, error catalogue, and the Mermaid ER/process/data-flow diagrams |
| `docs/05_solution_architecture.md` | Module boundaries, request flow, transactions, finance architecture |
| `docs/06_database_design.sql` | Generated DDL: tables, columns, keys, constraints, indexes, comments |
| `docs/07_api_documentation.md` | API conventions, endpoint catalogue, dynamic collections, error codes |
| `docs/08_frontend_and_ui_design.md` | Routes, metadata-driven pages, forms, validation, i18n, components |
| `docs/09_roles_and_permissions.md` | Permission catalog, role templates, page mapping, enforcement |
| `docs/10_testing_and_quality.md` | Test architecture, gates, coverage gaps, implementation status, open risks |
| `docs/11_deployment_and_security.md` | Deploy, CI/CD, migration, backup/restore, rollback, hardening, risks |

`README.md` is the repository entry point. `docs/06_database_design.sql` is
**generated**: the model DDL plus a description for every table and column, as
inline comments and executable `COMMENT ON` statements. Its prose lives in
`backend/scripts/schema_descriptions.py`; after changing a model or a description
run `uv run python scripts/generate_schema_docs.py` from `backend/`.
`tests/test_schema_docs.py` fails if it is stale, if a column is undocumented, or
if more than one SQL file exists. `scripts/generate_schema_dump.py` is a
compatibility wrapper for the same output.

## Financial data integrity

Non-negotiable, regardless of the task:

- **Debit equals credit** for every journal. Posting is atomic: journal, lines, posting link
  and document status commit together or not at all.
- **Posted history is immutable.** Corrections use `reverse_document`, never an edit or a
  delete — enforced in the service layer *and* by PostgreSQL triggers
  (`fn_guard_journal_entry`, `fn_guard_journal_line`).
- **Closed periods reject new postings**; entries must fall inside an `OPEN` period (deferred
  constraint trigger `fn_validate_journal_post`).
- **No duplicate posting, no over-allocation** — unique `financial_document_postings` and the
  `fn_guard_allocation` guard.
- **Money is `NUMERIC`, decoded as `Decimal`.** Never `float`.
- **Historical rates are preserved.** A posting snapshots its own `exchange_rate` and stores
  `base_debit_amount` / `base_credit_amount`; never recompute a posted amount from a newer
  rate.
- **Posting rules come from `posting_rules`**, resolved per `(document_type, fee_type_id)`
  with a NULL-fee default and the highest `priority` winning within a tier.
  `DEFAULT_ACCOUNTS` in `finance/service.py` is a last-resort fallback, not the
  configuration. `PostingRuleResolver` (`finance/posting_rules.py`) answers *which accounts*;
  `AccountingPostingService` (`finance/posting.py`) answers *what journal* from the
  `STRATEGIES` table. No account id belongs in either file — add the type to `STRATEGIES` and
  `DOCUMENT_TYPE_LABELS` instead of special-casing a document type.
- **Reports read posted data only** and must be reconciled before being called correct
  (trial balance nets to zero; AR/AP match their control accounts).

Any change touching postings, allocations, periods or account mapping is high risk: load the
`finance-accounting` skill and add regression tests.

## Documentation update rules

- Update the existing document; do not create a parallel one with a conflicting requirement.
  New documents only for genuinely uncovered topics.
- Generated files are never hand-edited: `docs/06_database_design.sql` comes from
  `backend/scripts/generate_schema_docs.py`; descriptions from
  `backend/scripts/schema_descriptions.py`.
- When a model, endpoint, permission or report changes, update the matching doc in the same
  change and refresh its implementation status.
- Never label unverified work as complete; record it in `docs/10_testing_and_quality.md`
  with the missing work named.
- Replace superseded text instead of appending a contradictory paragraph.

## Definition of Done

A change is complete only when all of these hold; report any that does not explicitly
instead of glossing over it.

1. The requested behaviour exists and is reachable from the UI or the API.
2. Authorization is enforced on the backend and a test proves the denial path.
3. Existing architecture and conventions are respected; no duplicate service, repository,
   endpoint, component or store was introduced.
4. Database changes are additive Alembic revisions with a working `downgrade()`, and
   `docs/06_database_design.sql` is regenerated and current.
5. Money paths keep debit/credit balance and `Decimal` arithmetic, with a test.
6. Tests cover the new behaviour, its failure modes and boundary cases; no failing test was
   deleted, skipped or weakened.
7. Gates pass: backend `pytest` + `ruff`; frontend `lint` + `typecheck` + `test` +
   `i18n:check`; plus the schema/migration checks when the schema changed.
8. Documentation reflects reality, including the new implementation status in
   `docs/10_testing_and_quality.md`.
9. No secret, credential, debug print or throwaway file was added. The known untracked
   `docs/lcssystem.pem` is an exception under owner review; never stage or commit it.
10. The result is reported with the exact commands run and their observed outcomes, and every
    unverified claim is named as such.
```
