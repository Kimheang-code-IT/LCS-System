---
name: nuxt-frontend
description: Use when implementing or changing the LCS Nuxt 4 frontend: pages, Vue components, TypeScript composables, repository and API integration, Pinia stores, i18n, responsive layout, accessibility, and inline form validation.
---

# Nuxt frontend

The frontend is a **static SPA** (`ssr: false`, `nuxt generate`, served by nginx,
which proxies `/api/` so the browser is same-origin). There is no Node runtime in
production and no mock data layer.

> Before editing, check file modification times. If another session is actively
> editing `frontend/`, stop and coordinate rather than racing it.

## When to use

- Adding or changing a page, component, composable, or store.
- Wiring an API call, or mapping a backend error onto a field.
- Changing form validation, error display, or success feedback behaviour.
- Changing i18n copy, layout, or accessibility.

## Required inputs

1. The module/page and the collection or endpoint it uses.
2. The backend contract: exact path, verb, request body, response envelope.
3. Whether the screen already exists (extend it) or is genuinely new.

## Project references

| Document | Use it for |
|---|---|
| `AGENTS.md` §Frontend | Enforced conventions and the icon/i18n gotchas |
| `docs/08_frontend_and_ui_design.md` | Intended page, component, and data-flow design |
| `frontend/app/config/freight-modules.ts`, `lcs-reference-modules.ts` | The metadata-driven page definitions |
| `frontend/app/utils/validation/` | The validation primitives |
| `frontend/app/composables/common/useFormValidation.ts` | The shared form-error state machine |
| `docs/10_testing_and_quality.md` §7-§8 | Current state and known gaps |

## Architecture

```text
pages/**            thin route wrappers: definePageMeta + one view component
components/**       view + field renderers
composables/**      state and orchestration (useFormValidation, useFreight, …)
repositories/http/  every HTTP call, behind repositories/contracts/ and repositories/index.ts
stores/**           Pinia (primary: useFreightStore)
config/*.ts         metadata-driven module, field, table, and report definitions
utils/**            auto-imported helpers (imports.dirs)
```

Hard rules:

- **No ad-hoc `fetch`.** Register the path in `app/utils/constants/api-v1-endpoints.ts`
  (controller-style calls) or `app/utils/api/freight-remote.ts` (`REMOTE_ENDPOINTS`,
  collection CRUD), then call it from a repository. The backend's
  `tests/test_frontend_api_contract.py` statically reads those exact files and
  fails if a referenced path or verb does not exist on the FastAPI app.
- `app/utils/**` is auto-imported; components, layouts, and composables use Nuxt
  defaults. Use the `~` alias for `app/`.
- **i18n**: bundles in `i18n/locales/<code>.json` must stay structurally identical
  to `en.json` (`pnpm i18n:check`, also enforced by `tests/i18n-locales.spec.ts`).
  Add copy to all locales; manage keys with `node scripts/i18n.mjs add <locale> '<json>'`.
  Never hardcode a `'en' | 'km'` union — derive from
  `app/utils/constants/app-languages.ts`.
- **Labels** for code-shipped copy resolve through
  `useFreightLabel().fieldLabel()`; do not add a parallel per-language field. The
  stored `labelKm` column is *admin-managed data* for user-defined component
  attributes and dynamic-table columns only.
- **Icons** are only bundled from files matched by `icon.clientBundle.scan`
  (`app/components/**`, `app/composables/**`, `app/config/**`, `app/layouts/**`,
  `app/pages/**`). An icon referenced only from `app/utils`, `app/types`, or JSON
  will not be bundled.
- Frontend tests are plain Vitest, `environment: node`, `import.meta.client = false`,
  alias `~ -> app`, only `tests/**/*.spec.ts`. They do **not** mount the Nuxt
  runtime — test pure functions, not rendered DOM.

## Inline validation model

Validation errors belong **under the field**, never in a toast. Toasts are for
confirmed successes only.

