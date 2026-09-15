# Test Cases and User Acceptance Testing

## 1. Test Format

Each test includes preconditions, action, expected result, and important data effects. Automated tests should use isolated organization and branch fixtures.

## 2. Core and Authorization Tests

| ID | Preconditions | Action | Expected result |
|---|---|---|---|
| CORE-001 | Active user with valid password | Log in | Session and access tokens are created; success is audited |
| CORE-002 | Active user | Enter invalid password repeatedly | Login is rejected; attempts are recorded; throttling/lock policy applies |
| CORE-003 | Revoked session | Use refresh token | Request is rejected |
| CORE-004 | User assigned organization-wide finance role | Request records from two branches in same organization | Both branches are accessible where permission allows |
| CORE-005 | User assigned operations role to Branch A | Request Branch A order | Request succeeds |
| CORE-006 | Same user, Branch B order | Request Branch B order | Request is denied or record is not exposed |
| CORE-007 | Branch A user changes `branch_id` query parameter to Branch B | Query orders | Server-side scope still denies Branch B |
| CORE-008 | User from Organization A | Request Organization B record ID | Record is not exposed |
| CORE-009 | User assigned Branch A and B | Switch active branch | Only A and B are selectable |
| CORE-010 | Role assignment expired | Request protected resource | Permission is denied |
| CORE-011 | Branch code exists in Organization A | Create same code in Organization A | Request is rejected |
| CORE-012 | Branch code exists in Organization A | Create same code in Organization B | Request succeeds |
| CORE-013 | Branch manager | Attempt to manage another branch | Request is denied |
| CORE-014 | User without credential permission | Retrieve customs password | Request is denied and audited |
| CORE-015 | Authorized user with reason | Retrieve customs password | Secret is revealed once through protected response and event is audited |

## 3. Quotation Tests

| ID | Preconditions | Action | Expected result |
|---|---|---|---|
| QUO-001 | User has quotation-create permission | Create quotation with two containers and three lines | Draft quotation and revision are created |
| QUO-002 | Draft revision | Send revision with valid data | Revision becomes `SENT` and becomes immutable |
| QUO-003 | Sent revision | Attempt direct update | Request is rejected |
| QUO-004 | Sent revision | Create new revision | New draft copies child data with a new revision number |
| QUO-005 | Sent revision | Accept it | Exact revision becomes `ACCEPTED` |
| QUO-006 | Accepted revision | Convert with idempotency key | One service order and one conversion record are created |
| QUO-007 | Accepted revision already converted | Repeat conversion with same key | Original result is returned; duplicate order is not created |
| QUO-008 | Rejected revision | Attempt conversion | Request is rejected |
| QUO-009 | Two currencies in line data | Save revision | Request is rejected or line currency is normalized to header currency |

## 4. Service-Order Tests

| ID | Preconditions | Action | Expected result |
|---|---|---|---|
| ORD-001 | Converted order | Add actual container | Container is created with order scope and unique number |
| ORD-002 | Actual container in Order A | Link it to Order B charge | Request is rejected |
| ORD-003 | Direction has required non-repeatable component | Create service order | Required component is created automatically |
| ORD-004 | Direction has repeatable component | Add two instances | Both instances are created with correct sequence |
| ORD-005 | Required attribute missing | Complete component | Completion is rejected |
| ORD-006 | Attribute has wrong data type | Save value | Validation error is returned |
| ORD-007 | Component template later changes | Read existing component | Original template version remains visible |
| ORD-008 | Gross weight less than net weight | Save container | Request is rejected |
| ORD-009 | Component attachment upload | Upload and link file | Metadata and link are created; file is retrievable by authorized user |

## 5. Service-Charge Tests

