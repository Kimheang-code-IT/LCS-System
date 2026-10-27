# Roles and Permissions

## 1. Interpretation

A permission answers **what may the user do?** The platform is single-tenant:
organizations and branches were removed, so there is no organization/branch scope.
Access is granted through roles; each role is a set of permission codes, and every
user has exactly one active role. Replaced assignments are retained as expired
history but do not grant permissions.

This document covers **RBAC user roles** (Administrator, Finance Officer, ...).
They are unrelated to the administrator-managed **Party Roles** master data
(Customer, Supplier, Carrier, ...) assigned to business parties; that is business
vocabulary, not an authorization role.

Every permission code is `module.action`, defined in code in
`backend/app/core/permissions.py` and synced into the `permissions` table on
startup (`ensure_permission_catalog`). The frontend mirrors the same catalog
(`frontend/app/utils/role/permissions.ts`)
and checks it through `useAuthStore().canAccessPage(pageId)`.

The catalog is composed of three groups:

1. **Source (API) permissions** — enforced by `require_permission(...)` on the
   backend routers.
2. **Page/configuration permissions** — legacy page-navigation keys.
3. **Matrix page permissions** — the action set shown on the Roles & Permissions
   screen; each page grant also implies the matching source/API permissions via
   `PAGE_PERMISSION_SOURCE_CODES`.

## 2. Permission Catalog

### 2.1 Source (API) permissions

These gate API endpoints. Every code below is enforced server-side.

| Permission | Resource | Action |
|---|---|---|
| user.read | user | read |
| user.manage | user | manage |
| role.read | role | read |
| role.manage | role | manage |
| quotation.read | quotation | read |
| quotation.create | quotation | create |
| quotation.update_draft | quotation | update_draft |
| quotation.send | quotation | send |
| quotation.accept | quotation | accept |
| quotation.convert | quotation | convert |
| service_order.read | service_order | read |
| service_order.create | service_order | create |
| service_order.update | service_order | update |
| service_order.complete | service_order | complete |
| service_order_config.view | service_order_config | view |
| service_order_config.create | service_order_config | create |
| service_order_config.update | service_order_config | update |
| service_order_config.delete | service_order_config | delete |
| service_order_config.publish | service_order_config | publish |
| configuration.read | configuration | read |
| configuration.publish | configuration | publish |
| configuration.activate | configuration | activate |
| configuration.rollback | configuration | rollback |
| configuration.compare | configuration | compare |
| service_charge.read | service_charge | read |
| service_charge.create | service_charge | create |
| service_charge.issue | service_charge | issue |
| service_charge.convert_to_invoice | service_charge | convert_to_invoice |
| financial_document.read | financial_document | read |
| financial_document.create | financial_document | create |
| financial_document.update_draft | financial_document | update_draft |
| financial_document.post | financial_document | post |
| financial_document.reverse | financial_document | reverse |
| financial_document.allocate | financial_document | allocate |
| journal_entry.read | journal_entry | read |
| journal_entry.create | journal_entry | create |
| journal_entry.post | journal_entry | post |
| accounting_period.read | accounting_period | read |
| accounting_period.close | accounting_period | close |
| chart_of_accounts.manage | chart_of_accounts | manage |
| posting_rule.read | posting_rule | read |
| posting_rule.manage | posting_rule | manage |
| customs_credential.retrieve | customs_credential | retrieve |
| attachment.read | attachment | read |
| attachment.upload | attachment | upload / edit note |
| attachment.delete | attachment | delete |
| audit_log.read | audit_log | read |
| archive.view | archive | view |
| archive.restore | archive | restore |
| archive.hard_delete | archive | hard_delete |
| report.read | report | read |

The shared record-status endpoint (`POST /api/v1/{collection}/{item_id}/status`)
introduces **no new codes**: each transition in
`backend/app/modules/master_data/status_policy.py` requires the permission that already owns
that area — `master.reference.manage` for reference data, `chart_of_accounts.manage`
for the ledger accounts, `posting_rule.manage`, `configuration.manage` for the
sequences, `accounting_period.close` for closing/reopening, `service_order.update`
for the order lifecycle, `user.manage` / `role.manage` — and the policy endpoint
returns only the transitions the caller may perform.

The shared Excel Import & Export endpoints follow the same rule: template download
and export need the module's view permission, while import validate/preview/commit
and the error report need the module's manage permission (`master.reference.view` /
`master.reference.manage` for the Master Data lists). Import history is readable by
holders of the module's view permission. No import is authorized by view alone.

### 2.2 Page and configuration permissions

| Permission | Resource | Action |
|---|---|---|
| master.reference.view | master_data | view |
| master.reference.manage | master_data | manage |
| configuration.manage | configuration | manage |
| configuration.configure | configuration | configure |
| admin.user_manage | admin | user_manage |
| admin.role_manage | admin | role_manage |
| settings.manage | settings | manage |
| backup.read | backup | read |
| backup.manage | backup | manage |
| finance.view | finance | view |
| report.export | report | export |

