# Frontend and UI Design

## 1. Stack and Runtime

The client is a Nuxt 4 single-page application (`ssr: false`) generated with
`nuxt generate` and served by nginx. nginx also reverse-proxies `/api/` so the
browser talks to the same origin and the HttpOnly auth cookies work without CORS.
The UI uses `@nuxt/ui` with Tailwind CSS, Pinia for state, and
`@nuxtjs/i18n` with English (`en`), Khmer (`km`), and Simplified Chinese (`zh`).

`app/utils/**` and Nuxt defaults are auto-imported; `~` maps to `app/`. The
frontend has no mock data layer: every business read and write goes through
`app/repositories/`, which is backed by `app/utils/api/freight-remote.ts`.

## 2. Shell, Routing, and Guards

- `layouts/default.vue` mounts the sidebar (`useMenu`), the header
  (`LayoutAppHeader` + `LayoutAppHeaderPageActions`), the global search entry
  point, and the content area.
- `layouts/auth.vue` is the unauthenticated shell; `layouts/print.vue` removes
  application chrome from print routes.
- `middleware/auth.global.ts` enforces session state, first-run setup, forced
  password change, and the page permission declared by `definePageMeta`.
  `middleware/report-area-auth.ts` additionally guards report areas.
- Page access is also mirrored in `useAuthStore().canAccessPage(pageId)` and the
  metadata catalogue. A missing permission denies the route; backend API
  authorization is still the final guard.
- The route table below is generated from `frontend/app/pages/**`. “Page guard” is
  the `definePageMeta` permission; write buttons use the module’s action
  permissions and the API enforces them independently.

## 3. Page Reference

