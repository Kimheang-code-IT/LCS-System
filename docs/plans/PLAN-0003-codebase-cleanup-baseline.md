# PLAN-0003 — Codebase Cleanup Audit and First Safe Batch

## Metadata and relationship to S01

Status: In Review (supporting audit; not the active release implementation plan)
Last updated: 2026-10-31
Batch 1: Complete. Batch 2: Global-search lifecycle fixes verified; broader audit remains open.
Authorization: User requested comprehensive read-only audit/baseline followed by one safe,
low-risk cleanup batch, then explicitly authorized continuation targeting global search.
Broad/high-risk changes and database modifications require approval.
The active release plan remains PLAN-0002 / S01. No S01–S13 dependency or status is changed.
This plan is the cleanup-specific evidence/Handoff record; it does not replace S01.

## Objective, requirements and exclusions

Inventory the existing code, classify candidates without mistaking framework entry points for
dead code, establish pre-change checks, remove proven-unused internal helpers and fix
deterministically reproduced search lifecycle defects in bounded batches.
Requirements: LCS-001/002/006/010/011/013/014; preserve all 44 pages and supporting routes,
Casbin/session semantics, Decimal accounting, transaction/audit guarantees and integrations.
No redesign, dependency upgrade/removal, schema/index change, deployment, Git reset or commit.
No edit to unrelated uncommitted source or diagnostic files.

## Baseline inventory and ownership

Git status was inspected before edits. The working tree already contains modified operations,
reports, shared UI, header/table components, configuration pages, translations, Nuxt config,
package/lockfiles and documentation, plus untracked diagnostic scripts and tooling resources.
These are user work, not abandoned cleanup targets. Baseline hashes/timestamps were captured
for 839 existing non-secret files; private keys and secret env files were excluded.

| Surface | Files inventoried |
|---|---:|
| backend/app | 122 |
| backend/tests | 78 |
| Alembic versions | 49 |
| backend/scripts | 6 |
| frontend pages | 90 (includes supporting routes, not 90 business pages) |
| frontend components / composables / utilities | 84 / 34 / 99 |
| frontend stores / configuration | 3 / 9 |
| frontend tests / e2e | 96 / 8 |
| frontend/scripts / infrastructure / workflows | 1 / 7 / 4 |

AST inventory covers backend function bodies; source/config searches include frontend,
routers, registries, tests and scripts. This is a repository-wide first pass, not an exhaustive
proof that every function, dependency, asset, CSS class or translation key is necessary.
The local graph timestamp predates current dirty work; callgraph results are corroborating
only. Direct source/dynamic-entry inspection governs removal decisions.

## Findings and risk ranking

| ID | Finding / source evidence | Classification | Risk / disposition |
|---|---|---|---|
| CLN-001 | `excel_io/registry.py:28,58`: IMPORT_MODES consumed only by is_known_mode; no method callers; service.py:381 validates modes directly | Confirmed unused within repository | Low; remove this pair only |
| CLN-002 | `AppLineTable.vue:105,826`: inputRef flagged by noUnusedLocals but required by string template ref; attachments.ts:176 clicks it | Shared/dynamically referenced | Preserve; removing it breaks file selection |
| CLN-003 | core/fx.py:is_valid_rate; core/security.py:generate_reset_code; core/validation.py:validate_payload,FieldSpec.describe_length; auth repository user_by_email/session_by_refresh_hash | Likely unused by token-count first pass | Preserve; shared money/auth/validation requires stronger impact checks and S01 alignment |
| CLN-004 | Identical _bool bodies in component_config.py:76, config_snapshot.py:56, component_tabs.py:35 | Shared duplicate implementation | Defer; snapshot/runtime compatibility and cross-module regression needed |
| CLN-005 | Identical _get_group bodies in component_config.py:627 and component_tabs.py:139; role-transform bodies in master_data/service.py:243,808 | Duplicate candidates | Preserve domain boundaries until reuse is justified; no new layer merely for line count |
| CLN-006 | Decorated API handlers, Pydantic validators, Nuxt auto-imports/routes/components, report/posting registries, startup/background tasks | Required or dynamically referenced entry points | Never delete from lack of direct imports |
| CLN-007 | `_diag_queries.py`, `_diag_sales.py`, user-modified source/package files | Uncertain ownership / user work | Preserve; diagnostics cause existing root Ruff findings |
| CLN-008 | i18n check reports 52 zh values identical to English | Uncertain translation completeness, not unused keys | Preserve keys; business-language review required before correction |

