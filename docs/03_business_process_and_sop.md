# Business Process and Standard Operating Procedures

## 1. Purpose and Control Principles

This SOP defines the operational steps, responsible roles, approvals, exceptions, and evidence required for the platform.

The system follows:

```text
Operational record
    → customer-facing service charge
        → optional financial document
            → accounting journal
```

Issuing a service charge does not post accounting. Accounting begins only when an authorized user posts a financial document or manual journal.

All procedures are constrained by organization and branch scope.

## 2. Roles and Responsibilities

| Role | Main responsibilities |
|---|---|
| Organization administrator | Organization, branch, user, role, and operational configuration |
| Branch manager | Branch operations, review, assignment, and branch approvals |
| Sales officer | Quotations, revisions, customer communication |
| Operations officer | Service orders, containers, components, documents, milestones |
| Finance officer | Financial drafts, receipts, payments, allocations, reconciliations |
| Finance manager | Posting, reversals, chart of accounts, periods, approvals |
| Auditor | Read-only review and evidence collection |

## 3. Organization and Branch Setup

### Normal procedure

1. Organization administrator creates the organization.
2. Administrator creates branches and assigns branch codes.
3. Administrator marks the head office.
4. Administrator assigns users to organizations and branches.
5. Administrator assigns roles at organization or branch scope.
6. Administrator selects default branch for each user where needed.
7. Administrator verifies branch access using a test account.

### Control points

- Branch code is unique within the organization.
- User cannot select an unassigned branch.
- A branch manager cannot administer another branch unless explicitly authorized.
- Organization-wide roles remain limited to their organization.

## 4. User and Permission Administration

### Invite user

1. Administrator creates a user invitation.
2. System sends an invitation or creates a temporary activation flow.
3. User sets a password.
4. System stores only the password hash.
5. Administrator assigns roles and scope.
6. User logs in and selects an assigned branch.

### Change access

1. Administrator reviews the requested change.
2. Administrator adds, changes, expires, or removes a role assignment.
3. System records the actor, old assignment, new assignment, reason, and timestamp.
4. Existing sessions are revoked when the change is security-sensitive.

### Disable user

1. Administrator changes status to `DISABLED`.
2. System revokes active sessions.
3. User can no longer authenticate or access records.
4. Historical records and audit events remain unchanged.

## 5. Master Data Procedure

1. Authorized user opens the relevant master-data screen.
2. User creates or edits the record.
3. System validates code uniqueness and required fields.
4. User saves the record.
5. System writes an audit event.
6. When a record is no longer valid, user deactivates it instead of deleting it.

## 6. Component Template Procedure

1. Administrator creates a component group.
2. Administrator creates a template with a code and version.
3. Administrator defines attributes and data types.
4. Administrator defines required, repeatable, display, reference, and validation behavior.
5. Administrator assigns the template to trade directions.
6. Administrator tests rendering with a sample service order.
7. When the structure changes, administrator creates a new template version.
8. Existing service components retain their original version.

## 7. Quotation Procedure

### Create draft

1. Sales officer selects the organization and branch.
2. User selects customer and trade direction.
3. User enters places, transport options, container requirements, and lines.
4. User verifies all lines use the revision currency.
5. System calculates subtotal, discount, tax, and total.
6. User saves the draft.

### Send

1. User reviews the draft.
2. User sends the revision.
3. System validates required commercial data.
4. System changes status to `SENT`.
5. System prevents editing of the sent revision.
6. System records the sent timestamp and audit event.

### Revise

1. User opens a sent revision.
2. User selects `Create Revision`.
3. System copies the previous revision and children.
4. User edits the new draft.
5. User sends the new revision.
6. Previous revision remains available for history.

### Accept and convert

1. User records customer acceptance against the exact revision.
2. Authorized user selects `Convert to Service Order`.
3. System locks the revision.
4. System copies required commercial and operational snapshots.
5. System creates the service order and required components.
6. System records conversion.
7. System marks the revision converted.

