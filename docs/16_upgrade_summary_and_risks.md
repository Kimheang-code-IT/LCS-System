# Upgrade summary: what changed, what was removed, what is still open

Companion to `docs/14_47_table_migration_analysis.md` (the gap analysis and
old→new table mapping) and `docs/15_migration_and_rollback_guide.md` (how to
apply and roll back). This file is the honest account of the work: the decisions
taken, what was and was not removed, and everything still unresolved.

---

## 1. Approach and the central decision

The four reference files under `docs/lcs_*` are design artifacts. The reference
DDL says of itself *"DESIGN FOR NEW/EMPTY DATABASE ONLY. NEVER run against
existing production tables"*, and the author's guide states it *"is NOT a safe
in-place migration for the original 59-table database"*.

Applying that DDL literally would have caused fifteen concrete losses, catalogued
as R1–R15 in `docs/14_47_table_migration_analysis.md` §6.

**Decision: implement the reference design's *capabilities* additively, and
document the equivalence wherever the reference proposes a different
representation of something that already works.** No table was dropped, no
column was dropped, no type was narrowed.

| The reference asks for | What this repository now has |
|---|---|
| `currencies` | **Added** (`currencies`). The reference's `currency_rates` table was added in `b3c4d5e6f7a8`, dropped as unused by `c1d2e3f4a5b7`, and re-added by `d2e3f4a5b6c8` as the approved-rate store documents resolve from |
| `app_settings` | **Added**, and the settings service reads/writes it |
| `configuration_versions` | **Added**, with publish/preview/retire and historical pinning |
| Database-level guards | **Added** (6 functions, 6 triggers, PostgreSQL-only) |
| Six reporting views | **Added** (8 views) |
| `quotation_versions` / `quotation_lines` | **Not renamed.** `quotation_revisions` / `quotation_revision_lines` already carry every field; renaming would invalidate 122 foreign keys, every API payload and the frontend for no functional gain. The mapping is in §3.1 of the analysis. |
| `payments` / `payment_allocations` | **Not created.** Payments are `financial_documents` with a payment `document_type`; creating a second cash table would duplicate the ledger. Exposed read-only as `vw_payments` / `vw_payment_allocations`. |
| Flat `service_order_charges` with `charge_type` | **Not adopted.** The header+line shape drives the invoice pipeline and the charge-number sequence. |
| RBAC in `roles.permissions` JSONB | **Not adopted.** It would lose the permission catalog, referential integrity and grant auditing. |
| `users.role_id`, `users.password_hash` | **Not adopted.** The current split is stronger (separate credential store, one *active* role enforced by a partial unique index, assignment history preserved). |

---

## 2. What was implemented

### Migrations (all additive, all reversible)

The revision-by-revision inventory — including what later revisions dropped, and
what came back — is maintained once in `docs/15_migration_and_rollback_guide.md`
§1, together with the apply, verify and rollback procedure (current head
`d2e3f4a5b6c8`).

### Backend

* **Currency master data** — `Currency` model and master-data CRUD at
  `/api/v1/currencies`, with validation that rejects an unknown currency code and
  a `decimal_places` column that gives each currency its own precision. The paired
  `CurrencyRate` model, its CRUD and its screen were removed as unused by
  `c1d2e3f4a5b7` and re-added by `d2e3f4a5b6c8` as the approved-rate store a
  document resolves its exchange rate from.
* **Application settings** — `AppSetting` model; `settings/service.py` now stores
  one row per group instead of a single JSON blob, falls back to `module_records`
  on read, and mirrors every write back there so an application-only rollback
  still sees the latest configuration.
* **Configuration versioning** — `master_data/config_versions.py` plus
  `/api/v1/configuration-versions` (list, preview, publish, retire). Publishing
  freezes the live tabs/groups/fields into a snapshot; `service_orders`,
  `component_tabs` and `service_order_component_rows` carry the version they were
  created under, so a later publish cannot re-interpret existing data. Publishing
  an unchanged configuration is rejected, a partial unique index permits only one
  live version, and the publish path takes a row lock so two administrators
  publishing at the same moment cannot allocate the same version number.
