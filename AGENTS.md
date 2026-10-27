# AGENTS.md

Modular-monolith freight forwarding + double-entry finance system. `backend/` (FastAPI),
`frontend/` (Nuxt static SPA), `infrastructure/` (compose + nginx). `docs/` is the
authoritative specification set.

## Task levels — classify before acting

Name the level in one line when it is not obvious, then follow it. Escalate when a change
turns out to touch finance, auth, schema, shared contracts or infrastructure; never downgrade.

**FAST** — copy or label, styling, a table column, one simple field, a local UI or logic bug.
1. Locate the file or symbol. 2. Read only what the edit needs. 3. Implement.
4. Run the focused check for that file (`pnpm vitest run tests/<spec>`,
`uv run pytest tests/<file>`, `pnpm lint`, `pnpm typecheck`). 5. Stop.

FAST does not use a plan, a subagent, Context7, Playwright MCP, a Docker rebuild, a full
test suite or unrelated backend/frontend/database gates.

**STANDARD** — CRUD page, FastAPI endpoint, master-data configuration, form wired to the API,
business validation.
1. Locate the owning modules. 2. Load the matching skill. 3. Implement across the layers the
feature actually needs. 4. Run focused backend and frontend tests. 5. Update the affected
doc section. 6. Stop when those pass.

**DEEP** — Alembic migrations, auth and permissions, finance/accounting, quotation →
service-order transactions, shared API contracts, deployment, infrastructure security.
1. Read the relevant `docs/` requirements. 2. Load the specialized skill. 3. Check impacted
callers before editing. 4. Plan before implementing. 5. Implement in controlled steps.
6. Run integration, regression and permission-denial tests. 7. Use the reviewer agent.
8. Update the docs. 9. Report remaining risks.

DEEP verification is never reduced, and never traded for tokens or speed.

Common to every level: `git diff --name-only` plus untracked files shows what the change
actually touches — gate the stacks it touches, not every gate "just in case". If another
session is editing a tree, check `LastWriteTime` first; uncommitted edits are user work,
never abandoned work.

## Agent tooling

- **Skills** — `.opencode/skills/<id>/SKILL.md`, auto-discovered. Load `lcs-development` for a
  change that does not match a focused skill, and each focused skill the task needs:
  `database-migration`, `fastapi-backend`, `nuxt-frontend`, `dynamic-ui-configuration`,
  `quotation-management`, `finance-accounting`, `security-rbac`, `testing-qa`,
  `deployment-devops`, `project-analysis`. Never load all of them, never load one twice.
- **Commands** — `.opencode/commands/`: `/check`, `/test-fast`, `/test-backend`,
  `/test-frontend`, `/verify`, `/debug`, `/docs-check`, `/build-fast`, `/project-audit`,
  `/token-report`.
- **Reviewer** — `.opencode/agents/reviewer.md`, read-only. DEEP changes only; not for copy,
  styling, small form or isolated bug fixes.
- **LeanCTX** (`ctx_*`, read-only — edits use the normal edit tools): `ctx_compose` first for
  "where/how is X", then `ctx_search`/`ctx_glob` scoped by `path` (one pattern per call; brace
  expansion silently matches nothing), `ctx_read` with `mode=map|signatures` or `lines:N-M`,
  `ctx_shell` for build/test output, `ctx_callgraph` when a shared service, schema or
  permission constant changes. Fall back to native `read`/`grep`/`glob`/`shell` outside its
  roots, when its allowlist blocks a command, or when an edit needs exact bytes.
- **Context7** — unfamiliar or version-specific library APIs only. Local code and `docs/`
  answer everything else.
- **Playwright MCP** — project-scoped, ~25 tool definitions. Only to observe a live page,
  console or network. A focused Vitest/Pytest/E2E spec is the cheaper, reusable answer.
- **Token discipline** — one discovery pass per task; reuse what you already read instead of
  re-reading an unchanged file or repeating a search. Never trade validation, authorization,
  error handling, tests or schema documentation for tokens.
