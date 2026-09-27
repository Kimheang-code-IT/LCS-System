# Permissions Matrix

## 1. Interpretation

A permission answers:

```text
What may the user do?
```

A scope answers:

```text
Where may the user do it?
```

Scopes are:

- `ORGANIZATION`: all branches in the assigned organization.
- `BRANCH`: only assigned branches.
- `OWN`: records created by the user, subject to policy.
- `NONE`: not granted.

All permissions are constrained by organization isolation.

In the current UI the role form captures only a role name and the permission
actions it grants; per-role scope/level columns were removed. Scope is applied
per user assignment and enforced by the API.

## 2. Permission Catalog

Permissions are `module.action` codes seeded from
`backend/app/core/permissions.py` (`SOURCE_PERMISSIONS` + `PAGE_PERMISSIONS`).

### 2.1 Source (API) permissions

| Permission | Resource | Action |
|---|---|---|
| organization.read | organization | read |
| organization.update | organization | update |
| branch.read | branch | read |
| branch.manage | branch | manage |
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

These gate frontend navigation and configuration screens.

| Permission | Resource | Action |
|---|---|---|
| master.reference.view | master_data | view |
| master.reference.manage | master_data | manage |
| configuration.manage | configuration | manage |
| configuration.configure | configuration | configure |
| admin.user_manage | admin | user_manage |
| admin.role_manage | admin | role_manage |
| admin.organization_manage | admin | organization_manage |
| settings.manage | settings | manage |
| finance.view | finance | view |
| report.export | report | export |

## 3. Role-Permission Matrix

The matrix shows the intended separation of duties. In the current UI a role is
defined only by its permission actions; organization/branch scope is applied per
user assignment and enforced by the API, not entered on the role form.

Legend: `O` = organization scope, `B` = branch scope, `-` = not granted.

| Permission group | Platform Admin | Organization Admin | Branch Manager | Sales Officer | Operations Officer | Finance Officer | Finance Manager | Auditor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Organization and branch administration | O | O | B | - | - | - | - | - |
| User and role administration | O | O | - | - | - | - | - | - |
| Master data read | O | O | B | B | B | O | O | O |
| Master data manage | O | O | B | - | - | - | - | - |
| Quotation read/create/update | O | O | B | B | B | - | - | B |
| Quotation send/accept | O | O | B | B | - | - | - | - |
| Quotation conversion | O | O | B | B | B | - | - | - |
| Service-order read | O | O | B | B | B | B | O | B |
| Service-order create/update | O | O | B | - | B | - | - | - |
| Service-order complete | O | O | B | - | B | - | - | - |
| Service-charge create | O | O | B | B | B | O | O | - |
| Service-charge issue | O | O | B | B | B | O | O | - |
| Financial-document read | O | O | B | - | - | B | O | O |
| Financial-document create | O | O | - | - | - | B | O | - |
| Financial-document draft update | O | O | - | - | - | B | O | - |
| Financial-document post | - | O | - | - | - | B | O | - |
| Financial-document allocate | O | O | - | - | - | B | O | - |
| Financial-document reverse | - | O | - | - | - | - | O | - |
| Manual journal create | O | O | - | - | - | B | O | - |
| Manual journal post | - | O | - | - | - | B | O | - |
| Accounting-period close | - | O | - | - | - | - | O | - |
| Chart of accounts manage | O | - | - | - | - | - | O | - |
| Customs credential retrieve | O | - | - | - | - | - | - | - |
| Attachments | O | O | B | B | B | B | O | O |
| Audit log read | O | O | B | - | - | B | O | O |
| Reports | O | O | B | B | B | B | O | O |

## 4. Separation of Duties

Recommended restrictions:

- A finance officer may prepare and post only when organizational policy permits.
- Reversal requires finance-manager permission.
- Chart-of-accounts management is separate from ordinary posting.
- Period closure requires finance-manager permission.
- Customs-password retrieval is separate from ordinary customer viewing.
- A user should not approve their own high-risk transaction when approval workflow is enabled.

## 5. Scope Rules

- An organization-scoped role sees all branches in that organization.
- A branch-scoped role sees only records whose `branch_id` matches an active assignment.
- Users with multiple branch assignments may switch only among assigned branches.
- A branch manager cannot grant organization-wide roles unless explicitly granted `role.manage` at organization scope.
- API authorization must re-check scope for every read and write.
