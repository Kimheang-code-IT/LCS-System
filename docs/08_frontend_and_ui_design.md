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
  point, and the content area. Every header action button — Save, New/Create and
  the document workflow buttons (Submit, Send, Accept…) — renders through the
  shared `CommonAppDocumentActionButton`, so one style rule
  (`utils/layout/document-action-button.ts`) governs every page.
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
| `/master-data/document-types/:id` | `app/pages/master-data/document-types/[id].vue` | `freight.pages.documentTypes` | `master.reference.view` |
| `/master-data/document-types` | `app/pages/master-data/document-types/index.vue` | `freight.pages.documentTypes` | `master.reference.view` |
| `/master-data/document-types/new` | `app/pages/master-data/document-types/new.vue` | `freight.pages.documentTypes` | `master.reference.view` |
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

The Quotation list is a `WorkspaceView` over nine business columns: Quotation
No., SO No., Business Party, Revision (`R01`), Trade Direction, Grand Total,
Status, Created By and Created At. The Quotation number opens the document, the
SO number opens the linked order, and both the company-name column and the filter
are labelled **Business Party** while the printed company name stays a separate
field. Created By is the author of the first revision, so a later editor never
takes over attribution.

The Service Order list shows SO No., Quotation No., Business Party, Trade
Direction, Containers, Total Charges, Status, Created By and Created At. The SO
number stays the `jobNo` data key and opens the service-order detail page; the
Quotation column is the source quotation number and id returned read-only by the
list API, so both numbers are clickable next to each other.

The Service Charge and Financial Document lists end with Created By then Created
At. All four lists resolve creator names in one batched query per page; a missing
user row shows `—` rather than a fabricated name.

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

Quotations use five tabs on the existing document page: Overview, Route, Pricing,
Files and Revisions. No separate quotation page was added.

- **Overview** distinguishes the linked **Business Party** from the printable
  **Company name**. Business Party, Trade Direction and Quotation Date are
  required; Valid Until may not precede the Quotation Date. Currency and Trade
  Direction options come from active Master Data.
- **Route** is the shared route-stop table: Place Role from the active Place Roles
  master, a required free-text location, planned date/time, Notes, add/remove and
  move buttons. The server renumbers the submitted order and persists planned
  dates.
- **Pricing** renames the former **By** column to **Charge Basis** (active
  Transport Types keyed by id). Fee Type comes from the Fee Types master, the
  Container Type is optional, and Quantity must be greater than zero. Line and
  grand totals are recalculated on both sides; the backend is authoritative and
  rounds each amount half-up to two decimals before saving. A line's discount
  amount and tax rate live in **Additional Details** in the row menu, not as
  permanent columns.
- **Files** uploads through the attachment API (size and configured extension
  allow-list checked in the browser, content checked again on the server), shows
  an upload state and page-level errors, and stores the returned file row on the
  quotation. The **Note** column is edited directly in its cell (up to 1000
  characters) and saved on leave through the attachment API. Removing a row
  detaches it from the quotation; the stored object is
  deleted only when the user has `attachment.delete`. Downloads use the stored
  URL/storage key and the server's `attachment.read` guard.
- **Revisions** lists revision number (`R01`, `R02`), status, grand total,
  creator and creation time, newest first, with a row actions menu for **View**
  and no add-row control. Editing a
  sent/accepted revision clones it instead of overwriting; the dirty marker
  blocks Send/Accept until Save, and Create Revision is offered only for a
  persisted quotation.

A **service order** offers **Create re-quotation** in its header for anyone with
`quotation.revise`. It confirms, creates a new draft quotation from the order's
customer, direction, route, containers and priced lines, then navigates to that
quotation. The order is left untouched, and the button is hidden on an unsaved
order; the endpoint refuses the call without the permission regardless.

## 5. Dynamic Service-Order Tabs and Versioning

Service-order tabs are database-configured. `useComponentTabs` and
`AppComponentTabs.vue` render the tabs allowed by the order’s trade direction and
the published configuration version the order was captured under.

- Configuration is edited in `/configuration/{component-tabs,component-groups,component-attributes}`.
- The Component Attributes screen is still one inline-editable grid. Its columns are
  reorder, `code`, `label`, `dataType`, `choices`, `master data`, `rules`, required
  and help text. `code` is the stable key and is unique; `choices` holds static
  select options (`A, B` or `Label|VALUE`); `master data` names the database source
  for a `reference`; `rules` holds `min`, `max`, `minLength`, `maxLength`,
  `pattern` and the `email`/`url`/`integer`/`nonNegative`/`positive` flags as
  `key=value` pairs. A new row keeps its typed values when validation fails.
- Row move buttons persist catalog order through
  `POST /component-attributes/reorder`; group membership order remains separate.
