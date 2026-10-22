# API Documentation

## 1. Scope and Source of Truth

The backend is a FastAPI application. Every business endpoint is mounted under
`/api/v1`; the OpenAPI document is available at `/openapi.json` when the API is
running with its documentation routes enabled. The routers in
`backend/app/modules/*/router.py` are the source of truth; this document is the
stable catalogue and the contract the Nuxt client relies on.

Requests and responses use JSON. Authentication is a JWT access token sent as
`Authorization: Bearer <token>`, or the HttpOnly access cookie set by the login
endpoint. Refresh tokens rotate on every refresh. Browser requests that
authenticate with cookies must also send the `X-CSRF-Token` header with the value
of the `XSRF-TOKEN` cookie; the middleware rejects a missing or mismatched token
with `CSRF_VALIDATION_FAILED`.

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

| Method | Path | Purpose |
|---|---|---|
| GET | `/permissions` | List Permissions |
| DELETE | `/roles` | Delete Roles |
| GET | `/roles` | List Roles |
| POST | `/roles` | Create Role |
| GET | `/roles/{role_id}` | Get Role |
| PUT | `/roles/{role_id}` | Update Role |
| POST | `/roles/{role_id}/duplicate` | Duplicate Role |
| DELETE | `/users` | Delete Users |
| GET | `/users` | List Users |
| POST | `/users` | Create User |
| GET | `/users/{user_id}` | Get User |
| PATCH | `/users/{user_id}` | Update User |
| PUT | `/users/{user_id}` | Update User |
| POST | `/users/{user_id}/password` | Set User Password |
| POST | `/users/{user_id}/revoke-sessions` | Revoke User Sessions |
| GET | `/users/{user_id}/role-assignments` | List Role Assignments |
| POST | `/users/{user_id}/role-assignments` | Assign Role |

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
| GET | `/quotations/{quotation_id}` | Get Quotation |
| PUT | `/quotations/{quotation_id}` | Update Quotation |
| GET | `/quotations/{quotation_id}/revisions` | List Revisions |
| POST | `/quotations/{quotation_id}/revisions` | Create Revision |

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
| POST | `/service-orders/{identifier}/containers` | Add Container |
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

### Configuration

| Method | Path | Purpose |
|---|---|---|
| GET | `/component-attributes` | List Component Attributes |
| POST | `/component-attributes` | Create Component Attribute |
| DELETE | `/component-attributes/{attribute_id}` | Delete Component Attribute |
| PATCH | `/component-attributes/{attribute_id}` | Update Component Attribute |
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

### Settings, search and UI schemas

| Method | Path | Purpose |
|---|---|---|
| GET | `/search` | Global Search |
| POST | `/search/ask` | Search Ask |
| GET | `/settings/app-config` | Get App Config |
| PATCH | `/settings/app-config` | Update App Config |
| POST | `/settings/app-config/email/send-test` | Send Test Email |
| POST | `/settings/app-config/email/test-connection` | Test Email Connection |
| POST | `/settings/app-config/telegram/send-test` | Send Test Telegram |
| POST | `/settings/app-config/telegram/test-connection` | Test Telegram Connection |
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
| GET | `/{collection}/status-policy` | Read the status policy for the collection |
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
| `transportAssets` | `master.transport_assets.*` | |
| `feeTypes` | `master.fee_types.*` | |
| `currencies` | `master.currencies.*` | Includes currency rates |
| `currencyRates` | `master.currencies.*` | Rate rows for a currency |

Generic records are stored in `module_records` and use the same CRUD shape:
`companies`, `shipments`, `customs`, `documents`, `deliveries`,
`customerPayments`, `supplierCosts`, and `supplierPayments`. Their authorization
comes from the owning page and module; the record serializer and reference
validator live in `master_data`.

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
