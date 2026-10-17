"""Guards the generated schema documentation against model drift.

``docs/06b_database_design_annotated.sql`` is produced by
``scripts/generate_schema_docs.py``. These tests make sure it cannot silently
fall behind the SQLAlchemy models, that every table and column is documented,
and that its DDL still agrees with the raw dump in ``docs/06_database_design.sql``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
ANNOTATED_SQL = REPO_ROOT / "docs" / "06b_database_design_annotated.sql"
RAW_SQL = REPO_ROOT / "docs" / "06_database_design.sql"
GENERATOR = BACKEND_ROOT / "scripts" / "generate_schema_docs.py"

sys.path.insert(0, str(BACKEND_ROOT / "scripts"))


def _split_top_level(body: str) -> list[str]:
    """Split a CREATE TABLE body on commas that are not nested in parentheses."""
    chunks: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            chunks.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        chunks.append("".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _schema_signature(sql: str) -> set[tuple]:
    """Reduce DDL to an order-insensitive structural signature.

    The two documents are produced by different tools, so the order of columns
    and constraints inside a CREATE TABLE is not comparable — only the set of
    them is. Comments and COMMENT ON statements carry no schema meaning and are
    dropped; COMMENT ON is filtered line-by-line rather than after splitting on
    ``;``, because descriptions themselves contain semicolons.
    """
    signature: set[tuple] = set()

    keep: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or stripped.startswith("COMMENT ON "):
            continue
        keep.append(line)
    body = "\n".join(keep)

    for raw in body.split(";"):
        statement = " ".join(raw.split())
        if not statement:
            continue

        alter = re.fullmatch(
            r"ALTER TABLE (\w+) ADD (CONSTRAINT .*)", statement, re.IGNORECASE
        )
        if alter:
            signature.add(("constraint", alter.group(1).lower(), _norm(alter.group(2))))
            continue

        create = re.fullmatch(r"CREATE TABLE (\w+) \((.*)\)", statement, re.IGNORECASE | re.DOTALL)
        if create:
            table = create.group(1).lower()
            for chunk in _split_top_level(create.group(2)):
                if chunk.upper().startswith("CONSTRAINT "):
                    signature.add(("constraint", table, _norm(chunk)))
                else:
                    column, _, definition = chunk.partition(" ")
                    signature.add(("column", table, column.lower(), _norm(definition)))
            continue

        if statement.upper().startswith(("CREATE INDEX", "CREATE UNIQUE INDEX")):
            signature.add(("index", _norm(statement)))
            continue

        signature.add(("statement", _norm(statement)))

    return signature


def _norm(text: str) -> str:
    return " ".join(text.split()).upper()


@pytest.fixture(scope="module")
def generator_module():
    """Import the generator so Base.metadata is populated by its model imports."""
    import generate_schema_docs

    return generate_schema_docs


def test_generator_output_is_committed(generator_module) -> None:
    """The checked-in file must match what the generator renders today."""
    rendered, _missing = generator_module.build_document()
    assert ANNOTATED_SQL.exists(), f"{ANNOTATED_SQL} is missing; run scripts/generate_schema_docs.py"
    committed = ANNOTATED_SQL.read_text(encoding="utf-8")
    assert committed == rendered, (
        f"{ANNOTATED_SQL} is stale. Regenerate it with:\n"
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


def test_annotated_ddl_matches_the_raw_dump(generator_module) -> None:
    """The annotated file must describe the same schema as the plain dump."""
    assert RAW_SQL.exists(), f"{RAW_SQL} is missing"
    annotated = _schema_signature(ANNOTATED_SQL.read_text(encoding="utf-8"))
    raw = _schema_signature(RAW_SQL.read_text(encoding="utf-8"))

    only_annotated = sorted(annotated - raw)
    only_raw = sorted(raw - annotated)
    assert annotated == raw, (
        "The annotated schema and docs/06_database_design.sql have drifted.\n"
        f"Only in annotated ({len(only_annotated)}): {only_annotated[:10]}\n"
        f"Only in raw dump ({len(only_raw)}): {only_raw[:10]}\n"
        "Regenerate with: cd backend && uv run python scripts/generate_schema_docs.py"
    )


def test_comment_statements_cover_every_table_and_column(generator_module) -> None:
    """Each table and column needs an executable COMMENT ON statement."""
    sql = ANNOTATED_SQL.read_text(encoding="utf-8")
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