Frontend text screening covered 466 source/test/config files: all 84 Vue components have
at least one static name match under the screened aliases. This does not prove every instance
is reachable, but gives no basis for a component-file deletion in batch 1. Ten single-token
export candidates remain **Likely/Uncertain**, not confirmed unused:
`COMPONENT_DISPLAY_MODES`, `startPasswordReset`, `clearPasswordResetSession`,
`documentTypeCategoryLabel`, `documentTypeBehaviorLabel`, `documentTypeModuleLabel`,
`JOB_FINANCE_LINE_LABEL_KEYS`, `pageActionPermission`, `buildCashFlowReportRows`,
`postedJournalLines`. Their type/config/auto-import/auth/report usage needs further review;
none was removed. No CSS, asset, fixture, dependency or translation-key deletion was justified.

### Complexity candidates, not performance claims

AST branch-node counts are a reproducible syntax proxy, not cognitive-complexity scores or
measured latency. Nested syntax is included. Top candidates on the inspected source:

| Function | Lines | Branch nodes | Constraint |
|---|---:|---:|---|
| finance/service.py:889 save_document | 240 | 37 | Finance DEEP; preserve calculations/transactions and obtain scoped approval |
| backup/service.py:649 restore_from_sheets | 98 | 30 | Recovery/high risk; no live restore or rewrite |
| master_data/config_compare.py:113 compare_snapshots | 165 | 28 | Pure comparison; benchmark and regression evidence before refactor |
| operations/service.py:974 save_charge | 149 | 26 | Already dirty user work and finance seam; untouched |
| master_data/service.py:479 _validate_asset_record | 119 | 25 | Business validation; boundary tests before simplification |
| operations/component_tabs.py:456 bulk_save | 106 | 24 | Snapshot/transaction/validation semantics; defer |

Security risk: false-positive dead-code removal can break sessions, guards or framework entry
points. Financial risk: rewriting posting/allocation/reporting without PostgreSQL and
reconciliation evidence can corrupt history or balances. Neither category is changed here.

## Baseline commands and observed results

Run frontend commands from frontend/ and backend commands from backend/.

| Command | Pre-change result |
|---|---|
| uv run ruff check . | FAIL: I001 and F401 in pre-existing untracked _diag_queries.py only |
| uv run ruff check app tests scripts | PASS |
| uv run python scripts/generate_schema_docs.py --check --strict | PASS; all 77 tables/columns current; existing SQLAlchemy cyclic-FK warning |
| pnpm lint | PASS |
| pnpm typecheck | PASS |
| pnpm typecheck:unused | FAIL: inputRef template-ref false positive; preserved |
| pnpm test (first run) | 770 passed, 2 source-policy tests timed out at 5 seconds during concurrent audit activity |
| pnpm vitest run tests/form-field-error.spec.ts tests/validation-notification-policy.spec.ts | 16 passed, 368 ms overall; no timeout changes or assertions weakened |
| pnpm test (unchanged rerun) | 772 passed / 93 files, 6.15 s; initial timeouts not reproduced |
| pnpm i18n:check | PASS: km/zh 3324 keys each; 52 zh English-identical values reported |
| uv run pytest -q | 748 passed, 7 skipped, 278 warnings in 873.13 s (14m33s); pre-change baseline run |
| uv run pytest -q tests/test_excel_import_export.py tests/test_frontend_api_contract.py tests/test_route_authorization.py | 52 passed, 47 warnings, 57.36 s before app edit |
| uv run pytest -q -rs tests/test_auth_postgres.py tests/test_postgres_places_migration.py tests/test_quotation_postgres.py tests/test_telegram_postgres.py | All 7 skipped, 0.26 s; each requires explicitly configured disposable PostgreSQL |

pnpm.cmd and docker commands were rejected by the lean-ctx allowlist; supported `pnpm`
invocations ran successfully. No allowlist or permission configuration was changed.
Safe live/browser/PostgreSQL profiling target has not been verified; no production probing,
EXPLAIN ANALYZE, load testing, restore or browser mutations were performed.

