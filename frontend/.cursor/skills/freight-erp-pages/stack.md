# Stack: Nuxt UI static SPA on a FastAPI /api/v1 backend

## Allowed UI

Use only:

- **Nuxt UI** components already in the project (`@nuxt/ui`)
- **TypeScript**
- **Tailwind** utility classes (existing tokens: `text-highlighted`, `text-muted`, `border-default`, `bg-elevated`, …)

Do not add Material, Ant Design, shadcn, Bootstrap, or a second chart library if ECharts is already used on the dashboard.

## API-only data

1. Pages read **Pinia** `useFreightStore()` / LCS HTTP repositories — the real `/api/v1` backend.
2. New collections: seed in `app/config/freight-seed.ts` (and LCS stamp in `app/config/lcs-seed.ts`), typed as `FreightRecord`.
3. Writes go through `store.save` / `store.create` / LCS commands in `app/utils/lcs/commands.ts` so audit and status rules stay in one place.
4. Scope with `filterScopedRecords` / tenant store (`organizationId`, `branchId`).
5. Aggregations (dashboard KPIs, aging, report totals) belong in store helpers (e.g. `dashboardSummary`) so lists are not loaded only to sum on the client when a helper already exists.

## API later

- Keep page contracts (columns, filters, tabs) stable.
- HTTP lives under `app/repositories/` (`createHttp*`), same origin behind nginx.
- Official document numbers are allocated by the backend; the UI must never pretend to allocate a legal number.
- Do not encode secrets, passwords, or tokens in audit payloads or settings display.

## Reusable UI (no hardcoded pages)

- Route files only set `definePageMeta` and mount `FreightWorkspaceView`, `FreightModulePage`, or `SystemSettingsPage`.
- Module columns/fields/tabs/actions live in `app/config/freight-modules.ts` and `app/config/lcs-reference-modules.ts`.
- Settings tabs/fields live in `app/config/settings-schemas.ts`. Render with `AppDocumentForm` + `AppDynamicFieldRenderer`.
- Shared option lists: `app/config/freight-options.ts`, `app/utils/constants/select-options.ts`.
- New control type → extend `FieldInput` or `AppDynamicFieldRenderer`, then reference it from schema. Do not add a one-off input on one page.
- Component map: [components.md](components.md).

## Settings (tenant customize)

Persist through settings repositories. Read at runtime:

- Branding / logo / primary color: `useAppBranding()`
- Language, timezone, date/number/currency formats: `useAppLocalization()`
- Feature flags from App Config (`enableComments`, `enableSharing`, `enableExport`, page size, landing page)

Do not hardcode those values in Vue or CSS. Do not show secrets; use `AppSecretInput`.

## Dynamic configuration

Job extra tabs are component instances from templates (groups + templates + trade-direction-components). Core tabs (Overview, Route, Containers, Finance, Files) are fixed. Render attributes from `values[]` by `dataType` / `inputType`. Preserve `templateVersion`. Do not ship a Vue form per document type (Customs, Invoice, …).

Posting account mapping is **posting-rules** config, not hardcoded fee→account switches.

## Forms and tables

- Field size **md** for inputs/selects/dates on document and module forms.
- **Helper text:** every form field has ERPNext-style `UFormField` `help`. Resolve with `resolveFormFieldHelp` / `useFormFieldHelp`. Add `freight.fieldHelp.<key>` (and km) when introducing a field. Do not suppress help for compact document forms.
- Compact tables: `freightTableUi*` in `app/utils/table/theme.ts`.
- Money/qty: right-align, `tabular-nums`. Format money/dates with `useAppLocalization()` when displaying.
- Secondary row actions: `UDropdownMenu` + `i-lucide-ellipsis` (`⋯`).