- A published version is a snapshot. Orders keep their captured version, so a
  later configuration change does not rewrite historical orders.
- `configuration-versions` supports publish, activate, compare, preview,
  rollback, retire, and activation history.
- Attributes carry type, required/repeatable flags, reference source, display
  order, validation rules, and trade-direction filtering.
- The dynamic field renderer supports text, number, integer, decimal, date,
  select, multi-select, boolean, textarea, reference, and repeatable table rows.

## 6. Record Status

Status is never an editable form field. A create seeds the module default
(`defaultStatusForModule` / `emptyFreightRecord`); `moduleDocumentTabs` strips
status from every compiled form.

- The list keeps the status column and badge.
- Every change is offered from the row or record “…” menu under **Change
  Status**. `useRecordStatus()` fetches the backend policy and renders only the
  transitions that are legal from the current status and permitted for the
  caller.
- The policy is requested only where a lifecycle can exist:
  `supportsStatusPolicy()` skips read-only collections (Audit Logs, Archive,
  Reports, AR/AP views) and any module without a `status` value. A `404` from
  `/{collection}/status-policy` means "no lifecycle" and is an expected answer,
  never a user-visible error.
- Identifier columns (for example the Audit Logs **Record** field) render as
  integer labels; only amount/price keys go through the money formatter.
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
- Password policy is one shared rule: `validatePasswordStrength` (mirroring
  `validate_password_strength`) plus `passwordRequirements`. Every new-password
  form (`/auth/setup`, `/auth/change-password`, `/auth/reset-password`, the profile
  dialog, the administrator password dialog and the create-user form) renders
  `CommonAppPasswordRequirements` under the input and disables submission until all
  five requirements pass and the confirmation matches. The login form does not
  apply it.
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
  query compaction, eligible expired-token refresh-and-retry, error normalisation, and success
  toasts. It does not toast validation or business refusals.
- The auth store owns one generation-guarded renewal promise. Route middleware
  awaits restoration before deciding on a login redirect. Timers use server
  expiration metadata (up to 90 seconds early, scaled for short tokens), run
  only for a visible recently active tab, and recover on focus/interaction.
  Web Locks serialize refresh/logout across tabs; BroadcastChannel and a
  storage event carry only non-secret renewal/logout metadata. A waiting tab
  verifies identity through shared HttpOnly cookies instead of rotating again.
  Cross-account changes lock the original draft until its account signs in.
- Access tokens returned in bearer mode live only in memory; old browser-stored
  credentials are removed. The production cookie mode keeps both credentials
  HttpOnly. Refresh tokens never enter JavaScript state. No financial draft is
  persisted for renewal. JSON requests retry once; uploads, binary bodies and
  streams require explicit resubmission. Temporary renewal failures preserve
  state with two bounded retries and a persistent retry message. Genuine
  expiry locks protected actions and shows a sign-in link in a new tab,
  preserving the current form. Sign-in to the same account restores access
  without automatic submission. Logout invalidates pending responses, waits
  for its in-flight cookie response, revokes the server session, and clears
  frontend state only after server confirmation (or an already-invalid 401).
- `useReferenceOptions()` loads dynamic options (Party Roles, Place Roles, trade
  directions, fee types, currencies, and other references) and caches them by
  collection and status filter. It never hardcodes a role option array.
- `useRolePermissionCatalog()` loads `/api/v1/permissions/catalog` once and
  feeds the role matrix: pages, actions, groups and label keys come from the
  backend, so a page added server-side appears without a frontend release. The
  built-in page list is only the fallback while the request is in flight. The
  matrix sends page codes and the server compiles them into API capabilities —
  the frontend holds no permission implication table.
- The users form assigns **roles** with a multi-select (`roles` list); the role
  form assigns **parentRoles** (inheritance) and shows the permissions inherited
  from them read-only.
- The frontend never computes financial balances. Report screens render backend
  `/reports/*` data through `ReportsRepository`.

### Report pages generate on demand

Opening `/reports/:area/:slug` loads no report rows. `ReportsView.vue` shows the
title, the filter controls and an empty state; only **Generate** (header action,
empty-state action, or the header Refresh control) requests data. This follows
the ERPNext report pattern and keeps a large ledger off the page-load path.

- `Trial Balance` and `General Ledger` post their filters to
  `/reports/trial-balance/generate` and `/reports/general-ledger/generate`
  through `reportGenerateBody()` (`app/utils/freight/report-request.ts`), which
  is a pure, unit-tested function. Both are server-paginated: the table's page
  controls request the page the user asked for and `meta.total` drives the
  pager.
- Every other catalogued report requests its existing endpoint only after
  Generate; operational registers still derive their rows from the freight store.
