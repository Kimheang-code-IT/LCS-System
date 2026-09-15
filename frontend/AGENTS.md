# LCS Freight Forwarding (frontend)

This file is the **OpenCode project rule**. OpenCode loads `AGENTS.md` on every session.

## Stack

Nuxt 4 + **Nuxt UI** + TypeScript + Tailwind. **API-only** (the Pinia `useFreightStore` and `app/repositories/http/` talk to the real `/api/v1` backend; the legacy mock layer has been removed). The app is built as a static SPA (`nuxt generate`) and served by nginx. Do not add another UI kit.

## Always

- Do not redesign, change global colors/type, or change the sidebar unless a catalog route is missing.
- Reuse existing components. Do **not** hardcode per-page forms, tables, options, labels, or task-type screens.
- Drive UI from module schemas (`freight-modules.ts`, `lcs-reference-modules.ts`), settings schemas (`settings-schemas.ts`), and **component templates**.
- Honour System Settings at runtime: branding (`useAppBranding`), localization (`useAppLocalization`), feature flags. Do not bake tenant settings into Vue/CSS.
- Job Tasks: render attributes from the assigned template `values[]` by data/input type. Never add a Vue form per task (Customs, Transport, …).
- Reuse `WorkspaceView`, `DocumentView`, `JobDetail`, `ReportsView`, `DashboardView`, `AppLineTable`, `FieldInput`, `FieldGrid`, `AppDocumentForm`, `AppDynamicFieldRenderer`, `SystemSettingsPage`.
- One shell per module kind: lists/details render through `WorkspaceView` / `ModulePage`. Do not create page-level clones (e.g. a second service-order list component).
- Delete superseded/orphaned `.vue` components. Do not leave dead code in the tree.
- Option lists live only in `app/config/freight-options.ts` / `select-options`. Never copy option arrays into components.
- Table cells: shared formatter + status badge helper (`formatFreightCell`, `statusColor`). No inline badge-color ternaries; do not copy date/format helpers between files.
- Data grids use `UTable` with the compact utilities; no raw `<table>` markup in components.
- No native `window.prompt` / `alert` / `confirm`. Use `AppConfirmDialog` / `useConfirm`, or a small `UModal` form for text input.
- Every form field shows ERPNext-style helper text under the control (`UFormField` `help`, `useFormFieldHelp`, `freight.fieldHelp.*` / `docetra.fieldHelp.*` in en+km). Do not hide help on compact forms.
- Compact ERP tables: small rows, subtle borders, light hover, `⋯` actions, right-align money, existing badges.
- English + Khmer in `i18n/locales/en.json` and `km.json`.
- Org / branch / `auth.canAccessPage`. Frontend hide is not security.
- Posted journals only for accounting reports. Issue service charge ≠ posting.
- Form fields: size `md`. Do not allocate official document numbers in the UI.

## Skill

When building or fixing dashboard, quotations, service orders, charges, finance, reports, master data, configuration, administration, settings, or dynamic fields, load skill **`freight-erp-pages`** (`.opencode/skills/freight-erp-pages/SKILL.md`). Then read `pages.md`, `components.md`, and `stack.md` in that same folder.