| ID | Preconditions | Action | Expected result |
|---|---|---|---|
| CHG-001 | Open service order with two actual containers | Create four fee lines | Charge is saved and totals are calculated |
| CHG-002 | Charge line references another order's container | Save charge | Request is rejected |
| CHG-003 | Draft charge | Issue charge | Customer-facing document is generated; no journal exists |
| CHG-004 | Issued charge | Create finance invoice | Draft financial invoice is created and source is recorded |
| CHG-005 | Generated financial draft | Edit line amount | Draft changes; original service charge remains unchanged |

## 6. Finance and Accounting Tests

| ID | Preconditions | Action | Expected result |
|---|---|---|---|
| FIN-001 | Finance user | Create standalone income | Common financial-document model is used |
| FIN-002 | Finance user | Create standalone expense | Common financial-document model is used; no type-specific detail table is required |
| FIN-003 | Draft customer invoice and open period | Post invoice | Journal is created and balanced: Dr AR, Cr Revenue/tax |
| FIN-004 | Draft supplier bill and open period | Post bill | Journal is created and balanced: Dr Expense, Cr AP |
| FIN-005 | Posted customer invoice | Post customer receipt | Journal is Dr Bank/Cash, Cr AR |
| FIN-006 | Posted receipt for 1,000 USD | Allocate 700 USD to invoice | Allocation succeeds; remaining payment is 300 USD |
| FIN-007 | Invoice outstanding balance 550 USD | Allocate 600 USD | Request is rejected unless overpayment policy is enabled |
| FIN-008 | Receipt allocated to customer invoice | Allocate to supplier bill | Request is rejected |
| FIN-009 | Draft manual journal with unequal totals | Post | Request is rejected with imbalance |
| FIN-010 | Draft document in closed period | Post | Request is rejected |
| FIN-011 | Posted document | Edit amount | Request is rejected |
| FIN-012 | Posted document | Reverse with authorized manager | Reversal document and opposite journal are created |
| FIN-013 | Posted document | Reverse twice | Second reversal is rejected |
| FIN-014 | Two concurrent posting requests | Post same document | One succeeds; duplicate request returns original result or is rejected safely |
| FIN-015 | Foreign-currency document | Post | Transaction and base amounts are stored using configured exchange rate |

## 7. Reporting Tests

| ID | Preconditions | Action | Expected result |
|---|---|---|---|
| REP-001 | Posted journals in two branches | View branch report | Only selected branch is shown to branch-scoped user |
| REP-002 | Organization-wide finance user | View ledger | All authorized branches are included |
| REP-003 | Draft and posted invoices | View ledger | Only posted journals affect ledger balances |
| REP-004 | Partial payment | View receivable report | Outstanding balance equals invoice less allocations |
| REP-005 | Unbalanced draft journal | View trial balance | Draft is excluded from posted trial balance |

## 8. User Acceptance Scenarios

### UAT-001 Import order

Sales creates a quotation with multiple containers, sends a revision, records acceptance, and explicitly converts it. Operations adds actual containers and cargo/transport components. The order reaches completion without exposing another branch's records.

### UAT-002 Service charge without accounting

Operations creates a container-linked service charge, issues a customer-facing note, and confirms that no accounting journal exists.

### UAT-003 Invoice conversion

Finance converts the service charge into a draft invoice, changes one line, posts it, and verifies the balanced journal and source relationship.

### UAT-004 Customer receipt

Finance creates a receipt, posts it to bank and accounts receivable, allocates it partially, and confirms the outstanding balance.

### UAT-005 Standalone expense

Finance creates an office expense unrelated to a service order, posts it against cash, and confirms it appears in the general ledger.

### UAT-006 Branch security

A Phnom Penh operations user attempts to access Bavet data by changing URL and query parameters. Every attempt is denied.

### UAT-007 Period close

Finance manager closes a month. Subsequent postings into that month fail, while a reversal in the next open period succeeds.

### UAT-008 Audit review

Auditor searches for quotation conversion, password retrieval, invoice posting, payment allocation, and reversal events and verifies actor, branch, timestamp, and result.