- **Read selectively** — `docs/10_testing_and_quality.md` (verified status, gaps, risks) and
  `docs/11_deployment_and_security.md` (deploy, backup, hardening); the relevant section, not
  the whole file.

## Commands

Each toolchain runs from its own directory (relative `.env`, `alembic.ini`, `script_location`
and test paths assume it).

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
pnpm test:e2e                          # Playwright against http://localhost (compose stack)
pnpm exec playwright test e2e/smoke.spec.ts
pnpm vitest run tests/format.spec.ts  # single test file
```

Gate order: frontend `lint -> typecheck -> test` (plus `i18n:check`), backend `pytest -> ruff`.
Branches: `dev` (integration), `main` (protected production, PR + `Dev CI` check required).
CI/CD, image publishing, the EC2 deploy and rollback are documented in
`docs/11_deployment_and_security.md`; `dev-ci.yml` never deploys and only `production.yml`
runs on `main`. EC2 is runtime-only — the repo is not cloned there.

## Run stack

```bash
docker compose -f infrastructure/docker-compose.yml up -d --build   # from repo root
```

Host ports: frontend 80, backend 8000, Postgres 5432, Redis 6379, MinIO 9000/9001 (all
env-driven in `infrastructure/.env`). The backend container runs `alembic upgrade head` on
start. The DB ships empty; first login is `/auth/setup`
(`POST /api/v1/auth/setup/initialize`, gated on no users existing), which provisions the
admin, default document sequences (current year) and default app info/config — no finance or
business data.

## Backend

- Python 3.12, async SQLAlchemy 2.x, Pydantic settings, `uv.lock` committed. Layering:
  router → service → repository → schema; reuse existing helpers before adding one.
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
- Auth: session-bound JWT access token (default 15 minutes) + opaque rotating refresh
  cookie, with PostgreSQL idle/absolute validation. Access uses `Authorization: Bearer`
  or HttpOnly cookie. Config in `app/core/config.py` and Settings → Security.
- Backup module runs an **in-process asyncio scheduler** (Google Sheets, no worker);
  `BACKUP_SCHEDULER_ENABLED` toggles it, config is per-install.
- Check impact before editing shared code: other callers, `tests/test_frontend_api_contract.py`,
  `app/core/permissions.py`, generated schema docs.

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
- **Docker-only fallback (no `uv` on PATH):** `docker run --rm -v "<repo>:/repo" -w
  /repo/backend freight_forwarding-backend:latest sh -c "uv sync --frozen --extra dev && uv run
  pytest -q"` — mount the repo so the contract test can read `frontend/app` (the image ships no
  tests or dev deps), and drop the path to run the full suite. Live API:
  `docker exec ff-api curl -fsS http://localhost:8000/health`.

## Frontend

- Nuxt 4, `ssr: false`, built with `nuxt generate`, served by nginx, which also
  reverse-proxies `/api/` so the browser is same-origin.
- **i18n (`@nuxtjs/i18n` v10, `strategy: no_prefix`):** English, Khmer, Simplified Chinese.
  `i18n/locales/<code>.json` must stay structurally identical to `en.json`. A new language is
  added in one place — `app/utils/constants/app-languages.ts` — then mirrored in
  `nuxt.config.ts` `i18n.locales`, the script font in `fonts.families` + `html[lang]` rules in
  `app/assets/css/main.css`, and `SUPPORTED_LANGUAGES` / `_LANGUAGE_LOCALES` in
  `backend/app/core/localization.py`. Never hardcode an `'en' | 'km'` union.
  `pnpm i18n:check` (also `tests/i18n-locales.spec.ts`).
- **Label resolution:** never add a per-language parallel field (`labelKm`) for copy shipped in
  code — `useFreightLabel().fieldLabel()` resolves
  `labelKey` -> `freight.modules.<collection>.fields.<key>` -> `freight.fields.<key>` ->
  English `label`. The `labelKm` column that remains is *admin-managed data* (user-defined
  attributes / dynamic-table columns), resolved per locale via `STORED_LABEL_FIELDS`.
