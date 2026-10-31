# Data Model

## Authoritative field and constraint reference

[Generated PostgreSQL DDL](06_database_design.sql) is the field-by-field reference for
types, keys, indexes, constraints, relationships, and table/column descriptions.
It is generated from models; this foundation does not introduce a second schema listing.
Descriptions live in `backend/scripts/schema_descriptions.py`.

## Entity groups and relationships

| Group | Principal entities / fields and relationships |
|---|---|
| Identity | Users, credentials, sessions, refresh-token hashes; roles and `casbin_rule` policies |
| Reference | Business parties ↔ party roles; place roles, trade directions, transport/container types, currencies and rates |
| Configuration | Component attributes, groups, tabs and assignments; configuration versions; JSON module records |
| Quotation | Quotation → revisions → route stops, container requirements, pricing lines; conversion reference to service order |
| Operations | Service order → routes, requirements, actual containers, component snapshots/rows, attachments and service charges |
| Financial document | Document number/type/date/status/party/currency/source; lines and posting relationship |
| Accounting | Chart of accounts, financial accounts, periods, posting rules; journal → debit/credit lines |
| Settlement | Allocations connect posted receipts/payments with eligible posted invoices/bills |
| Governance | Audit events, archive records, settings, sequences, integration run records |

Actual table/column spelling and nullability are defined by the linked generated DDL and
`backend/app/modules/*/models.py`; conceptual labels above are not API field contracts.
Preserve legacy references even when a collection is no longer exposed, such as old places.
Required conversion data includes customer, direction, currency, source revision, routes,
container requirements, pricing and configured operational snapshots; S02 verifies actual copying.

## Financial data integrity — canonical invariants

Non-negotiable, regardless of the task or level:

- **Debit equals credit** for every journal. Posting is atomic: journal, lines, posting link
  and document status commit together or not at all.
- **Posted history is immutable.** Corrections use `reverse_document`, never an edit or a
  delete — enforced in the service layer *and* by PostgreSQL triggers
  (`fn_guard_journal_entry`, `fn_guard_journal_line`).
- **Closed periods reject new postings**; entries must fall inside an `OPEN` period (deferred
  constraint trigger `fn_validate_journal_post`).
- **No duplicate posting, no over-allocation** — unique `financial_document_postings` and the
  `fn_guard_allocation` guard.
- **Money is `NUMERIC`, decoded as `Decimal`.** Never `float`.
- **Historical rates are preserved.** A posting snapshots its own `exchange_rate` and stores
  `base_debit_amount` / `base_credit_amount`; never recompute a posted amount from a newer rate.
- **Posting rules come from `posting_rules`**, resolved per `(document_type, fee_type_id)` with
  a NULL-fee default and the highest `priority` winning within a tier. `DEFAULT_ACCOUNTS` in
  `finance/service.py` is a last-resort fallback, not the configuration. `PostingRuleResolver`
  (`finance/posting_rules.py`) answers *which accounts*; `AccountingPostingService`
  (`finance/posting.py`) answers *what journal* from the `STRATEGIES` table. No account id
  belongs in either file — add the type to `STRATEGIES` and `DOCUMENT_TYPE_LABELS` instead of
  special-casing a document type.
- **Reports read posted data only** and must be reconciled before being called correct (trial
  balance nets to zero; AR/AP match their control accounts).

Closed periods reject posting for every role. Elevated permission allows the existing
authorized, audited reopening process; it does not imply a posting bypass.
Service charges are informational; issuing one creates neither a journal nor an automatic
financial draft. Explicit conversion creates one source-linked financial draft.
Historical tax fields do not authorize new tax workflows or deletion of historical data.

## Other constraints

Document numbers are transactional and unique within the existing type/year scope.
Actual containers are distinct from requirements; validate ownership and weight boundaries.
Snapshot configuration for historical service orders instead of applying current definitions
retroactively. Protect referenced records from destructive deletion.
Exact workflow guards are in [record lifecycle](04-record-workflow-lifecycle.md).

## Migration strategy

Use additive Alembic revisions under `backend/alembic/versions/` with working `downgrade()`.
Register models in `alembic/env.py` and applicable reset/bootstrap lists.
Inspect callers, permission/contract tests, and historical references before schema changes.
Regenerate SQL from `backend/` with `uv run python scripts/generate_schema_docs.py`;
the dump wrapper is compatibility-only. Check with `--check`; never hand-edit SQL.
Production runs migrations explicitly before replacing the serving images.
No models, migrations, or generated SQL were changed by foundation creation.

## Legacy requirement traceability

Stable identifiers migrated from the reviewed SRS. These are requirements, not assertions
that implementation or acceptance has passed. The approved LCS scope/priorities govern;
retired IDs and deferred advanced capabilities do not create extra pages or new workflows.