### 2.3 Matrix page permissions (Roles & Permissions screen)

These are the action codes stored by the role matrix. The page-level
`view/create/edit/delete/export` actions map to API permissions through
`PAGE_PERMISSION_SOURCE_CODES`.

| Page group | Permission codes |
|---|---|
| Dashboard | `dashboard.view`, `dashboard.export`, `dashboard.summary` |
| Quotations | `sales.quotations.view`, `sales.quotations.create`, `sales.quotations.update`, `sales.quotations.delete`, `sales.quotations.submit`, `sales.quotations.re_quotation`, `sales.quotations.quotation`, `sales.quotations.export` |
| Service orders | `operations.service_orders.view`, `operations.service_orders.create`, `operations.service_orders.update`, `operations.service_orders.delete`, `operations.service_orders.submit`, `operations.service_orders.export` |
| Service-order reports | `reports.service_order_register.*`, `reports.service_order_status.*`, `reports.service_order_containers.*`, `reports.service_order_profitability.*` (`view`, `export`) |
| Service charges | `finance.service_charges.view`, `finance.service_charges.create`, `finance.service_charges.update`, `finance.service_charges.delete`, `finance.service_charges.submit`, `finance.service_charges.export` |
| Financial documents | `finance.financial_documents.view`, `finance.financial_documents.create`, `finance.financial_documents.update`, `finance.financial_documents.delete`, `finance.financial_documents.submit`, `finance.financial_documents.export` |
| Chart of accounts | `finance.chart_of_accounts.view`, `.create`, `.update`, `.delete`, `.export` |
| Financial accounts | `finance.financial_accounts.view`, `.create`, `.update`, `.delete`, `.export` |
| Journal entries | `finance.journal_entries.view`, `.create`, `.update`, `.delete`, `.export` |
| Accounting periods | `finance.accounting_periods.view`, `.update`, `.export` |
| Posting rules | `finance.posting_rules.view`, `.create`, `.update`, `.delete`, `.export` |
| Financial reports | `reports.revenue_expense.*`, `reports.accounts_receivable.*`, `reports.accounts_payable.*`, `reports.general_ledger.*`, `reports.trial_balance.*`, `reports.profit_loss.*`, `reports.balance_sheet.*`, `reports.cash_flow.*` (`view`, `export`) |
| Master data | `master.business_parties.*`, `master.place_roles.*`, `master.party_roles.*`, `master.trade_directions.*`, `master.container_types.*`, `master.transport_types.*`, `master.transport_assets.*`, `master.fee_types.*`, `master.currencies.*` (`view`, `create`, `update`, `delete`, `export`) |
| Configuration | `configuration.view`, `.create`, `.update`, `.delete`, `.export` |
| Users | `admin.users.view`, `.create`, `.update`, `.delete`, `.export` |
| Roles | `admin.roles.view`, `.create`, `.update`, `.delete`, `.export` |
| Document sequences | `admin.document_sequences.view`, `.create`, `.update`, `.delete`, `.export` |
| Audit logs | `admin.audit_logs.view`, `admin.audit_logs.export` |
| Archive | `admin.archive.view`, `admin.archive.export`, `admin.archive.restore` |
| App config | `settings.app_config.view`, `settings.app_config.update` |
| Backup | `settings.backup.view`, `settings.backup.create`, `settings.backup.update` |

The redacted `GET /settings/app-config` is readable by any authenticated user so
the UI can load localization; the Settings page and every app-config write,
connection-test, and reset endpoint still require the codes above.

Older releases wrote `.edit` codes (`sales.quotations.edit`,
`operations.service_orders.edit`, `finance.service_charges.edit`,
`finance.financial_documents.edit`, `configuration.edit`,
`admin.users.edit`, `admin.roles.edit`, `admin.document_sequences.edit`,
`settings.app_config.edit`, `settings.backup.edit`) and the coarse
`finance.accounting.*`, `operations.reports.*`, `finance.reports.*`,
`master.reference.*`, and `admin.archive.edit/delete` codes. They remain in the
catalog and keep their documented behaviour for existing roles, but the matrix
no longer offers them to new roles.

