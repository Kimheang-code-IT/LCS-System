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
  it (and `docs/01-architecture/permission-catalog.md`) with any new endpoint. Authorization decisions
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
[security](../01-architecture/security-and-permissions.md) and [data model](../01-architecture/database-design.md) references.

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
- **Browser acceptance:** manual on the compose stack at `http://localhost` (no automated
  browser suite; browser e2e tooling was removed 2026-11-06). Data safety now depends on the
  tester: never write against production data, use only the dev containers, and stop at the
  requested scope.
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

[Agent tooling](agent-tooling.md) owns skill/command discovery, verified MCP status and optional
setup. AGENTS.md plus .agents/context/project-context.md is the short entry; .agents skills
supply six domain workflows and .opencode retains implementation detail/commands/reviewer.
Load only the relevant skill; do not copy the same guidance into both discovery directories.

Use available lean-ctx for focused search/read/shell; unknown ownership merits one compose
query. Reuse exact symbols/ranges and prior results, recovering omissions when necessary.
Native fallback is for actual availability/root/allowlist limitations and must respect safety
blocks. No guessed tool names, token-savings claims or stale global configuration assertions.
[Testing policy](testing-guide.md) is authoritative for gates; skill command inventories are
references, not a requirement to run full suites on ordinary work.