| Route | Page file | titleKey | Page guard |
|---|---|---|---|
| `/administration/archive` | `app/pages/administration/archive/index.vue` | `freight.pages.archive` | `admin.archive.view` |
| `/administration/audit-logs` | `app/pages/administration/audit-logs/index.vue` | `freight.pages.auditLogs` | `admin.audit_logs.view` |
| `/administration/document-sequences/:id` | `app/pages/administration/document-sequences/[id].vue` | `freight.pages.documentSequences` | `configuration.manage` |
| `/administration/document-sequences` | `app/pages/administration/document-sequences/index.vue` | `freight.pages.documentSequences` | `configuration.manage` |
| `/administration/document-sequences/new` | `app/pages/administration/document-sequences/new.vue` | `freight.pages.documentSequences` | `configuration.manage` |
| `/administration/roles/:id` | `app/pages/administration/roles/[id].vue` | `freight.pages.roles` | `admin.roles.view` |
| `/administration/roles` | `app/pages/administration/roles/index.vue` | `freight.pages.roles` | `admin.roles.view` |
| `/administration/roles/new` | `app/pages/administration/roles/new.vue` | `freight.pages.roles` | `admin.roles.view` |
| `/administration/system-settings` | `app/pages/administration/system-settings/index.vue` | `freight.pages.settings` | `settings.app_config.view` |
| `/administration/users/:id` | `app/pages/administration/users/[id].vue` | `freight.pages.users` | `admin.users.view` |
| `/administration/users` | `app/pages/administration/users/index.vue` | `freight.pages.users` | `admin.users.view` |
| `/administration/users/new` | `app/pages/administration/users/new.vue` | `freight.pages.users` | `admin.users.view` |
| `/auth/change-password` | `app/pages/auth/change-password.vue` | — | public |
| `/auth/forget-password` | `app/pages/auth/forget-password.vue` | — | public |
| `/auth/login` | `app/pages/auth/login.vue` | — | public |
| `/auth/reset-password` | `app/pages/auth/reset-password.vue` | — | public |
| `/auth/setup` | `app/pages/auth/setup.vue` | — | public |
| `/auth/verify-code` | `app/pages/auth/verify-code.vue` | — | public |
| `/configuration/component-attributes` | `app/pages/configuration/component-attributes/index.vue` | `freight.pages.componentAttributes` | `configuration.manage` |
| `/configuration/component-groups` | `app/pages/configuration/component-groups/index.vue` | `freight.pages.componentGroups` | `configuration.manage` |
| `/configuration/component-tabs` | `app/pages/configuration/component-tabs/index.vue` | `freight.pages.componentTabs` | `configuration.manage` |
| `/configuration/versions/:id` | `app/pages/configuration/versions/[id].vue` | `freight.pages.configurationVersions` | `configuration.manage` |
| `/configuration/versions` | `app/pages/configuration/versions/index.vue` | `freight.pages.configurationVersions` | `configuration.manage` |
| `/configuration/versions/new` | `app/pages/configuration/versions/new.vue` | `freight.pages.configurationVersions` | `configuration.manage` |
| `/finance/accounting-periods/:id` | `app/pages/finance/accounting-periods/[id].vue` | `freight.pages.accountingPeriods` | `finance.accounting.view` |
| `/finance/accounting-periods` | `app/pages/finance/accounting-periods/index.vue` | `freight.pages.accountingPeriods` | `finance.accounting.view` |
| `/finance/chart-of-accounts/:id` | `app/pages/finance/chart-of-accounts/[id].vue` | `freight.pages.chartOfAccounts` | `finance.accounting.view` |
| `/finance/chart-of-accounts` | `app/pages/finance/chart-of-accounts/index.vue` | `freight.pages.chartOfAccounts` | `finance.accounting.view` |
| `/finance/chart-of-accounts/new` | `app/pages/finance/chart-of-accounts/new.vue` | `freight.pages.chartOfAccounts` | `finance.accounting.view` |
| `/finance/documents/:id` | `app/pages/finance/documents/[id].vue` | `freight.pages.financialDocuments` | `finance.financial_documents.view` |
| `/finance/documents` | `app/pages/finance/documents/index.vue` | `freight.pages.financialDocuments` | `finance.financial_documents.view` |
| `/finance/documents/new` | `app/pages/finance/documents/new.vue` | `freight.pages.financialDocuments` | `finance.financial_documents.view` |
| `/finance/financial-accounts/:id` | `app/pages/finance/financial-accounts/[id].vue` | `freight.pages.financialAccounts` | `finance.accounting.view` |
| `/finance/financial-accounts` | `app/pages/finance/financial-accounts/index.vue` | `freight.pages.financialAccounts` | `finance.accounting.view` |
| `/finance/financial-accounts/new` | `app/pages/finance/financial-accounts/new.vue` | `freight.pages.financialAccounts` | `finance.accounting.view` |
| `/finance/journals/:id` | `app/pages/finance/journals/[id].vue` | `freight.pages.journals` | `finance.accounting.view` |
| `/finance/journals` | `app/pages/finance/journals/index.vue` | `freight.pages.journals` | `finance.accounting.view` |
| `/finance/posting-rules/:id` | `app/pages/finance/posting-rules/[id].vue` | `freight.pages.postingRules` | `finance.posting_rules.view` |
| `/finance/posting-rules` | `app/pages/finance/posting-rules/index.vue` | `freight.pages.postingRules` | `finance.posting_rules.view` |
| `/finance/posting-rules/new` | `app/pages/finance/posting-rules/new.vue` | `freight.pages.postingRules` | `finance.posting_rules.view` |
| `/` | `app/pages/index.vue` | `freight.pages.dashboard` | `dashboard.view` |
| `/master-data/business-parties/:id` | `app/pages/master-data/business-parties/[id].vue` | `freight.pages.businessParties` | `master.reference.view` |
| `/master-data/business-parties` | `app/pages/master-data/business-parties/index.vue` | `freight.pages.businessParties` | `master.reference.view` |
| `/master-data/business-parties/new` | `app/pages/master-data/business-parties/new.vue` | `freight.pages.businessParties` | `master.reference.view` |
| `/master-data/container-types/:id` | `app/pages/master-data/container-types/[id].vue` | `freight.pages.containerTypes` | `master.reference.view` |
| `/master-data/container-types` | `app/pages/master-data/container-types/index.vue` | `freight.pages.containerTypes` | `master.reference.view` |
| `/master-data/container-types/new` | `app/pages/master-data/container-types/new.vue` | `freight.pages.containerTypes` | `master.reference.view` |
| `/master-data/currencies/:id` | `app/pages/master-data/currencies/[id].vue` | `freight.pages.currencies` | `master.reference.view` |
| `/master-data/currencies` | `app/pages/master-data/currencies/index.vue` | `freight.pages.currencies` | `master.reference.view` |
| `/master-data/currencies/new` | `app/pages/master-data/currencies/new.vue` | `freight.pages.currencies` | `master.reference.view` |
| `/master-data/fee-types/:id` | `app/pages/master-data/fee-types/[id].vue` | `freight.pages.feeTypes` | `master.reference.view` |
| `/master-data/fee-types` | `app/pages/master-data/fee-types/index.vue` | `freight.pages.feeTypes` | `master.reference.view` |
| `/master-data/fee-types/new` | `app/pages/master-data/fee-types/new.vue` | `freight.pages.feeTypes` | `master.reference.view` |
| `/master-data/party-roles/:id` | `app/pages/master-data/party-roles/[id].vue` | `freight.pages.partyRoles` | `master.party_roles.view` |
| `/master-data/party-roles` | `app/pages/master-data/party-roles/index.vue` | `freight.pages.partyRoles` | `master.party_roles.view` |
| `/master-data/party-roles/new` | `app/pages/master-data/party-roles/new.vue` | `freight.pages.partyRoles` | `master.party_roles.view` |
| `/master-data/place-roles/:id` | `app/pages/master-data/place-roles/[id].vue` | `freight.pages.placeRoles` | `master.reference.view` |
| `/master-data/place-roles` | `app/pages/master-data/place-roles/index.vue` | `freight.pages.placeRoles` | `master.reference.view` |
| `/master-data/place-roles/new` | `app/pages/master-data/place-roles/new.vue` | `freight.pages.placeRoles` | `master.reference.view` |
| `/master-data/trade-directions/:id` | `app/pages/master-data/trade-directions/[id].vue` | `freight.pages.tradeDirections` | `master.reference.view` |
| `/master-data/trade-directions` | `app/pages/master-data/trade-directions/index.vue` | `freight.pages.tradeDirections` | `master.reference.view` |
| `/master-data/trade-directions/new` | `app/pages/master-data/trade-directions/new.vue` | `freight.pages.tradeDirections` | `master.reference.view` |
| `/master-data/transport-assets/:id` | `app/pages/master-data/transport-assets/[id].vue` | `freight.pages.transportAssets` | `master.reference.view` |
| `/master-data/transport-assets` | `app/pages/master-data/transport-assets/index.vue` | `freight.pages.transportAssets` | `master.reference.view` |
| `/master-data/transport-assets/new` | `app/pages/master-data/transport-assets/new.vue` | `freight.pages.transportAssets` | `master.reference.view` |
| `/master-data/transport-types/:id` | `app/pages/master-data/transport-types/[id].vue` | `freight.pages.transportTypes` | `master.reference.view` |
| `/master-data/transport-types` | `app/pages/master-data/transport-types/index.vue` | `freight.pages.transportTypes` | `master.reference.view` |
| `/master-data/transport-types/new` | `app/pages/master-data/transport-types/new.vue` | `freight.pages.transportTypes` | `master.reference.view` |
| `/print/:collection/:id` | `app/pages/print/[collection]/[id].vue` | `freight.print.previewTitle` | public |
| `/quotations/:id` | `app/pages/quotations/[id].vue` | `freight.pages.quotations` | `sales.quotations.view` |
| `/quotations` | `app/pages/quotations/index.vue` | `freight.pages.quotations` | `sales.quotations.view` |
| `/quotations/new` | `app/pages/quotations/new.vue` | `freight.pages.quotations` | `sales.quotations.view` |
| `/reports/:area/:slug` | `app/pages/reports/[area]/[slug].vue` | `freight.nav.reports` | public |
| `/reports/:slug` | `app/pages/reports/[slug].vue` | `freight.nav.reports` | public |
| `/reports` | `app/pages/reports/index.vue` | `freight.nav.reports` | public |
| `/service-charges/:id` | `app/pages/service-charges/[id].vue` | `freight.pages.serviceCharges` | `finance.service_charges.view` |
| `/service-charges` | `app/pages/service-charges/index.vue` | `freight.pages.serviceCharges` | `finance.service_charges.view` |
| `/service-charges/new` | `app/pages/service-charges/new.vue` | `freight.pages.serviceCharges` | `finance.service_charges.view` |
| `/service-orders/:id` | `app/pages/service-orders/[id].vue` | `freight.pages.serviceOrders` | `operations.service_orders.view` |
| `/service-orders` | `app/pages/service-orders/index.vue` | `freight.pages.serviceOrders` | `operations.service_orders.view` |
| `/service-orders/new` | `app/pages/service-orders/new.vue` | `freight.pages.serviceOrders` | `operations.service_orders.view` |

