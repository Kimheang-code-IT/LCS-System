# Permissions Matrix

## 1. Interpretation

A permission answers **what may the user do?** The platform is single-tenant:
organizations and branches were removed, so there is no organization/branch scope.
Access is granted through roles, each role is a set of permission codes, and a
user may hold several roles (with optional start/expiry dates).

Every permission code is `module.action`, defined in code in
`backend/app/core/permissions.py` and synced into the `permissions` table on
startup (`ensure_permission_catalog`). The frontend mirrors the same catalog
(`frontend/app/utils/lcs/permissions.ts`, `frontend/app/utils/role/permissions.ts`)
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
| customs_credential.retrieve | customs_credential | retrieve |
| attachment.read | attachment | read |
| attachment.upload | attachment | upload |
| attachment.delete | attachment | delete |
| audit_log.read | audit_log | read |
| report.read | report | read |

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
| Dashboard | `dashboard.view` |
| Quotations | `sales.quotations.view`, `sales.quotations.create`, `sales.quotations.edit`, `sales.quotations.delete`, `sales.quotations.export` |
| Service orders | `operations.service_orders.view`, `operations.service_orders.create`, `operations.service_orders.edit`, `operations.service_orders.delete`, `operations.service_orders.export` |
| Service charges | `finance.service_charges.view`, `finance.service_charges.create`, `finance.service_charges.edit`, `finance.service_charges.delete`, `finance.service_charges.export` |
| Financial documents | `finance.financial_documents.view`, `finance.financial_documents.create`, `finance.financial_documents.edit`, `finance.financial_documents.delete`, `finance.financial_documents.export` |
| Accounting | `finance.accounting.view`, `finance.accounting.create`, `finance.accounting.edit`, `finance.accounting.delete`, `finance.accounting.export` |
| Operations reports | `operations.reports.view`, `operations.reports.export` |
| Finance reports | `finance.reports.view`, `finance.reports.export` |
| Master data | `master.reference.create`, `master.reference.edit`, `master.reference.delete`, `master.reference.export` |
| Configuration | `configuration.view`, `configuration.create`, `configuration.edit`, `configuration.delete` |
| Users | `admin.users.view`, `admin.users.create`, `admin.users.edit`, `admin.users.delete` |
| Roles | `admin.roles.view`, `admin.roles.create`, `admin.roles.edit`, `admin.roles.delete` |
| Document sequences | `admin.document_sequences.view`, `admin.document_sequences.create`, `admin.document_sequences.edit`, `admin.document_sequences.delete` |
| Audit logs | `admin.audit_logs.view`, `admin.audit_logs.export` |
| App config | `settings.app_config.view`, `settings.app_config.edit` |
| Backup | `settings.backup.view`, `settings.backup.edit` |

### 2.4 Page grant → API permission mapping

Granting a page/action also enables the API permissions it implies.

