---
name: freight-erp-pages
description: >-
  Review, standardize, and complete LCS freight-forwarding ERP pages (dashboard,
  quotations, service orders, charges, finance, reports, master data,
  configuration, administration, system settings) without redesigning. Use when
  building or fixing those routes, reusable schema-driven components, dynamic
  component-template fields, settings customization, OpenCode/Cursor ERP work,
  Nuxt UI screens, or when the user mentions the page catalog, KPI
  cards, job workspace, or posted accounting reports.
---

# Freight ERP pages

Execute page work **in this repository**. Do not stop at a proposal.

Stack for now: **Nuxt UI + TypeScript + Tailwind CSS + the live /api/v1 backend**. HTTP API later through existing repositories (`app/repositories/`). Do not add another UI kit.

## Critical rules (verbatim)

* DO NOT redesign the application.
* DO NOT replace the existing UI framework.
* DO NOT change the sidebar structure unless a listed route is missing.
* DO NOT change global colors or typography.
* Reuse existing components. Do not hardcode per-page forms, tables, or task-type screens.
* Reuse > create: extend the shared renderer or component first; never fork a page-local copy.
* One shell per module kind. Do not clone `WorkspaceView` / `DocumentView` into per-page list components.
* Delete dead code. No orphaned `.vue` components left in the tree.
* Option lists live only in `app/config/freight-options.ts` / `select-options`; never copy option arrays into components.
* Drive UI from module schemas, settings schemas, and component templates.
* Honour System Settings (branding, localization, feature flags).
* Every form field must show ERPNext-style helper text under the control (UFormField `help`).
* Render job tasks from dynamic template attributes — never a Vue form per task type.
* Keep the UI compact and ERPNext-like.
* Use small table rows.
* Use subtle borders.
* Use very light gray hover only.
* Avoid large cards and excessive whitespace.
* Avoid heavy shadows.
* Use `⋯` for secondary row actions.
* Right-align numbers and currency.
* Use existing status badges.
* Badge cells go through the shared status helper (`statusColor()` + `UBadge` `subtle`/`sm`) — no inline color ternaries.
* Data grids use `UTable` with the compact utilities; no raw `<table>` markup.
* Shared date/format helpers live beside `formatFreightCell` in composables — do not copy helpers between components.
* No native browser dialogs (`window.prompt` / `alert` / `confirm`); use `AppConfirmDialog` / `useConfirm` / a small `UModal`.
* Keep responsive behavior.
* Keep English/Khmer localization.
* Respect organization, branch, and permission scope.
* Backend remains authoritative for security.

## Stack (now vs later)

- **Now:** Vue/Nuxt pages, Nuxt UI (`UButton`, `UTable`, `UBadge`, `USelect`, …), Tailwind, Pinia store, `app/repositories/http/`.
- **Later:** swap HTTP repositories for HTTP; keep the same page contracts. Do not generate official document numbers in the frontend.
- Form controls: **md** size (not compact, not lg) unless a header/icon button already uses `xs`/`sm`.
- i18n: `i18n/locales/en.json` and `km.json`. Add keys in both.

Read [stack.md](stack.md) before changing data loading. Read [components.md](components.md) before adding UI.

## Workflow

Copy this checklist and mark progress:

```
Task Progress:
- [ ] Audit table (Page | Route | Existing | Missing | Action)
- [ ] Implement necessary updates only
- [ ] Reuse existing components (schema-driven, no one-off forms)
- [ ] ERPNext helper text on every form field (en + km)
- [ ] Settings + dynamic templates respected
- [ ] i18n en + km
- [ ] Permissions + org/branch scope
- [ ] Reuse audit clean: no clones, hand-built grids, hardcoded options, copied helpers
- [ ] Orphaned/dead components deleted
- [ ] pnpm typecheck / lint / test as asked
```