## First safe batch and dependency proof

Before any app edit, inspect the complete 138-line registry, its service/template/router
callers, source references and tests. `is_known_mode` is not a route, validator, registered
callback, serialized dataclass field or dynamically dispatched method. Source search finds
only its definition and its sole constant dependency. `start_import` independently rejects
unknown modes before workbook parsing. Keep that behavior and error envelope unchanged.

1. Add a meaningful API regression for an unsupported mode; prove it passes before removal.
2. Remove only `ImportModule.is_known_mode` and its otherwise-unused `IMPORT_MODES` tuple.
3. Run focused Excel, API-contract, route-denial and lint checks after removal.
4. Preserve exact post-change evidence and all unrelated baseline hashes.

Backend: one internal helper pair removed; public REST/data contracts unchanged.
Frontend: no change. Database/migrations/indexes: none. Authorization/finance rules: none.
No performance gain is expected or claimed from removing this unreachable wrapper.

## Test scenarios, acceptance and Definition of Done

Cover unsupported-mode 422 with field_errors.mode and no business/import-session writes;
existing tests cover valid modes, preview/no writes, atomic commit, duplicate/single-use
confirmation, ownership and permission denial. No test is removed, skipped or weakened.
All 44 page routes, API router registrations and protected code paths must remain intact.
Apply canonical DoD to this scope; record pre-existing failures explicitly rather than
claiming the entire project is green. No new test mirrors the removed helper's implementation.
Locale/print behavior is unaffected; existing frontend/print validation tests remain evidence
only for their actual scope, not full browser or stakeholder acceptance.

## Performance baseline and deferred work

No production or endpoint performance improvement is established. Record any safe pure-function
measurement with dataset, timing method and environmental limitations. Current priorities:
validate S01 as approved; then profile demonstrated query/request bottlenecks before selecting
larger refactors. Do not infer N+1 or missing indexes from a large function or loop alone.
Dependencies, CSS, translation keys and assets remain removal candidates only after dynamic
configuration/build/runtime reachability checks; dirty package/lockfiles are protected.

## Post-change results

- Removed one unused internal method and its otherwise-unused constant from registry.py.
  No file, dependency, endpoint, model, migration, calculation or transaction was removed.
- Added `test_unsupported_import_mode_is_rejected_without_writes`: passed against the original
  implementation (1 passed, 2.25 s), proving the live guard did not depend on the dead helper.
- After removal, `uv run pytest -q tests/test_excel_import_export.py tests/test_frontend_api_contract.py
  tests/test_route_authorization.py`: **53 passed**, 48 warnings, **55.82 s**. The extra test is
  the new guard regression. Timings are test-run observations, not an application speedup.
- `uv run ruff check app tests scripts` and the focused registry/test Ruff check passed.
  Root Ruff still has the two pre-existing untracked-diagnostic findings; not suppressed.
- API-contract check reports existing duplicate OpenAPI operation-ID warnings; schema/test
  setup reports existing cyclic-FK warnings and Starlette 422-name deprecations. None fixed
  by changing contracts or dependencies in this bounded batch.
- `graphify update .` was attempted but blocked by the tool allowlist. The local graph
  remains stale; do not use it as fresh impact evidence. No permission settings changed.
- The full backend baseline was started before edits and collected the original tests;
  its module imports preceded helper removal. The 53-test post-change run exercises the
  final registry plus the new regression. A second full backend run was not performed.
  Seven skipped baseline tests are not evidence of live PostgreSQL guarantees.
- Final task-scope verification compared 839 baseline files: only registry.py, its Excel
  test file, the supporting roadmap link and canonical quality evidence changed; this plan
  is the only new lasting file. AST comparison proves registry semantics differ only by the
  removed helper/constant and every pre-existing test body remains intact. All 44 page routes
  remain documented, S01 is byte-for-byte unchanged, and all nine changed-document links resolve.
  `git diff --check` passed; temporary audit/benchmark/verification scripts are removed.
- `node scripts/feature-status.mjs` completed; its ORDER/PLAT/REP source changes predate this
  batch. This internal dead-code removal does not upgrade a business feature's status, and
  the pre-existing dirty feature report is preserved. New verification evidence is recorded here.

### Safe performance measurements

