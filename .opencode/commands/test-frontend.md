---
description: Run frontend Vitest specs (argument = spec file, pattern or -t name)
---

Run from `frontend/`. The suite is plain Vitest (`environment: node`, no Nuxt runtime,
no browser), so a full run costs seconds and needs no build.

- No argument: `pnpm test` (`vitest run`).
- One spec: `pnpm vitest run tests/format.spec.ts`.
- Filter by test name: `pnpm vitest run tests/format.spec.ts -t "currency"`.
- Watch mode while iterating: `pnpm test:watch`, then exit.

`$ARGUMENTS`

Related specs by area:

| Area | Specs |
|---|---|
| Form validation, field errors, API error mapping | `tests/document-form-validation.spec.ts`, `tests/form-field-error.spec.ts`, `tests/validation-api-error.spec.ts` |
| Validation rules and messages | `tests/validation-field-rules.spec.ts`, `tests/validation-messages.spec.ts` |
| Notification policy (no toast for validation) | `tests/validation-notification-policy.spec.ts` |
| i18n parity and placeholders | `tests/i18n-locales.spec.ts`, `tests/navigation-i18n.spec.ts` |
| Formatting | `tests/format.spec.ts`, `tests/format-service.spec.ts` |
| Dynamic tables and component configuration | `tests/dynamic-table.spec.ts`, `tests/component-config-tables.spec.ts` |
| Quotations and service orders | `tests/quotation-actions.spec.ts`, `tests/job-component-tabs.spec.ts` |
| Permissions and page access | `tests/page-access.spec.ts`, `tests/role-permission-coverage.spec.ts` |

There is no Playwright or other browser suite in this repo; do not invent a UI test
command. Component behaviour that needs a DOM is covered by these specs, the backend API
contract test, and manual verification against the running stack.
