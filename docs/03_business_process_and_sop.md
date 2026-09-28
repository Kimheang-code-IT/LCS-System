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

The runtime is single-tenant: there is no organization or branch scope. Access is
governed entirely by users, roles and permissions. A granted permission applies to
all records of that module.

## 2. Roles and Responsibilities

Roles are defined in code (`backend/app/core/permissions.py`). Only the Platform
Administrator is provisioned at first-run setup; every other role below is a
template that an administrator creates from Roles & Permissions.

| Role (code) | Main responsibilities |
|---|---|
| Platform Administrator (`PLATFORM_ADMIN`) | Full platform administration; built in |
| Administrator (`ADMINISTRATOR`) | Users, roles, configuration, reference data, settings, backup |
| Operations Manager (`OPERATIONS_MANAGER`) | Service-order and quotation review, configuration |
| Sales Officer (`SALES_OFFICER`) | Quotations, revisions, customer communication |
| Operations Officer (`OPERATIONS_OFFICER`) | Service orders, containers, components, documents, milestones |
| Finance Officer (`FINANCE_OFFICER`) | Financial drafts, receipts, payments, allocations, journals |
| Finance Manager (`FINANCE_MANAGER`) | Posting, reversals, chart of accounts, periods, approvals |
| Auditor (`AUDITOR`) | Read-only review and evidence collection |

## 3. First-Run Setup

### First-run setup (empty database)

1. On a freshly migrated database there are no users, so the app redirects to the
   first-run setup page (`/setup`).
2. The installer enters the administrator credential (and optional name/username),
   then submits.
3. System provisions the permission catalog, the built-in Platform Administrator
   role, the administrator credential, the current-year document sequences and the
   default app info/config. No finance or business data is seeded, and no other
   roles are created.
4. System signs the administrator in. Setup is accepted only while no user exists
   (`GET /api/v1/setup/status` / `POST /api/v1/setup/initialize`).

### Headless provisioning

The same provisioning is available without the browser (idempotent — re-run to
reset the password):

```bash
python -m app.create_admin --email admin@example.com --password 'Passw0rd!'
```

Additional users, roles and role assignments are administered from the UI or API
afterwards. Posting rules remain server-side; they are not exposed in the UI.

### Control points

- Setup can run only while no user exists.
- User codes, usernames and emails are unique.
- Role assignments support start and expiry dates; expired assignments grant no
  permissions.
- The Platform Administrator role cannot be reduced below the bootstrap
  administrator.

## 4. User and Permission Administration

### Create user

1. Administrator opens Users and creates the user (code, username, email, display
   name, locale, timezone).
2. Administrator sets the initial password (stored as an Argon2id hash).
3. Administrator assigns one or more roles.
4. User logs in and can change their own password.

### Change access

1. Administrator reviews the requested change.
2. Administrator adds, changes, expires, or removes a role assignment.
3. System records the actor and assignment metadata.
4. Existing sessions can be revoked for security-sensitive changes.

### Disable user

1. Administrator changes the user status to `DISABLED`.
2. System refuses authentication and active access.
3. Historical records and audit events remain unchanged.

Role administration uses a streamlined form: a role records a name and the
permission actions it grants; per-role scope/level and code/status columns are not
used. Permissions are enforced by the API.

## 5. Master Data Procedure

1. Authorized user opens the relevant master-data screen.
2. User creates or edits the record.
3. System validates code uniqueness and required fields.
4. User saves the record.
5. Status is changed from the record's row action menu: an **active** record can
   only be deactivated; a **deactivated** record can be reactivated or deleted.
6. The API refuses to delete an active reference record; deactivate it first.
   Status is not entered on the record form.

The same activate-before-delete rule applies to **service orders**, which use a
simple `ACTIVE` / `INACTIVE` status instead of a draft/closed lifecycle.

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

### Create or edit the draft

1. Sales officer selects the customer and trade direction.
2. User enters places, transport options, container requirements, and lines.
3. User verifies all lines use the revision currency.
4. System calculates subtotal, discount, tax, and total.
5. User selects **Save** to create the draft. While the draft has unsaved changes
   the only action is **Save changes**.
6. The saved draft stays editable and can be deleted from its row action menu.

### Accept and auto-convert

1. Once the draft has no unsaved changes, the primary action becomes **Accept**
   (Save changes and Accept are never shown at the same time).
2. User selects **Accept** and confirms.
3. System sends the revision (`DRAFT → SENT`), records acceptance
   (`SENT → ACCEPTED`) and converts it to a service order
   (`ACCEPTED → CONVERTED`) in a single action.
4. System locks the revision and copies the required commercial and operational
   snapshots, creates the service order and its required components, and records
   the conversion.
5. System opens the created service order.

### API-level steps (advanced)

The streamlined Accept flow is a convenience wrapper around the revision state
machine, which remains available through the API: `send` → `accept` → `convert`.

### Exceptions

- Rejected, expired, or cancelled revisions cannot be converted.
- A duplicate conversion attempt is rejected with `DUPLICATE_CONVERSION`; the
  existing service order is opened instead.
- A sent revision cannot be edited directly; create a new revision first.
- A customer change after acceptance requires a new revision and approval policy.

## 8. Service-Order Procedure

1. Operations officer reviews the converted order.
2. User confirms customer, direction, and operational places.
3. User confirms container requirements.
4. User adds actual containers when numbers are available.
5. User adds repeatable components such as cargo, transport, documents, and milestones.
6. User enters template-defined values.
7. User uploads supporting files.
8. User completes each component after validation.
9. The service order uses a simple **Active / Inactive** status. A saved order is
   **Active**; the status is changed from the record's row action menu, not the
   form.
10. An active order cannot be deleted; deactivate it first. Only an inactive order
    can be deleted.
11. Activity feeds and comments are not shown on service-order documents or lists.

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
2. User selects party, currency, date, and optional service order.
3. User enters lines.
4. User selects or confirms account mappings.
5. System calculates the total.
6. User saves the draft.

### Post document

1. Finance user validates the draft.
2. System resolves an open accounting period.
3. System resolves posting rules.
4. System builds journal lines.
5. System verifies account postability.
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
6. System rejects future posting into the closed period (`PERIOD_CLOSED`).
7. Reopening requires elevated permission and an audit event.

## 12. Exception Handling

### Missing required document

Keep the component pending or on hold. Record the missing document and notify the responsible user.

### Incorrect container number

Do not overwrite historical movement evidence. Correct using a controlled correction record or documented update policy.

### Failed posting

Keep the financial document in draft or an error state. No partial journal may remain.

### Unbalanced journal

Do not post. Display the imbalance and affected lines to the finance user
(`JOURNAL_UNBALANCED`).

### Overpayment

Keep the excess as unapplied balance or create a refund/credit process according to accounting policy. Do not silently allocate beyond the target balance (`ALLOCATION_EXCEEDS_BALANCE`).

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
