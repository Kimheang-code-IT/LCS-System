# Permissions Matrix

## 1. Interpretation

A permission answers **what may the user do?** The platform is single-tenant:
organizations and branches were removed, so there is no organization/branch scope.
Access is granted through roles, each role is a set of permission codes, and a
every user has exactly one active role. Replaced assignments are retained as
expired history but do not grant permissions.

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
| service_order_config.publish | service_order_config | publish |
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
| attachment.upload | attachment | upload |
| attachment.delete | attachment | delete |
| audit_log.read | audit_log | read |
| archive.view | archive | view |
| archive.restore | archive | restore |
| archive.hard_delete | archive | hard_delete |
| report.read | report | read |

The shared record-status endpoint (`POST /api/v1/{collection}/{item_id}/status`)
introduces **no new codes**: each transition in
`backend/app/modules/status/policy.py` requires the permission that already owns
that area — `master.reference.manage` for reference data, `chart_of_accounts.manage`
for the ledger accounts, `posting_rule.manage`, `configuration.manage` for the
sequences, `accounting_period.close` for closing/reopening, `service_order.update`
for the order lifecycle, `user.manage` / `role.manage` — and the policy endpoint
returns only the transitions the caller may perform.

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
| Posting Rules | `finance.posting_rules.view`, `finance.posting_rules.create`, `finance.posting_rules.edit`, `finance.posting_rules.delete` |
| Operations reports | `operations.reports.view`, `operations.reports.export` |
| Finance reports | `finance.reports.view`, `finance.reports.export` |
| Master data | `master.reference.create`, `master.reference.edit`, `master.reference.delete`, `master.reference.export` |
| Configuration | `configuration.view`, `configuration.create`, `configuration.edit`, `configuration.delete` |
| Users | `admin.users.view`, `admin.users.create`, `admin.users.edit`, `admin.users.delete` |
| Roles | `admin.roles.view`, `admin.roles.create`, `admin.roles.edit`, `admin.roles.delete` |
| Document sequences | `admin.document_sequences.view`, `admin.document_sequences.create`, `admin.document_sequences.edit`, `admin.document_sequences.delete` |
| Audit logs | `admin.audit_logs.view`, `admin.audit_logs.export` |
| Archive | `admin.archive.view`, `admin.archive.edit`, `admin.archive.delete` |
| App config | `settings.app_config.view`, `settings.app_config.edit` |
| Backup | `settings.backup.view`, `settings.backup.edit` |

### 2.4 Navigation page codes (aliases)

Some pages are served by another matrix row and therefore have no checkbox of
their own. Their navigation code travels with the row that serves them
(`NAVIGATION_PAGE_ALIASES`), so a role created in Roles & Permissions can open
them. Without this, the page stayed invisible to every non-administrator role.

| Pages | Navigation code | Granted with | API permission |
|---|---|---|---|
| Companies, Jobs, Shipments, Customs, Operations documents, Deliveries, Debit notes, Customer payments, Job charges, Supplier costs, Supplier payments | `sales.companies.view`, `operations.jobs.view`, `operations.shipments.view`, `operations.customs.view`, `operations.documents.view`, `operations.deliveries.view`, `finance.debit_notes.view`, `finance.customer_payments.view`, `finance.job_charges.view`, `finance.supplier_costs.view`, `finance.supplier_payments.view` | Master data (`master.reference.*`) | `master.reference.view` |
| Reports | `reports.view` | Operations reports | `report.read` |
| Accounts receivable, Accounts payable, Job profitability | `finance.accounts_receivable.view`, `finance.accounts_payable.view`, `finance.job_profitability.view` | Finance reports | `report.read` |

### 2.5 Page grant → API permission mapping

Granting a page/action also enables the API permissions it implies.