* **Attribute-code protection** — renaming a field whose code is already stored
  on Service Orders is rejected with `ATTRIBUTE_CODE_IN_USE`; the label may still
  change. Previously `code` was silently ignored on update.
* **Movements and milestones** — the two tables existed with no service or
  endpoints. Added list/create/update/delete with per-order sequence allocation,
  duplicate detection, status normalisation, timestamp validation and an
  inactive-order guard.
* **Quotation version management** — revision numbers are now allocated under a
  `SELECT … FOR UPDATE` on the quotation header (two concurrent re-quotes can no
  longer collide on the unique `(quotation_id, revision_no)`); added
  `GET /quotation-revisions/{id}/compare/{other}` and
  `POST /quotation-revisions/{id}/reject` (which now actually sets `rejected_at`,
  a column that was never written before).
* **Reference validation** — a supplied reference that matches no master record
  is now rejected with a field error instead of being silently stored as NULL.
* **Finance posting flow** — `post_document` and `reverse_document` now create
  their journal as `DRAFT` and promote it to `POSTED` once the lines exist. This
  is required by the new line guard and matches the workflow the reference guide
  prescribes. Public behaviour is unchanged.
* **Administrative reset** — `reset_all_data` opens the transaction-scoped
  `lcs.allow_financial_purge` escape hatch so the audited reset still works
  despite the immutability guards.
* **Permissions** — `service_order_config.publish` added, mapped to the
  configuration page keys so it is grantable from the Roles & Permissions screen.

### Frontend

* New **Currency Rates** master page (`/master-data/currency-rates`) with the
  from/to currency selects resolving to ISO codes.
* New **Configuration Versions** page (`/configuration/versions`): shows the live
  version, whether there are unpublished changes, publishes with a change note,
  and lists history.
* Endpoint constants and repository methods for configuration versions,
  movements, milestones, the pinned configuration, and quotation
  reject/compare; `currencyRates` registered in `REMOTE_ENDPOINTS`.
* 21 new i18n keys in all three locales (English, Khmer, Simplified Chinese).

### Fixed pre-existing defects

| Defect | Impact | Fix |
|---|---|---|
| `alembic/env.py` never imported `app.modules.backup.models` | `alembic revision --autogenerate` would propose dropping all five backup tables | Import added |
| `docs/06b_database_design_annotated.sql` had been overwritten with the 47-table reference DDL | 4 test failures; the documented schema no longer matched the models | Regenerated from the models |
| `docs/06_database_design.sql` had no generator, so it could silently drift from the models | `test_schema_docs.py` would fail with no stated remedy | Added `backend/scripts/generate_schema_dump.py` |
| `rejected_at` on quotations was never written | Rejections were indistinguishable from abandoned drafts | Wired up via the new reject endpoint |
| Revision numbers were allocated with `MAX()+1` and no lock | Concurrent re-quotes could collide | Row lock added |

---

## 3. Obsolete code removed

**Superseded in part.** Since this summary was written, the currency-rate table,
model, endpoints and screen, and the posting-rule-history screen and endpoints,
were removed (see `docs/18_implementation_checklist.md` §6 and §8). Everything
else below still holds: no other module, endpoint, table, column, frontend page,
store, or repository was removed. The only code replaced rather than added is the storage
implementation inside `settings/service.py`: `get_app_info`, `update_app_info`,
`reset_app_info`, `get_app_config` and `update_app_config` were rewritten to read
and write `app_settings` instead of a single `module_records` blob. They keep
identical signatures and return shapes, and the previous store is still read as a
fallback and written as a mirror, so nothing that depended on them changed.

