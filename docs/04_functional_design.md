# Functional Design

## 1. Purpose

This document defines how the platform behaves internally. It translates business requirements into module boundaries, use cases, validation rules, state transitions, authorization decisions, transaction boundaries, and error behavior.

## 2. Design Principles

1. Separate operational records, commercial service charges, financial documents, and accounting journals.
2. Enforce organization and branch scope on the server.
3. Use relational tables for stable references and vertical templates for dynamic operational data.
4. Treat sent quotation revisions and posted accounting records as immutable.
5. Prefer explicit user actions for conversion, posting, allocation, and reversal.
6. Preserve source snapshots so historical documents do not change when master data changes.

## 3. Module Boundaries

### 3.1 Identity and authorization

Owns users, credentials, sessions, roles, permissions, branch assignments, and authorization decisions.

It does not own business records. Other modules call authorization services before reading or changing records.

### 3.2 Organization and administration

Owns organizations, branches, system settings, accounting periods, document sequences, and administrative configuration.

### 3.3 Master data

Owns places, trade directions, container types, transport types, transport assets, fee types, parties, and party roles.

### 3.4 Configuration

Owns component groups, templates, attributes, versions, and trade-direction component assignments.

### 3.5 Quotation

Owns quotation aggregates, immutable revisions, revision children, and conversion eligibility.

### 3.6 Service order

Owns service-order aggregates, places, container requirements, actual containers, pricing snapshots, dynamic components, and operational statuses.

### 3.7 Service charge

Owns informational charges under service orders. It calculates commercial totals and generates customer-facing documents. It does not post accounting.

### 3.8 Finance

Owns reusable financial documents, financial lines, allocation, chart of accounts, posting rules, accounting periods, journal entries, and reversals.

### 3.9 Document management

Owns attachment metadata, object-storage operations, document versions, and secure downloads.

### 3.10 Reporting

Reads transactional data or reporting projections. It must not modify operational or accounting records.

## 4. Context Resolution

Every request must establish:

```text
current_user
current_organization
current_branch_or_all_branch_scope
current_permissions
request_id
correlation_id
```

The context middleware must:

1. Authenticate the request.
2. Resolve the organization requested by the token or context header.
3. Verify user membership and active assignment.
4. Resolve the selected branch.
5. Reject invalid organization/branch combinations.
6. Attach the authorization context to the request.

## 5. Authorization Decision

A policy check receives:

```text
user_id
permission_code
organization_id
branch_id
resource_type
resource_id
operation
```

It returns:

```text
allowed
reason
matched_role
matched_scope
```

Rules:

- Organization isolation is always checked.
- A null assignment branch means all branches in that organization.
- A non-null assignment branch permits only that branch.
- Record-level restrictions may further narrow access.
- The UI may hide unavailable actions, but the API remains authoritative.

## 6. Quotation Use Cases

### 6.1 Create quotation

1. Authorize `quotation.create` for the current branch.
2. Allocate a quotation number using the organization sequence.
3. Create quotation header.
4. Create revision 1 in `DRAFT`.
5. Save children in the same transaction.
6. Validate all references belong to allowed scope or shared master data.

### 6.2 Send revision

1. Lock the revision.
2. Verify status is `DRAFT`.
3. Recalculate totals.
4. Validate required commercial data.
5. Set status to `SENT`.
6. Set `sent_at`.
7. Write audit event.

### 6.3 Create revision

1. Verify source revision is eligible.
2. Lock the quotation.
3. Allocate the next revision number.
4. Copy revision children.
5. Create the new revision as `DRAFT`.
6. Mark the previous sent revision `SUPERSEDED` only when business policy requires it.
7. Audit the operation.

### 6.4 Accept revision

1. Verify the revision is `SENT`.
2. Confirm the accepting actor has permission.
3. Mark the selected revision `ACCEPTED`.
4. Mark competing active revisions `SUPERSEDED` if configured.
5. Update quotation aggregate status.
6. Audit acceptance.

### 6.5 Convert revision

1. Authorize `quotation.convert`.
2. Lock the accepted revision.
3. Reject if a conversion record already exists.
4. Create service-order header and number.
5. Copy customer, direction, currency, branch, places, containers, and pricing snapshots.
6. Resolve current component configuration for the direction.
7. Create required non-repeatable component instances.
8. Create quotation conversion record.
9. Mark revision `CONVERTED`.
10. Commit all changes atomically.

If any step fails, the entire conversion rolls back.

## 7. Service-Order Use Cases

### 7.1 Add actual container

1. Authorize branch access.
2. Verify the service order is not closed or cancelled.
3. Verify container requirement belongs to the same order.
4. Verify container number uniqueness.
5. Validate type, seal, and weights.
6. Create the actual container.
7. Audit creation.

### 7.2 Add component

1. Authorize `service_order.component.create`.
2. Verify the selected template is configured for the order direction.
3. Verify repeatability rules.
4. Copy template, group, version, required flag, and sequence snapshot.
5. Create component in `PENDING` status.
6. Audit creation.

### 7.3 Save component values

1. Verify component belongs to the service order in the current scope.
2. Verify each attribute belongs to the captured template version.
3. Validate data type and reference type.
4. Reject duplicate values for non-repeatable attributes.
5. Save typed values atomically.

### 7.4 Complete component

1. Verify component status permits completion.
2. Load captured template attributes.
3. Validate all required attributes.
4. Validate references and configured rules.
5. Verify required attachment rules.
6. Set status `COMPLETED` and completion metadata.
7. Audit completion.

