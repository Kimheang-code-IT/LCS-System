# Reusable Data Import and Export

Status: source-reviewed target, 2026-11-04. Master Data implementation is PARTIAL against
this request. Configuration imports are implemented (excel_io registry `component_config` /
`config_versions` pipelines): attributes/groups/tabs import create-only by stable code with
preview/commit/error reports, and a five-sheet version workbook (Version/Attributes/Groups/
Tabs/Relationships) creates a new DRAFT version; per-tab layout fields are not imported
(assignments fall back to the legacy render-mode defaults). This document specifies behavior,
not implementation or a new generic write path.
[Inventory/architecture](../01-architecture/integration-architecture.md) and
[Plan F](../04-implementation/plans/PLAN-0005-settings-integrations.md#phase-f--data-importexport)
own current-state evidence and task order. Preserve existing master-data Excel functionality.

## IO-001 — Shared workflow and reuse

Reuse frontend/app/components/excel/ImportExportDialog.vue, existing ExportDialog/control
where used, page header More Actions, repository contracts and backend/app/modules/excel_io/.
Refresh stays separate. More Actions offers Import Data, Export Data and Download Template
only when the server module catalog and action permission allow them. Retain current UI style,
input/error components and en/km/zh keys; no new sidebar or separate IO subsystem.

Import: select CSV/XLSX → validate → preview rows/errors/conflicts → choose explicit mode →
confirm writes → show created/updated/skipped/failed counts and failed-row report. Validation
writes only a bounded temporary preview session/history, never target business records.
Cancel/close expires/cancels preview without applying it. Only server validates authorization,
values, relationships and status; hidden buttons are not protection.

Existing behavior: twelve master entries; XLSX templates with exact Data columns/order/version,
openpyxl read-only parsing, formula/archive-bomb rejection, row preview, user-owned expiring
single-use claim, revalidation at confirm and atomic transaction. CSV/XLSX exports escape
formula prefixes. CSV import is a new adapter to the SAME row validator, not a second service.
Do not claim current CSV upload merely because CSV export exists.

## IO-002 — Master Data coverage

| Page / module key | Stable business identity / safety |
|---|---|
| Business Parties / businessParties | partyCode; role memberships resolved by stable role code; retain historical references |
| Party Roles / partyRoles | code; protected/system-role constraints remain |
| Place Roles / placeRoles | code |
| Trade Directions / tradeDirections | code; used historical directions retained |
| Container Types / containerTypes | code; never treat a type as an actual physical container |
| Transport Types / transportTypes | code |
| Transport Assets / transportAssets | assetCode; identity/capacity/type relationships validated |
| Asset Identity Types / transportAssetIdentityTypes | Current registry matches name: NEEDS_REVIEW; require unique canonical stable identity/ID or approved code design before update mode. Ambiguous names must be refused |
| Capacity Units / capacityUnits | code |
| Fee Types / feeTypes | code; preserve accounting references |
| Currencies / currencies | code; numeric precision/current references validated; no rewriting historical rate snapshots |
| Document Types / documentTypes | code; protected canonical rows and fixed accountingBehavior cannot be overwritten |

All twelve support the approved shared template/validate/preview/confirm/error report and
CSV/XLSX export target. Existing registry import/export flags and master service protections
remain authoritative until a reviewed change. Used codes/identifiers may not be renamed or
deleted through update. Inactive references are refused for new choices but old records remain
renderable. Cross-installation imports resolve references explicitly; never copy raw database IDs
from another installation as if they were valid local identities. LCS is single-tenant; reject
foreign installation/organization provenance and unauthorized records, do not invent tenants.

## IO-003 — Configuration graph import

Cover Component Attributes, Component Groups, Component Tabs and safe Configuration Versions.
Extend excel_io registry with configuration adapters calling existing master_data/component_config.py,
config_snapshot.py and config_versions.py validators. Do not route config through a master-data
Spec that cannot preserve graph semantics. Use versioned CSV set or multi-sheet XLSX/manifest.

Declare stable attribute/group/tab keys, template/config schema version, membership references,
order and draft namespace. Validate attributes/types/options/regex/reference targets first,
then group memberships, then tab memberships/layout, then draft version. Resolve source IDs
to local identities with an explicit remap; preserve valid local identifiers. Reject missing
parents, duplicate memberships, cycles/invalid order, incompatible schema and concurrent edits.

One confirmation atomically imports the whole graph into DRAFT, not a partially published
configuration. Show conflict/diff/revision preview; update only draft objects allowed by normal
services. Never mutate a captured published version, historical SO snapshots or finance data.
Import does not activate. Activation is a second separately authorized confirmation through
the existing publish/activation API, with fresh concurrency/compatibility checks and audit.
Version export includes schema/version/reference metadata, no credentials. Restore of a system
backup is not this configuration import operation.

## IO-004 — Explicit eligibility for all other approved pages

This is target policy; existence of an export menu is not evidence of a registered generic
Excel importer/exporter. The current Excel registry covers Master Data only. Use owning report/
module exporters where they exist; new export coverage requires normal authorization/validation.

| Approved page(s) | Import default / conditions | Export target |
|---|---|---|
| Dashboard MOD-001 | No import | Authorized summary only, source/date/currency disclosed |
| Quotations MOD-002 | Disabled generic import; later approved draft/revision workflow only | Authorized records; preserve revision identity |
| Service Orders MOD-003 | Disabled generic import; later draft capture/source/config/container validators and idempotency required | Authorized operational data; no sensitive attachments by default |
| Service Charges MOD-004 | Disabled generic import; no issue/invoice side effect; separate approval for owning lifecycle | Authorized charges with source/currency/status |
| Operations reports MOD-005–008 | None | Export only, same authorized filters/rows |
| Financial Documents MOD-009 | Disabled generic import; any future input uses document lifecycle/Decimal/posting protections; never direct posted rows | Authorized source documents, sensitive fields excluded |
| Chart of Accounts MOD-010 | Controlled draft/config import only after explicit need; hierarchy/postability/used-account checks | Authorized configuration |
| Financial Accounts MOD-011 | Controlled configuration only; no balances/secrets via import | Masked authorized account data |
| Journal Entries MOD-012 | Export-only default; separately authorized validated draft/posting workflow if ever needed | Authorized journal/ledger facts |
| Accounting Periods MOD-013 | Disabled unless a separately approved custom-range draft import is needed; no close/reopen side effect | Authorized periods |
| Posting Rules MOD-014 | Controlled configuration preview/confirm only; account/type/priority/ambiguity checks and audit | Authorized rules |
| Financial reports MOD-015–022 | None | Export only through report source/filters/permissions |
| User Management MOD-039 | Restricted separately approved admin import; no passwords/tokens/role-escalation shortcut | Minimal authorized identity metadata; exclude credential hashes/session data |
| Roles & Permissions MOD-040 | No generic import; audited Casbin management only | Restricted catalog/grants if supported; preserve protected admin |
| Document Sequences MOD-041 | No arbitrary import/reset; cannot lower counters or cause duplicate numbering | Authorized configuration/preview only, not credential data |
| Settings MOD-042 | No generic secret/settings import; owning group patch/secret policy only | Approved non-secret settings only |
| Archive MOD-043 | No generic import/restore | Permission-scoped export; archive restore uses existing guarded lifecycle |
| Audit Logs MOD-044 | None; never writable history | Export only with safe field policy |

Together with MOD-023–034 and MOD-035–038 above this covers all 44 pages. Unsupported actions
are absent or clearly disabled, not an unguarded catch-all /excel/<arbitrary collection> route.

## IO-005 — File and row validation

Validate actual format/MIME/signature, extension, compressed/uncompressed size, entry count,
rows/columns/cell length, encoding, exact template headers/version, required values, types,
Decimal precision/currency, dates/timezone, enums, unique keys, references, permission and
business status. Use existing limits as baseline; document reviewed bounds before raising them.
Reject XLS/XLSM/macros, formula cells/external links/active content, hidden business payloads,
invalid archives, decompression bombs and unsupported workbook layouts. CSV is UTF-8 with
optional BOM, fixed delimiter/quoting/template columns; no guessing locale date/decimal formats.
Treat CSV text as data and reject unsafe formula prefixes according to the shared import policy;
do not evaluate formulas. Keep formatting/export escaping separate from canonical stored values.

Validate duplicates within the file AND database. Stable-key modes:
- Insert New Only (current CREATE_ONLY): duplicate = error; no overwrites.
- Skip Existing: explicit new mode where supported; duplicate stable key = skipped, with count.
- Update Existing by Stable Business Key: explicit update confirmation, allowlisted mutable
  fields only; preserve current CREATE_AND_UPDATE compatibility and clarify whether new keys
  create or are refused. Never silently change this existing mode's meaning.
- Validate Only (current VALIDATE_ONLY): no business write/confirm.

Name matching cannot authorize updates when names are ambiguous. Show identity, action and
conflict reasons in preview. A repeated upload is not assumed safe merely by matching filename;
use content checksum + mode/template identity, user ownership and command replay rules.
Same confirmed command returns its original job/result, or explicit already-consumed status;
never execute a second import. Handle expired/replayed/foreign sessions and changed files.

## IO-006 — Transactions and concurrency

Default atomic all-or-nothing per file/graph; no financial posting within this import. Confirm
rechecks permission, session ownership/TTL, file/template checksum, stable keys, reference/status
and conflicting record revision inside a controlled transaction. Lock/rely on unique constraints
for racing keys; refuse stale updates (409) instead of silently overwriting another editor.
On failure rollback all target writes and record sanitized job failure in a separate clean
transaction. Consume/claim once with crash handling; current single-use failure may require a
fresh validation token, explicitly explained in UI. A process crash in claim→business commit
must have a durable outcome/reconciliation policy before retry can be called safe.
Controlled partial imports are out of initial scope; any later mode requires per-row results,
explicit approval and no configuration graph or accounting inconsistency.

## IO-007 — Export and audit

Offer current filtered results (across all matching pages, not just visible page), selected rows
where supported, and all authorized records as explicit scopes. Reuse server filter definitions;
validate counts/filters before execution. Stable schema column order, UTF-8 BOM CSV when needed
for spreadsheet Unicode, XLSX, Khmer round-trip, unambiguous ISO dates/timezone and exact Decimal
text preserve values. Never export money through a lossy float round-trip.

Neutralize spreadsheet formula/CSV injection including leading whitespace/control characters
and =,+,-,@ prefixes; preserve true typed numeric values deliberately. No password hashes,
reset/session tokens, bot/API/OAuth keys, service JSON, private object URLs or unauthorized
customer data. Exports recheck access and apply field allowlists; admin view is not blanket
permission to download credentials. Large exports use bounded streaming/pagination and existing
job mechanisms only when needed, with expiry and authorization-bound download tickets.

Record actor, module, operation/mode, timestamp, safe filename metadata/checksum/template version,
total/create/update/skip/fail counts, filters/scope, job ID and result in job history and audit.
Include template download, validation, confirm, cancel, failure and export events as appropriate;
no raw private file contents, cells, credentials or unbounded errors. Error reports contain only
necessary user-authorized rows/field messages, are formula-safe, short-lived and access-checked.

## Focused verification

Extend tests/test_excel_import_export.py and existing excel-io/export-dialog specs. Cover each
registered master template, CSV/XLSX equivalence, Khmer, formula/zip bomb/oversize rejection,
relationship/status/protected document types, ambiguous identity names, duplicate modes, stale
preview, revoked permission, foreign session, concurrent same-key imports, rollback and job
replay. For configuration cover draft dependency remap/cycles and unchanged published SO
snapshots. Real race behavior requires disposable PostgreSQL. Manual: More Actions → Template
→ invalid-file preview/error report → valid preview → cancel → confirm once → filtered export;
verify counts/audit and no records before confirmation. No runtime tests are run by this doc task.
