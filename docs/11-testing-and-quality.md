# Testing and Quality

## Test strategy and required types

Verify existing behavior before editing; implement only demonstrated gaps. Use unit/service,
API integration, cross-stack contracts, permission-denial, boundary/refusal, frontend validation,
localization, print and browser checks. Financial slices require reconciliation and concurrency
checks; PostgreSQL integration must exercise triggers/locking that SQLite cannot prove.
Recovery requires an isolated full restore drill, not a successful dump command.
Synthetic end-to-end technical scenarios are mandatory. Stakeholder business approval remains
separate; anonymized cases are recommended when safely available.

## Test architecture

Backend tests use in-memory SQLite/aiosqlite with `get_session` overrides and once-precompiled
DDL, not per-test metadata compilation. `backend/tests/seed.py` is test-only; use fixture
credentials from that source, never production accounts. Runtime/test counts and durations
are variable and must be measured rather than copied as current results.
The frontend API contract test statically reads frontend endpoint/config registrations.
Vitest uses node, `import.meta.client=false`, alias `~` to app, and `tests/**/*.spec.ts`.
Playwright uses `frontend/e2e/` separately; configured target defaults to localhost Compose.
Current configuration selects Chromium only. Firefox/WebKit and actual Safari, plus Edge,
need explicit validation; WebKit alone is not proof of actual Safari compatibility.
Existing read-only browser tests may skip authentication without dedicated account variables;
a skipped authenticated test does not satisfy synthetic business-transaction acceptance.

## Quality gates and validation commands

Run commands from their owning directory. Scope FAST checks to the changed file/feature;
STANDARD uses affected backend/frontend tests; DEEP requires relevant integration, regression,
denial and reviewer checks. Gate the stacks touched, never omit DEEP validation for speed.

```bash
# backend/
uv run pytest -q
uv run ruff check .
uv run pytest -q tests/test_frontend_api_contract.py tests/test_route_authorization.py
uv run alembic heads
uv run python scripts/generate_schema_docs.py --check
# frontend/ (order preserved)
pnpm lint
pnpm typecheck
pnpm test
pnpm i18n:check
pnpm exec playwright test e2e/smoke.spec.ts
```

For a focused check use `uv run pytest tests/<file>` or `pnpm vitest run tests/<spec>`.
Use `E2E_BASE_URL` and dedicated non-production account settings for an isolated browser target.
Build/generate only when relevant. Do not rebuild Docker for FAST changes.
If uv is unavailable, the existing Docker test fallback must mount the whole repository
so the contract test can read frontend sources. From the repository root, substitute its
absolute path for `<repo>` and the focused test file as needed:

```bash
docker run --rm -v "<repo>:/repo" -w /repo/backend freight_forwarding-backend:latest sh -c "uv sync --frozen --extra dev && uv run pytest -q tests/test_frontend_api_contract.py"
```

## Evidence and release acceptance

Record revision, environment, dataset, exact command, exit/result, skipped cases and limitations
in the active plan. Never mark a feature WORKING merely because its code or test file exists.
Required scenarios include login/denial/logout, conversion, execution, charges, customer/supplier
posting, partial/full settlement, journals, period closure, report reconciliation, localized
validation, bilingual print and recovery. See the plan template for acceptance fields.
Critical/high defects and unresolved critical security/finance/recovery/legal requirements
block production. Noncritical gaps need explicit impact acceptance by the responsible stakeholder.
Proposed performance/accessibility/recovery targets remain proposals until approved and tested.

## Foundation verification status

Foundation work is documentation only. Application tests, browser acceptance, load tests,
live hosting checks and restore drills were not executed in this task; S01 has not started.
[Historical quality report](10_testing_and_quality.md) and
[feature status](12_feature_status.md) retain prior evidence without converting it into a
newly verified claim. Portions of legacy testing/deployment text were withheld by the context
gateway during review; exhaustive consistency with those portions remains unverified.
Documentation link/structure/scope verification is reported separately in the delivery result.

## Foundation documentation checks — 2026-10-30

- `python .foundation-validate.py`: passed; 21 required files, 72 required sections,
  104 local Markdown links, AGENTS 72 lines, CLAUDE 4 lines, inventory 44 pages.
  The task-local validator compares 854 baseline files and checks preserved legacy notice
  bodies; zero failures. Temporary generation/validation scripts are removed after checks.
- `git diff --check`: passed, with line-ending normalization warnings only.
- `node scripts/feature-status.mjs`: completed; reported existing ORDER/PLAT/REP working-tree
  changes from before this task. No feature row was updated for documentation-only work.
- Baseline comparison distinguishes pre-existing dirty application files from this task's
  documentation edits. No non-output baseline file changed; no application, schema, migration,
  CI or deployment configuration was modified by this task.
- Unverified: runtime behavior, application test gates, live infrastructure, exhaustive legacy
  consistency in gateway-withheld files, proposed numerical targets and stakeholder acceptance.

## Documentation cleanup checks — 2026-10-31

- `python .doc-cleanup-validate.py --projected`: passed before deletion. Final
  `python .doc-cleanup-validate.py`: passed after deletion; 22 required documents including
  the source prompt, 63 project Markdown files, 87 local links, 44 page routes, AGENTS 72
  lines, CLAUDE 4 lines, and zero broken links or stale live references to removed paths.
- Identifier coverage: 185 FR, 21 NFR, 14 INV and 12 BR IDs retained; eight UR responsibilities
  and the 19 approved LCS IDs remain documented. Retired and deferred requirements retain
  their explicit scope/status limits rather than becoming newly implemented features.
- `python .doc-cleanup-routes.py`: 215 concrete API catalog rows matched router source;
  15 generic templates tracked separately. Static presence is not runtime/schema/permission proof.
- `git diff --check`: passed with line-ending warnings only.
- `node scripts/feature-status.mjs`: completed; its reported ORDER/PLAT/REP source changes
  predate this cleanup. No feature-status row was changed by cleanup.
- `python scripts/generate_schema_docs.py --check --strict` from backend: failed because the
  available interpreter lacks `casbin`. The project-interpreter invocation was blocked by
  tool hooks. Schema freshness remains unverified; generated SQL is byte-for-byte unchanged.
- Baseline comparison covers 869 existing files: cleanup changes only approved Markdown
  documentation, including QA skill references; pre-existing source/configuration edits
  are preserved. No application, test, schema, migration, CI or deployment source was modified.
- Project-owned document/reference count: 93 → 67; `docs/` document/reference count: 56 → 30.
  Counts exclude the private key, vendor/cache contents and local generated reports/graphs.
  Temporary audit/consolidation/validation scripts are removed after checks.
- Retained exceptions and incomplete legacy review are itemized in
  [documentation standards](12-documentation-standards.md#documentation-cleanup-inventory).
  No application tests, live deployment checks, restore drills or S01 execution occurred.

## Codebase audit baseline and safe batch — 2026-10-31

The separately requested cleanup audit is recorded in
[PLAN-0003](plans/PLAN-0003-codebase-cleanup-baseline.md); it does not replace S01 or change
the approved roadmap order. One unused Excel-registry method and its sole constant were
removed; an API regression verifies unknown-mode refusal without business/import-session writes.

| Check | Observed outcome |
|---|---|
| backend: `uv run pytest -q` | Pre-change baseline: 748 passed, 7 skipped, 278 warnings, 873.13 s |
| backend: `uv run pytest -q tests/test_excel_import_export.py tests/test_frontend_api_contract.py tests/test_route_authorization.py` | Before: 52 passed, 57.36 s; after: 53 passed, 55.82 s |
| backend: new unsupported-mode regression alone | Passed before helper removal: 1 passed, 2.25 s |
| backend: `uv run pytest -q tests/test_repository_queries.py tests/test_config_compare.py` | 7 passed, 4.59 s; verifies existing query-count/compare properties |
| backend: explicitly selected PostgreSQL integration files with `-rs` | 7 skipped, 0.26 s; each requires a configured disposable PostgreSQL target |
| backend: `uv run ruff check app tests scripts` | Passed before and after |
| backend: `uv run ruff check .` | Pre-existing failure: I001/F401 only in untracked `_diag_queries.py`; not modified or suppressed |
| backend: `uv run python scripts/generate_schema_docs.py --check --strict` | Passed: all 77 tables current; cyclic-FK warning remains |
| frontend: `pnpm lint`, `pnpm typecheck` | Passed; no frontend source changed |
| frontend: `pnpm test` | First run: 770 passed / 2 timeouts; unchanged rerun: all 772 passed / 93 files, 6.15 s |
| frontend: focused two timeout specs | All 16 passed, 368 ms; no assertions/timeouts weakened |
| frontend: `pnpm i18n:check` | Passed: km/zh 3324 keys; 52 zh values English-identical, not classified unused |
| frontend: `pnpm typecheck:unused` | Flags inputRef, used by Vue string template ref; false positive preserved |

The full backend run collected tests before the app edit; post-change coverage is the targeted
53-test run, not a second full run. Seven skipped integration tests do not validate PostgreSQL
trigger/locking or live external-service guarantees. Existing duplicate OpenAPI operation-ID,
cyclic-FK and deprecation warnings remain. No application speedup is inferred from test timings.

Safe pure-function configuration comparison used two warmups/nine samples, no database:
2,000 synthetic attributes median 6.583 ms; 20,000 median 80.618 ms under concurrent test load.
Method and min/max are in PLAN-0003. No endpoint, bundle, database or production optimization
was made. E2E/load testing and EXPLAIN were not run without a verified safe target.
`graphify update .` was attempted and tool-blocked; no tool permissions were changed.
All pre-existing user source/dependency edits remain protected; no business feature status
was upgraded merely because an unused internal wrapper was removed.
Task-scope hash/AST checks passed across 839 baseline files; only the registry/test and directly
affected plan/quality/roadmap documents changed. All 44 page routes remain documented, S01
is unchanged, nine affected-document links resolve, and `git diff --check` passed.

## Global-search cleanup verification — 2026-10-31

[PLAN-0003 batch 2](plans/PLAN-0003-codebase-cleanup-baseline.md#batch-2--global-search-response-and-lifecycle-ownership)
records deterministic reproduction: 14 of the initial 17 cases failed before the fix.
The final 21-case suite verifies response ownership across queries/modes, stale catch/finally,
debounce cleanup, close/clear/unmount, per-instance cancellation keys, network recovery and
existing answer/source contracts. Real Vue scopes and search composables use mocked transport;
late responses are intentionally allowed after cancellation to exercise generation guards.

- `pnpm test`: 793 passed / 94 files, 5.35 s; includes all 21 search regressions.
- Focused search/configuration command in the plan: 29 passed / 3 files, 521 ms.
- `pnpm lint`, `pnpm typecheck` and `pnpm i18n:check` passed after production edits.
  Existing 52 English-identical zh values remain a language-review item.
- Backend API-completeness/contract/route-authorization selection: 11 passed, 24 warnings,
  9.86 s; `uv run ruff check app tests scripts` passed. No backend source changed.
- Controlled dispatch counts: whitespace-equivalent edits 2→1; close before debounce 1→0;
  closed nonempty edits 1→0. These are fixture request counts, not latency/SQL improvements.
- Browser focus/E2E, production latency and PostgreSQL guarantees remain unverified here.
  Prior seven PostgreSQL skips and diagnostic root Ruff findings remain open above.
  Shared auth transport, backend Casbin checks, finance, schemas and S01 are unchanged.