- **Print output is deliberately bilingual English + Khmer** (Cambodian tax invoice
  requirement) via `composables/print/usePrintBilingual.ts`, independent of the UI language.
- **Form validation is one shared pipeline — never per page:** `useFormValidation` with leaf
  rules in `app/utils/validation/`. A form supplies only its field `order`, a `label` resolver
  and a `reveal` callback. Rules come from module config (`required`, optional `rule`) and, for
  Service Order dynamic tabs, the attribute's `validationRules`.
  - Errors use a canonical camelCase model path; repeatable rows use `table.<row>.<column>`.
    Tag new inputs with `data-field-key="<path>"`.
  - `:error` on `UFormField` supplies `aria-invalid` / `aria-describedby`; a field error is
    reported **only** there. `CommonAppFormErrorSummary` renders just the messages that belong
    to no field, and every form producing `formErrors` renders it.
  - **Notification policy:** validation errors and business refusals are never toasts — on the
    field, or in a persistent form/page message. A toast is only for confirmed success; `useApi`
    suppresses its own toast for 400/409/422. Enforced by
    `tests/validation-notification-policy.spec.ts`.
  - `validation.<code>` keys must exist in all three bundles (`tests/validation-messages.spec.ts`).
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
- Tests are plain Vitest (`environment: node`, `import.meta.client = false`, alias `~ -> app`);
  only `tests/**/*.spec.ts`; no Nuxt runtime.
- **Browser suite:** Playwright Test in `frontend/e2e/` (`pnpm test:e2e`), configured by
  `frontend/playwright.config.ts`; it is separate from the Vitest directory on purpose. Default
  target is the compose stack at `http://localhost`; override with `E2E_BASE_URL` (for example
  `http://localhost:3000` for `pnpm dev`). Authenticated steps are skipped unless
  `E2E_USERNAME`/`E2E_PASSWORD` name a dedicated non-production account, and the suite is
  read-only: it creates, edits and deletes nothing.
- **No editor/Tiptap deps:** `frontend/.pnpmfile.cjs` strips `@tiptap/*` from `@nuxt/ui`. The
  lockfile pins the hook via `pnpmfileChecksum`, so CI and Docker (`--frozen-lockfile`) need
  the file present. Adopting Nuxt UI's editor means deleting the hook and running
  `pnpm install --no-frozen-lockfile`.
- `pnpm-workspace.yaml` only lists `ignoredBuiltDependencies` — this is **not** a monorepo.

## Reference docs

`docs/` is authoritative and contains exactly twelve documents (eleven Markdown files plus one SQL
schema reference) and one untracked private key, `docs/lcssystem.pem`; never read, copy, commit
or expose that key.

| File | Contents |
|---|---|
| `docs/01_business_requirements.md` | Business goals, scope, actors, requirements |
| `docs/02_software_requirements.md` | Functional and non-functional requirements |
| `docs/03_business_process_and_sop.md` | Operational procedures and controls |
| `docs/04_functional_design.md` | Use cases, posting rules, error catalogue, Mermaid ER/process/data-flow diagrams |
| `docs/05_solution_architecture.md` | Module boundaries, request flow, transactions, finance architecture |
| `docs/06_database_design.sql` | Generated DDL: tables, columns, keys, constraints, indexes, comments |
| `docs/07_api_documentation.md` | API conventions, endpoint catalogue, dynamic collections, error codes |
| `docs/08_frontend_and_ui_design.md` | Routes, metadata-driven pages, forms, validation, i18n, components |
| `docs/09_roles_and_permissions.md` | Permission catalog, role templates, page mapping, enforcement |
| `docs/10_testing_and_quality.md` | Test architecture, gates, coverage gaps, implementation status, open risks |
| `docs/11_deployment_and_security.md` | Deploy, CI/CD, migration, backup/restore, rollback, hardening, risks |
| `docs/12_feature_status.md` | Living feature status matrix, module assessments, readiness, backlog, change map |

