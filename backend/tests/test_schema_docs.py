"""Guards the single generated schema documentation against model drift.

``docs/06_database_design.sql`` is produced by ``scripts/generate_schema_docs.py``.
These tests make sure it cannot silently fall behind the SQLAlchemy models, that
every table and column is documented, and that the project keeps exactly one SQL
reference file.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SCHEMA_SQL = REPO_ROOT / "docs" / "06_database_design.sql"
GENERATOR = BACKEND_ROOT / "scripts" / "generate_schema_docs.py"

sys.path.insert(0, str(BACKEND_ROOT / "scripts"))


@pytest.fixture(scope="module")
def generator_module():
    """Import the generator so Base.metadata is populated by its model imports."""
    import generate_schema_docs

    return generate_schema_docs


def test_generator_output_is_committed(generator_module) -> None:
    """The checked-in file must match what the generator renders today."""
    rendered, _missing = generator_module.build_document()
    assert SCHEMA_SQL.exists(), f"{SCHEMA_SQL} is missing; run scripts/generate_schema_docs.py"
    committed = SCHEMA_SQL.read_text(encoding="utf-8")
    assert committed == rendered, (
        f"{SCHEMA_SQL} is stale. Regenerate it with:\n"
        "    cd backend && uv run python scripts/generate_schema_docs.py"
    )


def test_every_table_and_column_is_documented(generator_module) -> None:
    """No table or column may ship without prose."""
    _rendered, missing = generator_module.build_document()
    assert not missing, "Undocumented schema objects:\n" + "\n".join(f"  - {item}" for item in missing)


def test_description_catalogue_has_no_stale_entries(generator_module) -> None:
    """The catalogue must not describe tables or columns that no longer exist."""
    from schema_descriptions import COLUMN_DESCRIPTIONS, TABLE_DESCRIPTIONS

    tables = set(generator_module.Base.metadata.tables)
    stale_tables = set(TABLE_DESCRIPTIONS) - tables
    assert not stale_tables, f"Descriptions for removed tables: {sorted(stale_tables)}"

    for table_name, columns in COLUMN_DESCRIPTIONS.items():
        if table_name not in tables:
            continue
        live = {column.name for column in generator_module.Base.metadata.tables[table_name].columns}
        stale_columns = set(columns) - live
        assert not stale_columns, f"Descriptions for removed columns on {table_name}: {sorted(stale_columns)}"


def test_docs_contains_exactly_one_sql_file() -> None:
    """The documentation set keeps one schema reference, not parallel SQL files."""
    sql_files = sorted((REPO_ROOT / "docs").glob("*.sql"))
    assert sql_files == [SCHEMA_SQL], f"unexpected SQL files in docs: {sql_files}"


def test_comment_statements_cover_every_table_and_column(generator_module) -> None:
    """Each table and column needs an executable COMMENT ON statement."""
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    tables = generator_module.Base.metadata.tables

    for table_name, table in tables.items():
        assert f"COMMENT ON TABLE {table_name} IS " in sql, f"missing COMMENT ON TABLE {table_name}"
        for column in table.columns:
            pattern = rf"^COMMENT ON COLUMN {re.escape(table_name)}\.{re.escape(column.name)} IS "
            assert re.search(pattern, sql, re.MULTILINE), (
                f"missing COMMENT ON COLUMN {table_name}.{column.name}"
            )


def test_generator_does_not_mutate_metadata(generator_module) -> None:
    """Running the generator must leave Base.metadata usable.

    Compiling ``sqlalchemy.schema.AddConstraint`` detaches the constraint from its
    table, so an earlier version of the generator silently stripped every PRIMARY
    KEY and UNIQUE constraint from the metadata it had already visited. The test
    suite then failed with ``NOT NULL constraint failed: permissions.id`` because
    SQLite no longer saw ``permissions`` as ``INTEGER PRIMARY KEY``. Rendering via
    ``CreateTable`` avoids that; this test pins the behaviour so it cannot regress.
    """
    from sqlalchemy.dialects import sqlite
    from sqlalchemy.schema import CreateTable

    tables = generator_module.Base.metadata.tables

    def ddl_snapshot() -> dict[str, str]:
        return {
            name: str(CreateTable(table).compile(dialect=sqlite.dialect()))
            for name, table in tables.items()
        }

    before = ddl_snapshot()
    generator_module.build_document()
    after = ddl_snapshot()

    assert before == after, "The generator mutated Base.metadata; DDL changed after running it"

    # A spot check that makes the failure mode obvious if the comparison is weakened.
    permissions = after["permissions"]
    assert "CONSTRAINT pk_permissions PRIMARY KEY (id)" in permissions
    assert "id INTEGER NOT NULL" in permissions


def test_check_mode_passes_on_a_clean_tree(generator_module) -> None:
    """`--check` is what CI calls; it must exit zero on an up-to-date file."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(GENERATOR), "--check", "--strict"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr