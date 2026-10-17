# LCS Freight Forwarding — migration and rollback guide

**Scope:** the additive Alembic revisions listed in §1, which give the existing
59-table system the capabilities the 47-table reference design has. Read alongside
`docs/14_47_table_migration_analysis.md`, which records *why* each change is
additive and which proposal tables were deliberately not adopted.

**Head after this work:** `d2e3f4a5b6c8` — the four capability revisions in §1, the
posting-rules revisions `f8a9b0c1d2e3` and `a9b0c1d2e3f4`, the credential
revision `b0c1d2e3f4a5`, the revision that dropped the unused `currency_rates`
table (`c1d2e3f4a5b7`), and the multi-currency revision that brought it back as
the approved-rate store a document resolves from and added the base-currency
amounts (`d2e3f4a5b6c8`).
**Head before this work:** `a2b3c4d5e6f7`

---

## 1. What the revisions do

| Order | Revision | Adds | Data touched |
|---|---|---|---|
| 1 | `b3c4d5e6f7a8` | `currencies`, `currency_rates` | Inserts one row per currency code already stored, per ISO default, and per legacy `module_records('currencies')` entry |
| 2 | `c4d5e6f7a8b9` | `app_settings` | Copies the `__app_info__` / `__app_config__` payloads into one row per setting group |
| 3 | `d5e6f7a8b9c0` | `configuration_versions`, `config_version_id` on `component_tabs` and `service_order_component_rows`, `configuration_version_id` on `service_orders` | Publishes version 1 from the live configuration and stamps existing rows |
| 4 | `e6f7a8b9c0d1` | 8 reporting views, 6 guard functions, 6 triggers, `updated_at` triggers | None |
| 5 | `f8a9b0c1d2e3` | `posting_rules.priority`, `posting_rules.description`, 2 indexes | None |
| 6 | `a9b0c1d2e3f4` | `journal_entries.posting_rule_id` + FK + index | Backfills the rule id from the `journal_entries.data.ruleId` snapshot where present; a no-op otherwise |
| 7 | `b0c1d2e3f4a5` | `user_credentials.must_change_password` | None — defaults to false, so nobody is locked out |
| 8 | `c1d2e3f4a5b7` | **Drops `currency_rates`** | None. The FX-rate editor was removed from the product. No posting read this table: every posting snapshots its own rate into `financial_documents.exchange_rate` and `journal_entry_lines.exchange_rate`, with the base-currency amounts beside them, so no posted amount can change. `downgrade()` recreates the table empty. |
| 9 | `d2e3f4a5b6c8` | `currencies.decimal_places`, **re-adds `currency_rates`** as the approved-rate store documents read (ISO-code pairs, effective date, PENDING/APPROVED/INACTIVE), `financial_documents.base_currency_code` and the four `base_*_amount` columns | Backfills `base_* = amount * exchange_rate` for every existing document — the arithmetic `post_document` already used — so the stored converted amounts agree with the journal lines already in the ledger. `base_currency_code` stays NULL for those rows: the base currency in force when they were written was a setting that may since have changed. |

Nothing is renamed or narrowed. Revision 8 drops a table whose owning feature was
removed; revision 9 re-adds it as a store that documents read, and only adds
columns elsewhere. Every `downgrade()` reverses only what its own `upgrade()`
created, and uses `IF EXISTS`/`DROP … IF EXISTS` so a partially-applied earlier
form of a revision still rolls back cleanly.

### Revision 5 — posting rules (added after the initial migration work)

`f8a9b0c1d2e3` is independent of the four above and is applied on top of
`e6f7a8b9c0d1`. It is the supporting change for the Posting Rules Management
feature: it adds the `priority` column that orders competing rules, an
administrator-facing `description`, a covering index for resolution, and the
partial unique index that makes "one active rule per scope *and* priority" a
database guarantee rather than a read-then-write in the service.

```bash
cd backend
DATABASE_URL=... uv run alembic upgrade head                    # -> f8a9b0c1d2e3
DATABASE_URL=... uv run alembic downgrade e6f7a8b9c0d1           # reversible
DATABASE_URL=... uv run alembic upgrade head                    # back at head
```

Both directions were exercised against PostgreSQL 16: after the downgrade the
table carries its original 9 columns and the primary key only, and re-upgrading
restores both indexes. The index can be confirmed directly:

```sql
SELECT indexdef FROM pg_indexes
 WHERE tablename = 'posting_rules' AND indexname LIKE 'uq_%';
-- CREATE UNIQUE INDEX uq_posting_rules_active_priority
--   ON posting_rules USING btree (document_type, COALESCE(fee_type_id, 0), priority)
--   WHERE status = 'ACTIVE'
```