| ID | Requirement |
|---|---|
| FR-111 | The finance module shall use one reusable financial-document table for invoices, bills, receipts, payments, income, expenses, transfers, and adjustments. |
| FR-112 | A financial document shall contain document number, type, date, status, party, currency, description, reference, and amount. |
| FR-113 | A financial document shall support multiple lines. |
| FR-114 | A financial line shall contain description, quantity, unit amount, discount, tax, amount, optional fee type, optional service order, optional container, and optional account mapping. |
| FR-115 | Users shall manually create financial documents unrelated to service orders. |
| FR-116 | Users shall create financial documents from service-order charges or other operational sources. |
| FR-117 | The system shall record source relationships for generated financial documents. |
| FR-118 | Financial documents shall support draft, posted, cancelled, and reversed states. |
| FR-119 | Draft financial documents shall be editable by authorized users. |
| FR-120 | Posted financial documents shall be immutable. |
| FR-121 | The system shall use reversal or adjustment documents for corrections. |
| FR-122 | The system shall apply configurable posting rules for routine document types. |
| FR-123 | The system shall allow authorized users to create manual journal entries when posting rules are insufficient. |
| FR-124 | A customer receipt shall be represented as a financial document. |
| FR-125 | A supplier payment shall be represented as a financial document. |
| FR-126 | A financial document may contain payment method, financial account, value date, and external reference fields. |
| FR-127 | The system shall support cash, bank transfer, cheque, card, mobile wallet, and other payment methods. |
| FR-128 | The system shall support financial accounts such as cash, bank, petty cash, and wallets. |
| FR-129 | Payment settlement shall use a separate allocation table. |
| FR-130 | One payment shall be allocatable to multiple target documents. |
| FR-131 | One target document shall be settleable by multiple payments. |
| FR-132 | The system shall support partial payment. |
| FR-133 | The system shall reject allocation greater than available payment balance. |
| FR-134 | The system shall reject allocation greater than the target outstanding balance. The historical optional overpayment exception is superseded by approved LCS-007; unapplied excess must not be silently over-allocated. |
| FR-135 | The system shall validate customer receipts against eligible customer invoices. |
| FR-136 | The system shall validate supplier payments against eligible supplier bills. |
| FR-137 | The system shall maintain a single global chart of accounts. |
| FR-138 | The system shall support account hierarchy and parent accounts. |
| FR-139 | The system shall distinguish postable and non-postable accounts. |
| FR-140 | The system shall maintain global accounting periods. |
| FR-141 | The system shall reject posting into a closed accounting period. |
| FR-142 | The system shall create journal entries when eligible financial documents are posted. |
| FR-143 | A journal entry shall contain one or more journal lines. |
| FR-144 | Every posted journal entry shall contain at least one debit and one credit. |
| FR-145 | Every posted journal entry shall satisfy total debits equal total credits. |
| FR-146 | A journal line shall reference one postable account. |
| FR-147 | A journal line shall support party, service order, and source-document dimensions. |
| FR-148 | The system shall support base-currency amounts when the transaction currency differs from the base currency. |
| FR-149 | The system shall prevent editing posted journal entries. |
| FR-150 | Reversal journals shall link to the original journal. |
| FR-151 | The system shall support revenue, expense, receivable, payable, cash, bank, tax, equity, and adjustment account mappings. |
| FR-152 | The system shall report ledger balances by account, party, service order, and period. |
| FR-160 | The system shall allocate quotation, service-order, charge, financial-document, receipt, payment, and journal numbers using transactional sequences. |
| FR-161 | Number sequences shall be scoped by document type and year. |
| FR-162 | The system shall prevent duplicate numbers under concurrent requests. |
| FR-163 | Administrators shall configure global application settings. |
| FR-164 | Global settings shall apply across the platform; there are no organization or branch overrides. |
| FR-165 | The system shall preserve the configuration used for historical records where required. |
| INV-001 | Effective permissions are the permissions granted by the user's single active role; an expired assignment contributes nothing. |
| INV-002 | A request without an active user context or the required permission must be denied server-side; the platform is single-tenant and has no organization or branch scope. |
| INV-003 | A sent quotation revision cannot be edited. |
| INV-004 | Only an accepted quotation revision can be converted. |
| INV-005 | A service-order charge does not create accounting merely by being issued. |
| INV-006 | A posted financial document cannot be edited. |
| INV-007 | A posted journal must balance. |
| INV-008 | A journal line must use a postable account. |
| INV-009 | A closed accounting period cannot accept posting. |
| INV-010 | Payment allocation cannot exceed configured settlement limits. |
| INV-011 | A financial document source must reference an existing source record of the declared type. |
| INV-012 | Actual container numbers are unique according to the configured historical-reuse policy. |
| INV-013 | Required dynamic component attributes must be present before completion. |
| INV-014 | Sensitive credentials must never be returned in ordinary list or detail responses. |