- Client rules come from `app/utils/validation/record-validation.ts`
  (`validateDocumentFields`, `validateTableRows`) and
  `component-rules.ts` (dynamic component attributes, driven by each attribute's
  `validationRules` JSON).
- State comes from `useFormValidation()`: `fieldErrors`, `formErrors`, `submitting`,
  `applyFailures`, `applyServerError`, `clearFieldError`, `clearTableErrors`,
  `focusFirstInvalid`.
- Display: pass `:error` to `UFormField` (directly or through
  `AppDynamicFieldRenderer`, `AppFieldGrid`, `AppComponentTabs`, `AppLineTable`),
  and put `data-field-key="<key>"` on the wrapper so focus and scroll can find it.
- Server errors: `applyServerError(error)` uses `normalizeApiError` plus
  `error-paths.ts` to map `field_errors` keys onto registered keys; anything
  unmatched becomes a form-level message. **A new backend error key must be
  resolvable by `error-paths.ts` or it silently becomes page-level.**
- Submit order: validate → if invalid, `applyFailures` + `focusFirstInvalid()` and
  return → else persist → on throw, `applyServerError` + `focusFirstInvalid()`.
- `AppFormErrorSummary` renders **only** the fieldless messages, as a slim
  `role="alert"` + `aria-live="assertive"` line. It deliberately does **not**
  repeat field errors: each one is already under its own control, and
  `focusFirstInvalid()` navigates to it. Do not reintroduce a duplicate list.
  A refusal with no field (`formErrors`) must never be dropped — if nothing
  renders `formErrors`, the user gets no feedback at all.
- Duplicate-submission protection is two layers: a `saving`/`submitting` guard at
  the top of the handler, and the button's `:loading` state.
- `focus.ts` opens the owning tab before focusing, so an error on a hidden tab is
  revealed. Keep the `data-field-key` contract intact when restructuring markup.
- Suppress the global error toast on form submits (`suppressErrorToast` in
  `useApi`) so the same failure is not reported twice.

## Workflow

1. **Find the closest existing page** and copy its shape. Most screens are
   metadata-driven; a genuinely bespoke screen is the exception.
2. **Add the endpoint** to the constants and the repository, then the composable,
   then the view. Keep the layers in that order.
3. **Model the state** explicitly: `loading`, `saving`, `fieldErrors`, `formErrors`.
4. **Add copy to all locales.**
5. **Run the gates** before declaring anything done.

## Security requirements

- A frontend permission check is convenience only; the backend must enforce it.
  Never claim a feature is protected because a button is hidden.
- Never render a secret returned by an API; the backend masks sensitive fields, but
  do not add a new field that reintroduces one.
- Do not log tokens or credentials in the browser console.

## Testing

```bash
cd frontend
pnpm lint
pnpm typecheck
pnpm test                                    # all specs
pnpm vitest run tests/<file>.spec.ts         # one spec
pnpm i18n:check
pnpm generate                                # only for build-affecting changes
```

Prioritise tests for pure logic — validation rules, key mapping
(`error-paths.ts`), formatters, table calculators, module resolvers. A validator or
error-mapping change without a spec is incomplete.

## Acceptance criteria

- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm i18n:check` all pass.
- Every API path the change introduces exists on the backend (contract test).
- Validation errors render under the correct field; no validation failure is
  reported by a toast.
- An invalid form cannot be submitted, and focus moves to the first invalid field,
  opening its tab or section first.
- User input survives a failed submit.
- Keyboard accessible: the summary is announced, its items are focusable, and
  inputs receive focus.
- Copy exists in every locale.

## Expected outputs

- Changed pages/components/composables/repositories/stores and locale bundles.
- Endpoint constants and `REMOTE_ENDPOINTS` entries when the surface grew.
- Vitest specs for the pure logic added or changed.
- An updated UI description in the relevant `docs/` file.
