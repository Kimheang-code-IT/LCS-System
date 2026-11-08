# Application Flow

## Main user journeys

1. Administrator completes first-run setup on an empty deployment and manages roles/reference
   configuration through existing pages. Setup does not establish finance readiness by itself.
2. Sales saves/submits a quotation and explicitly creates source-linked Service Orders;
   the offer can be reused. Changed commercial terms preserve revision history.
3. Operations receives the service order with snapshots, records actual containers and dynamic
   components, and attaches authorized documents.
4. Operations issues service charges. Finance explicitly creates/reviews the financial draft.
5. Finance posts invoices/bills; authorized receipt/payment posting and allocation settle them.
6. Finance uses reversals/adjustments for corrections, reconciles accounts and closes periods.
7. Managers/auditors review permitted operational and posted financial reporting.

## System flows and boundaries

Quotation → Service Order → Operational Execution → Service Charges → Financial Documents
→ Payment/Allocation → Accounting → Reports.

This business journey does not imply that accounting waits until payment: invoice and
receipt/payment posting each produce their appropriate accounting effects.
Charge issue alone has no journal effect. Financial-draft creation is distinct from posting.
Reports distinguish operational/quoted/draft amounts from posted accounting results.
Source relationships and historical snapshots preserve traceability throughout.

Login/session → page/action visibility → API authentication and Casbin guard → service
validation/transaction → response → localized field/page messages or confirmed success.
Access through a direct URL or API must enforce the same underlying permissions.

## Supporting routes and exceptional paths