These matrix codes are not only page checkboxes. The master-data router uses the
collection's matrix prefix for its API actions (`master.party_roles.view/create/
update/delete`, for example) and falls back to `master.reference.view` /
`master.reference.manage` for a role that predates the granular page. This keeps
existing roles working while new roles can be granted one collection without
granting every master-data screen.

### 2.4 Navigation page codes (aliases)

Some pages are served by another matrix row and therefore have no checkbox of
their own. Their navigation code travels with the row that serves them
(`NAVIGATION_PAGE_ALIASES`), so a role created in Roles & Permissions can open
them. Without this, the page stayed invisible to every non-administrator role.

| Pages | Navigation code | Granted with | API permission |
|---|---|---|---|
| Companies, Jobs, Shipments, Customs, Operations documents, Deliveries, Debit notes, Customer payments, Job charges, Supplier costs, Supplier payments | `sales.companies.view`, `operations.jobs.view`, `operations.shipments.view`, `operations.customs.view`, `operations.documents.view`, `operations.deliveries.view`, `finance.debit_notes.view`, `finance.customer_payments.view`, `finance.job_charges.view`, `finance.supplier_costs.view`, `finance.supplier_payments.view` | Master data (`master.reference.*`) | `master.reference.view` |
| Reports | `reports.view` | Any report grant (`report.read`) | `report.read` |
| Accounts receivable, Accounts payable, Job profitability | `finance.accounts_receivable.view`, `finance.accounts_payable.view`, `finance.job_profitability.view` | Any report grant (`report.read`) | `report.read` |

### 2.5 Page grant -> API permission mapping

Granting a page/action also enables the API source permissions shown below.
`-` means the page code has no additional source mapping. For master-data
collections the page code is itself checked by the collection router, so it
is still an API guard even when no extra source is listed.

| Page permission | Implied API source permissions |
|---|---|
| `admin.archive.delete` | `archive.view`, `archive.hard_delete` |
| `admin.archive.edit` | `archive.view`, `archive.restore` |
| `admin.archive.export` | `report.export` |
| `admin.archive.restore` | `archive.restore` |
| `admin.archive.view` | `archive.view` |
| `admin.audit_logs.export` | `report.export` |
| `admin.audit_logs.view` | `audit_log.read` |
| `admin.document_sequences.create` | `document_sequence.create` |
| `admin.document_sequences.delete` | `document_sequence.delete` |
| `admin.document_sequences.edit` | `document_sequence.update` |
| `admin.document_sequences.export` | `report.export` |
| `admin.document_sequences.update` | `document_sequence.update` |
| `admin.document_sequences.view` | `document_sequence.read` |
| `admin.roles.create` | `role.manage` |
| `admin.roles.delete` | `role.manage` |
| `admin.roles.edit` | `role.manage` |
| `admin.roles.export` | `report.export` |
| `admin.roles.update` | `role.manage` |
| `admin.roles.view` | `role.read` |
| `admin.users.create` | `user.manage` |
| `admin.users.delete` | `user.manage` |
| `admin.users.edit` | `user.manage` |
| `admin.users.export` | `report.export` |
| `admin.users.update` | `user.manage` |
| `admin.users.view` | `user.read` |
| `configuration.create` | `configuration.manage` |
| `configuration.delete` | `configuration.manage` |
| `configuration.edit` | `configuration.manage`, `configuration.configure`, `service_order_config.publish`, `configuration.publish`, `configuration.activate`, `configuration.rollback` |
| `configuration.export` | `report.export` |
| `configuration.update` | `configuration.manage`, `configuration.configure`, `service_order_config.publish`, `configuration.publish`, `configuration.activate`, `configuration.rollback` |
| `configuration.view` | `configuration.manage`, `service_order_config.view`, `configuration.read`, `configuration.compare` |
| `dashboard.export` | `report.export` |
| `dashboard.summary` | `dashboard.summary` |
| `dashboard.view` | - |
| `finance.accounting.create` | `journal_entry.create`, `chart_of_accounts.create`, `financial_account.create` |
| `finance.accounting.delete` | `journal_entry.create`, `journal_entry.delete`, `chart_of_accounts.delete`, `financial_account.delete` |
| `finance.accounting.edit` | `journal_entry.post`, `journal_entry.update`, `accounting_period.close`, `accounting_period.update`, `chart_of_accounts.manage`, `chart_of_accounts.create`, `chart_of_accounts.update`, `chart_of_accounts.delete`, `financial_account.create`, `financial_account.update`, `financial_account.delete` |
| `finance.accounting.export` | `report.export` |
| `finance.accounting.view` | `journal_entry.read`, `accounting_period.read`, `chart_of_accounts.read`, `financial_account.read` |
| `finance.accounting_periods.export` | `report.export` |
| `finance.accounting_periods.update` | `accounting_period.update`, `accounting_period.close` |
| `finance.accounting_periods.view` | `accounting_period.read` |
| `finance.accounts_payable.view` | `report.read` |
| `finance.accounts_receivable.view` | `report.read` |
| `finance.chart_of_accounts.create` | `chart_of_accounts.create` |
| `finance.chart_of_accounts.delete` | `chart_of_accounts.delete` |
| `finance.chart_of_accounts.export` | `report.export` |
| `finance.chart_of_accounts.update` | `chart_of_accounts.update` |
| `finance.chart_of_accounts.view` | `journal_entry.read`, `chart_of_accounts.read` |
| `finance.customer_payments.view` | `master.reference.view` |
| `finance.debit_notes.view` | `master.reference.view` |
| `finance.financial_accounts.create` | `financial_account.create` |
| `finance.financial_accounts.delete` | `financial_account.delete` |
| `finance.financial_accounts.export` | `report.export` |
| `finance.financial_accounts.update` | `financial_account.update` |
| `finance.financial_accounts.view` | `journal_entry.read`, `financial_account.read` |
| `finance.financial_documents.create` | `financial_document.create` |
| `finance.financial_documents.delete` | `financial_document.delete` |
| `finance.financial_documents.edit` | `financial_document.update_draft`, `financial_document.update`, `financial_document.delete`, `financial_document.post`, `financial_document.submit`, `financial_document.reverse`, `financial_document.allocate`, `attachment.upload`, `attachment.delete` |
| `finance.financial_documents.export` | `report.export` |
| `finance.financial_documents.submit` | `financial_document.submit` |
| `finance.financial_documents.update` | `financial_document.update`, `attachment.upload`, `attachment.delete` |
| `finance.financial_documents.view` | `financial_document.read`, `attachment.read` |
| `finance.job_charges.view` | `master.reference.view` |
| `finance.job_profitability.view` | `report.read` |
| `finance.journal_entries.create` | `journal_entry.create` |
| `finance.journal_entries.delete` | `journal_entry.delete` |
| `finance.journal_entries.export` | `report.export` |
| `finance.journal_entries.update` | `journal_entry.update` |
| `finance.journal_entries.view` | `journal_entry.read` |
| `finance.posting_rules.create` | `posting_rule.create` |
| `finance.posting_rules.delete` | `posting_rule.delete` |
| `finance.posting_rules.edit` | `posting_rule.manage`, `posting_rule.create`, `posting_rule.update`, `posting_rule.delete` |
| `finance.posting_rules.export` | `report.export` |
| `finance.posting_rules.update` | `posting_rule.update` |
| `finance.posting_rules.view` | `posting_rule.read` |
| `finance.reports.export` | `reports.revenue_expense.export`, `reports.accounts_receivable.export`, `reports.accounts_payable.export`, `reports.general_ledger.export`, `reports.trial_balance.export`, `reports.profit_loss.export`, `reports.balance_sheet.export`, `reports.cash_flow.export` |
| `finance.reports.view` | `reports.revenue_expense.view`, `reports.accounts_receivable.view`, `reports.accounts_payable.view`, `reports.general_ledger.view`, `reports.trial_balance.view`, `reports.profit_loss.view`, `reports.balance_sheet.view`, `reports.cash_flow.view` |
| `finance.service_charges.create` | `service_charge.create` |
| `finance.service_charges.delete` | `service_charge.delete` |
| `finance.service_charges.edit` | `service_charge.create`, `service_charge.update`, `service_charge.issue`, `service_charge.submit`, `service_charge.convert_to_invoice` |
| `finance.service_charges.export` | `report.export` |
| `finance.service_charges.submit` | `service_charge.submit` |
| `finance.service_charges.update` | `service_charge.update` |
| `finance.service_charges.view` | `service_charge.read` |
| `finance.supplier_costs.view` | `master.reference.view` |
| `finance.supplier_payments.view` | `master.reference.view` |
| `master.business_parties.create` | - |
| `master.business_parties.delete` | - |
| `master.business_parties.export` | `report.export` |
| `master.business_parties.update` | - |
| `master.business_parties.view` | - |
| `master.container_types.create` | - |
| `master.container_types.delete` | - |
| `master.container_types.export` | `report.export` |
| `master.container_types.update` | - |
| `master.container_types.view` | - |
| `master.currencies.create` | - |
| `master.currencies.delete` | - |
| `master.currencies.export` | `report.export` |
| `master.currencies.update` | - |
| `master.currencies.view` | - |
| `master.fee_types.create` | - |
| `master.fee_types.delete` | - |
| `master.fee_types.export` | `report.export` |
| `master.fee_types.update` | - |
| `master.fee_types.view` | - |
| `master.party_roles.create` | - |
| `master.party_roles.delete` | - |
| `master.party_roles.export` | `report.export` |
| `master.party_roles.update` | - |
| `master.party_roles.view` | - |
| `master.place_roles.create` | - |
| `master.place_roles.delete` | - |
| `master.place_roles.export` | `report.export` |
| `master.place_roles.update` | - |
| `master.place_roles.view` | - |
| `master.reference.create` | `master.reference.manage` |
| `master.reference.delete` | `master.reference.manage` |
| `master.reference.edit` | `master.reference.manage`, `customs_credential.retrieve` |
| `master.reference.export` | `report.export` |
| `master.reference.view` | `master.reference.view` |
| `master.trade_directions.create` | - |
| `master.trade_directions.delete` | - |
| `master.trade_directions.export` | `report.export` |
| `master.trade_directions.update` | - |
| `master.trade_directions.view` | - |
| `master.transport_assets.create` | - |
| `master.transport_assets.delete` | - |
| `master.transport_assets.export` | `report.export` |
| `master.transport_assets.update` | - |
| `master.transport_assets.view` | - |
| `master.transport_types.create` | - |
| `master.transport_types.delete` | - |
| `master.transport_types.export` | `report.export` |
| `master.transport_types.update` | - |
| `master.transport_types.view` | - |
| `operations.customs.view` | `master.reference.view` |
| `operations.deliveries.view` | `master.reference.view` |
| `operations.documents.view` | `master.reference.view` |
| `operations.jobs.view` | `master.reference.view` |
| `operations.reports.export` | `reports.service_order_register.export`, `reports.service_order_status.export`, `reports.service_order_containers.export`, `reports.service_order_profitability.export` |
| `operations.reports.view` | `reports.service_order_register.view`, `reports.service_order_status.view`, `reports.service_order_containers.view`, `reports.service_order_profitability.view` |
| `operations.service_orders.create` | `service_order.create`, `service_order_config.create` |
| `operations.service_orders.delete` | `service_order.delete`, `service_order_config.delete` |
| `operations.service_orders.edit` | `service_order.update`, `service_order.complete`, `service_order.delete`, `service_order.submit`, `service_order_config.create`, `service_order_config.update`, `service_order_config.delete`, `attachment.upload` |
| `operations.service_orders.export` | `report.export` |
| `operations.service_orders.submit` | `service_order.submit` |
| `operations.service_orders.update` | `service_order.update`, `service_order_config.create`, `service_order_config.update`, `attachment.upload` |
| `operations.service_orders.view` | `service_order.read`, `service_order_config.view`, `attachment.read` |
| `operations.shipments.view` | `master.reference.view` |
| `reports.accounts_payable.export` | `report.export` |
| `reports.accounts_payable.view` | - |
| `reports.accounts_receivable.export` | `report.export` |
| `reports.accounts_receivable.view` | - |
| `reports.balance_sheet.export` | `report.export` |
| `reports.balance_sheet.view` | - |
| `reports.cash_flow.export` | `report.export` |
| `reports.cash_flow.view` | - |
| `reports.general_ledger.export` | `report.export` |
| `reports.general_ledger.view` | - |
| `reports.profit_loss.export` | `report.export` |
| `reports.profit_loss.view` | - |
| `reports.revenue_expense.export` | `report.export` |
| `reports.revenue_expense.view` | - |
| `reports.service_order_containers.export` | `report.export` |
| `reports.service_order_containers.view` | - |
| `reports.service_order_profitability.export` | `report.export` |
| `reports.service_order_profitability.view` | - |
| `reports.service_order_register.export` | `report.export` |
| `reports.service_order_register.view` | - |
| `reports.service_order_status.export` | `report.export` |
| `reports.service_order_status.view` | - |
| `reports.trial_balance.export` | `report.export` |
| `reports.trial_balance.view` | - |
| `reports.view` | `report.read` |
| `sales.companies.view` | `master.reference.view` |
| `sales.quotations.create` | `quotation.create` |
| `sales.quotations.delete` | `quotation.delete` |
| `sales.quotations.edit` | `quotation.update`, `quotation.update_draft`, `quotation.send`, `quotation.accept`, `quotation.convert`, `quotation.delete`, `quotation.submit`, `quotation.revise`, `attachment.upload` |
| `sales.quotations.export` | `report.export` |
| `sales.quotations.quotation` | `quotation.send` |
| `sales.quotations.re_quotation` | `quotation.revise` |
| `sales.quotations.submit` | `quotation.submit` |
| `sales.quotations.update` | `quotation.update`, `quotation.update_draft`, `attachment.upload` |
| `sales.quotations.view` | `quotation.read`, `attachment.read` |
| `settings.app_config.edit` | - |
| `settings.app_config.update` | - |
| `settings.app_config.view` | - |
| `settings.backup.create` | `backup.manage` |
| `settings.backup.edit` | `backup.manage` |
| `settings.backup.update` | `backup.manage` |
| `settings.backup.view` | `backup.read` |
| `settings.manage` | `settings.app_config.view`, `settings.app_config.update`, `settings.backup.view`, `settings.backup.create`, `settings.backup.update` |

Notes:

- Posting rules are their own page rather than part of Accounting: which
  accounts a document posts through is a distinct decision from the accounts
  themselves, and an auditor should be able to read the rules without being
  able to rewrite them. `posting_rule.manage` is deliberately **not** implied
  by `finance.accounting.edit`, so granting "edit accounting" does not
  silently grant the ability to redirect where a document posts.
- The master-data collections use their page code directly: for example
  `master.party_roles.view` guards `GET /partyRoles`, and
  `master.party_roles.update` guards `PUT /partyRoles/{id}`. The coarse
  `master.reference.view` / `master.reference.manage` fallback remains for
  roles created before the granular pages existed.
- Setting another account's password (`POST /users/{id}/password`) is gated
  on `user.manage`, not a permission of its own. Only a platform administrator
  may reset the built-in administrator, enforced by
  `_assert_can_manage_platform_admin`.
- Archive hard delete is backend-only. The matrix offers view, export, and
  restore; `archive.hard_delete` is never exposed as a page action. Legacy
  `admin.archive.edit` and `admin.archive.delete` codes are still accepted for
  existing roles but are not offered to new roles.

## 3. Role Definitions

Roles are defined in code in `ROLE_DEFINITIONS`. Only **PLATFORM_ADMIN** is
provisioned automatically (`BUILTIN_ROLE_CODES`); every other defined role is a
convenience template that must be created manually from Roles & Permissions, and
the platform administrator can also create entirely custom roles.

| Code | Name | Provisioned at setup | Description |
|---|---|---|---|
| PLATFORM_ADMIN | Platform Administrator | Yes | Full platform administration (all permission codes) |
| ADMINISTRATOR | Administrator | No | System administration |
| OPERATIONS_MANAGER | Operations Manager | No | Operations and review |
| SALES_OFFICER | Sales Officer | No | Quotation and commercial work |
| OPERATIONS_OFFICER | Operations Officer | No | Service-order operations |
| FINANCE_OFFICER | Finance Officer | No | Financial drafts, payments, and allocations |
| FINANCE_MANAGER | Finance Manager | No | Posting, periods, journals, and reversals |
| AUDITOR | Auditor | No | Read-only review |

### 3.1 Platform Administrator

All permission codes in the catalog (`ALL_PERMISSION_CODES`), including every
source, page and matrix permission. This role is built in and is the super-admin
role used for first-run provisioning; it cannot be locked out.

### 3.2 Administrator

Source permissions:

```text
user.read, user.manage, role.read, role.manage,
quotation.read, quotation.create, quotation.update_draft, quotation.send, quotation.accept, quotation.convert,
service_order.read, service_order.create, service_order.update, service_order.complete,
service_order_config.view, service_order_config.create, service_order_config.update, service_order_config.delete,
service_charge.read, service_charge.create, service_charge.issue, service_charge.convert_to_invoice,
financial_document.read, financial_document.create, financial_document.update_draft, financial_document.post, financial_document.reverse, financial_document.allocate,
journal_entry.read, journal_entry.create, journal_entry.post,
accounting_period.read, accounting_period.close, chart_of_accounts.manage, posting_rule.read, posting_rule.manage,
attachment.read, attachment.upload, attachment.delete, audit_log.read, report.read,
archive.view, archive.restore, archive.hard_delete,
master.reference.view, master.reference.manage,
configuration.manage, configuration.read, configuration.publish, configuration.activate,
configuration.rollback, configuration.compare,
admin.user_manage, admin.role_manage, settings.manage, backup.read, backup.manage
```

### 3.3 Operations Manager

```text
user.read, role.read,
quotation.read, quotation.create, quotation.update_draft, quotation.send, quotation.accept, quotation.convert,
service_order.read, service_order.create, service_order.update, service_order.complete,
service_order_config.view, service_order_config.update,
service_charge.read, service_charge.create, service_charge.issue,
financial_document.read, attachment.read, attachment.upload, audit_log.read, report.read,
master.reference.view, master.reference.manage
```

### 3.4 Sales Officer

```text
quotation.read, quotation.create, quotation.update_draft, quotation.send, quotation.accept, quotation.convert,
service_order.read, service_charge.read, service_charge.create, service_charge.issue,
attachment.read, attachment.upload, report.read, master.reference.view
```

### 3.5 Operations Officer

```text
quotation.read, quotation.convert,
service_order.read, service_order.create, service_order.update, service_order.complete,
service_charge.read, service_charge.create, service_charge.issue,
attachment.read, attachment.upload, report.read, master.reference.view
```

### 3.6 Finance Officer

```text
service_order.read, service_charge.read, service_charge.create, service_charge.issue, service_charge.convert_to_invoice,
financial_document.read, financial_document.create, financial_document.update_draft, financial_document.post, financial_document.allocate,
journal_entry.read, journal_entry.create, journal_entry.post,
accounting_period.read, attachment.read, attachment.upload, report.read,
master.reference.view, finance.view
```

### 3.7 Finance Manager

```text
service_charge.read,
financial_document.read, financial_document.create, financial_document.update_draft, financial_document.post, financial_document.reverse, financial_document.allocate,
journal_entry.read, journal_entry.create, journal_entry.post,
accounting_period.read, accounting_period.close, chart_of_accounts.manage,
posting_rule.read, posting_rule.manage,
audit_log.read, attachment.read, report.read, master.reference.view, finance.view, report.export
```

### 3.8 Auditor

```text
user.read, role.read,
quotation.read, service_order.read, service_charge.read,
financial_document.read, journal_entry.read, accounting_period.read, posting_rule.read,
attachment.read, audit_log.read, report.read, master.reference.view, finance.view
```

## 4. Role-Permission Matrix

Legend: `Y` = granted, `-` = not granted. `ALL` = every permission code.

| Capability | Platform Admin | Admin | Ops Manager | Sales Officer | Ops Officer | Finance Officer | Finance Manager | Auditor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Users read | ALL | Y | Y | - | - | - | - | Y |
| Users manage | ALL | Y | - | - | - | - | - | - |
| Roles read | ALL | Y | Y | - | - | - | - | Y |
| Roles manage | ALL | Y | - | - | - | - | - | - |
| Quotation create/edit | ALL | Y | Y | Y | - | - | - | - |
| Quotation send/accept/convert | ALL | Y | Y | Y | convert only | - | - | - |
| Service-order create/update | ALL | Y | Y | - | Y | - | - | - |
| Service-order complete | ALL | Y | Y | - | Y | - | - | - |
| Service-order config | ALL | Y | view/update | - | - | - | - | - |
| Service-charge create/issue | ALL | Y | Y | Y | Y | Y | - | - |
| Service-charge convert to invoice | ALL | Y | - | - | - | Y | - | - |
| Financial-document read | ALL | Y | Y | - | - | Y | Y | Y |
| Financial-document create/draft | ALL | Y | - | - | - | Y | Y | - |
| Financial-document post | ALL | Y | - | - | - | Y | Y | - |
| Financial-document allocate | ALL | Y | - | - | - | Y | Y | - |
| Financial-document reverse | ALL | Y | - | - | - | - | Y | - |
| Journal read | ALL | Y | - | - | - | Y | Y | Y |
| Journal create/post | ALL | Y | - | - | - | Y | Y | - |
| Accounting-period close | ALL | Y | - | - | - | - | Y | - |
| Chart of accounts manage | ALL | Y | - | - | - | - | Y | - |
| Posting-rule read | ALL | Y | - | - | - | - | Y | Y |
| Posting-rule manage | ALL | Y | - | - | - | - | Y | - |
| Master data view | ALL | Y | Y | Y | Y | Y | Y | Y |
| Master data manage | ALL | Y | Y | - | - | - | - | - |
| Configuration | ALL | Y | - | - | - | - | - | - |
| Attachments | ALL | read/upload/delete | read/upload | read/upload | read/upload | read/upload | read | read |
| Archive view/export/restore | ALL | Y | - | - | - | - | - | - |
| Audit log read | ALL | Y | Y | - | - | - | Y | Y |
| Reports | ALL | Y | Y | Y | Y | Y | Y | Y |
| Report export | ALL | - | - | - | - | - | Y | - |
| Backup read/manage | ALL | Y | - | - | - | - | - | - |
| Settings manage | ALL | Y | - | - | - | - | - | - |
| Finance view | ALL | - | - | - | - | Y | Y | Y |

## 5. Separation of Duties

Recommended restrictions (not enforced by the catalog itself; apply through
role design):

- A finance officer may prepare and post only when organizational policy permits.
- Reversal requires the finance-manager role (`financial_document.reverse`).
- Chart-of-accounts management is separate from ordinary posting.
- Period closure requires the finance-manager role (`accounting_period.close`).
- `customs_credential.retrieve` is reserved for a future dedicated
  customs-password retrieval workflow; no route currently checks it. Grant it
  sparingly when that workflow is implemented.
- A user should not approve their own high-risk transaction when an approval
  workflow is enabled.

## 6. Scope and Assignment Rules

- There is no organization/branch scope. A granted permission applies to all
  records of that module.
- A user has exactly one active role assignment. Replaced assignments are
  expired for history, and expired assignments do not contribute permissions.
- The API is authoritative: the UI hides unavailable actions, but every
  protected endpoint re-checks the permission server-side.
- The Platform Administrator role is built in (`is_system_role = true`) and
  always resolves to all permission codes; it cannot be reduced below the
  bootstrap administrator.

## 7. Protected System Administrator

The account created by first-run setup is permanently identified by
`users.system_identity = 'DEFAULT_SYSTEM_ADMIN'`. This machine identifier is
unique, is never accepted from an API request, and is independent of mutable
username, email, display name, and user code.

Backend rules return HTTP 403 and write a rejected audit event when an operation
attempts to:

- delete the protected account, including a mixed bulk deletion;
- deactivate it;
- replace or clear its Platform Administrator role;
- deactivate or delete the built-in Platform Administrator role; or
- remove any catalog permission from that role.

The account's ordinary profile fields remain editable. The UI marks protected
records from the backend-provided flags, hides destructive row/detail actions,
disables bulk destructive actions containing a protected record, and makes the
protected role and permission matrix read-only. These UI controls are only a
convenience; service-layer checks are authoritative.

Administrative business-data reset preserves users, credentials, roles,
permissions, assignments, sessions, and audit history. It therefore cannot
delete the protected account or reopen first-run setup.

### Access recovery

Recovery requires production-host/database administrator access; there is no
HTTP bypass. Find the protected account by `system_identity`, then restore its
credential through the forgot-password flow (`/auth/forgot-password/...` email
codes) with that account's email, or by direct database/administrator-assisted
password entry. Rotate exposed credentials, inspect rejected/successful
administrative audit events, and revoke active sessions after recovery.

## 8. Role Administration and Delegation Safety

- `GET /api/v1/roles` supports search, status filtering, stable sorting and the
  standard paginated `{items, meta}` envelope. Each row includes the number of
  currently assigned users; role detail also includes their identifiers and
  display names.
- `POST /api/v1/roles/{role_id}/duplicate` creates an active custom copy with a
  distinct code and an audit event. The Roles & Permissions page exposes this
  operation from the record action menu.
- A delegated role manager may grant or assign only capabilities already held
  by that manager. Page-level matrix permissions are evaluated through their
  implied API permissions, preventing a custom role from being used as a
  privilege-escalation bridge.
- No user, including a Platform Administrator, may replace their own role.
- A role assigned to an active user cannot be deactivated. Reassign those users
  first. The built-in Platform Administrator role remains non-deletable and
  cannot lose catalog permissions.
- Role replacement locks the user row, permission updates lock the role row,
  and last-Platform-Administrator checks lock the built-in role. PostgreSQL's
  partial unique index remains the final concurrency backstop.
- The permission matrix supports module/action filtering, search, applicable
  Select All/Clear All operations, and an unsaved-change indicator.

Migration `a2b3c4d5e6f7` normalizes every current assignment into the
non-expiring form covered by the unique index. Any legacy active user without a
role is mapped to the active, zero-permission `MIGRATED_NO_ACCESS` role. This is
an explicit least-privilege mapping; administrators must review and reassign
those users after deployment.

## 9. Enforcement in the Frontend

- `middleware/auth.global.ts` checks `definePageMeta.permission` before rendering a
  protected page. The page guard is a UX gate; the API check is authoritative.
- `useAuthStore().canAccessPage(pageId)` and `useMenu` decide whether a navigation
  entry is visible. The page ids come from the same metadata catalogue that the
  Roles & Permissions matrix edits.
- Buttons and row actions call `can('permission.code')` (or the module action
  helper) before rendering. A hidden button is not a security control; every
  protected route re-checks on the backend.
- The Role editor renders `AppRolePermissionMatrix`, which supports module/action
  filtering, search, select-all/clear-all, an unsaved-change indicator, and the
  protected-role read-only state.
- Client-side validation never grants access. A user who forges a request reaches
  the same `require_permission` dependency as the UI.
- The UI marks protected users/roles from backend flags and disables destructive
  actions; the service layer still rejects the operation.

## 10. Permission Validation, Audit, and Security Rules

- `ensure_permission_catalog` runs on startup and inserts missing permission
  codes. Code is the source of truth; the `permissions` table is a projection used
  for joins and administration.
- A role may contain only known codes. Assigning or updating a role resolves the
  submitted codes against the catalog and rejects unknown codes with a field
  error.
- A delegated role manager may grant or assign only capabilities the manager
  already holds. Page-level matrix permissions are evaluated through their implied
  API permissions, so a custom role cannot become a privilege-escalation bridge.
- A user cannot replace their own role. A role assigned to an active user cannot
  be deactivated or deleted until the user is reassigned.
- The built-in Platform Administrator role is `is_system_role`, always resolves to
  all permission codes, and cannot be reduced, deactivated, or deleted.
- User, role, assignment, password, and session administration writes an audit
  event with actor, action, target, result, and request id. Rejected attempts to
  modify the protected administrator are audited too.
- Passwords are Argon2id hashes and are never returned. Administrator-set
  passwords set `must_change_password`, revoke existing sessions, and restrict the
  next token to `auth/change-password`, `auth/logout`, `auth/refresh`, and
  `auth/me` until the password is replaced.
- Refresh tokens rotate on a stable PostgreSQL session; consumed hashes detect
  replay and revoke that session. Browser cookie sessions use HttpOnly cookies,
  signed double-submit CSRF and trusted Origin validation. Every protected
  request checks the JWT session ID, idle/absolute deadlines, account status
  and token version, so logout immediately denies its existing access tokens.
  Refresh and identity endpoints require a valid session rather than a role
  permission; existing business endpoints retain their permission dependencies.
- Permission changes take effect for new requests. Revoking a session or changing
  a password invalidates the old access path immediately; the frontend refreshes
  `/auth/me` after a permission-sensitive operation.