`README.md` is the repository entry point. `docs/06_database_design.sql` is **generated**:
model DDL plus a description for every table and column, as inline comments and executable
`COMMENT ON` statements; its prose lives in `backend/scripts/schema_descriptions.py`.
`tests/test_schema_docs.py` fails if it is stale, if a column is undocumented, or if more than
one SQL file exists. `scripts/generate_schema_dump.py` is a compatibility wrapper for the same
output.

## Financial data integrity

Non-negotiable, regardless of the task or level:

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
  `base_debit_amount` / `base_credit_amount`; never recompute a posted amount from a newer rate.
- **Posting rules come from `posting_rules`**, resolved per `(document_type, fee_type_id)` with
  a NULL-fee default and the highest `priority` winning within a tier. `DEFAULT_ACCOUNTS` in
  `finance/service.py` is a last-resort fallback, not the configuration. `PostingRuleResolver`
  (`finance/posting_rules.py`) answers *which accounts*; `AccountingPostingService`
  (`finance/posting.py`) answers *what journal* from the `STRATEGIES` table. No account id
  belongs in either file — add the type to `STRATEGIES` and `DOCUMENT_TYPE_LABELS` instead of
  special-casing a document type.
- **Reports read posted data only** and must be reconciled before being called correct (trial
  balance nets to zero; AR/AP match their control accounts).

## Documentation update rules

- Update the existing document; do not create a parallel one with a conflicting requirement.
  New documents only for genuinely uncovered topics. Generated files are never hand-edited:
  regenerate `docs/06_database_design.sql`, never patch it.
- When a model, endpoint, permission or report changes, update the matching doc in the same
  change and refresh its implementation status. FAST changes need a doc edit only when
  behaviour or a documented requirement changed.
- Never label unverified work as complete; record it in `docs/10_testing_and_quality.md` with
  the missing work named.
- Replace superseded text instead of appending a contradictory paragraph.

### Feature status report

`docs/12_feature_status.md` is the single feature status record; keep it current for verified changes.

1. Run `node scripts/feature-status.mjs --base <ref>` (or with no flag for the working tree) after a
   change. It prints the affected feature prefixes and files from the diff; it never edits the report
   and never decides a status.
2. Update only those matrix rows and the matching module assessment: status, evidence, `Last Verified`.
   If the status actually changed, add one Change History line. Keep IDs and history intact.
3. Mark a row WORKING only with a test or live check you ran on this revision, and put the exact
   command/outcome in the evidence. Otherwise leave it UNVERIFIED or record the failure — never invent
   a result.
4. Comments, formatting, documentation-only and unrelated edits update no row. Never regenerate the
   whole report for one feature.

## Definition of Done

A change is complete only when all of these hold; report any that does not explicitly instead
of glossing over it. FAST changes still satisfy every item that applies to them.

1. The requested behaviour exists and is reachable from the UI or the API.
2. Authorization is enforced on the backend and a test proves the denial path.
3. Existing architecture and conventions are respected; no duplicate service, repository,
   endpoint, component or store was introduced.
4. Database changes are additive Alembic revisions with a working `downgrade()`, and
   `docs/06_database_design.sql` is regenerated and current.
5. Money paths keep debit/credit balance and `Decimal` arithmetic, with a test.
6. Tests cover the new behaviour, its failure modes and boundary cases; no failing test was
   deleted, skipped or weakened.
7. Gates pass for the stacks touched: backend `pytest` + `ruff`; frontend `lint` + `typecheck`
   + `test` + `i18n:check`; plus the schema/migration checks when the schema changed.
8. Documentation reflects reality, including the new implementation status in
   `docs/10_testing_and_quality.md` and the affected rows of `docs/12_feature_status.md` when behaviour
   changed.
9. No secret, credential, debug print or throwaway file was added. The known untracked
   `docs/lcssystem.pem` is an exception under owner review; never stage or commit it.
10. The result is reported with the exact commands run and their observed outcomes, and every
    unverified claim is named as such.