| Page permission | Implied API permissions |
|---|---|
| dashboard.view | (none) |
| sales.quotations.view | quotation.read |
| sales.quotations.create | quotation.create |
| sales.quotations.edit | quotation.update_draft, quotation.send, quotation.accept, quotation.convert |
| sales.quotations.delete | quotation.update_draft |
| sales.quotations.export | report.export |
| operations.service_orders.view | service_order.read |
| operations.service_orders.create | service_order.create |
| operations.service_orders.edit | service_order.update, service_order.complete |
| operations.service_orders.delete | service_order.update |
| operations.service_orders.export | report.export |
| finance.service_charges.view | service_charge.create |
| finance.service_charges.create | service_charge.create |
| finance.service_charges.edit | service_charge.issue, service_charge.convert_to_invoice |
| finance.service_charges.delete | service_charge.create |
| finance.service_charges.export | report.export |
| finance.financial_documents.view | financial_document.read |
| finance.financial_documents.create | financial_document.create |
| finance.financial_documents.edit | financial_document.update_draft, financial_document.post, financial_document.reverse, financial_document.allocate |
| finance.financial_documents.delete | financial_document.update_draft |
| finance.financial_documents.export | report.export |
| finance.accounting.view | journal_entry.read, accounting_period.read |
| finance.accounting.create | journal_entry.create |
| finance.accounting.edit | journal_entry.post, accounting_period.close, chart_of_accounts.manage |
| finance.accounting.delete | journal_entry.create |
| finance.accounting.export | report.export |
| operations.reports.view | report.read |
| operations.reports.export | report.export |
| finance.reports.view | report.read |
| finance.reports.export | report.export |
| master.reference.view | master.reference.view |
| master.reference.create/edit/delete | master.reference.manage |
| master.reference.export | report.export |
| configuration.view/create/delete | configuration.manage |
| configuration.edit | configuration.manage, configuration.configure |
| admin.users.view | user.read |
| admin.users.create/edit/delete | user.manage |
| admin.roles.view | role.read |
| admin.roles.create/edit/delete | role.manage |
| admin.document_sequences.* | configuration.manage |
| admin.audit_logs.view | audit_log.read |
| admin.audit_logs.export | report.export |
| settings.app_config.view/edit | configuration.manage |
| settings.backup.view | backup.read |
| settings.backup.edit | backup.manage |

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
service_charge.create, service_charge.issue, service_charge.convert_to_invoice,
financial_document.read, financial_document.create, financial_document.update_draft, financial_document.post, financial_document.reverse, financial_document.allocate,
journal_entry.read, journal_entry.create, journal_entry.post,
accounting_period.read, accounting_period.close, chart_of_accounts.manage,
attachment.read, attachment.upload, attachment.delete, audit_log.read, report.read,
master.reference.view, master.reference.manage, configuration.manage,
admin.user_manage, admin.role_manage, settings.manage, backup.read, backup.manage
```

### 3.3 Operations Manager

```text
user.read, role.read,
quotation.read, quotation.create, quotation.update_draft, quotation.send, quotation.accept, quotation.convert,
service_order.read, service_order.create, service_order.update, service_order.complete,
service_order_config.view, service_order_config.update,
service_charge.create, service_charge.issue,
financial_document.read, attachment.read, attachment.upload, audit_log.read, report.read,
master.reference.view, master.reference.manage
```

### 3.4 Sales Officer

```text
quotation.read, quotation.create, quotation.update_draft, quotation.send, quotation.accept, quotation.convert,
service_order.read, service_charge.create, service_charge.issue,
attachment.read, attachment.upload, report.read, master.reference.view
```

### 3.5 Operations Officer

```text
quotation.read, quotation.convert,
service_order.read, service_order.create, service_order.update, service_order.complete,
service_charge.create, service_charge.issue,
attachment.read, attachment.upload, report.read, master.reference.view
```

### 3.6 Finance Officer

```text
service_order.read, service_charge.create, service_charge.issue, service_charge.convert_to_invoice,
financial_document.read, financial_document.create, financial_document.update_draft, financial_document.post, financial_document.allocate,
journal_entry.read, journal_entry.create, journal_entry.post,
accounting_period.read, attachment.read, attachment.upload, report.read,
master.reference.view, finance.view
```

### 3.7 Finance Manager

```text
financial_document.read, financial_document.create, financial_document.update_draft, financial_document.post, financial_document.reverse, financial_document.allocate,
journal_entry.read, journal_entry.create, journal_entry.post,
accounting_period.read, accounting_period.close, chart_of_accounts.manage,
audit_log.read, attachment.read, report.read, master.reference.view, finance.view, report.export
```

### 3.8 Auditor

```text
user.read, role.read,
quotation.read, service_order.read,
financial_document.read, journal_entry.read, accounting_period.read,
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
| Master data view | ALL | Y | Y | Y | Y | Y | Y | Y |
| Master data manage | ALL | Y | Y | - | - | - | - | - |
| Configuration | ALL | Y | - | - | - | - | - | - |
| Attachments | ALL | read/upload/delete | read/upload | read/upload | read/upload | read/upload | read | read |
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
- Customs-password retrieval (`customs_credential.retrieve`) is separate from
  ordinary customer viewing and should be granted sparingly.
- A user should not approve their own high-risk transaction when an approval
  workflow is enabled.

## 6. Scope and Assignment Rules

- There is no organization/branch scope. A granted permission applies to all
  records of that module.
- A user may hold multiple role assignments; assignments support `starts_at` and
  `expires_at`, and expired/future assignments do not contribute permissions.
- The API is authoritative: the UI hides unavailable actions, but every
  protected endpoint re-checks the permission server-side.
- The Platform Administrator role is built in (`is_system_role = true`) and
  always resolves to all permission codes; it cannot be reduced below the
  bootstrap administrator.
