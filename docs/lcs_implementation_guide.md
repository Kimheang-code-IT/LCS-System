# LCS Freight Forwarding — implementation and validation guide

**Deliverables**: `lcs_complete_drawdb_47.sql` (diagram) and `lcs_complete_postgresql_reference.sql` (new empty database DDL).

## Scope and limitations

These are design artifacts, **not a functioning FastAPI/Nuxt implementation**. The full reference schema extends the 44-table proposal to **47 tables** by adding `currency_rates`, `backup_states`, and `backup_records`. It adds PostgreSQL guards for a subset of business invariants, and six starter views. It is NOT a safe in-place migration for the original 59-table database.

The 47-table design intentionally does not reproduce every screen behavior or every original table. In particular, it does not preserve all customer customs credentials, granular original backup logs, quotation container requirements, full multi-leg itinerary documents, posting reversal/FX base-ledger features, original attachment versioning, or every component override. Those need an explicit requirement-by-requirement gap check before replacing the old system.

## Module ownership

- `auth`: roles, users, sessions and RBAC backend checks.
- `master_data`: parties, places, currencies, rates, fee types, trade directions, transport and containers.
- `quotations`: quotations, quotation_versions, quotation_lines.
- `operations`: service orders, charge, containers, pricing, movements, milestones.
- `settings`: attributes, groups, tabs, layout mappings, configuration_versions, app_settings and sequences.
- `finance`: accounts, periods, documents/lines, payments/allocations, journal_entries/lines, posting_rules.
- `audit/archive/backup`: audit_events, archive_records, attachments, attachment_links, backup_runs/states/records.
- `reports`: SQL views, API query services; do not persist derived totals without explicit consistency design.

## Essential workflows to implement in FastAPI

1. **Quotation**: create header + draft V1 in transaction; allocate next version with quotation row lock; clone lines; submit; approve; supersede; convert approved version to service order; protect history.
2. **Service order**: resolve published configuration for trade direction, snapshot config version into order, render tabs/groups/attributes, validate JSONB rows server-side, retain values across config revisions. Changing direction requires migration/confirmation of field values.
3. **Pricing & finance**: create charges, draft invoice, post through rules, create balanced journal and FX/base amounts, settle payments, guard under/over-payment, issue reversal journals and credit notes. Ensure immutable posted documents.
4. **Reports**: trial balance & GL starter views are supplied; financial statements, AR/AP aging, cash flow and job-level realized profitability require separately reviewed definitions, currency and period logic.
5. **Security**: apply one-role-per-user authorization checks in FastAPI; avoid exposing password hashes; rate limit login, hash tokens; audit security and finance actions; use DB roles with least privilege.
6. **Backup**: PostgreSQL PITR/WAL and encrypted offsite backups, restore drills. The backup state/record tables are optional telemetry, not a backup guarantee.

## Critical issues before production

- Reference DDL does not create application endpoints, UI, workers, deployment configuration or migrations.
- Guard functions intentionally support **same-currency** allocations only. Multi-currency settlement needs a reviewed redesign to store allocated payment amount, document amount, FX rate and base-currency amount.
- Journal figures use `debit`/`credit` in one currency; proper multicurrency accounting requires a base-currency amount on each journal line plus exchange-rate snapshots before deployment.
- No automatic change capture is wired to audit_events; append-only prevention is present, but event generation must be implemented.
- `is_active` must never be used to erase history of posted financial transactions.
- Direct changes by privileged database owners can bypass triggers. Use restricted application roles and audited migrations.
- Draft→posted validation uses a trigger only for status UPDATE; do not insert already-posted journals through the app. API must enforce the full workflow.

## Validation steps on a disposable PostgreSQL database

1. Create a fresh EMPTY PostgreSQL database locally (not the production database).
2. Run `psql -v ON_ERROR_STOP=1 -d lcs_schema_test -f lcs_complete_postgresql_reference.sql`.
3. Run `psql -v ON_ERROR_STOP=1 -d lcs_schema_test -f lcs_schema_smoke_tests.sql`.
4. Verify table count (`47`), six views, every table's `is_active` column and absence of broken foreign keys.
5. Build Alembic revisions matching SQLAlchemy models; compare Alembic-generated schema to the reference.
6. Run integration tests for version locking, concurrent allocations, duplicate posting, closed period rejection, and tab configuration history.
7. Restore a realistic anonymized backup into staging and rehearse rollback before production cutover.

**DrawDB**: import `lcs_complete_drawdb_47.sql` in PostgreSQL mode. Do NOT run the DrawDB-only diagram file as your production schema.