The key includes `priority` deliberately. A scope-wide unique key would have made
`priority` meaningless — two active rules for one scope could never coexist, so
there would be nothing to prioritise. Keying on the triple weakens the constraint
relative to the old service-level check, so it cannot fail on an existing
database: every row satisfying "one active rule per scope" also satisfies "one
active rule per scope *and* priority".

### Revision 6 — the journal's link to its rule

`a9b0c1d2e3f4` adds `journal_entries.posting_rule_id`, a foreign key and an index.
Every journal already carried the accounts and amounts it was posted with, so
posted history survives a rule change; what it did not carry was a *joinable*
link to the rule. That link is what answers "which documents posted through this
rule?" — the Posting Rule History screen.

The foreign key has no `ON DELETE` action on purpose. A rule that posted something
may be deactivated but never deleted, and `app/core/deletion.py` picks the new
reference up from the SQLAlchemy metadata, so the delete guard needed no change
and no list to maintain. Deleting such a rule now answers:

```
Posting rule CREDIT_NOTE is still referenced by journal_entries (2). Deactivate …
```

```bash
cd backend
DATABASE_URL=... uv run alembic upgrade head                    # -> a9b0c1d2e3f4
DATABASE_URL=... uv run alembic downgrade f8a9b0c1d2e3           # reversible
DATABASE_URL=... uv run alembic upgrade head                    # back at head
```

Exercised against PostgreSQL 16: the column, the constraint and the index appear
on upgrade, and after the downgrade the table is back to its previous shape with
all 18 existing journals intact.

The backfill adopts a rule id previously recorded only inside
`journal_entries.data` and skips an id that no longer exists, so it can never
violate the new foreign key. On a database that has not run this feature it
simply does nothing.

### Revision 7 — forced password change after an administrative reset

`b0c1d2e3f4a5` adds `user_credentials.must_change_password`, a boolean defaulting
to `false`. It records that the current password was chosen by somebody other
than its owner, which is what lets an administrator help a user who cannot
receive the self-service reset email.

No password is stored in a form anybody can read, before or after this revision:
`user_credentials.password_hash` is an Argon2id digest written by
`hash_password()`, and there is deliberately no reversible column. What the new
flag adds is the *consequence* of an administrative reset: while it is set, the
access token carries a `pwd` claim and `get_current_context` answers
`403 ACCESS_DENIED` for every route except changing the password, refreshing,
reading the profile and signing out.

```bash
cd backend
DATABASE_URL=... uv run alembic upgrade head                    # -> b0c1d2e3f4a5
DATABASE_URL=... uv run alembic downgrade a9b0c1d2e3f4           # reversible
DATABASE_URL=... uv run alembic upgrade head                    # back at head
```

Exercised against PostgreSQL 16: the column arrives as `boolean NOT NULL DEFAULT
false` and disappears again on downgrade. Because the default is `false`, no
existing credential is affected and nobody is locked out by applying it.

### Verification already performed

The rows below were recorded when the then-head was `b0c1d2e3f4a5`. The current
head is `d2e3f4a5b6c8`: 63 application tables (64 with `alembic_version`), 8 views
and 122 foreign keys. Re-run §2–§4 on the target environment rather than reading
this table as the current shape.

| Check | Result |
|---|---|
| `alembic upgrade head` on a fresh empty database | 22 revisions applied, 64 tables, 8 views |
| `alembic downgrade a2b3c4d5e6f7` (previous release head) | 4 downgrades, 0 errors, 60 tables, 0 views |
| `alembic upgrade head` again | 4 upgrades, back at head |
| Row-count reconciliation across a downgrade/upgrade cycle | Role grants 188, permissions 128, users 3, audit events 14 — unchanged |
| Fresh database vs the migrated development database | Identical table set |
| Generated DDL (`docs/06_database_design.sql`) loaded into PostgreSQL vs `alembic upgrade head` | Same table set, **122/122 identical foreign keys**, identical indexes, and only 2 column differences — both pre-existing and already documented in `generate_schema_docs.py` (`archive_records.snapshot_json` is `json` not `jsonb`; `business_parties.roles` carries a server default). The new migrations add **zero** model/migration drift. |
| `backend/tests/sql/integrity_guards.sql` | 16/16 guard scenarios behave as specified; trial balance nets to zero |
| `pg_dump` → `pg_restore` → `alembic upgrade head` | Restores the exact pre-migration state and upgrades forward cleanly |

---

## 2. Pre-flight (do this first, every time)