## 8. Service-Charge Use Cases

### 8.1 Create service charge

1. Authorize charge creation for the service-order branch.
2. Verify service order is not cancelled.
3. Create charge in `DRAFT`.
4. Add fee lines.
5. Verify linked containers belong to the service order.
6. Calculate line and header totals.
7. Save the charge.

### 8.2 Issue service charge

1. Lock the draft charge.
2. Recalculate totals.
3. Validate customer and document fields.
4. Set status `ISSUED`.
5. Render customer-facing document from a snapshot.
6. Write audit event.
7. Do not create a journal entry.

### 8.3 Convert charge to financial invoice

1. Authorize finance-document creation.
2. Lock the service charge.
3. Copy charge lines into a draft `CUSTOMER_INVOICE`.
4. Create source relationship `SERVICE_ORDER_CHARGE`.
5. Preserve service-order and container references.
6. Allow finance users to edit the draft.
7. Do not post automatically.

## 9. Finance Use Cases

### 9.1 Create financial document

1. Authorize document creation.
2. Resolve organization and branch.
3. Validate document type and party role.
4. Allocate document number.
5. Create draft header and lines.
6. Calculate totals.
7. Save source references and attachments.

### 9.2 Post financial document

1. Authorize `financial_document.post`.
2. Lock the draft document.
3. Verify status is `DRAFT`.
4. Recalculate line and header totals.
5. Resolve an open accounting period.
6. Resolve posting rules.
7. Build journal lines.
8. Validate every account is postable and belongs to the organization.
9. Validate at least one debit and one credit.
10. Validate total debits equal total credits.
11. Insert journal entry and lines.
12. Insert document-posting relationship.
13. Set document status `POSTED`.
14. Write audit event.
15. Commit atomically.

### 9.3 Create manual journal

1. Authorize journal creation.
2. Create a draft journal with lines.
3. Validate account scope and dimensions.
4. Display balance difference.
5. Permit posting only when balanced and period is open.

### 9.4 Record payment or receipt

1. Create a common financial document with appropriate type.
2. Store payment method, financial account, reference, and value date on the document.
3. Create draft lines.
4. Apply payment posting rule.
5. Post to cash/bank and receivable/payable accounts.
6. Allocate separately to target documents.

### 9.5 Allocate payment

1. Authorize allocation.
2. Lock payment and target documents.
3. Verify both documents are posted.
4. Verify document types are compatible.
5. Verify currency or exchange-rate rules.
6. Verify available payment balance.
7. Verify target outstanding balance.
8. Insert allocation.
9. Recalculate settlement status.
10. Audit allocation.

### 9.6 Reverse document

1. Authorize reversal.
2. Lock the posted document and source journal.
3. Verify it is not already reversed.
4. Create reversal financial document.
5. Create opposite journal lines.
6. Post reversal in an open period.
7. Link original and reversal records.
8. Preserve original data.

## 10. Posting Rules

Posting rules are selected by organization, document type, and optionally fee type.

Examples:

```text
CUSTOMER_INVOICE:
  Dr Accounts Receivable
  Cr Service Revenue
  Cr Output Tax

SUPPLIER_BILL:
  Dr Expense or Cost Account
  Cr Accounts Payable

CUSTOMER_RECEIPT:
  Dr Bank or Cash
  Cr Accounts Receivable

SUPPLIER_PAYMENT:
  Dr Accounts Payable
  Cr Bank or Cash
```

If multiple lines use different accounts, the posting engine creates multiple revenue or expense credit/debit lines while preserving the total balance.

## 11. Error Handling

Use stable error codes:

```text
AUTH_REQUIRED
ACCESS_DENIED
ORGANIZATION_CONTEXT_REQUIRED
BRANCH_SCOPE_DENIED
INVALID_STATE_TRANSITION
REFERENCE_NOT_FOUND
REFERENCE_OUT_OF_SCOPE
DUPLICATE_NUMBER
DUPLICATE_CONVERSION
REQUIRED_VALUE_MISSING
INVALID_ATTRIBUTE_TYPE
PERIOD_CLOSED
JOURNAL_UNBALANCED
DOCUMENT_ALREADY_POSTED
DOCUMENT_ALREADY_REVERSED
ALLOCATION_EXCEEDS_BALANCE
CURRENCY_MISMATCH
```

Errors must include a request ID. Do not reveal another organization's record existence through detailed error messages.

## 12. Idempotency

The following commands require an idempotency key or equivalent unique command constraint:

- quotation conversion;
- financial-document posting;
- journal posting;
- payment allocation;
- reversal;
- document-number allocation.

Repeated requests with the same key should return the original result rather than create duplicates.

## 13. Concurrency and Locking

Lock records before:

- allocating revision numbers;
- converting quotations;
- posting documents;
- allocating payments;
- reversing entries;
- closing periods.

Use PostgreSQL row locks and unique constraints as the final duplicate-prevention mechanism.

## 14. Immutability

The following records cannot be edited after their final state:

- sent quotation revisions;
- converted quotation revisions;
- completed service components, except through controlled correction;
- posted financial documents;
- posted journal entries;
- closed accounting periods.

Corrections create new records linked to the original.

## 15. Reporting Rules

Reports use posted journal lines for accounting balances. Draft financial documents are excluded from ledger balances but may appear in operational work queues.

Every report must apply:

```text
organization filter
branch filter
permission filter
period/date filter
```
