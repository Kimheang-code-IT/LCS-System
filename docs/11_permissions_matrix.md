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

## 2. Permission Catalog

| Permission | Resource | Action | Risk |
|---|---|---|---|
| organization.read | organization | read | Low |
| organization.update | organization | update | High |
| branch.read | branch | read | Low |
| branch.manage | branch | manage | High |
| user.read | user | read | Medium |
| user.manage | user | manage | High |
| role.read | role | read | Medium |
| role.manage | role | manage | Critical |
| quotation.read | quotation | read | Low |
| quotation.create | quotation | create | Medium |
| quotation.update_draft | quotation | update draft | Medium |
| quotation.send | quotation | send | Medium |
| quotation.accept | quotation | accept | High |
| quotation.convert | quotation | convert | High |
| service_order.read | service order | read | Low |
| service_order.create | service order | create | Medium |
| service_order.update | service order | update | Medium |
| service_order.complete | service order | complete | High |
| service_charge.create | service charge | create | Medium |
| service_charge.issue | service charge | issue | Medium |
| service_charge.convert_to_invoice | service charge | convert | High |
| financial_document.read | financial document | read | Medium |
| financial_document.create | financial document | create | High |
| financial_document.update_draft | financial document | update draft | High |
| financial_document.post | financial document | post | Critical |
| financial_document.reverse | financial document | reverse | Critical |
| financial_document.allocate | financial document | allocate | High |
| journal_entry.read | journal entry | read | High |
| journal_entry.create | journal entry | create | Critical |
| journal_entry.post | journal entry | post | Critical |
| accounting_period.read | accounting period | read | High |
| accounting_period.close | accounting period | close | Critical |
| chart_of_accounts.manage | chart of accounts | manage | Critical |
| customs_credential.retrieve | customs credential | retrieve | Critical |
| attachment.read | attachment | read | Medium |
| attachment.upload | attachment | upload | Medium |
| attachment.delete | attachment | delete | High |
| audit_log.read | audit log | read | High |
| report.read | report | read | Medium |

## 3. Role-Permission Matrix

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