```bash
# 1. Confirm where you are.
cd backend && uv run alembic current          # expect a2b3c4d5e6f7 before the upgrade

# 2. Take a base backup. Never migrate without one.
docker exec <db-container> pg_dump -U <user> -d <db> -Fc -f /tmp/pre-migration.dump
docker cp <db-container>:/tmp/pre-migration.dump ./backups/pre-migration-$(date +%Y%m%d-%H%M%S).dump

# 3. Record the pre-migration row counts you will reconcile against.
psql "$DATABASE_URL" -f backend/tests/sql/pre_migration_counts.sql > pre-counts.txt
```

`backend/tests/sql/pre_migration_counts.sql` prints every table with its row
count plus the financial control totals. Keep the output: §4 compares against it.

### Rehearse on a copy

```bash
createdb lcs_rehearsal
pg_restore -d lcs_rehearsal --no-owner --no-privileges ./backups/pre-migration-*.dump
cd backend && DATABASE_URL=postgresql+asyncpg://user:pass@host/lcs_rehearsal uv run alembic upgrade head
psql lcs_rehearsal -f tests/sql/integrity_guards.sql   # disposable database only
```

Only run the real migration once the rehearsal and §4 pass on the copy.

---

## 3. Applying

The backend container already runs `alembic upgrade head` on start, so a normal
deploy needs no extra step. To apply explicitly:

```bash
cd backend
DATABASE_URL=... uv run alembic upgrade head
```

If a revision fails, Alembic rolls the whole `upgrade` invocation back
(`transaction_per_migration` is not enabled), so the database stays on its
previous revision and you can fix forward. Check with `alembic current`.

---

## 4. Post-migration verification

```bash
# Revision and shape.
psql "$DATABASE_URL" -c "SELECT version_num FROM alembic_version;"   # d2e3f4a5b6c8
psql "$DATABASE_URL" -c "
  SELECT
    (SELECT count(*) FROM information_schema.tables
      WHERE table_schema='public' AND table_type='BASE TABLE') AS tables,
    (SELECT count(*) FROM information_schema.views WHERE table_schema='public') AS views;"
# expect: tables 64, views 8 (63 application tables + alembic_version, and 8 views)

# Row-count reconciliation — diff against pre-counts.txt.
psql "$DATABASE_URL" -f backend/tests/sql/pre_migration_counts.sql > post-counts.txt
diff pre-counts.txt post-counts.txt
# expected differences, and nothing else:
#   currencies                0 -> (number of distinct codes found)
#   app_settings              0 -> 9
#   configuration_versions    0 -> 0 or 1 (1 when any active tab existed)
#   alembic_version           1 -> 1 (different value)

# The ledger must still net to zero.
psql "$DATABASE_URL" -c "
  SELECT COALESCE(SUM(l.debit_amount) - SUM(l.credit_amount), 0) AS imbalance
  FROM journal_entry_lines l JOIN journal_entries j ON j.id = l.journal_entry_id
  WHERE j.status = 'POSTED';"
# expect: 0.0000

# No orphaned rows and no invalid foreign keys.
psql "$DATABASE_URL" -c "
  SELECT conrelid::regclass AS table_name, conname
  FROM pg_constraint
  WHERE contype = 'f' AND connamespace = 'public'::regnamespace AND NOT convalidated;"
# expect: 0 rows

# Every service order still points at a real customer and direction.
psql "$DATABASE_URL" -c "
  SELECT count(*) FROM service_orders so
  LEFT JOIN business_parties bp ON bp.id = so.customer_party_id
  LEFT JOIN trade_directions td ON td.id = so.trade_direction_id
  WHERE bp.id IS NULL OR td.id IS NULL;"
# expect: 0

# Duplicate revision numbers must not exist.
psql "$DATABASE_URL" -c "
  SELECT quotation_id, revision_no, count(*) FROM quotation_revisions
  GROUP BY 1, 2 HAVING count(*) > 1;"
# expect: 0 rows
```

Then confirm the application starts and a page loads:

```bash
docker exec <api-container> curl -fsS http://localhost:8000/health
docker exec <api-container> curl -fsS http://localhost:8000/health/ready
```

---

## 5. Backup and recovery procedure

**A backup you have never restored is not a backup.** The restore path below was
executed successfully against this repository's development database; repeat it
on your own dump before relying on it.

```bash
# Recover into a scratch database (never over the live one).
createdb lcs_restore
pg_restore -d lcs_restore --no-owner --no-privileges ./backups/pre-migration-<stamp>.dump

psql lcs_restore -c "SELECT version_num FROM alembic_version;"
# The verified run produced: a2b3c4d5e6f7, 60 tables, 188 role grants,
# 128 permissions, 3 users, 14 audit events — i.e. the exact pre-migration state.

# A restored pre-migration dump upgrades forward cleanly.
cd backend && DATABASE_URL=...lcs_restore uv run alembic upgrade head
```