README, stored procedure, and dead-table analysis found no code that could be
safely deleted *and* was verified to be unreachable, so per the brief ("Remove
obsolete code only after confirming that replacement functionality works") the
candidates are recorded here rather than deleted:

| Candidate | Why it is not deleted yet |
|---|---|
| `master_data/ModuleRecord` generic collections (`companies`, `shipments`, `customs`, `documents`, `deliveries`) | Still the storage for those metadata-driven screens. Out of scope to promote them to real tables. |
| The legacy `module_records('currencies')` row | Its content was migrated into the new `currencies` table and the collection is no longer used by the app (the archive registry now has a real `Currency` adapter). Retained only so a schema rollback still finds it. |
| The `module_records` settings mirror (`__app_config__`, `__app_info__`) | Deliberately retained so an application-only rollback is lossless. Safe to delete once the schema rollback path is retired. |
| `app/utils/freight/job-task-fields.ts` + `job-component-line-table.ts` | Genuinely dead: the second imports the first, and nothing imports either. They belong to the superseded component-template model. Deleting them is safe but unrelated to this change, so it is left for a dedicated cleanup. |
| Frontend `freight-options.ts` static lists (`TRANSPORT_MODES`, `CONTAINER_STATUSES`, …) | Duplicate master data that also exists in the database. `CURRENCIES` is now honoured through the real `currencies` table; the rest still accept a value the database does not know. Migrating each is a separate, user-visible change. |
| `reports/service.py` `"cashBankBalance": 0.0` | Hardcoded placeholder in the dashboard payload |

---

## 4. Verification performed

The commands run and their observed results are recorded in
`docs/18_implementation_checklist.md` → Verification log; the migration-cycle
rows (fresh upgrade, downgrade to `a2b3c4d5e6f7`, re-upgrade, `pg_dump`/restore,
row-count reconciliation) are in `docs/15_migration_and_rollback_guide.md` §1.
Nothing in this summary is asserted from inspection alone.

---

## 5. Remaining known risks and limitations

1. **`alembic downgrade base` cannot complete — pre-existing.** Measured on the
   pre-change chain: 17 of 18 revisions roll back, then legacy revision
   `6e862ce04e46` fails dropping `ix_service_order_tab_configs_organization_id`,
   an index belonging to the multi-tenancy tables that an earlier revision had
   already removed. Fixing it means editing a long-released revision, which would
   change its checksum for environments that already applied it. The supported
   rollback boundary is the previous release revision (`a2b3c4d5e6f7`), which
   works cleanly. Use the restore path in the migration guide for anything
   deeper.
2. **Guard triggers are PostgreSQL-only.** They are installed by a migration, so
   the SQLite test database never has them; the declarative parts are asserted by
   `tests/test_schema_integrity.py` and the runtime behaviour only by
   `tests/sql/integrity_guards.sql`, which is a manual, disposable-database step.
   CI does not currently run it.
3. **A database owner can bypass the guards.** `SET LOCAL lcs.allow_financial_purge = 'on'`
   is available to any session that can issue SQL. The guards defend against
   mistakes and out-of-band edits, not against a hostile DBA. Least-privilege
   database roles are still required.
4. **No FX conversion on allocation.** `financial_document_allocations` requires
   the payment and the invoice to share a currency, exactly as the reference
   guard does. Cross-currency settlement is unimplemented and needs a reviewed
   design (the reference guide flags the same limitation).
5. **Tracked elsewhere, not here.** The movements/milestones editor, the
   quotation-comparison view, the remaining frontend static option lists and the
   browser-side financial statements are tracked in
   `docs/17_repository_analysis.md` §5–§6 and the `docs/18_implementation_checklist.md`
   work queue, which are the current status homes. The `currency_rates`
   limitation originally recorded in this position is closed: the store is back
   and consumed (`d2e3f4a5b6c8`), so a document in another currency resolves and
   stores the rate it converts at.
8. **`payments` and `quotation_versions` naming.** The reference names are exposed
   only through compatibility views and the documented mapping. Any external
   consumer written against the reference names needs adapting.
11. **`06_database_design.sql` was regenerated wholesale.** The new generator emits
    tables in the same dependency order as the annotated generator, which
    reordered sections relative to the previous hand-maintained file. The content
    is verified equivalent (the docs test compares structurally), but the diff is
    large.
12. **Concurrent publish is not covered by an automated test.** The row lock and
    the `IntegrityError → 409 CONFIGURATION_PUBLISH_CONFLICT` fallback are in
    place, but the in-process SQLite test client uses a single shared connection,
    so the race cannot be provoked deterministically. The equivalent quotation
    case is covered by serialisation assertions instead.
13. **The Postman collection was not updated.** `docs/LCS_API.postman_collection.json`
    does not list the new endpoints (currencies, configuration
    versions, movements, milestones, quotation reject/compare). FastAPI's
    `/docs` and `/openapi.json` are authoritative and up to date.
