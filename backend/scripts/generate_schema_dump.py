"""Compatibility wrapper for the single generated schema reference.

The canonical file is ``docs/06_database_design.sql`` and is produced by
``scripts/generate_schema_docs.py`` (DDL plus a description for every table and
column). This entry point is kept so existing commands and CI jobs that call
``generate_schema_dump.py`` continue to regenerate that same file::

    uv run python scripts/generate_schema_dump.py
    uv run python scripts/generate_schema_dump.py --check

Alembic remains the migration source of truth. The SQL file is documentation,
not an automatic production migration.
"""

from __future__ import annotations

from generate_schema_docs import main

if __name__ == "__main__":
    raise SystemExit(main())
