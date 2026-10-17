---
name: database-migration
description: Use when changing the PostgreSQL schema, SQLAlchemy models, or Alembic migrations in the LCS backend, including foreign keys, indexes, data backfills, constraint changes, destructive-operation review, and schema rollback.
---

# Database migration

Change the LCS schema safely. Financial data, posted journals, and historical
documents must survive every migration.

## When to use

- Adding or changing a SQLAlchemy model or a column, constraint, or index.
- Writing or reviewing an Alembic revision.
- Backfilling or transforming data.
- Planning a rollback, or asked to "clean up" an old table.

## Required inputs

1. The exact schema change and why it is needed.
2. Which tables and columns are affected, and whether existing rows must be kept.
3. Whether existing code (including a not-yet-upgraded deployment) still works
   against the new schema.

## Project references

| Document | Use it for |
|---|---|
| `docs/06b_database_design_annotated.sql` | Generated DDL plus a description of every table and column |
| `backend/scripts/schema_descriptions.py` | The prose behind that file; must be extended with every new table/column |
| `docs/15_migration_and_rollback_guide.md` | Apply/verify/roll back procedure and the supported rollback boundary |
| `docs/14_47_table_migration_analysis.md` | Why the schema is 63 tables and not the proposed 47 |
| `AGENTS.md` §Backend | `alembic/env.py` import list, `reset_all_data`, ruff settings |

## Non-negotiable rules

1. **Additive by default.** Do not drop a table or column, narrow a type, or
   recompute a stored amount in the same release that introduces its replacement.
   Retire old structures in a later, approved migration.
2. **Never edit a released revision.** Changing an applied revision's content
   changes its checksum for every environment that already ran it. Add a new
   revision instead.
3. **A database owner is not the application.** Enforce financial invariants in the
   database too (see the triggers in `e6f7a8b9c0d1_reporting_views_and_integrity.py`),
   because the service layer can be bypassed.
4. **Money is `NUMERIC`.** Never `Float`. `Decimal` end to end.
5. **Preserve identifiers and timestamps.** Existing `id`, `created_at`, and
   `updated_at` values are referenced by documents, audit rows, and reports.
6. **No silent truncation.** Widening a `VARCHAR` is safe; narrowing is not.

## Workflow

1. **Measure the current state** from the live database, not the migrations:

   ```sql
   SELECT table_name,
          (xpath('/row/c/text()', query_to_xml(
             'SELECT count(*) AS c FROM public.' || quote_ident(table_name), false, true, '')))[1]::text::bigint
   FROM information_schema.tables
   WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1;
   ```

   `backend/tests/sql/pre_migration_counts.sql` does this plus the financial
   control totals; run it before and after and diff the two outputs.
2. **Back up first.** `pg_dump -Fc`, then restore the dump into a scratch database
   and confirm the revision and row counts. A backup you have never restored is
   not a backup. See `docs/15` §5.
3. **Write the revision** in `backend/alembic/versions/`, chained from the current
   head (`uv run python -m alembic heads`), with a real `downgrade()`.
   - Use `IF EXISTS` in `downgrade()` (`DROP INDEX IF EXISTS`, `ALTER TABLE … DROP
     CONSTRAINT IF EXISTS`) so a partially applied earlier form still rolls back.
   - Guard PostgreSQL-only objects:
     `if op.get_bind().dialect.name != "postgresql": return`.
   - Tests run on SQLite via `Base.metadata.create_all`, so a model change is
     reflected in tests automatically — a migration-only change is not.
4. **Backfill idempotently.** Insert only what is missing; re-running must not
   duplicate. Never rewrite a value a user or a posting produced.
5. **Register every new model module** in `backend/alembic/env.py`,
   `backend/scripts/generate_schema_docs.py`, `backend/scripts/generate_schema_dump.py`,
   and (if it holds resettable config) `reset_all_data` in `app/core/bootstrap.py`.
6. **Regenerate both schema documents** and extend the description catalogue:

   ```bash
   cd backend
   uv run python scripts/generate_schema_docs.py   # docs/06b
   uv run python scripts/generate_schema_dump.py   # docs/06
   uv run python scripts/generate_schema_docs.py --check --strict
   ```

   `tests/test_schema_docs.py` fails if either file is stale, if any column lacks
   prose, or if the two disagree structurally.
7. **Verify** against a disposable database (never the developer's working one):

   ```bash
   createdb lcs_rehearsal
   pg_restore -d lcs_rehearsal --no-owner --no-privileges <dump>
   cd backend && DATABASE_URL=... uv run python -m alembic upgrade head
   psql lcs_rehearsal -f tests/sql/integrity_guards.sql     # disposable only
   DATABASE_URL=... uv run python -m alembic downgrade <previous-release-revision>
   DATABASE_URL=... uv run python -m alembic upgrade head
   ```

8. **Prove model/migration agreement.** Load the generated DDL into a scratch
   database and compare it with the migrated one: the table set, every column's
   type and nullability, and the foreign-key set must match. A small number of
   documented divergences already exist (`archive_records.snapshot_json` is `json`
   not `jsonb`; `business_parties.roles` carries a server default). Any *new*
   divergence is a defect.

## Security and validation requirements

- Never enable `sslmode=disable` or embed credentials in a migration.
- PostgreSQL guards must honour the documented purge escape hatch
  (`fn_financial_purge_allowed`, keyed on `SET LOCAL lcs.allow_financial_purge`),
  which only the audited `POST /api/v1/settings/reset-data` path sets.
- Do not add a trigger that blocks the application's own legitimate write path.
  Worked example: the line guard forbids editing lines of a POSTED journal, so
  `post_document()` creates the journal as `DRAFT` and promotes it after the lines
  exist. Always test a new guard against the real service flow.
- Constraint changes must not make an existing valid row invalid. If they would,
  the migration must fix the data first — and that is a reviewable decision.

## Testing

| Requirement | Command / artifact |
|---|---|
| Chain integrity (single head, linear, every downgrade non-empty) | `uv run python -m pytest tests/test_migration_chain.py -q` |
| Declarative constraints (partial unique indexes, checks, FK targets, NUMERIC, tz-aware timestamps) | `uv run python -m pytest tests/test_schema_integrity.py -q` |
| Generated docs in sync | `tests/test_schema_docs.py` |
| Runtime guard behaviour | `psql <disposable> -f tests/sql/integrity_guards.sql` (16 scenarios) |
| Data preservation | diff `pre_migration_counts.sql` before/after |
| Full suite | `uv run python -m pytest -q` |

## Acceptance criteria

- `alembic upgrade head` succeeds on an empty database and on a restored copy.
- `alembic downgrade <previous-release-head>` then `upgrade head` both succeed.
- Row counts and financial control totals are unchanged except for the tables the
  migration is meant to populate, and every difference is explained.
- No unvalidated foreign keys; the ledger still nets to zero.
- Both schema documents are regenerated and pass `--check --strict`.
- The revision is additive, or the destructive part was explicitly approved.
- `docs/15_migration_and_rollback_guide.md` is updated if the procedure changed.

## Expected outputs

- One or more `backend/alembic/versions/<rev>_<slug>.py` revisions with `downgrade()`.
- Updated models, the `env.py`/generator import lists, and `schema_descriptions.py`.
- Regenerated `docs/06_database_design.sql` and `docs/06b_database_design_annotated.sql`.
- An updated verification table in `docs/15`.
- A migration or data-loss risk entry in `docs/17` when anything is irreversible.