1. Inspect the current page (route file → `FreightModulePage` / `FreightWorkspaceView` / `FreightDocumentView` / `FreightJobDetail` / `FreightReportsView` / `FreightDashboardView`).
2. Compare to [pages.md](pages.md).
3. Mark **correct** / **needs update** / **missing**.
4. Implement only gaps. Reuse shells + field renderers (see [components.md](components.md)). Put new fields in schema/config, not in the page.
5. Keep current design.
6. Run `pnpm typecheck`, `pnpm lint`, `pnpm test` when finishing a batch. This repo is frontend-only; there is no backend test suite here.

### First output (before large changes)

```text
Page | Route | Existing | Missing | Action

Dashboard | / | Yes | two charts, no filter bar | Update
Quotations | /quotations | Yes | compact pricing | Update
...
```

Then execute the changes.

## Repo map

| Area | Where |
|------|--------|
| Routes | `app/pages/**` |
| Nav + permissions | `app/composables/layout/useMenu.ts` |
| List UI | `app/components/freight/WorkspaceView.vue` |
| Generic detail | `app/components/freight/DocumentView.vue` |
| Job workspace | `app/components/freight/JobDetail.vue`, `app/utils/freight/job-workspace.ts` |
| Dashboard | `app/components/freight/DashboardView.vue`, `app/components/dashboard/` |
| Reports | `app/components/freight/ReportsView.vue`, `app/pages/reports/[area]/[slug].vue` |
| Schemas | `app/config/freight-modules.ts`, `app/config/lcs-reference-modules.ts` |
| Settings UI + schema | `app/components/settings/SystemSettingsPage.vue`, `app/config/settings-schemas.ts` |
| Dynamic fields | `document/AppDynamicFieldRenderer.vue`, `freight/FieldInput.vue`, `useFormFieldHelp`, configuration builders |
| Brand / locale | `useAppBranding`, `useAppLocalization` |
| Data | `app/stores/freight.ts`, `app/repositories/http/` |
| Auth | `app/stores/auth.ts`, `app/middleware/auth.global.ts` |

## Reusable + configurable UI

Pages are thin. Lists/details come from module config. Settings and component templates change fields at runtime.

- **Do not** hardcode forms, columns, or Customs/Transport/etc. task screens in Vue.
- **Do** add fields to `freight-modules.ts` / `settings-schemas.ts` / component templates and render with `FieldGrid`, `FieldInput`, `AppLineTable`, `AppDocumentForm`, `AppDynamicFieldRenderer`.
- **Do** read branding, locale, page size, and feature flags from System Settings composables.
- **Do** show ERPNext-style helper text under every form field (`UFormField` `help`, i18n `freight.fieldHelp.*` / `docetra.fieldHelp.*`). Never hide help in compact document forms.
- Full component map: [components.md](components.md).
- Quick reuse-audit greps before finishing a batch: `size="sm"` on `FieldGrid`/`FieldInput` usage (must be `md`), `window.(prompt|confirm|alert)`, raw `<table` in `app/components`, duplicated helper names (`shortDay`, badge-cell lambdas).

## Page standards

**List:** compact header, filters, New if permitted, compact table, pagination, `⋯` actions.

**Detail:** compact header, status, primary actions, tabs.

**Report:** compact header, filters, small KPI strip, table or statement, export.

Loading / empty / error: reuse project patterns. Empty copy: `No records found.`

## Accounting

Posted journal/accounting data only for: Revenue & Expense, GL, Trial Balance, P&L, Balance Sheet, Cash Flow / Cash & Bank.

Do **not** include draft financial documents, issued service charges, or unposted journals in posted balances.

`Gross Profit = Posted Revenue - Posted Cost`. Quoted and service-charge amounts are not posted revenue.

`Issue Service Charge` ≠ accounting posting.

## Permissions

Hide by `auth.canAccessPage` / `lcs.can`. Do not treat the label `System Administrator` as a hard-coded bypass; SuperAdmin uses `pageAccess: ALL_PAGES` / role checks already in `canAccessPage`.

## Additional resources

- Page catalog (columns, tabs, KPIs): [pages.md](pages.md)
- Reusable components, settings, dynamic config: [components.md](components.md)
- Data flow: [stack.md](stack.md)
