# Reusable UI, settings, and dynamic configuration

This system is **schema-driven**. Pages are thin route shells. Do **not** hardcode forms, columns, filters, options, labels, or task-type screens in Vue.

When a field, column, tab, or action is needed, put it in config and render it with an existing component.

## Never hardcode

Do **not**:

- Copy-paste a new list/detail page instead of `WorkspaceView` / `DocumentView` / `JobDetail` / `ReportsView` / `DashboardView`.
- Hand-write per-page `UInput` / `USelect` / `UTable` grids when `FieldGrid`, `FieldInput`, `AppLineTable`, or `AppDynamicFieldRenderer` already cover the type.
- Hardcode Customs / Transport / Shipping forms for service-order tasks. Tasks come from **component templates**.
- Hardcode tenant branding, date format, page size, or language. Those come from **System Settings**.
- Hardcode select options that already live in `app/config/freight-options.ts` or settings `select-options`.
- Hardcode English (or Khmer) strings in templates. Use i18n keys, or literal labels only when the text is user-configured (attribute catalog).
- Duplicate confirm, export, date, color, icon, secret, or search widgets. Use `app/components/common/*`.

**Allowed one-off markup:** a route file that only sets `definePageMeta` and mounts `FreightWorkspaceView`, `FreightModulePage`, or `SystemSettingsPage`.

## Route pattern

```vue
<script setup lang="ts">
definePageMeta({ titleKey: 'freight.pages.quotations', permission: 'sales.quotations.view' })
</script>
<template><FreightWorkspaceView /></template>
```

Detail/edit/new for the same module: `<FreightModulePage />` (resolves list vs job vs document vs reports from the module schema).

Settings: `<SystemSettingsPage />` — do not rebuild the settings form on the page.

## Which component to reuse

### Page shells

| Need | Use |
|------|-----|
| Module list | `freight/WorkspaceView.vue` |
| Generic record detail/create | `freight/DocumentView.vue` via `freight/ModulePage.vue` |
| Service order job workspace | `freight/JobDetail.vue` + section components |
| Dashboard | `freight/DashboardView.vue` + `dashboard/AppKpiSection.vue` + `dashboard/AppSummaryCard.vue` + `dashboard/AppChartGrid.vue` + `dashboard/AppChartPanel.vue` + `dashboard/AppEChart.vue` |
| Reports | `freight/ReportsView.vue` |
| System settings | `settings/SystemSettingsPage.vue` |

### Schema-driven fields and tables

| Need | Use |
|------|-----|
| Freight module fields (`FreightField`) | `freight/FieldGrid.vue` → `freight/FieldInput.vue` |
| Document / settings fields (`DocumentFieldSchema`) | `document/AppDocumentForm.vue` → `document/AppDynamicFieldRenderer.vue` |
| Module / report list tables | `table/AppListTable.vue` → `table/AppTableRowMeta.vue` |
| Line / pricing / child tables | `table/AppLineTable.vue` |
| Related records | `table/AppRelatedRecords.vue`, `table/AppJobRelatedTable.vue` |
| Dynamic task attribute values | Render from template `values[]` by `dataType` / `inputType` through the field renderer — **never** a Vue file per task type |

### Job workspace sections

Reuse `JobOverview`, `JobRoute`, `JobContainers`, `JobTasks`, `JobCharges`, `JobFinance`, `JobFiles`, `JobActivity`, plus `JobSectionHeader`, `JobSummaryStrip`, `JobEmptyState`, `JobDefinitionList`. Do not invent a second job layout.

### Common widgets (`app/components/common/`)

`AppConfirmDialog` / `useConfirm`, `AppExportDialog`, `AppDateRangeFilter`, `AppInputDate` / `AppDatePickerPopover`, `AppLiveSearch`, `AppFilterSelect` (toolbar multi-select filters), `AppSortableList`, `AppColorPicker`, `AppIconPicker`, `AppSecretInput`, `AppImageUploadField`, `AppRolePermissionMatrix`, `AppConnectionStatusCard`, `AppConnectionTestButton`, `AppMentionMultiInput`, `AppAuthLocaleSwitch`, `AppAccessAlertHost`.

### Tables (`app/components/table/`)

`AppListTable` (search, filters, pagination, row click), `AppTableRowMeta` (avatar, relative time, comments, `⋯`), `AppLineTable` (pricing / containers / route / files), `AppRelatedRecords`, `AppJobRelatedTable`. Used by `WorkspaceView`, `ReportsView`, `AppDynamicFieldRenderer`, and job sections. Helpers stay in `app/utils/table/`.

### Dashboard widgets (`app/components/dashboard/`)

`AppKpiSection` (titled 4-up KPI grid), `AppSummaryCard`, `AppChartGrid` (two-chart layout), `AppChartPanel` (year/period + download), `AppEChart`. Used by `DashboardView` / `/`. Do not add a dashboard filter bar.

### Configuration builders (`app/components/configuration/`)

Use these from `AppDynamicFieldRenderer` field types — do not rebuild:

| Field type | Component |
|------------|-----------|
| `options-builder` | `AppAttributeOptionsBuilder` |
| `validation-builder` | `AppValidationRuleBuilder` |
| `visibility-builder` | `AppVisibilityRuleBuilder` |
| `workflow-builder` | `AppWorkflowStageBuilder` |
| `numbering-preview` | `AppNumberingPreview` |

### Settings UI (`app/components/settings/`)

`SystemSettingsPage`.

### Document chrome

`AppDocumentPage`, `AppDocumentForm`, `AppDocumentTabBar`, `AppDocumentContentShell`, `AppDocumentMetaRail`, `AppCommentsActivity`.

If a widget is missing, **extend the existing renderer** (new `FieldType` + `AppDynamicFieldRenderer` branch, or new `FreightFieldType` + `FieldInput` branch) and add it to the schema. Do not add a one-off control on a single page.

## ERPNext helper text (required)

Every **form field** shows a short description under the control (`UFormField` `help`), like ERPNext field descriptions.

- Render through `FieldInput`, `AppDynamicFieldRenderer`, or `useFormFieldHelp()` — do not omit `:help`.
- Copy lives in i18n: `freight.fieldHelp.<key>` and `docetra.fieldHelp.<key>` (en + km). Optional `help` / `helpKey` on the schema wins.
- Template attributes should store `helpText`; job Tasks show that text, otherwise fall back to i18n / default.
- Do **not** hide help when a form is compact. List **filters** and **table cells** do not need per-cell help.
- Default fallback: `docetra.fieldHelp.default` (“Enter or update {field}.”). Prefer a real description when adding a field.

## Where configuration lives (not in Vue)

| What | Where |
|------|--------|
| List columns, filters, fields, tabs, line tables, actions | `app/config/freight-modules.ts`, `app/config/lcs-reference-modules.ts` |
| Shared option lists | `app/config/freight-options.ts`, `app/utils/constants/select-options.ts` |
| Settings form tabs/fields | `app/config/settings-schemas.ts` (`appInfoTabs`, `appConfigTabs`) |
| Settings values (brand, locale, features) | settings repositories + `useAppBranding`, `useAppLocalization` |
| Job tasks / dynamic attributes | Configuration: component groups, **component templates**, trade-direction-components |
| Posting mapping | Configuration: posting-rules |
| Role matrix | `AppRolePermissionMatrix` + role form config |

## Settings page (tenant customize)

Routes: `/administration/system-settings`, `/configuration/system-settings` — both mount `SystemSettingsPage`.

Runtime settings must drive the app. Do not bake them into components:

- **App Info:** name, logo, primary color → `useAppBranding()` (CSS brand tokens). Do not restyle global colors in CSS instead of this.
- **Localization:** language, timezone, date/time/number/currency formats → `useAppLocalization()`. Format dates/money through it.
- **General:** landing page, page size, record view, upload size, comments / sharing / export flags. Honour feature flags (`enableComments`, `enableSharing`, `enableExport`) instead of always showing those actions.
- **Email / Telegram / notifications / security / system:** schema fields + connection test widgets. Never show raw secrets; use `AppSecretInput`.

Adding a setting: add the field to `settings-schemas.ts`, persist through settings repositories, read it via a composable. Do not add a parallel settings screen.

## Dynamic configuration (operations)

Administrators configure **what fields appear on a job**, not developers.

1. **Component groups** — grouping for tasks.
2. **Component templates** — versioned attribute catalog (`dataType`, `inputType`, required, repeatable, reference type, validation, options, visibility). Preserve version history; a job captures `templateVersion`.
3. **Trade-direction-components** — which templates apply to Import/Export (required, repeatable, display order).
4. **Posting rules** — fee type → debit/credit/tax accounts. Not hardcoded per fee in Vue.

On each service-order **component-group tab** (not Overview / Route / Containers / Finance / Files):

- Tab list comes from Component Groups (`showOnJobWorkspace`). Fields come from the assigned Component Template (trade-direction-components for Import/Export).
- Render each attribute with `AppDynamicFieldRenderer` using `dataType` / `inputType` (`lcs.components.listForJob` / `ensureForJob` / `saveValues`).
- Show ERPNext-style helper text (`helpText` on the attribute, else i18n / default).
- Enforce required attributes before complete.
- Do **not** hard-code a form for Customs Clearance, Transport Booking, Invoice, etc.

When templates gain a new input type, extend `FieldInput` / `AppDynamicFieldRenderer` (or the shared task-value control) once so every template gets it.

## Extend, don't fork

1. Prefer adding a field to the module/settings schema.
2. If the control type is new, extend the shared renderer.
3. If the page kind is new, extend `ModulePage` kinds — do not create a third document layout.
4. Keep Nuxt UI + existing Tailwind tokens. No new UI kit.
