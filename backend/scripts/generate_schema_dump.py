"""Generate the raw ``docs/06_database_design.sql`` dump from the SQLAlchemy models.

``docs/06b_database_design_annotated.sql`` is produced by
``scripts/generate_schema_docs.py``; this script produces its un-annotated
companion. ``tests/test_schema_docs.py`` asserts that the two files describe the
same schema, so both must be regenerated together whenever a model changes::

    uv run python scripts/generate_schema_docs.py     # annotated (06b)
    uv run python scripts/generate_schema_dump.py     # raw dump (06)

Both render DDL by compiling the live SQLAlchemy models against the PostgreSQL
dialect. That matters: the naming convention hash-truncates long foreign-key
names (for example ``fk_service_order_charge_lines_service_order_charge_id_s_b0ca``),
so hand-written DDL silently drifts from what Alembic actually creates.

The table order is the same global foreign-key dependency sort used by the
annotated generator, so the file can be applied top to bottom.

Usage (from ``backend/``)::

    uv run python scripts/generate_schema_dump.py           # write the file
    uv run python scripts/generate_schema_dump.py --check    # fail if stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "06_database_design.sql"

# The generator lives outside the package, so make the backend root importable
# when it is run as a plain script.
sys.path.insert(0, str(BACKEND_ROOT))

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

HEADER = """\
-- Freight Forwarding, Service Operations, and Double-Entry Finance
-- Consolidated PostgreSQL schema (design reference).
--
-- Generated from the live SQLAlchemy models in
--   backend/app/core/database.py + backend/app/modules/*/models.py
-- The Alembic migrations in backend/alembic/ remain the migration source of
-- truth; this file mirrors the resulting schema for design/reference use.
--
-- {table_count} tables. The database ships empty after migration. First-run
-- provisioning seeds only the permission catalog, the built-in Platform
-- Administrator role, the current-year document sequences, the default app
-- info/config settings and the currency master seeded from the supported
-- currency list.
--
-- NOTE: Organizations and branches are NOT part of this schema. Multi-tenancy
-- was removed (migration b7f1c2a9d4e0_remove_organization_and_branch.py); access
-- is governed entirely by users, roles and permissions. Status-like columns are
-- plain VARCHAR values (no SQL enum types)."""


def build_dump() -> str:
    """Render the whole raw schema dump."""
    named_tables = [Base.metadata.tables[name] for name in sorted(Base.metadata.tables)]
    ordered = sort_tables(named_tables)

    lines: list[str] = [HEADER.format(table_count=len(ordered)), ""]
    for table in ordered:
        ddl = str(CreateTable(table).compile(dialect=DIALECT)).strip()
        if not ddl.endswith(";"):
            ddl += ";"
        lines.extend(ddl.splitlines())
        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            lines.append(str(CreateIndex(index).compile(dialect=DIALECT)).strip() + ";")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Target SQL file.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the file on disk differs from the generated output.",
    )
    args = parser.parse_args()

    rendered = build_dump()
    target: Path = args.output

    if args.check:
        if not target.exists():
            print(f"{target} is missing; run scripts/generate_schema_dump.py", file=sys.stderr)
            return 1
        if target.read_text(encoding="utf-8") != rendered:
            print(f"{target} is stale; run scripts/generate_schema_dump.py", file=sys.stderr)
            return 1
        print(f"{target} is up to date")
        return 0

    target.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {target} ({len(Base.metadata.tables)} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