## 4. Metadata-Driven Pages

Most list/detail screens reuse two generic views:

- `FreightWorkspaceView` (`components/freight/WorkspaceView.vue`) for reference
  collections, with search, filters, sortable columns, pagination, and row
  actions.
- `FreightModulePage` (`components/freight/ModulePage.vue` ->
  `DocumentView.vue`) for document modules, driven by
  `app/config/freight-modules.ts`.

`app/config/lcs-reference-modules.ts` describes each reference collection:
columns, form fields, filters, title field, icon, group, permission, and whether
create is allowed. `app/utils/freight/page-access.ts` derives the visible menu
and page ids from the same catalogue. Adding a reference collection means adding
one spec and one page trio; it does not mean hand-writing a table and form.

Tables use `AppListTable` / `DynamicDataTable`, with:

- server-side pagination (`page`, `page_size`) and total count;
- debounced search and filter values translated by `app/utils/filter/`;
- sort by a whitelisted column and direction;
- a status badge column and a row “…” menu;
- permission-filtered actions, confirmation for destructive actions, and a
  success toast only after the API confirms.

The Business Parties form loads active Party Roles from the database and stores a
`roleIds` array. Party Roles themselves are a standard reference collection:

- Role Code is required and unique; Role Name is required and unique.
- Description is optional. Active is on by default; status is changed from the row
  menu, not the form.
- A role assigned to a party cannot be deleted. The API returns
  `PARTY_ROLE_IN_USE`; deactivation remains available.
- Renaming a role changes every party display because the join table stores the
  role id, not a copied label.
- The selector offers active roles for new assignments; inactive roles remain
  readable on existing parties.

Quotation pricing lines take their **By** options from Master Data → Transport
Types. The select offers active types keyed by id, so renaming a type updates the
label without rewriting quotation history. An inactive type, or a legacy line
that stored the type name, stays readable on the quotation but is not offered for
new lines.

## 5. Dynamic Service-Order Tabs and Versioning

Service-order tabs are database-configured. `useComponentTabs` and
`AppComponentTabs.vue` render the tabs allowed by the order’s trade direction and
the published configuration version the order was captured under.

- Configuration is edited in `/configuration/{component-tabs,component-groups,component-attributes}`.
- A published version is a snapshot. Orders keep their captured version, so a
  later configuration change does not rewrite historical orders.
- `configuration-versions` supports publish, activate, compare, preview,
  rollback, retire, and activation history.
- Attributes carry type, required/repeatable flags, reference source, display
  order, validation rules, and trade-direction filtering.
- The dynamic field renderer supports text, number, decimal, date, select,
  multi-select, boolean, textarea, reference, and repeatable table rows.

## 6. Record Status

Status is never an editable form field. A create seeds the module default
(`defaultStatusForModule` / `emptyFreightRecord`); `moduleDocumentTabs` strips
status from every compiled form.

- The list keeps the status column and badge.
- Every change is offered from the row or record “…” menu under **Change
  Status**. `useRecordStatus()` fetches the backend policy and renders only the
  transitions that are legal from the current status and permitted for the
  caller.
- Plain activate/deactivate transitions use
  `POST /{collection}/{item_id}/status`. Workflow transitions use the endpoint
  that owns them (`utils/freight/status-commands.ts`), so posting, reversal,
  issuing a charge, closing a period, and the quotation workflow stay inside
  their engines.
- A refusal (closed period, invalid transition, missing permission) is a
  persistent page/form message, never a toast. Only a confirmed change toasts.

## 7. Form Validation and Error Presentation

One shared pipeline covers every form; no page implements its own.

- `app/utils/validation/` holds the framework-free rules:
  `field-rules.ts` (rules -> `{ code, params }`), `record-validation.ts`
  (document fields, repeatable rows, flat drafts), `component-rules.ts`
  (database-driven Service Order attributes, including admin-managed
  `validationRules`), `error-paths.ts` (canonical camelCase paths and
  `table.<row>.<column>`), `api-error.ts` (FastAPI envelope, raw Pydantic
  `detail`, and `LcsDomainError`), `messages.ts` (`validation.*` copy), and
  `focus.ts` (first-invalid navigation).
- `useFormValidation()` owns the three error buckets - field, row cell, form -
  plus submission state, clearing, and the reveal/focus contract. A form supplies
  its field order, label resolver, and a way to open the section that owns a key.
- Every addressable input carries `data-field-key` with its canonical model path.
  `focus.ts` uses it to scroll and focus the first invalid control after asking
  the host to reveal the owning tab, section, accordion, or dynamic group.
- `UFormField :error` supplies `aria-invalid` and `aria-describedby` and renders
  the message under the control. That is the only place a field error appears.
  `CommonAppFormErrorSummary` renders only messages that belong to no field.
- Notification policy: validation errors and business refusals are never toasts.
  A toast is used only for confirmed success. `useApi` suppresses its own toast
  for 400/409/422.
- Rules cover length, pattern, email/phone/URL, integer, non-negative, strictly
  positive, decimal precision per column scale, dates, closed option sets,
  password policy, cross-field date order, and admin-managed
  `validationRules`. Validation runs on blur and again on submit; editing a field
  clears only its own message.
- Frontend validation is a convenience. The API validates every write again in
  `backend/app/core/validation.py` and the module schemas; an API client cannot
  bypass it.

## 8. Data Access and State

- Pinia stores: `auth` (session, user, permission checks), `freight` (module
  cache and remote persistence), and `preferences` (theme, locale, font size).
- Repositories under `app/repositories/` (`contracts/` + `http/` + `index.ts`
  factories) are the only HTTP layer. Endpoints are registered in
  `app/utils/constants/api-v1-endpoints.ts`,
  `app/utils/constants/api-endpoints.ts`, and
  `app/utils/api/freight-remote.ts` (`REMOTE_ENDPOINTS`).
- `useApi()` is the central fetch client: auth header/cookies, CSRF header,
  query compaction, 401 refresh-and-retry, error normalisation, and success
  toasts. It does not toast validation or business refusals.
- `useReferenceOptions()` loads dynamic options (Party Roles, Place Roles, trade
  directions, fee types, currencies, and other references) and caches them by
  collection and status filter. It never hardcodes a role option array.
- The frontend never computes financial balances. Report screens render backend
  `/reports/*` data through `ReportsRepository`.

## 9. Shared Components

| Folder | Main components |
|---|---|
| `components/common/` | `AppConfirmDialog`, `AppDateRangeFilter`, `AppExportDialog`, `AppFilterSelect`, `AppFormErrorSummary`, `AppReferenceSelect`, `AppRolePermissionMatrix`, `AppSecretInput`, `AppSortableList` |
| `components/document/` | `AppDocumentForm`, `AppDocumentPage`, `AppDocumentTabBar`, `AppDynamicFieldRenderer`, `AppDynamicTableField`, `AppFieldGrid` |
| `components/freight/` | `WorkspaceView`, `ModulePage`, `DocumentView`, `DynamicDataTable`, `JobDetail`, `JobOverview`, `JobRoute`, `JobContainers`, `JobCharges`, `JobFiles`, `JobFinance`, `ReportsView` |
| `components/table/` | `AppListTable`, `AppRelatedRecords`, `AppSaveGrid`, `AppTableRowMeta` |
| `components/print/` | `DocumentPreview`, `TaxInvoiceLayout`, `DebitNoteLayout`, `LinesTable`, `TotalsBlock`, `SignatureBlock` |
| `components/layout/` | `AppHeader`, `AppHeaderPageActions`, `AppSlidebar`, `AppUserProfileDialog`, `AppAboutDialog` |
| `components/dashboard/` | `AppSummaryCard`, `AppChartGrid` |

## 10. Internationalisation, Formatting, and Print

- Locale bundles live in `i18n/locales/{en,km,zh}.json` and must stay
  structurally identical. `pnpm i18n:check` and
  `tests/i18n-locales.spec.ts` enforce parity.
- Labels for copy shipped in code resolve through
  `useFreightLabel().fieldLabel()`:
  `labelKey` -> `freight.modules.<collection>.fields.<key>` ->
  `freight.fields.<key>` -> English `label`. Do not add per-language parallel
  fields (`labelKm`) for code-owned copy.
- `labelKm` remains only for admin-managed data (user-defined attributes and
  dynamic-table columns), resolved per locale through `STORED_LABEL_FIELDS`.
- Add a language in one place (`app/utils/constants/app-languages.ts`) and mirror
  it in `nuxt.config.ts`, the font family map, `html[lang]` CSS, and the backend
  `SUPPORTED_LANGUAGES` / `_LANGUAGE_LOCALES`.
- Print output is deliberately bilingual English + Khmer for the Cambodian tax
  invoice, independent of the UI locale, through
  `composables/print/usePrintBilingual.ts`.
- Dates, numbers, and money use the shared formatters in
  `app/utils/format/`; money is never formatted through a binary float.

## 11. Accessibility and Responsive Behaviour

- Every input has a label or an accessible name; `UFormField` associates the
  error and help text.
- Errors are announced on the field and focus moves to the first invalid input
  after submit.
- Icon-only actions have an accessible label and a tooltip.
- Tables keep a header row, sortable controls are buttons, and row actions are
  reachable by keyboard.
- Dialogs use the shared confirm host and trap focus.
- The layout collapses the sidebar on narrow screens; document tabs scroll
  horizontally rather than clipping; print routes are not constrained by the app
  shell.
- Status and other meaning is never conveyed by colour alone; badges include
  text.

## 12. Frontend Tests and Known Gaps

Frontend tests are plain Vitest (`environment: node`, alias `~ -> app`); only
`tests/**/*.spec.ts` run and there is no browser suite. They cover validation
rules, notification policy, i18n parity, reference options, form metadata,
formatting, page access, permissions, and contract constants. The full strategy
and commands are in `docs/10_testing_and_quality.md`.

Known gaps:

- No Playwright/Cypress browser suite; drag-and-drop, focus order, and responsive
  layout are verified manually.
- Some screens are metadata-driven and have no page-specific component test.
- Report rendering is checked at the repository/format layer, not pixel by pixel.
