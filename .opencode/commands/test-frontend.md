---
description: Run focused frontend tests and explain browser limits
---

Run from frontend/: pnpm exec vitest run <existing spec>.
User selector: $ARGUMENTS

Without an argument select specs for changed behavior; no default whole suite. Useful
existing areas: tests/financial-print.spec.ts, print-navigation.spec.ts,
quotation-actions.spec.ts, job-component-tabs.spec.ts, form-field-error.spec.ts,
validation-api-error.spec.ts, page-access.spec.ts, role-permission-coverage.spec.ts.
Verify filenames before execution. Explicit broad/release work may use pnpm test.

Vitest uses node/import.meta.client=false; these tests do not mount Vue/Nuxt or prove DOM
behavior. Playwright DOES exist separately in frontend/e2e/ with playwright.config.ts;
pnpm test:e2e is for relevant safe browser scenarios, not an automatic companion to Vitest.
Locale edits add pnpm i18n:check. Use a short manual journey for ordinary UI; no large new
suite/framework. Preserve required financial/security checks. Report exact scope/results.