- States are explicit: idle empty state, loading, generated empty state, success,
  and an error alert carrying the backend `message`. Changing any filter marks
  the current result **stale** instead of silently showing it as current;
  regenerating clears the marker. Repeated Generate clicks are ignored while a
  request is in flight.
- Trial Balance shows period debit/credit and closing debit/credit totals above
  the table, plus an error badge when the backend reports an imbalance.
- **Export** for these two reports asks the backend for the whole filtered
  result (`POST /reports/<key>/export`) and saves the streamed CSV, so an export
  is never limited to the visible page. The export dialog's column selection is
  sent as `fields`; the format is CSV, even though the shared dialog also lists
  Excel. Every other report still exports the rows already on screen.
- Filters are remembered per report for the session (going to another report and
  back keeps the period), results are not.
- The `labelKm` rule, the shared validation pipeline and the notification policy
  are untouched: filter input stays inline, a refusal is shown in an alert, and
  only confirmed success raises a toast.

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

### Editable grids must not re-create a focused control

`AppLineTable` is the single renderer for every editable grid (document line
tables, dynamic component tables, `AppSaveGrid`). Its column definitions carry
the cell renderers, and TanStack mounts a cell renderer as a functional
component — so a *new* renderer replaces the cell's DOM, and the input the user
is typing in loses focus and caret after one character.

The document form recompiles its tab tree from the record
(`moduleDocumentTabs(..., { record: model.value })`) and `lineTableField` spreads
a fresh table object on each pass, so a host hands over a new-but-equal
descriptor on every keystroke. `AppLineTable` therefore memoises its column
array on the descriptor's **shape** (`tableColumnSignature`,
`app/utils/table/table-shape.ts`) plus the props that affect the column set, and
returns the identical array while the shape holds. Inputs are patched in place
instead of being re-created.

Rules that follow from it:

- Never render a control behind a value-dependent `v-if` or a value-derived
  `:key`; tabs use `v-show` so a hidden panel keeps its inputs.
- A repeatable row's identity is its array position (`get-row-id` is
  `_rowIndex`), never a generated or value-derived id.
- `e2e/form-typing.spec.ts` locks this in: it types character by character and
  asserts the same DOM element stays focused.


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
- Service-charge printing reuses `buildChargePrintViewModel`. Each fee line has
  **Print Invoice** in its row menu (`?line`/`?lineId`, the id wins) and the
  table header has **Print All**; on the Service Order's Service Charge tab that
  header button prints every charge of the order as one read-only statement
  (`?statementOrder`), fetching the charges through the read API. A draft charge
  keeps its watermark and is never presented as an issued customer invoice.
  Printing never issues, posts or creates a document.
- Dates, numbers, and money use the shared formatters in
  `app/utils/format/`; money is never formatted through a binary float.

### Excel Import & Export actions (`app/components/excel/ImportExportDialog.vue`)

Eligible list pages (the backend catalog `GET /api/v1/excel/modules` is the single
source of support) offer **Export** and **Import** as items in the page-header
**⋯** menu — not as buttons above the table. The header keeps its primary
**New/Create** button for the modules that allow creating a record. Export needs
the module's view permission; import validate/commit need its manage permission
and are refused (`403`) otherwise.
A view-only caller therefore sees Export only. Export sends the selected rows,
or every filtered row when nothing is selected — never just the current table
page. Choosing Import opens the shared dialog, which drives the workflow:
download template → pick mode (Create Only default) → upload `.xlsx` → backend
validate & preview (read-only table: Excel row no., identifier, action, status,
error details, with summary counts) → confirm (single-use server session;
commit-time revalidation, atomic all-or-nothing) → result with a downloadable
XLSX error report and the five most recent imports for that module.
Import/Export items are **hidden** for modules the catalog does not list;
validation errors render in the dialog, never as toasts.

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

Frontend unit tests are plain Vitest (`environment: node`, alias `~ -> app`); only
`tests/**/*.spec.ts` run. They cover validation rules, notification policy, i18n parity,
reference options, form metadata, formatting, page access, permissions, and contract
constants. A separate Playwright Test suite lives in `e2e/` and runs with `pnpm test:e2e`
against the compose stack (`frontend/playwright.config.ts`). The full strategy and
commands are in `docs/10_testing_and_quality.md`.

Known gaps:

- The Playwright suite is read-only and covers startup, the anonymous auth guard and login
  validation; authenticated CRUD journeys are skipped without `E2E_USERNAME`/`E2E_PASSWORD`.
  Drag-and-drop, focus order, and responsive layout are still verified manually.
- Some screens are metadata-driven and have no page-specific component test.
- Report rendering is checked at the repository/format layer, not pixel by pixel.
