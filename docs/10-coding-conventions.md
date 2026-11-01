# Coding Conventions

## Naming and code organization

Use existing module naming: Python snake_case, TypeScript camelCase, Vue components PascalCase,
route slugs kebab-case. Follow nearby established patterns for symbols and translation keys.
Router → service → repository/model boundaries are defined in architecture.
Avoid duplicate helpers, stores and services. No unrelated refactoring.

## Backend implementation rules

- Python 3.12, async SQLAlchemy 2.x, Pydantic settings, `uv.lock` committed. Layering:
  router → service → repository → schema; reuse existing helpers before adding one.
- Modules under `app/modules/<name>/` (`router.py`, `service.py`, `models.py`); register new
  routers in `app/api/v1/router.py`.
- **API envelope:** success is `{"data": ...}`. Lists return
  `{"data": {"items": [...], "meta": {page, page_size, total}}}` (`core/pagination.py`).
  Errors are `{code, message, request_id, field_errors}` (`app/main.py` handlers).
- Permission catalog is **code-defined** in `app/core/permissions.py`, synced on startup; update
  it (and `docs/09_roles_and_permissions.md`) with any new endpoint. Authorization decisions
  come from **Casbin** (`app/core/authorization/`, policies in `casbin_rule`); never add a
  second role→permission mapping.
- Migrations live in `alembic/versions/`. `alembic/env.py` imports every model module — add
  new ones there and to `reset_all_data` in `app/core/bootstrap.py`.
- Ruff: line-length 120, `select = [E,F,I,UP,B]`, ignores `B008`, `E501`.
- Auth: session-bound JWT access token (default 15 minutes) + opaque rotating refresh
  cookie, with PostgreSQL idle/absolute validation. Access uses `Authorization: Bearer`
  or HttpOnly cookie. Config in `app/core/config.py` and Settings → Security.
- Backup module runs an **in-process asyncio scheduler** (Google Sheets, no worker);
  `BACKUP_SCHEDULER_ENABLED` toggles it, config is per-install.
- Check impact before editing shared code: other callers, `tests/test_frontend_api_contract.py`,
  `tests/test_route_authorization.py`, `app/core/permissions.py`, generated schema docs.

The original backend rules above are retained as implementation detail. First-run baseline
includes reference/configuration seeds; it does not establish business/finance records.
Telegram also has existing in-process background processing; “no worker” above means no
separately deployed worker service. Security and accounting authorities are the linked
[security](03-security-access-control.md) and [data model](02-data-model.md) references.

## Frontend implementation rules

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
- **Print output is deliberately bilingual English + Khmer** via `composables/print/usePrintBilingual.ts`, independent of the UI language.
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

Bilingual printing is an approved product requirement; no legal tax conclusion or additional
tax workflow is inferred. Frontend tests are implementation gates, not evidence of browser
compatibility or business acceptance by themselves.

## Error handling

Use typed backend exceptions and central envelope handlers. Client validation improves input
but does not replace server checks. Persistent field/page errors handle refusals; success
notifications follow the existing shared pipeline described above.

## Dependencies and comments

Justify new dependencies and maintain lockfiles. Prefer stdlib/existing packages and existing
helpers before adding another abstraction. Comments explain non-obvious constraints and intent;
remove debug prints. Significant architecture decisions belong in the ADR log.

## Project agent tooling

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
- **Context7** — currently disabled as a plugin (token optimization; re-enable by
  uncommenting its line in the global `opencode.jsonc` `plugins`). For real use cases only:
  unfamiliar or version-specific library APIs. Local code and `docs/` answer everything else.
- **Serena MCP** (`tools.serena.serena_repl` — global registration, cwd auto-activates this
  project) — semantic symbol navigation: `s.lsp.find_symbol`, `get_symbols_overview` (cheap
  file structure), `find_referencing_symbols`, plus `rename_symbol`/`safe_delete_symbol` for
  reference-aware refactors. Use it for "where is X used" over reading whole files; one fresh
  session reports `python, typescript, vue` LS (set in `.serena/project.yml`). Skip it on
  one-line edits — native edit tools are cheaper with known bytes.
- **ast-grep** (`sgconfig.yml` + `ast-grep/rules/`) — structural pattern search for recurring
  code shapes (`ast-grep scan`, `ast-grep run -l python -p '...'`). Read-only; investigate
  matches, never auto-delete. This build does NOT parse `.vue` — for SFCs use Serena or grep.
  Prefer rule files over CLI patterns; PowerShell keeps expanding `$` inside double quotes.
- **Playwright MCP** — project-scoped, currently `disabled: true` in the project
  `opencode.jsonc` (token optimization; delete that line to re-enable). Only to observe a live
  page, console or network — distinct from the Playwright *Test* suite (`pnpm test:e2e`), which
  is unaffected. A focused Vitest/Pytest/E2E spec is the cheaper, reusable answer.
- **Token discipline** — one discovery pass per task; reuse what you already read instead of
  re-reading an unchanged file or repeating a search. Never trade validation, authorization,
  error handling, tests or schema documentation for tokens.
- **Read selectively** — `docs/10_testing_and_quality.md` (verified status, gaps, risks) and
  `docs/11_deployment_and_security.md` (deploy, backup, hardening); the relevant section, not
  the whole file.

Use lean-ctx MCP equivalents where available under current session instructions. Native
fallback is for allowlist/root limitations or exact-byte editing; never bypass safety blocks.
Load a focused project skill when relevant; do not load all skills or reread unchanged files.

## Graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Use graphify selectively — it answers cross-module questions, not every search:

- Use it when the file is unknown or the question involves cross-module architecture,
  dependencies or change impact: `graphify query "<question>"` (scoped subgraph, much smaller
  than GRAPH_REPORT.md), `graphify path "<A>" "<B>"`, `graphify explain "<concept>"`.
- Skip it for FAST tasks and small isolated edits where the target file is already known —
  native tools / Serena there are cheaper. Also skip broad doc, copy, styling-only work.
- Do not force a graphify query before every grep/search/read; put this rule (not a forced
  graphify call) in subagent prompts that explore code.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when
  query/path/explain do not surface enough context; `graphify-out/wiki/index.md` (if present)
  for broad navigation.
- Trust the graph only when fresh: compare `graphify-out/graph.json` LastWriteTime against
  `git diff --name-only` before relying on it for impact analysis.
- After code changes in indexed source paths, run `graphify update .` (AST-only, no API cost).
  Skip it for comment-, doc- or styling-only edits.
- `graphify-out/` is gitignored locally: generated graph artifacts are not committed. If you
  intentionally adopt graph outputs in version control, decide that explicitly with the owner.
- Dirty graphify-out/ files are expected after hooks or incremental updates; that is not a
  reason to skip graphify.