To promote the restore, stop the application, `ALTER DATABASE lcs RENAME TO lcs_broken`,
then rename the restore into place. Renaming rather than dropping keeps the
damaged database available for forensics.

### What the backup tables are *not*

`backup_runs`, `backup_states` and `backup_records` are Google-Sheets
replication telemetry. They are **not** a substitute for a PostgreSQL base
backup plus WAL archiving, and this migration does not change that. Off-host,
encrypted backups are still required for production; see
`docs/12_deployment_runbook.md`.

---

## 6. Rollback

### 6.1 Rolling back this work (the supported path)

```bash
cd backend
DATABASE_URL=... uv run alembic downgrade a2b3c4d5e6f7
```

Verified: 4 downgrades, 0 errors, 60 tables, 0 views, all data preserved.

Effects:

* the 8 views and all guard/`updated_at` triggers are dropped, so the database
  behaves exactly as it did before — application-level validation is unaffected;
* `configuration_versions` and the three pointer columns are dropped;
* `app_settings` is dropped, and the settings service falls back to reading
  `module_records`, which is kept mirrored on every write (see §6.3);
* `currencies` and `currency_rates` are dropped. The `currency_code` strings on
  monetary columns were never touched, so **no amount changes**.

Roll the application back to the matching build at the same time. The previous
build reads only pre-existing tables, so it works against either schema.

### 6.2 Rolling back further — known limitation

`alembic downgrade base` **cannot complete**, and this is a pre-existing defect,
not something introduced here. Measured on the pre-change chain (18 revisions,
head `a2b3c4d5e6f7`), `downgrade base` ran 17 of 18 steps and failed inside the
legacy revision `6e862ce04e46` with:

```
asyncpg.exceptions.UndefinedObjectError: index "ix_service_order_tab_configs_organization_id" does not exist
```

That revision's `downgrade()` re-creates indexes for the multi-tenancy tables
that `b7f1c2a9d4e0_remove_organization_and_branch` had already removed, so the
index never exists to be dropped. Fixing it means editing a long-released
revision, which would change the checksum of a migration other environments have
already applied — so it is left alone and documented here instead.

**Practical consequence:** the rollback boundary is the previous *release*
revision (`a2b3c4d5e6f7`), which is exactly what §6.1 does and what a real
rollback needs. Never plan a rollback that goes past it; use the restore
procedure in §5 instead.

### 6.3 State that a rollback does not restore

* Settings written after the upgrade live only in `app_settings`. Every write is
  mirrored into `module_records` (`_mirror_legacy_settings` in
  `app/modules/settings/service.py`), so a code rollback still sees them. If the
  mirror is ever removed, a rollback would show the last pre-migration settings
  and they would have to be re-entered.
* `configuration_versions` snapshots are dropped. Service Orders keep their
  component rows; they simply stop being pinned to a version.
* `currencies` rows are dropped and are re-derived from the stored
  `currency_code` strings if the migration is applied again.

No business or financial record is affected by any of the above.

---

## 7. The `updated_at` and guard triggers

Migration 4 installs `trg_touch_<table>` on every table that has an `updated_at`
column, plus the guard triggers. They are PostgreSQL-only; other dialects are
skipped.

### Administrative escape hatch

The immutability guards are absolute, which would make the audited data reset
(`POST /api/v1/settings/reset-data`) impossible. That path opens a
transaction-scoped escape hatch first:

```sql
SET LOCAL lcs.allow_financial_purge = 'on';
```

`SET LOCAL` cannot outlive its transaction, so it cannot leak into a later
request. Any session that can already issue arbitrary SQL can set it — the
guards protect against mistakes and out-of-band edits, not against a hostile
database owner. Restrict application database roles accordingly and treat
migrations as audited changes.

### Verifying the guards

```bash
docker cp backend/tests/sql/integrity_guards.sql <db-container>:/tmp/guards.sql
docker exec <db-container> psql -U <user> -d <DISPOSABLE_DB> -f /tmp/guards.sql
```

The script truncates every table, so it must **only** run against a disposable
database. Each step prints its expectation; a "must FAIL" step that prints no
`ERROR` means the guard is missing.

---

## 8. Deploying the code and the schema together

1. Take the base backup (§2).
2. Deploy the new backend image. Its entrypoint runs `alembic upgrade head`
   before it serves; the server does not accept traffic until that succeeds.
3. Run §4 against production.
4. Deploy the frontend image (static assets; no schema dependency).
5. Leave the previous backend image tagged and ready. A rollback is
   `alembic downgrade a2b3c4d5e6f7` plus redeploying that image.

Nothing in this work requires a maintenance window: every revision is additive,
and the previous application build is valid against both schemas.
