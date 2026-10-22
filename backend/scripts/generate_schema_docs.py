"""Generate ``docs/06_database_design.sql`` from the live SQLAlchemy models.

This is the single canonical schema reference for the project. It renders the
PostgreSQL DDL, plus a description for every table and every column, two ways:

* ``--`` inline comments, so the file reads well for a human scanning it;
* ``COMMENT ON TABLE`` / ``COMMENT ON COLUMN`` statements, so the prose is
  stored in the database and is queryable through ``pg_description``.

Usage (from ``backend/``)::

    uv run python scripts/generate_schema_docs.py            # write the file
    uv run python scripts/generate_schema_docs.py --check     # fail if stale
    uv run python scripts/generate_schema_docs.py --strict    # also fail on undocumented columns

The DDL itself is compiled with SQLAlchemy against the PostgreSQL dialect, so
it always reflects the models; the prose comes from
``scripts/schema_descriptions.py``. Alembic remains the migration source of
truth — this file is documentation, not a migration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "06_database_design.sql"

# The generator lives outside the package, so make both roots importable when it
# is run as a plain script (`python scripts/generate_schema_docs.py`).
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from schema_descriptions import (  # noqa: E402
    MODULE_TITLES,
    TABLE_DESCRIPTIONS,
    describe_column,
)
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable, sort_tables  # noqa: E402

import app.modules.archive.models  # noqa: E402, F401  (populates Base.metadata)
import app.modules.audit.models  # noqa: E402, F401
import app.modules.auth.models  # noqa: E402, F401
import app.modules.backup.models  # noqa: E402, F401
import app.modules.finance.models  # noqa: E402, F401
import app.modules.master_data.models  # noqa: E402, F401
import app.modules.operations.models  # noqa: E402, F401
import app.modules.quotations.models  # noqa: E402, F401
import app.modules.settings.models  # noqa: E402, F401
from app.core.database import Base  # noqa: E402

DIALECT = postgresql.dialect()
# Rule lines are prefixed with `--` so the whole file is valid SQL and can be fed
# straight to `psql -f`, not just read.
SECTION_RULE = "-- " + "=" * 74
SUBSECTION_RULE = "-- " + "-" * 74
UNMAPPED_MODULE = "<unmapped>"

PREAMBLE = """\
-- Freight Forwarding, Service Operations, and Double-Entry Finance
-- PostgreSQL schema reference.
--
-- GENERATED FILE - DO NOT EDIT BY HAND.
-- Regenerate from backend/ with:
--     cd backend && uv run python scripts/generate_schema_docs.py
-- Check that it is up to date (used by CI and tests/test_schema_docs.py) with:
--     cd backend && uv run python scripts/generate_schema_docs.py --check
--
-- DDL is compiled from the live SQLAlchemy models (the same import list as
-- backend/alembic/env.py) against the PostgreSQL dialect, so it always reflects
-- the current schema. Alembic remains the migration source of truth; this file is
-- documentation only. It is a reference schema, not an automatic production
-- migration: do not run it against an existing database.
--
-- Every table and column carries its meaning twice: once as an inline `--`
-- comment for readers of this file, and once as an executable `COMMENT ON`
-- statement. The latter means the descriptions live in the database and can be
-- read back with:
--
--     SELECT c.relname AS table_name, a.attname AS column_name,
--            col_description(c.oid, a.attnum) AS description
--     FROM pg_class c
--     JOIN pg_namespace n ON n.oid = c.relnamespace
--     JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
--     WHERE n.nspname = 'public'
--     ORDER BY c.relname, a.attnum;
--
-- Applying the file to an empty database creates the schema together with all
-- descriptions. Applying the COMMENT ON section to an existing database refreshes
-- the prose without touching data:
--
--     psql -d "$DATABASE_URL" -f docs/06_database_design.sql
--
-- ---------------------------------------------------------------------------
-- Conventions
-- ---------------------------------------------------------------------------
-- * Tables are emitted in foreign-key dependency order, so the file can be run
--   top to bottom without deferring constraints.
-- * There is no multi-tenancy. Organizations and branches were removed
--   (migration b7f1c2a9d4e0_remove_organization_and_branch); access is governed
--   by users, roles and permissions only.
-- * No SQL enum types. Status-like columns are plain VARCHAR so new values do not
--   require a migration; the permitted values are listed in each description.
-- * PKMixin supplies `id BIGSERIAL`; TimestampMixin supplies `created_at` and
--   `updated_at`. Because the mixins are applied last they appear after the
--   table's own columns below.
-- * SoftDeleteMixin (on master-data tables) supplies `deleted_at` and
--   `deleted_by_user_id`. A non-NULL `deleted_at` archives the row: it leaves
--   listings and uniqueness checks but stays in place so historic documents keep
--   resolving. This is why those tables use partial unique indexes
--   (`... _active`) instead of plain UNIQUE constraints.
-- * JSONB columns hold module-specific payloads for collections that are driven
--   by the frontend schema rather than dedicated relational columns.
-- * Money is NUMERIC(19,4) in the document currency. Exchange rates are
--   NUMERIC(19,8). Journal lines also carry base-currency amounts so the ledger
--   balances across currencies.
-- * All timestamps are `TIMESTAMP WITH TIME ZONE` and are stored in UTC.
-- * The database ships empty. First-run provisioning (`/auth/setup`) seeds only
--   the permission catalog, the built-in
--   Platform Administrator role, the current-year document sequences and the
--   default app info/config — no finance or business data.
--
-- ---------------------------------------------------------------------------
-- Known divergences from the migrations (verified against PostgreSQL 16)
-- ---------------------------------------------------------------------------
-- This file mirrors the SQLAlchemy models. Building a database from these
-- statements and building one with `alembic upgrade head` currently differ in
-- exactly two places, both pre-existing model/migration drift:
--
--   1. archive_records.snapshot_json — migration e3f4a5b6c7d8 created this with
--      sa.JSON(), so the migrated column is `json`. The model uses JSONType, which
--      is JSONB on PostgreSQL, so this file emits `jsonb`.
--   2. business_parties.roles — migration a5b6c7d8e9f0 added
--      server_default `'[]'::jsonb`. The model declares only a Python-side
--      `default=list`, so this file emits no server default.
--
-- Every other table, column, constraint and index is identical between the two.
"""


def _one_line(text: str) -> str:
    """Collapse a description to a single line for use inside a COMMENT literal."""
    return " ".join(text.split())


def _sql_literal(text: str) -> str:
    """Quote text as a single-quoted PostgreSQL string literal."""
    return "'" + _one_line(text).replace("'", "''") + "'"


def _comment_block(text: str, prefix: str = "-- ") -> list[str]:
    """Render a description as a run of `--` comment lines, wrapped to 78 columns."""
    words = _one_line(text).split(" ")
    lines: list[str] = []
    current = prefix
    for word in words:
        candidate = f"{current} {word}" if current.strip() != "--" else f"{prefix}{word}"
        if len(candidate) > 78 and current.strip() != "--":
            lines.append(current)
            current = f"{prefix}{word}"
        else:
            current = candidate
    if current.strip() != "--":
        lines.append(current)
    return lines


def _module_of(table_name: str) -> str:
    """Return the declaring module for a mapped table.

    Every table is expected to be mapped to an ORM class, which is what lets the
    generated file label each table with its owning module. An unmapped table is
    reported by ``build_document`` rather than silently labelled "unknown".
    """
    for mapper in sorted(Base.registry.mappers, key=lambda m: (m.class_.__module__, m.class_.__name__)):
        local_table = mapper.local_table
        if local_table is not None and local_table.name == table_name:
            return mapper.class_.__module__
    return UNMAPPED_MODULE


def _render_table(table) -> tuple[list[str], list[str]]:
    """Render one table: inline comments, CREATE TABLE, indexes and COMMENT ON."""
    name = table.name
    description = TABLE_DESCRIPTIONS.get(name)
    missing: list[str] = []

    out: list[str] = [SUBSECTION_RULE]
    out.append(f"-- Table: {name}")
    module = _module_of(name)
    if module == UNMAPPED_MODULE:
        missing.append(f"{name} (table is not mapped to an ORM class)")
    out.append(f"-- Module: {MODULE_TITLES.get(module, module)}  [{module}]")
    if description:
        out.extend(_comment_block(description))
    else:
        out.append("-- (no description recorded in scripts/schema_descriptions.py)")
        missing.append(f"table {name}")
    out.append(SUBSECTION_RULE)

    # Compile the whole CREATE TABLE so SQLAlchemy produces the canonical DDL,
    # including the hash-truncated long foreign-key names that the naming
    # convention generates (e.g. fk_service_order_containers_..._se_2d3c). Rendering
    # constraints by hand would silently disagree with the Alembic-migrated schema.
    ddl = str(CreateTable(table).compile(dialect=DIALECT)).strip()
    if not ddl.endswith(";"):
        ddl += ";"

    column_names = {column.name for column in table.columns}
    column_comments = {column.name: column.comment for column in table.columns}
    ddl_lines = ddl.splitlines()
    body: list[str] = []
    for position, raw in enumerate(ddl_lines):
        # SQLAlchemy indents with a tab and leaves a trailing space before the
        # comma; normalise both so the comments above each column line up. The
        # opening `CREATE TABLE (` and closing `);` stay flush left.
        stripped = raw.lstrip().rstrip()
        head = stripped.split(" ", 1)[0].rstrip(",")
        if stripped and head in column_names:
            description_text = describe_column(name, head) or column_comments[head]
            if description_text:
                body.extend(_comment_block(description_text, prefix="    -- "))
            else:
                body.append(f"    -- (undocumented column {name}.{head})")
                missing.append(f"{name}.{head}")
        if not stripped:
            body.append("")
        elif position == 0 or position == len(ddl_lines) - 1:
            body.append(stripped)
        else:
            body.append(f"    {stripped}")

    out.extend(body)

    # Indexes (UniqueConstraints already rendered inline above).
    for index in sorted(table.indexes, key=lambda i: i.name or ""):
        out.append(str(CreateIndex(index).compile(dialect=DIALECT)).strip() + ";")

    # Executable descriptions, stored in the database alongside the schema.
    if description:
        out.append("")
        out.append(f"COMMENT ON TABLE {name} IS {_sql_literal(description)};")
    for column in table.columns:
        description_text = describe_column(name, column.name) or column.comment
        if description_text:
            out.append(
                f"COMMENT ON COLUMN {name}.{column.name} IS {_sql_literal(description_text)};"
            )
    out.append("")

    return out, missing


def build_document() -> tuple[str, list[str]]:
    """Render the whole annotated schema. Returns (sql_text, missing_descriptions).

    The table order is a single global foreign-key dependency sort, NOT grouped by
    module: reordering by module would place, say, ``backup_runs`` (which references
    ``users``) before ``users`` exists and the file would no longer be executable.
    Because the dependency order interleaves modules, each table carries its own
    one-line module label instead of the file being split into module sections.
    """
    named_tables = [Base.metadata.tables[name] for name in sorted(Base.metadata.tables)]
    ordered = sort_tables(named_tables)

    lines: list[str] = [PREAMBLE.rstrip(), ""]
    missing: list[str] = []

    for table in ordered:
        rendered, table_missing = _render_table(table)
        lines.extend(rendered)
        missing.extend(table_missing)

    lines.append(SECTION_RULE)
    lines.append(f"-- END OF SCHEMA - {len(ordered)} tables")
    lines.append(SECTION_RULE)
    lines.append("")

    return "\n".join(lines), missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Target SQL file.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit non-zero if the target file differs from the rendered output.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any table or column has no description.",
    )
    args = parser.parse_args()

    rendered, missing = build_document()

    if missing:
        preview = "\n".join(f"  - {item}" for item in missing)
        print(f"WARNING: {len(missing)} undocumented schema objects:\n{preview}", file=sys.stderr)
    else:
        print(f"All {len(Base.metadata.tables)} tables and their columns are documented.")

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != rendered:
            print(f"STALE: {args.output} does not match the models. Re-run without --check.")
            return 1
        print(f"Up to date: {args.output}")
        if args.strict and missing:
            return 1
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {args.output} ({len(rendered.splitlines())} lines).")

    if args.strict and missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())