`uv run python ../.codebase-benchmark.py` used Python 3.12.10, `perf_counter`, two warmups and
nine samples per synthetic dataset; deep-copy/setup was outside timing. Only the pure
`compare_snapshots` function ran, without database/network or production data:

| Tabs / groups / attributes | Median | Min / max |
|---|---:|---:|
| 10 / 100 / 2,000 | 6.583 ms | 6.378 / 9.941 ms |
| 100 / 1,000 / 20,000 | 80.618 ms | 76.358 / 135.364 ms |

One attribute label per tab changed; the result count was checked on each iteration.
Measurements ran under concurrent test load and are a baseline only; no optimization was
applied and no percentage improvement is claimed. These are not approved business volumes,
API targets or PostgreSQL query plans. Temporary audit/benchmark scripts are removed at handoff.
Existing repository query-count guards plus snapshot comparisons passed:
`uv run pytest -q tests/test_repository_queries.py tests/test_config_compare.py` — 7 passed,
2 warnings, 4.59 s. Those guards verify existing batching, not a new performance change.

### Additional audit candidates, not changes

`useGlobalSearch.ts:55–81` assigns results/loading after awaiting requests without a local
request-generation check and leaves a debounce timer without explicit scope cleanup.
`useSearch.ts` already cancels prior requests within each mode; keyword and semantic use
different request keys. Cross-mode/clear/unmount races need deterministic deferred-response
tests before calling them confirmed defects. Preserve this code in batch 1.
Excel `start_import` calls synchronous workbook parsing inside an async path; input/archive
caps exist. Measure event-loop delay with a safe fixture before proposing thread/worker changes.
Ledger page/export source already uses SQL LIMIT/window balances and streaming batches;
do not replace it or add permission/financial caching merely because report code is large.

## Batch 2 — Global-search response and lifecycle ownership

### Reproduction and root causes

The initial 17 deterministic Vitest cases ran against unchanged production search code:
14 failed and 3 passed. Deferred transport promises deliberately complete after cancellation;
fake timers control the 120 ms debounce. This demonstrates behavior independently of network
timing. Four additional positive/boundary cases bring the final regression suite to 21.

- Older keyword/semantic responses and answer responses could overwrite newer state; catch
  and finally handlers also lacked ownership checks and could clear current results/loading.
- Query invalidation waited for the next debounce; clearing, closing and scope disposal did
  not reliably discard pending work or late completions. The debounce lacked scope cleanup.
- Whitespace-equivalent input dispatched duplicate queries. Closed palettes could dispatch
  searches, and fixed global cancellation keys could interfere across mounted consumers.

### Smallest scoped changes and acceptance evidence

`useGlobalSearch.ts` now invalidates synchronously on normalized query, mode or open changes;
only the current generation may publish results, errors, answers or loading completion.
It clears timers/state and requests cancellation on close, clear and scope disposal.
`useSearch.ts` uses the existing cancellation API with per-instance keys from the existing
client-ID helper. REST payloads, result mapping, navigation, layout and shared auth transport
are unchanged. No dependency, file, route or business function was removed in this batch.

`frontend/tests/global-search.spec.ts` uses real Vue scopes/watchers and both real search
composables, mocking only transport/menu boundaries. Coverage includes cross-mode ordering,
the debounce gap, stale rejection/finally, rapid typing/clearing, close/reopen, disposal,
instance isolation, failed-request recovery, duplicate answer clicks, source payloads and
preservation of permission-filtered navigation. Backend permission checks were inspected;
no authorization or query code changed. The menu mock is not proof of live Casbin policy.

| Command (owning directory) | Batch 2 result |
|---|---|
| frontend: `pnpm vitest run tests/global-search.spec.ts tests/component-layout.spec.ts tests/configuration-version-preview.spec.ts` | 29 passed / 3 files, 521 ms |
| frontend: `pnpm lint` | Passed |
| frontend: `pnpm typecheck` | Passed before/after production edits and after all 21 tests were finalized |
| frontend: `pnpm test` | 793 passed / 94 files, 5.35 s |
| frontend: `pnpm i18n:check` | Passed; km/zh 3324 keys; existing 52 zh English-identical values remain |
| backend: `uv run pytest -q tests/test_api_completeness.py tests/test_frontend_api_contract.py tests/test_route_authorization.py` | 11 passed, 24 warnings, 9.86 s |
| backend: `uv run ruff check app tests scripts` | Passed; root diagnostic findings remain as recorded in baseline |
| root: `node scripts/feature-status.mjs` | Completed; search files unmapped; unrelated dirty feature report preserved, no feature-status upgrade |