### Exceptions

- Rejected, expired, or cancelled revisions cannot be converted.
- Duplicate conversion attempts return the existing conversion result.
- A sent revision cannot be edited directly.
- A customer change after acceptance requires a new revision and approval policy.

## 8. Service-Order Procedure

1. Operations officer reviews the converted order.
2. User confirms branch, customer, direction, and operational places.
3. User confirms container requirements.
4. User adds actual containers when numbers are available.
5. User adds repeatable components such as cargo, transport, documents, and milestones.
6. User enters template-defined values.
7. User uploads supporting files.
8. User completes each component after validation.
9. Manager reviews exceptions and may place the order on hold.
10. User marks the order completed after required components are complete.
11. Finance and operations review before administrative closure.

## 9. Service-Charge Procedure

1. User opens a service order and selects `New Service Charge`.
2. User selects document type and currency.
3. User adds fee lines.
4. User optionally links each line to an actual container.
5. System validates container ownership.
6. System calculates totals.
7. User issues the service charge.
8. System generates the customer-facing note or service document.
9. No journal is created.

### Convert to finance invoice

1. Authorized user selects `Create Finance Invoice`.
2. System copies the charge into a draft financial document.
3. System records the source relationship.
4. Finance user reviews and may edit the draft.
5. Finance user posts it separately.

## 10. Financial Document Procedure

### Create manual document

1. Finance user selects a document type.
2. User selects party, branch, currency, date, and optional service order.
3. User enters lines.
4. User selects or confirms account mappings.
5. System calculates the total.
6. User saves the draft.

### Post document

1. Finance user validates the draft.
2. System resolves an open accounting period.
3. System resolves posting rules.
4. System builds journal lines.
5. System verifies account ownership and postability.
6. System verifies debit equals credit.
7. Authorized user posts the document.
8. System creates the journal and audit event.
9. System marks the document `POSTED`.

### Receipt or payment

1. User creates a `CUSTOMER_RECEIPT` or `SUPPLIER_PAYMENT`.
2. User enters payment method, financial account, value date, and external reference.
3. User posts the document.
4. System records the cash/bank journal effect.
5. User allocates the payment to invoices or bills.

### Allocation

1. User selects a posted payment.
2. User selects one or more eligible posted target documents.
3. User enters allocation amounts.
4. System locks payment and target documents.
5. System validates remaining balances and currency.
6. System saves allocations.
7. System updates settlement reporting.

### Reversal

1. Finance manager selects a posted document.
2. Manager enters a reason.
3. System creates a reversal document and journal.
4. Original document remains immutable.
5. System records the relationship and audit event.

## 11. Accounting Period Procedure

1. Finance manager opens the accounting period.
2. Finance users post transactions during the period.
3. Manager reviews ledger, receivables, payables, and unallocated payments.
4. Manager reconciles bank and cash balances.
5. Manager closes the period with a reason.
6. System rejects future posting into the closed period.
7. Reopening requires elevated permission and an audit event.

## 12. Exception Handling

### Wrong branch

Stop processing, correct the branch assignment if authorized, and audit the correction. Do not silently move records by changing a filter.

### Missing required document

Keep the component pending or on hold. Record the missing document and notify the responsible user.

### Incorrect container number

Do not overwrite historical movement evidence. Correct using a controlled correction record or documented update policy.

### Failed posting

Keep the financial document in draft or an error state. No partial journal may remain.

### Unbalanced journal

Do not post. Display the imbalance and affected lines to the finance user.

### Overpayment

Keep the excess as unapplied balance or create a refund/credit process according to accounting policy. Do not silently allocate beyond the target balance.

### Duplicate request

Return the original idempotent result when the same command key is reused.

## 13. Evidence and Records

Required evidence includes:

- quotation revision history;
- customer acceptance;
- conversion record;
- service-order attachments;
- issued service charge;
- financial source relationship;
- journal entry;
- payment allocation;
- reversal reason;
- accounting-period closure;
- audit event.
