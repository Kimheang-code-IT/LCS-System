# API Documentation

## 1. Scope and Source of Truth

The backend is a FastAPI application. Every business endpoint is mounted under
`/api/v1`; the OpenAPI document is available at `/openapi.json` when the API is
running with its documentation routes enabled. The routers in
`backend/app/modules/*/router.py` are the source of truth; this document is the
stable catalogue and the contract the Nuxt client relies on.

Requests and responses use JSON. Authentication is a JWT access token sent as
`Authorization: Bearer <token>`, or the HttpOnly access cookie set by the login
endpoint. Login/refresh return `data.user`, `expires_in` and authoritative Unix
`expires_at`; `access_token` and `token_type` are included only when
`AUTH_RETURN_TOKENS=true`. Refresh credentials are never returned in JSON.
`POST /auth/refresh` accepts an empty JSON object and authenticates only with
the HttpOnly refresh cookie; body/query refresh tokens are unsupported.
Refresh tokens are opaque random values, hashed in PostgreSQL and rotated
atomically on the same `user_sessions` row. Consumed hashes are retained in
`used_refresh_tokens`. A duplicate within five seconds receives
`409 REFRESH_CONFLICT` with no credential or cookie changes; later reuse revokes
that session and records `REFRESH_REPLAY`. Browser requests that
authenticate with cookies must also send the `X-CSRF-Token` header with the value
of the `XSRF-TOKEN` cookie; the middleware rejects a missing or mismatched token
with `CSRF_VALIDATION_FAILED`.

Refresh/logout require the signed CSRF pair even when an Authorization header
is present, and reject an Origin outside the configured trusted origins.
Only `401 ACCESS_TOKEN_EXPIRED` authorizes a renewal/retry. `SESSION_EXPIRED`,
`SESSION_REVOKED` and `SESSION_INVALID` require sign-in; refresh 401 responses
clear auth cookies. Invalid signatures, issuer/audience errors, business errors
and permission denials do not trigger automatic renewal. Every protected
request validates the token's `sid` against the session and checks user status
and token version. `X-User-Activity: 1` marks a user-driven API operation;
activity writes are throttled to 15 seconds. Refresh, health checks, `/auth/me`
and unmarked passive API calls never extend idle time.

`tests/test_frontend_api_contract.py` statically checks every endpoint referenced
by the frontend constants against the FastAPI route table, so a frontend call
that has no backend route fails the backend suite.

## 2. Envelope, Pagination, and Errors

Success responses are wrapped:

```json
{"data": {"id": 42, "code": "ACME"}}
```

Collections add pagination metadata:

```json
{"data": {"items": [], "meta": {"page": 1, "page_size": 25, "total": 0}}}
```

List endpoints accept `page` (1-based) and `page_size`; master-data and document
lists also accept `search`, `sort_by`, `sort_dir`, `status`, and endpoint-specific
filters. Unknown filters are rejected rather than ignored.

Errors use one envelope and never expose a stack trace:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Please correct the highlighted fields.",
  "request_id": "…",
  "field_errors": {"code": "Code is required."}
}
```

`field_errors` contains canonical field paths; repeatable rows use
`table.<row>.<column>`. A validation error is returned as a field error, not as a
success toast. `request_id` is also returned in the `X-Request-Id` response
header.

Money is handled as `Decimal` on the server and serialized without a binary-float
round trip. Dates are ISO 8601. Identifiers are integers unless a route documents
a document number or code.

## 3. Endpoint Catalogue

Paths below are relative to `/api/v1`. “Purpose” is the OpenAPI summary; the
handler and its request/response schemas are in the linked router.

### Authentication and Access

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/change-password` | Change Password |
| POST | `/auth/forgot-password` | Forgot Password |
| POST | `/auth/forgot-password/resend` | Resend Code |
| POST | `/auth/forgot-password/reset` | Reset Password |
| POST | `/auth/forgot-password/verify` | Verify Code |
| POST | `/auth/login` | Login |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Me |
| DELETE | `/auth/profile/avatar` | Remove Profile Avatar |
| POST | `/auth/profile/avatar` | Update Profile Avatar |
| POST | `/auth/refresh` | Refresh |
| POST | `/auth/setup/initialize` | Setup Initialize |
| GET | `/auth/setup/status` | Setup Status |

### Users, roles and permissions