| Page permission | Implied API permissions |
|---|---|
| dashboard.view | (none) |
| sales.quotations.view | quotation.read, attachment.read |
| sales.quotations.create | quotation.create |
| sales.quotations.edit | quotation.update_draft, quotation.send, quotation.accept, quotation.convert, attachment.upload |
| sales.quotations.delete | quotation.update_draft |
| sales.quotations.export | report.export |
| operations.service_orders.view | service_order.read, service_order_config.view, attachment.read |
| operations.service_orders.create | service_order.create, service_order_config.create |
| operations.service_orders.edit | service_order.update, service_order.complete, service_order_config.create, service_order_config.update, attachment.upload |
| operations.service_orders.delete | service_order.update, service_order_config.delete |
| operations.service_orders.export | report.export |
| finance.service_charges.view | service_charge.read |
| finance.service_charges.create | service_charge.create |
| finance.service_charges.edit | service_charge.issue, service_charge.convert_to_invoice |
| finance.service_charges.delete | service_charge.create |
| finance.service_charges.export | report.export |
| finance.financial_documents.view | financial_document.read, attachment.read |
| finance.financial_documents.create | financial_document.create |
| finance.financial_documents.edit | financial_document.update_draft, financial_document.post, financial_document.reverse, financial_document.allocate, attachment.upload, attachment.delete |
| finance.financial_documents.delete | financial_document.update_draft |
| finance.financial_documents.export | report.export |
| finance.accounting.view | journal_entry.read, accounting_period.read |
| finance.accounting.create | journal_entry.create |
| finance.accounting.edit | journal_entry.post, accounting_period.close, chart_of_accounts.manage |
| finance.accounting.delete | journal_entry.create |
| finance.accounting.export | report.export |
| finance.posting_rules.view | posting_rule.read |
| finance.posting_rules.create | posting_rule.manage |
| finance.posting_rules.edit | posting_rule.manage |
| finance.posting_rules.delete | posting_rule.manage |

Posting rules are their own page rather than part of Accounting: which accounts a
document posts through is a distinct decision from the accounts themselves, and an
auditor should be able to read the rules without being able to rewrite them.
`posting_rule.manage` is deliberately **not** implied by `finance.accounting.edit`,
so granting "edit accounting" does not silently grant the ability to redirect
where a document posts.

Setting another account's password (`POST /users/{id}/password`) is gated on the
existing `user.manage`, not a permission of its own. Creating a user already means
choosing that user's password, so a reset is a recovery path rather than a wider
capability; a separate code would have implied a restriction that does not exist.
The one guard it does carry is that only a platform administrator may reset the
built-in administrator, which `_assert_can_manage_platform_admin` enforces.

**Posting Rule History** (the change history of every rule, and the change history
and posting usage on a single rule) is gated on `posting_rule.read`, not on
`audit_log.read`. The events it returns are exclusively about an entity the caller
can already read and leak no other entity's data, so requiring the generic audit
permission would mean the person who manages the rules could not see why a rule
changed. The generic Audit Logs screen keeps its own `audit_log.read` gate.
| operations.reports.view | report.read |
| operations.reports.export | report.export |
| finance.reports.view | report.read |
| finance.reports.export | report.export |
| master.reference.view | master.reference.view |
| master.reference.create/edit/delete | master.reference.manage |
| master.reference.edit | master.reference.manage, customs_credential.retrieve |
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
| admin.archive.view | archive.view |
| admin.archive.edit | archive.view, archive.restore |
| admin.archive.delete | archive.view, archive.hard_delete |
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
service_charge.read, service_charge.create, service_charge.issue, service_charge.convert_to_invoice,
financial_document.read, financial_document.create, financial_document.update_draft, financial_document.post, financial_document.reverse, financial_document.allocate,
journal_entry.read, journal_entry.create, journal_entry.post,
accounting_period.read, accounting_period.close, chart_of_accounts.manage, posting_rule.read, posting_rule.manage,
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
- A user has exactly one active role assignment. Replaced assignments are
  expired for history, and expired/future assignments do not contribute permissions.
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
HTTP bypass. Find the protected account by `system_identity`, then use the
documented `app.create_admin` CLI with that account's email or username and a
new strong password. Rotate exposed credentials, inspect rejected/successful
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