The full frontend suite covers the final 21-case search regression. Backend is unchanged;
the prior full baseline and seven skipped PostgreSQL tests remain visible above, not newly
verified PostgreSQL evidence. Browser focus/keyboard behavior and browser E2E were not run:
an isolated target/account was not established. No focus/DOM/layout code was modified.
`graphify update .` remains tool-blocked; no settings were changed to bypass the block.

### Controlled request-count measurements

Same fake-clock/deferred-transport fixtures before and after, counting dispatched reads:

| Scenario | Before | After | Reduction in this fixture |
|---|---:|---:|---:|
| Completed `freight`, then ` freight `, advance 120 ms | 2 | 1 | 50% |
| Type nonempty query, close at 60 ms, advance past debounce | 1 | 0 | 100% |
| Type a nonempty query while closed, advance past debounce | 1 | 0 | 100% |

Rapid typing already debounced correctly and remains one request. These counts demonstrate
avoided dispatches only; no elapsed-time, bundle-size, SQL or production speedup is claimed.
Cancellation is best effort for controllers already registered by `useApi`; generation checks
protect state even if cancellation loses a race. Cancellation does not prove server query
termination, and the shared authentication preflight was deliberately not refactored.

### Remaining candidate review

Final preservation check compared 839 baseline files: only the two search composables and
this plan/canonical quality document changed; the new search regression is the only lasting
new file from batch 2. All unrelated work, S01, roadmap, page routes, backend and configuration
remain byte-for-byte unchanged. The 44-page inventory and five local links in affected
documents pass checks. `git diff --check` passes with pre-existing line-ending warnings only.

Reviewed `types/component-config.ts` and its type/runtime consumers. `COMPONENT_DISPLAY_MODES`
remains a likely unused runtime export; retain until re-export/dynamic reachability proof is
completed in a separate small batch. Keep the used type union and `COMPONENT_DATA_TYPES`.
No evidence justifies broader component, translation, finance, authorization or recovery
refactoring. Existing configuration-comparison timings remain a baseline only.

## Handoff

- Current status: Batches 1 and 2 complete; supporting audit is In Review, not active S01.
- Completed work: Repository inventory, dirty-file protection, baseline frontend gates,
  full backend baseline, schema/scoped Ruff checks, candidate classification, template-ref
  false-positive review, safe pure-function timing, confirmed-unused helper/constant removal
  and a passing before/after API regression. Focused post-change checks passed.
- Batch 2 completed work: Reproduced search races before editing, fixed request ownership,
  debounce/disposal/cancellation and duplicate normalized-query dispatch, added 21 regressions,
  ran full frontend gates and focused backend contract/denial checks. No S01 status change.
- Remaining work: Broader dead-code/dependency/dynamic reachability review, profiled endpoint/
  PostgreSQL/bundle/browser baselines and individually scoped duplicate/complexity refactors.
  Do not treat the repository-wide first pass as exhaustive verification or production acceptance.
- Exact next action: On ordinary “Continue development”, follow active S01 PLAN-0002.
  If explicitly continuing cleanup, finish the repository-wide import/re-export/dynamic and
  Nuxt auto-import proof for COMPONENT_DISPLAY_MODES before considering that export alone
  for removal; retain the type and used runtime registry. Run focused configuration tests,
  typecheck and full frontend gates if changed. Do not refactor deferred finance/auth code.
- Relevant files/commands: excel_io/registry.py and service.py; test_excel_import_export.py;
  search/useGlobalSearch.ts, search/useSearch.ts, tests/global-search.spec.ts;
  commands and measured datasets in the evidence tables; canonical testing/architecture docs.
- Open blockers: Safe live profiling environment is unverified. Pre-existing diagnostic lint
  findings, template-ref unused warning, skipped integration checks, English-identical Chinese
  values and existing warnings remain. Graph refresh is tool-blocked. No performance gain or
  exhaustive unused-dependency proof is claimed.
- Commit status: No commit authorized or made.