Authorization decisions come from Casbin (`docs/09_roles_and_permissions.md`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/permissions` | List Permissions (flat catalog with `module`) |
| GET | `/permissions/catalog` | Permission Matrix Metadata (pages, actions, groups, roles, modules) |
| DELETE | `/roles` | Delete Roles (inactive, unassigned, not `SUPER_ADMIN`) |
| GET | `/roles` | List Roles (grants, counts) |
| POST | `/roles` | Create Role (direct grants) |
| GET | `/roles/{role_id}` | Get Role (grants, users) |
| PUT | `/roles/{role_id}` | Update Role (fields, status, grants) |
| POST | `/roles/{role_id}/duplicate` | Duplicate Role |
| PUT | `/roles/{role_id}/permissions` | Replace Role Permissions |
| POST | `/roles/{role_id}/permissions` | Grant Role Permissions |
| DELETE | `/roles/{role_id}/permissions` | Revoke Role Permissions |
| DELETE | `/users` | Delete Users (inactive only) |
| GET | `/users` | List Users (paginated; assigned role per user) |
| POST | `/users` | Create User (one role) |
| GET | `/users/{user_id}` | Get User (assigned role + effective permissions) |
| PATCH | `/users/{user_id}` | Update User |
| PUT | `/users/{user_id}` | Update User |
| GET | `/users/{user_id}/effective-permissions` | Effective Permissions (the assigned role's grants) |
| POST | `/users/{user_id}/password` | Set User Password |
| POST | `/users/{user_id}/revoke-sessions` | Revoke User Sessions |
| GET | `/users/{user_id}/role-assignments` | List Role Assignments (zero or one) |
| POST | `/users/{user_id}/role-assignments` | Assign Role (replaces the previous role) |
| DELETE | `/users/{user_id}/role-assignments/{role_code}` | Remove Role Assignment |

Missing credentials answer `401`; an authenticated caller without the code answers
`403 ACCESS_DENIED` and the attempt is recorded as an `AUTHORIZATION_DENIED` audit
event. Payload shapes (single `roleCode`, compiled `permissions`) are in
`docs/09_roles_and_permissions.md` §10.

### Record status

| Method | Path | Purpose |
|---|---|---|
| GET | `/{collection}/status-policy` | Read Status Policy |
| POST | `/{collection}/{item_id}/status` | Change Record Status |

### Quotations

| Method | Path | Purpose |
|---|---|---|
| POST | `/quotation-revisions/{revision_id}/accept` | Accept Revision |
| POST | `/quotation-revisions/{revision_id}/cancel` | Cancel Revision |
| GET | `/quotation-revisions/{revision_id}/compare/{other_revision_id}` | Compare Revisions |
| POST | `/quotation-revisions/{revision_id}/convert` | Convert Revision |
| POST | `/quotation-revisions/{revision_id}/reject` | Reject Revision |
| POST | `/quotation-revisions/{revision_id}/send` | Send Revision |
| POST | `/quotation-revisions/{revision_id}/submit` | Submit Revision |
| DELETE | `/quotations` | Delete Quotations |
| GET | `/quotations` | List Quotations |
| POST | `/quotations` | Save Quotation |
| POST | `/quotations/from-service-order/{identifier}` | Re-quote from a Service Order |
| GET | `/quotations/{quotation_id}` | Get Quotation |
| PUT | `/quotations/{quotation_id}` | Update Quotation |
| GET | `/quotations/{quotation_id}/revisions` | List Revisions |
| POST | `/quotations/{quotation_id}/revisions` | Create Revision |

A new quotation requires a Quotation Date, a Business Party (or the legacy
free-text `customer` name, which resolves or creates one) and a Trade Direction;
an unknown supplied direction is refused rather than replaced. `validUntil` may
not precede `date`.
When `pricingLines` (or `lines`) are supplied the server recomputes every line
and the revision roll-up from quantity, unit price, discount and tax, rounding
each amount half-up to two decimals; a browser-supplied `amount`/`total` is
never trusted. Route stops require a Place Role and a free-text location, keep
their submitted order, and persist planned dates. `POST /attachments/upload`
accepts optional `module`, `record_no` and `note` form fields and links the stored
file to that document; the Files tab sends `module`/`record_no`.
`PATCH /attachments/{attachment_id}` edits only that note (maximum 1000
characters, empty clears it) and needs `attachment.upload`; the stored file is
unchanged.

`POST /quotations/from-service-order/{identifier}` is the re-quotation path: it
accepts a service order id or number, copies the customer, trade direction, route
stops, container requirements and priced lines into a **new** draft quotation, and
records `sourceServiceOrderId` on the new record. The service order is read only —
nothing on it, on its pricing or on the quotation it came from is modified. It
requires `quotation.revise`.

`POST /quotation-revisions/{revision_id}/convert` accepts an optional
`Idempotency-Key` header: a replay with the same key returns the original
conversion instead of creating a second service order, and a concurrent duplicate
is rolled back and reported as `409 DUPLICATE_CONVERSION`.

### Service orders

| Method | Path | Purpose |
|---|---|---|
| DELETE | `/service-orders` | Delete Service Orders |
| GET | `/service-orders` | List Service Orders |
| POST | `/service-orders` | Create Service Order |
| GET | `/service-orders/{identifier}` | Get Service Order |
| POST | `/service-orders/{identifier}` | Update Service Order |
| PUT | `/service-orders/{identifier}` | Update Service Order |
| GET | `/service-orders/{identifier}/charges` | List Order Charges |
| POST | `/service-orders/{identifier}/charges` | Create Order Charge |
| GET | `/service-orders/{identifier}/component-tabs` | List Component Tabs |
| GET | `/service-orders/{identifier}/component-tabs/groups/{group_id}/rows` | List Component Group Rows |
| POST | `/service-orders/{identifier}/component-tabs/groups/{group_id}/rows/bulk` | Bulk Save Component Group Rows |
| GET | `/service-orders/{identifier}/configuration-version` | Get Service Order Configuration Version |
| GET | `/service-orders/{identifier}/containers` | List Containers |
| POST | `/service-orders/{identifier}/containers` | Add or number a Container (send `id` to update a prepared row) |
| DELETE | `/service-orders/{identifier}/containers` | Delete Containers (refused while a payment references one) |
| POST | `/service-orders/{identifier}/finish` | Finish Service Order |
| GET | `/service-orders/{identifier}/invoice` | Get Service Order Invoice |
| POST | `/service-orders/{identifier}/invoice` | Create Service Order Invoice |
| DELETE | `/service-orders/{identifier}/milestones` | Delete Milestones |
| GET | `/service-orders/{identifier}/milestones` | List Milestones |
| POST | `/service-orders/{identifier}/milestones` | Save Milestone |
| DELETE | `/service-orders/{identifier}/movements` | Delete Movements |
| GET | `/service-orders/{identifier}/movements` | List Movements |
| POST | `/service-orders/{identifier}/movements` | Save Movement |

### Service charges

| Method | Path | Purpose |
|---|---|---|
| DELETE | `/service-charges` | Delete Service Charges |
| GET | `/service-charges` | List Service Charges |
| POST | `/service-charges` | Create Service Charge |
| GET | `/service-charges/{charge_id}` | Get Service Charge |
| PUT | `/service-charges/{charge_id}` | Update Service Charge |
| POST | `/service-charges/{charge_id}/create-finance-invoice` | Create Finance Invoice |
| POST | `/service-charges/{charge_id}/issue` | Issue Service Charge |

### Attachments

| Method | Path | Purpose |
|---|---|---|
| DELETE | `/attachments` | Delete Attachments |
| GET | `/attachments` | List Attachments |
| GET | `/attachments/file/{storage_key}` | Download Attachment |
| PATCH | `/attachments/{attachment_id}` | Update Attachment Note |
| POST | `/attachments/presign` | Presign Attachment |
| POST | `/attachments/upload` | Upload Attachment |

### Financial documents

| Method | Path | Purpose |
|---|---|---|
| DELETE | `/financial-documents` | Delete Financial Documents |
| GET | `/financial-documents` | List Financial Documents |
| POST | `/financial-documents` | Create Financial Document |
| GET | `/financial-documents/{document_id}` | Get Financial Document |
| PUT | `/financial-documents/{document_id}` | Update Financial Document |
| POST | `/financial-documents/{document_id}/allocate` | Allocate Payment |
| POST | `/financial-documents/{document_id}/post` | Post Financial Document |
| POST | `/financial-documents/{document_id}/reverse` | Reverse Financial Document |

### Accounting

| Method | Path | Purpose |
|---|---|---|
| GET | `/accounting-periods` | List Periods |
| GET | `/accounting-periods/{period_id}` | Get Period |
| PATCH | `/accounting-periods/{period_id}` | Update Period |
| PUT | `/accounting-periods/{period_id}` | Update Period |
| POST | `/accounting-periods/{period_id}/close` | Close Period |
| DELETE | `/chart-of-accounts` | Delete Accounts |
| GET | `/chart-of-accounts` | List Accounts |
| POST | `/chart-of-accounts` | Create Account |
| GET | `/chart-of-accounts/{account_id}` | Get Account |
| PUT | `/chart-of-accounts/{account_id}` | Update Account |
| GET | `/document-sequences` | List Sequences |
| POST | `/document-sequences` | Upsert Sequence |
| GET | `/document-sequences/{sequence_id}` | Get Sequence |
| DELETE | `/financial-accounts` | Delete Financial Accounts |
| GET | `/financial-accounts` | List Financial Accounts |
| POST | `/financial-accounts` | Create Financial Account |
| GET | `/financial-accounts/{account_id}` | Get Financial Account |
| PUT | `/financial-accounts/{account_id}` | Update Financial Account |

### Journals and posting rules

| Method | Path | Purpose |
|---|---|---|
| GET | `/journal-entries` | List Journals |
| POST | `/journal-entries` | Create Journal |
| DELETE | `/journal-entries/{journal_id}` | Delete Journal |
| GET | `/journal-entries/{journal_id}` | Get Journal |
| PUT | `/journal-entries/{journal_id}` | Update Journal |
| POST | `/journal-entries/{journal_id}/post` | Post Journal |
| DELETE | `/posting-rules` | Delete Posting Rules |
| GET | `/posting-rules` | List Posting Rules |
| POST | `/posting-rules` | Create Posting Rule |
| GET | `/posting-rules/{rule_id}` | Get Posting Rule |
| PUT | `/posting-rules/{rule_id}` | Update Posting Rule |

### Reports

| Method | Path | Purpose |
|---|---|---|
| GET | `/reports/balance-sheet` | Balance Sheet Report |
| GET | `/reports/cash-flow` | Cash Flow Report |
| GET | `/reports/container-register` | Container Register Report |
| GET | `/reports/dashboard` | Dashboard |
| GET | `/reports/expenses` | Expenses |
| GET | `/reports/financial-summary` | Financial Summary |
| GET | `/reports/income` | Income |
| GET | `/reports/ledger-lines` | Ledger Lines |
| GET | `/reports/payables` | Payables |
| GET | `/reports/profit-loss` | Profit Loss Report |
| GET | `/reports/profitability` | Profitability |
| GET | `/reports/quotation-performance` | Quotation Performance |
| GET | `/reports/receivables` | Receivables |
| GET | `/reports/service-order-profitability` | Profitability |
| GET | `/reports/service-orders` | Service Orders Report |
| GET | `/reports/trial-balance` | Trial Balance |
| POST | `/reports/trial-balance/generate` | Generate Trial Balance |
| POST | `/reports/general-ledger/generate` | Generate General Ledger |
| POST | `/reports/trial-balance/export` | Export Trial Balance (CSV) |
| POST | `/reports/general-ledger/export` | Export General Ledger (CSV) |

#### Generated financial reports

A report page posts its filters and receives one page of rows plus the metadata
that produced it. Both endpoints are read-only, are guarded by the report's own
page permission (`reports.trial_balance.view`, `reports.general_ledger.view`,
with `report.read` accepted for legacy roles) and share the report rate limit.

Request body (all fields optional, `extra="forbid"`):

| Field | Type | Applies to | Meaning |
|---|---|---|---|
| `fromDate` / `toDate` | `YYYY-MM-DD` | both | Period bounds. Omitted bound = no bound. `fromDate > toDate` is a `422` on `toDate`. |
| `fiscalYear` | int | both | Resolves the range to that year's `accounting_periods`; explicit dates narrow it. Unknown year is a `422` on `fiscalYear`. |
| `page` / `pageSize` | int | both | 1-based page, `1..200` (default `1` / `50`). |
| `accountFrom` / `accountTo` | string | trial balance | Account-code range, inclusive. |
| `accountCode` | string | general ledger | Exact account code. |
| `party` | string | general ledger | Case-insensitive contains on the party display name. |
| `voucherType` | string | general ledger | `journal_entries.entry_type`, case-insensitive. |
| `voucherNo` | string | general ledger | Contains match on the journal number. |
| `currency` | 3 letters | general ledger | Transaction currency of the line. |

Response envelope:

```json
{
  "data": {
    "meta": {
      "reportKey": "trial-balance",
      "title": "Trial Balance",
      "titleKey": "freight.reportCatalog.reports.trial-balance.title",
      "generatedAt": "2026-10-27T08:00:00Z",
      "page": 1,
      "pageSize": 50,
      "total": 42,
      "filters": { "fromDate": "2026-10-01", "toDate": "2026-10-31", "fiscalYear": null },
      "warnings": []
    },
    "items": [],
    "totals": {},
    "balanced": true,
    "imbalance": 0
  }
}
```

Trial Balance items carry `accountId`, `accountCode`, `accountName`,
`accountType`, `openingDebit`, `openingCredit`, `periodDebit`, `periodCredit`,
`closingDebit`, `closingCredit`; `totals` sums the same six columns over the whole
filtered set (not just the page). `balanced` is false when the period or the
closing position does not net to zero, and `meta.warnings` then names the
difference — an imbalance is reported, never hidden.

General Ledger items carry `postingDate`, `journalNo`, `journalId`,
`voucherType`, `voucherNo`, `sourceDocument`, `accountId`, `accountCode`,
`accountName`, `account`, `description`, `partyId`, `party`, `currency`, `debit`,
`credit`, `runningBalance`, plus the response-level `openingBalance` and
`totals: {debit, credit, closingBalance}`.

Calculation rules: only `journal_entries.status = 'POSTED'` rows are read, so a
draft never contributes and a reversal appears as its own opposite journal.
Amounts are `base_debit_amount` / `base_credit_amount` (`NUMERIC`, summed in
`Decimal`), so a multi-currency ledger is never added up in mixed denominations.
Opening balances are the movement strictly before `fromDate`; the running balance
is a window function over the filtered set evaluated before `LIMIT`, so page two
continues from page one. Ordering is `(posting_date, journal_entry_id, line_no)`.
No caching: each generation reads the ledger as it is and stamps `generatedAt`.

Errors use the standard envelope: `422 VALIDATION_ERROR` with `field_errors`
(`toDate`, `fiscalYear`, unknown field), `403 ACCESS_DENIED` without the report
permission, `429` above the report rate limit. The system read-only mode does not
block generation — it writes nothing, so `access_modes.py` keeps these two paths
available while every other `POST` still returns `409 READ_ONLY_MODE`.

#### Report exports

`POST /reports/<key>/export` takes the same filter body as `/generate` plus an
optional `fields` list (report column keys, in report order) and returns
`text/csv; charset=utf-8` with a `Content-Disposition: attachment` filename of
`<report>-<date>.csv`. Permission, filters and calculations are the generated
report's own: the export is not a second query path, and the footer totals are
the totals `/generate` returns.

- Every matching row is exported, not the visible page: the general ledger is
  read through a server-side cursor and written one line at a time, so memory is
  bounded by the batch (500 rows), not by the result size. The trial balance is
  bounded by the account count, which the report already loads to total it.
- The file starts with metadata rows — report title, `Generated at`, `Period`,
  the active filters, and for the trial balance `Balanced` / `Imbalance` — so an
  exported file states what it contains and when it was produced.
- Money is written as the fixed four-decimal `NUMERIC(19,4)` value. A text cell
  that starts with `=`, `+`, `@`, a tab or a carriage return is prefixed with an
  apostrophe so a spreadsheet cannot execute it; a negative amount is data and
  keeps its sign.
- An unknown `fields` value is a `422` on `fields`. The read-only carve-out above
  covers `/export` as well as `/generate`.

### Configuration

| Method | Path | Purpose |
|---|---|---|
| GET | `/component-attributes` | List Component Attributes |
| POST | `/component-attributes` | Create Component Attribute |
| DELETE | `/component-attributes/{attribute_id}` | Delete Component Attribute |
| PATCH | `/component-attributes/{attribute_id}` | Update Component Attribute |
| POST | `/component-attributes/reorder` | Reorder Component Attributes |
| DELETE | `/component-group-attributes/{membership_id}` | Remove Component Group Attribute |
| PATCH | `/component-group-attributes/{membership_id}` | Update Component Group Attribute |
| GET | `/component-groups` | List Component Groups |
| POST | `/component-groups` | Create Component Group |
| DELETE | `/component-groups/{group_id}` | Delete Component Group |
| PATCH | `/component-groups/{group_id}` | Update Component Group |
| GET | `/component-groups/{group_id}/attributes` | List Component Group Attributes |
| POST | `/component-groups/{group_id}/attributes` | Add Component Group Attribute |
| POST | `/component-groups/{group_id}/attributes/reorder` | Reorder Component Group Attributes |
| DELETE | `/component-tab-groups/{tab_group_id}` | Remove Component Tab Group |
| PATCH | `/component-tab-groups/{tab_group_id}` | Update Component Tab Group |
| GET | `/component-tabs` | List Component Tabs |
| POST | `/component-tabs` | Create Component Tab |
| GET | `/component-tabs/meta/types` | Component Config Types |
| DELETE | `/component-tabs/{tab_id}` | Delete Component Tab |
| GET | `/component-tabs/{tab_id}` | Get Component Tab |
| PATCH | `/component-tabs/{tab_id}` | Update Component Tab |
| GET | `/component-tabs/{tab_id}/groups` | List Component Tab Groups |
| POST | `/component-tabs/{tab_id}/groups` | Add Component Tab Group |
| POST | `/component-tabs/{tab_id}/groups/reorder` | Reorder Component Tab Groups |
| GET | `/configuration-versions` | List Configuration Versions |
| POST | `/configuration-versions` | Publish Configuration Version |
| GET | `/configuration-versions/activation-history` | Configuration Activation History |
| GET | `/configuration-versions/active` | Active Configuration Version |
| GET | `/configuration-versions/preview` | Preview Configuration Version |
| DELETE | `/configuration-versions/{version_id}` | Delete Configuration Version |
| GET | `/configuration-versions/{version_id}` | Get Configuration Version |
| PATCH | `/configuration-versions/{version_id}` | Update Configuration Version |
| POST | `/configuration-versions/{version_id}/activate` | Activate Configuration Version |
| GET | `/configuration-versions/{version_id}/activate-history` | Configuration Version Activation History |
| GET | `/configuration-versions/{version_id}/compare/{other_version_id}` | Compare Configuration Versions |
| GET | `/configuration-versions/{version_id}/preview` | Preview Configuration Version Snapshot |
| POST | `/configuration-versions/{version_id}/retire` | Retire Configuration Version |
| POST | `/configuration-versions/{version_id}/rollback` | Rollback Configuration Version |

Component attributes are validated on both sides. `code` is a stable, unique,
lower-case key (letters, digits, hyphens) and may not be reused; `select` and
`multi_select` require a non-empty `options` array; `reference` requires a
`referenceType` from `business_party`, `transport_asset`, `transport_type`,
`container`, `fee_type` or `user`. `validationRules` accepts `min`, `max`,
`minLength`, `maxLength` (non-negative numbers), `pattern` (a compilable regular
expression) and the boolean flags `email`, `url`, `integer`, `nonNegative` and
`positive`. A malformed rule is a 422 on `validationRules`. Deleting an attribute
that a group, a saved Service Order row, or any published configuration snapshot
still references archives it (`status = INACTIVE`) instead of removing the row.

### Settings, search and UI schemas

| Method | Path | Purpose |
|---|---|---|
| GET | `/search` | Global Search |
| POST | `/search/ask` | Search Ask |
| GET | `/settings/app-config` | Get App Config |
| PATCH | `/settings/app-config` | Update App Config |
| POST | `/settings/app-config/email/send-test` | Send Test Email (configuration check only) |
| POST | `/settings/app-config/email/test-connection` | Test Email Connection (configuration check only) |
| POST | `/settings/app-config/telegram/send-test` | Send Test Telegram (configuration check only) |
| POST | `/settings/app-config/telegram/test-connection` | Test Telegram Connection (configuration check only) |
| GET | `/settings/app-info` | Get App Info |
| PATCH | `/settings/app-info` | Update App Info |
| POST | `/settings/app-info/reset` | Reset App Info |
| POST | `/settings/reset-data` | Reset Data |
| GET | `/ui-schemas/{page}` | Get Ui Schema |

### Backup

| Method | Path | Purpose |
|---|---|---|
| POST | `/backup/restore` | Restore Backup |
| POST | `/backup/run` | Run Backup |
| GET | `/backup/runs` | List Runs |
| GET | `/backup/runs/{run_id}` | Get Run |
| GET | `/backup/status` | Backup Status |
| POST | `/backup/test-connection` | Test Connection |

### Audit

| Method | Path | Purpose |
|---|---|---|
| GET | `/audit-events` | List Audit Events |

### Archive

| Method | Path | Purpose |
|---|---|---|
| GET | `/archive` | List Archive |
| GET | `/archive/options` | Get Archive Options |
| DELETE | `/archive/{entity_type}/{entity_id}` | Hard Delete Archive Record |
| GET | `/archive/{entity_type}/{entity_id}` | Get Archive Record |
| POST | `/archive/{entity_type}/{entity_id}/restore` | Restore Archive Record |

## 4. Dynamic Reference and Generic Collections

The following collections share one CRUD shape:

| Method | Path | Purpose |
|---|---|---|
| GET | `/{collection}` | Paginated list with `search`, `status`, `sort_by`, `sort_dir` |
| GET | `/{collection}/{item_id}` | Read one record |
| POST | `/{collection}` | Create |
| PUT | `/{collection}/{item_id}` | Update |
| DELETE | `/{collection}` | Bulk delete by submitted ids |
| DELETE | `/{collection}/{item_id}` | Delete one record |
| POST | `/{collection}/bulk-delete` | Explicit bulk delete |

`DELETE` of an active reference record is refused with `REFERENCE_ACTIVE`;
deactivate it first. The status command is separate:

| Method | Path | Purpose |
|---|---|---|
| GET | `/{collection}/status-policy` | Read the status policy for the collection. Answer is `404` for a collection with no lifecycle (for example `auditLogs`, `archive`, report views); callers must treat that as "no status actions", not an error. |
| POST | `/{collection}/{item_id}/status` | Change `ACTIVE` / `INACTIVE` status |

Reference collections and their permission families:

| Collection | Permission family | Notes |
|---|---|---|
| `businessParties` | `master.business_parties.*` | Shared parties; `roleIds` carries the many-to-many Party Roles |
| `partyRoles` | `master.party_roles.*` | Unique code/name, active by default; a role in use cannot be deleted (`PARTY_ROLE_IN_USE`) |
| `placeRoles` | `master.place_roles.*` | Route-stop roles |
| `tradeDirections` | `master.trade_directions.*` | Import, export, transit, and related directions |
| `containerTypes` | `master.container_types.*` | Size, kind, ISO code, dimensions, weight |
| `transportTypes` | `master.transport_types.*` | |
| `transportAssets` | `master.transport_assets.*` | `identityType` must name a live (non-archived) `transportAssetIdentityTypes` row that applies to the asset's transport type — a stored type that was later renamed or archived keeps describing the asset and stays editable, and only a value that actually changes is re-validated. The type's `validationPattern` is full-match: enforced on the supplied identity, and on the stored identity when only `identityType` moves. An asset saved without `identityType` defaults to the first applicable row. Optional `assetName`; `capacityValue` (>= 0) and `capacityUnit` (normally a `capacityUnits` code, the dropdown) are optional as a pair — a write leaving exactly one of them set is refused on the missing field, and a stored unit code is preserved even if the unit is later archived. Status is `ACTIVE` / `INACTIVE` / `MAINTENANCE` (three-state policy) |
| `transportAssetIdentityTypes` | `master.transport_assets.*` | The asset identity vocabulary, seeded as data (License Plate, IMO Number, ...); unique active name, optional transport-type link, `identityLabel` / `identityPlaceholder` / `validationPattern` drive the asset form. A pattern must compile under Python `re` and be free of nested quantifiers such as `(x+)+`; a bad one is refused on save with a `validationPattern` field error, so the asset write path never meets a pattern that hangs |
| `capacityUnits` | `master.transport_assets.*` | The asset capacity-unit list, seeded as data (PCS, KG, T, CBM, CTN, PAL); unique active `code` is what `transportAssets.capacityUnit` stores, `name` is the label, status is two-state |
| `feeTypes` | `master.fee_types.*` | |
| `currencies` | `master.currencies.*` | Includes currency rates |
| `currencyRates` | `master.currencies.*` | Rate rows for a currency |
| `documentTypes` | `master.reference.*` | Administrator-managed document classification, seeded with the ten canonical accounting behaviours. A custom row must reference one of them in `accountingBehavior`; a canonical code keeps its behaviour and cannot be deleted (`SYSTEM_DOCUMENT_TYPE`). `availableIn` lists where the type may be selected (financial_documents, service_order_finance, posting_rules, operations_documents, attachments). Financial documents accept `documentTypeId`; the canonical behaviour is stored as `documentType` and `documentTypeId/Code/Name` ride in the payload `data` echo |

Generic records are stored in `module_records` and use the same CRUD shape:
`companies`, `shipments`, `customs`, `documents`, `deliveries`,
`customerPayments`, `supplierCosts`, and `supplierPayments`. Their authorization
comes from the owning page and module; the record serializer and reference
validator live in `master_data`.

### Shared Excel Import & Export (`/api/v1/excel`)

A centralized, allowlisted engine — only collections registered in
`backend/app/modules/excel_io/registry.py` are reachable; the API never exposes
arbitrary tables. Each collection read/export/template uses the module's view
permission (`master.reference.view` for the Master Data lists); every import call
requires the module's manage permission (`master.reference.manage`) — viewing a
list is never enough to import. Uploads accept only `.xlsx`, are capped (10 MB,
2 000 rows), reject formulas and stale template versions, and the confirmation is
a short-lived session bound to the uploading user, module, file checksum, mode
and validated preview; a token confirms at most once and the commit revalidates.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/excel/modules` | Supported modules with columns, match keys and permissions |
| GET | `/api/v1/excel/{module}/template` | Download the generated .xlsx import template |
| POST | `/api/v1/excel/{module}/validate` | Upload a workbook (`file`, `mode`), validate and preview (writes nothing) |
| GET | `/api/v1/excel/imports/{token}` | Re-read the stored preview for the session owner |
| POST | `/api/v1/excel/imports/{token}/commit` | Revalidate and commit the batch atomically (single use) |
| POST | `/api/v1/excel/imports/{token}/cancel` | Discard a not-yet-committed session |
| GET | `/api/v1/excel/imports/{token}/error-report` | Download the XLSX per-row error report |
| POST | `/api/v1/excel/{module}/export` | Export rows as .xlsx or .csv; body `{"ids": [...]}` selects rows, omitted exports all authorized rows. Optional `format` (`xlsx` default, `csv`) and `filters` (`dateFrom`, `dateTo`, `createdBy`, `updatedBy` — only where the module tracks attribution, `status`, `search`); invalid dates/users/formats or a user filter on an unsupported module are 422s, and filters apply at the database query level |
| GET | `/api/v1/excel/{module}/export-count` | Number of rows the export filters would include (same filter validation; used by the Export dialog to disable exporting when nothing matches) |
| GET | `/api/v1/excel/history` | Import history (`?module=` filters; view permission required) |

Registered modules (Phase B): `businessParties`, `partyRoles`, `placeRoles`,
`tradeDirections`, `containerTypes`, `transportTypes`, `transportAssets`,
`transportAssetIdentityTypes`, `capacityUnits`, `feeTypes`, `currencies`,
`documentTypes`. Service-order operations, configuration, finance setup,
finance documents and report exports are **not registered yet** (Phases C–F).

## 5. Error Codes

The principal domain codes are:

```text
AUTH_REQUIRED
ACCESS_DENIED
CSRF_VALIDATION_FAILED
REFERENCE_NOT_FOUND
VALIDATION_ERROR
INVALID_STATE_TRANSITION
REFERENCE_ACTIVE
ORDER_ACTIVE
DUPLICATE_NUMBER
DUPLICATE_CONVERSION
DUPLICATE_USERNAME
DUPLICATE_EMAIL
DUPLICATE_ROLE
PARTY_ROLE_IN_USE
INVALID_RESET_CODE
BACKUP_RUNNING
SETUP_COMPLETED
PERIOD_CLOSED
JOURNAL_UNBALANCED
DOCUMENT_ALREADY_REVERSED
ALLOCATION_EXCEEDS_BALANCE
CURRENCY_MISMATCH
```

Authorization details, including the page-to-API permission mapping, are in
`docs/09_roles_and_permissions.md`. Field-level validation rules are in
`docs/08_frontend_and_ui_design.md` and the shared validators in
`backend/app/core/validation.py`; the same rules are enforced by the API even
when a non-browser client calls it.

## 6. Versioning and Compatibility

- `/api/v1` is the current contract; a breaking change requires a new prefix or
  an additive, versioned route.
- Additive fields and endpoints are compatible; removing or renaming a field is
  not.
- The frontend contract test and the backend request-schema tests must pass
  together before a release.
- The generated schema reference (`docs/06_database_design.sql`) and this
  catalogue are documentation, not migrations. Alembic owns schema changes.