Authentication/recovery, create/edit/detail, print and error routes support the 44-page scope.
They are not new business pages. Preserve them during documentation migration.
Refused actions, invalid fields, duplicate commands, missing references, closed periods,
over-allocation and immutable-record changes have explicit persistent errors.
State guards are in [lifecycle](business-rules.md), API errors in
[API specification](../01-architecture/api-design.md), and detailed SOP in
[business process](workflows.md#operating-procedures).

## Localization and print journey

English, Khmer and Simplified Chinese apply to navigation, forms, tables, dialogs and
understandable validation/errors. Language switching must not corrupt in-progress workflows.
Applicable business documents print English–Khmer independent of UI language, with correct
company/customer details, amounts, fonts, wrapping and no clipping/overlap.
Historical tax references do not expand the approved tax-workflow scope.

## Operating procedures

Consolidated from the reviewed SOP. Role names describe responsibilities; existing Casbin
capabilities govern each action. No new approval workflow is introduced. Source checks:
`quotations/service.py::convert_revision` (reuse/retry), `operations/service.py::save_service_order`
and `finish_service_order` (snapshot/Finish), `core/bootstrap.py` (setup), `core/permissions.py` (single role).
The procedure remains a verification specification; cleanup does not establish acceptance.

### 3. First-Run Setup

#### First-run setup (empty database)

1. On a freshly migrated database there are no users, so the app redirects to the
   first-run setup page (`/auth/setup`).
2. The installer enters the administrator credential (and optional name/username),
   then submits.
3. System provisions the permission catalog, the built-in Platform Administrator
   role, the administrator credential, the default currency catalog, the default
   Party Roles and Place Roles, the current-year document sequences and the
   default app info/config. No finance or transactional data (accounts, periods,
   parties, documents) is seeded, and no other user roles are created.
4. System signs the administrator in. Setup is accepted only while no user exists
   (`GET /api/v1/auth/setup/status` / `POST /api/v1/auth/setup/initialize`).

Lost administrator access is recovered through the forgot-password flow
(`/auth/forgot-password/...` email codes) or by an administrator setting the
password per user (`POST /api/v1/users/{user_id}/password`).

Additional users, roles and role assignments are administered from the UI or API
afterwards. Posting rules are configured in the Posting Rules screen; the service
layer falls back to `DEFAULT_ACCOUNTS` only when no rule matches.

#### Control points

- Setup can run only while no user exists.
- User codes, usernames and emails are unique.
- A user holds exactly one role; the effective permissions are that role's
  direct grants (roles do not inherit from other roles).
  Removing the role stops it contributing on the next request.
- The Super Administrator role cannot be reduced below the bootstrap
  administrator, and its wildcard grant cannot be removed.

### 4. User and Permission Administration

#### Create user

1. Administrator opens Users and creates the user (code, username, email, display
   name, locale, timezone).
2. Administrator sets the initial password (stored as an Argon2id hash).
3. Administrator assigns the user exactly one active role.
4. User logs in and can change their own password.

#### Change access

1. Administrator reviews the requested change.
2. Administrator replaces the user's single Casbin role assignment; preserve the audit evidence of the change.
3. System records the actor and assignment metadata.
4. Existing sessions can be revoked for security-sensitive changes.

#### Disable user

1. Administrator changes the user status to `DISABLED`.
2. System refuses authentication and active access.
3. Historical records and audit events remain unchanged.

Role administration uses a dedicated form: a role records a name and the
permission actions it grants; per-role scope/level and code/status columns are not
used. Permissions are enforced by the API.

### 5. Master Data Procedure

1. Authorized user opens the relevant master-data screen.
2. User creates or edits the record.
3. System validates code uniqueness and required fields.
4. User saves the record.
5. Status is changed from the record's row action menu: an **active** record can
   only be deactivated; a **deactivated** record can be reactivated or deleted.
6. The API refuses to delete an active reference record; deactivate it first.
   Status is not entered on the record form.

Service-order inactive/deletion controls remain, alongside the explicit operational Finish
command. Finish is not financial closure; see [lifecycle](business-rules.md).

#### Party Roles

1. Authorized user opens **Master Data > Party Roles**.
2. User creates a role with a unique code, a unique name, an optional description,
   and the default active status.
3. Active roles appear immediately in the Business Parties role selector; inactive
   roles appear only when the list is filtered to inactive records.
4. A business party can hold multiple roles; the same role cannot be assigned to
   the same party twice.
5. Renaming a role updates every party that references it because parties store
   the role id, not a copied label.
6. A role assigned to at least one party cannot be deleted. Deactivate it instead;
   existing assignments remain readable.

### 6. Component Template Procedure

1. Administrator creates a component group.
2. Administrator creates a template with a code and version.
3. Administrator defines attributes and data types.
4. Administrator defines required, repeatable, display, reference, and validation behavior.
5. Administrator assigns the template to trade directions.
6. Administrator tests rendering with a sample service order.
7. When the structure changes, administrator creates a new template version.
8. Existing service components retain their original version.

### 7. Quotation Procedure

#### Create or edit the draft

1. Sales officer selects the customer and trade direction.
2. User enters route stops, transport options, container requirements, and lines.
3. User verifies all lines use the revision currency.
4. System calculates subtotal, discount, tax, and total.
5. User selects **Save** to create the draft. While the draft has unsaved changes
   the only action is **Save changes**.
6. The saved draft stays editable and can be deleted from its row action menu.

#### Submit and preserve history

1. Save Changes persists valid edits; Submit validates and records the commercial offer.
2. No new Send/Accept steps are required. Preserve legacy states/history.
3. Re-Quotation creates a new draft revision for changed submitted terms; re-quotation
   from a Service Order creates a new quotation and leaves the original order unchanged.

#### Convert to service order

1. A user with the existing conversion capability selects the quotation/revision.
2. System creates an SO with copied commercial/operational snapshots and source relationship;
   capture the revision actually used. Another intentional SO can reuse the same offer.
3. System opens the created service order.
4. Same-command retries reuse the idempotency key and original order; another intentional
   booking gets a fresh key. Changed quotation/SO pricing never rewrites prior SO snapshots.

#### API-level steps

Save Changes / Submit / Convert / Re-Quotation are the intended actions. Existing legacy
send/accept endpoints remain compatibility paths, not required new UI steps.

#### Exceptions

- Backend conversion currently has no revision-state gate; test eligible/ineligible source
  handling in S02 rather than claiming the intended Submit-first journey is enforced.
- Same-key/different-source requests must not return an unrelated booking; verify replay scope.
- Submitted and legacy sent/accepted history is preserved; changed terms use a new draft.

### 8. Service-Order Procedure

1. Operations officer reviews the converted order.
2. User confirms customer, direction, and operational route stops. Each stop uses
   a configured Place Role (for example port, warehouse, or checkpoint) and a
   free-text location; the separate Places collection is no longer editable, but
   legacy rows are retained for historical route references.
3. User confirms container requirements.
4. Actual Containers starts empty. Add real container number/type/seal/weights when known;
   quoted requirements and physical boxes are separate records.
5. User adds repeatable components such as cargo, transport, documents, and milestones.
6. User enters template-defined values.
7. User uploads supporting files.
8. User completes each component after validation.
9. Save persists operational data and allowed copied-price overrides. Finish records
   FINISHED with actor/time and locks prohibited operational edits. Neither creates a journal
   nor requires full settlement. Existing inactive controls remain.
10. An active order cannot be deleted; deactivate it first. Only an inactive order
    can be deleted.
11. Activity feeds and comments are not shown on service-order documents or lists.

### 9. Service-Charge Procedure

1. User opens a service order and selects `New Service Charge`.
2. User selects document type and currency.
3. User adds fee lines.
4. User optionally links each line to an actual container.
5. System validates container ownership.
6. System calculates totals.
7. User issues the service charge.
8. System generates the customer-facing note or service document.
9. Issuing the charge does not create a finance draft and does not post accounting.
10. An authorized finance user may select `Create Finance Invoice` to create the draft.

#### Convert to finance invoice

1. An authorized user selects `Create Finance Invoice` on an issued charge.
2. System copies the charge into a draft financial document only when one does not already exist.
3. System records the source relationship.
4. Finance user reviews and may edit the draft.
5. Finance user posts it separately.

#### Automatic service-order finance reporting

1. The captured quotation revision provides quoted commercial value.
2. Issued service charges provide confirmed charge value; drafts are reported separately.
3. Draft customer invoices provide pending revenue.
4. Posted customer invoices provide recognized job revenue.
5. Posted supplier bills provide recognized job cost.
6. The system calculates gross profit, margin, and uninvoiced issued charges without browser-side aggregation.

### 10. Financial Document Procedure

#### Create manual document

1. Finance user selects a document type.
2. User selects party, currency, date, and optional service order.
3. User enters lines.
4. User selects or confirms account mappings.
5. System calculates the total.
6. User saves the draft.

#### Post document

1. Finance user validates the draft.
2. System resolves an open accounting period.
3. System resolves posting rules.
4. System builds journal lines.
5. System verifies account postability.
6. System verifies debit equals credit.
7. Authorized user posts the document.
8. System creates the journal and audit event.
9. System marks the document `POSTED`.

#### Receipt or payment

1. User creates a `CUSTOMER_RECEIPT` or `SUPPLIER_PAYMENT`.
2. User enters payment method, financial account, value date, and external reference.
3. User posts the document.
4. System records the cash/bank journal effect.
5. User allocates the payment to invoices or bills.

#### Allocation

1. User selects a posted payment.
2. User selects one or more eligible posted target documents.
3. User enters allocation amounts.
4. System locks payment and target documents.
5. System validates remaining balances and currency.
6. System saves allocations.
7. System updates settlement reporting.

#### Reversal

1. Finance manager selects a posted document.
2. Manager enters a reason.
3. System creates a reversal document and journal.
4. Original document remains immutable.
5. System records the relationship and audit event.

### 11. Accounting Period Procedure

1. Finance manager opens the accounting period.
2. Finance users post transactions during the period.
3. Manager reviews ledger, receivables, payables, and unallocated payments.
4. Manager reconciles bank and cash balances.
5. Target: manager reviews blocking errors/warnings and confirms closing through the backend;
   the rich review workflow remains unimplemented. See [closing specification](accounting-and-posting.md#smart-accounting-period-closing).
6. System rejects future posting into the closed period (`PERIOD_CLOSED`).
7. Reopening requires elevated permission and an audit event.

### 12. Exception Handling

#### Missing required document

Do not complete a component with missing required values/documents. Report the missing evidence to the responsible user without inventing a new hold status or mandatory notification integration.

#### Incorrect container number

Do not overwrite historical movement evidence. Correct using a controlled correction record or documented update policy.

#### Failed posting

Keep the unposted document in its existing draft state. No partial journal may remain; do not invent a new error status.

#### Unbalanced journal

Do not post. Display the imbalance and affected lines to the finance user
(`JOURNAL_UNBALANCED`).

#### Overpayment

Keep excess unapplied or use an existing authorized correction/refund mechanism where applicable; do not invent an unapproved workflow. Do not silently allocate beyond the target balance (`ALLOCATION_EXCEEDS_BALANCE`).

#### Duplicate request

Use the command-specific retry contract: same-key quotation conversion returns the original result; other commands may use explicit duplicate guards. Never promise universal key support.

### 13. Evidence and Records

Required evidence includes:

- quotation revision history;
- submission and any preserved legacy customer acceptance evidence;
- conversion record;
- service-order attachments;
- issued service charge;
- financial source relationship;
- journal entry;
- payment allocation;
- reversal reason;
- accounting-period closure;
- audit event.
