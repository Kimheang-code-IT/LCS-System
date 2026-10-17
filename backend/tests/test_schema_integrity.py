"""Schema-level guarantees for the structures added by the additive migrations.

The PostgreSQL triggers and views cannot run on the SQLite test database, but the
*declarative* guarantees can: partial unique indexes, check constraints, unique
constraints and foreign keys all live in ``Base.metadata`` and therefore in the
schema the tests actually build. ``backend/tests/sql/integrity_guards.sql``
exercises the runtime behaviour against PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy import UniqueConstraint
from sqlalchemy.schema import CheckConstraint

from app.core.database import Base


def _index_named(table: str, name: str):
    matches = [index for index in Base.metadata.tables[table].indexes if index.name == name]
    assert matches, f"{table} has no index named {name}"
    return matches[0]


def _check_named(table: str, name: str):
    for constraint in Base.metadata.tables[table].constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == name:
            return constraint
    raise AssertionError(f"{table} has no check constraint named {name}")


def _unique_on(table: str, columns: set[str]):
    for constraint in Base.metadata.tables[table].constraints:
        if isinstance(constraint, UniqueConstraint) and {c.name for c in constraint.columns} == columns:
            return constraint
    raise AssertionError(f"{table} has no unique constraint on {sorted(columns)}")


def test_the_currency_master_keeps_codes_unique_among_active_rows():
    index = _index_named("currencies", "uq_currencies_code_active")
    assert index.unique is True
    assert {column.name for column in index.columns} == {"code"}
    # Archived rows keep their code so historic documents still resolve, which is
    # why uniqueness is scoped to rows that are not soft-deleted.
    assert "deleted_at IS NULL" in str(index.dialect_options["postgresql"]["where"])
    assert "deleted_at IS NULL" in str(index.dialect_options["sqlite"]["where"])


def test_app_settings_keys_are_unique():
    table = Base.metadata.tables["app_settings"]
    assert {column.name for column in table.primary_key.columns} == {"id"}
    _unique_on("app_settings", {"setting_key"})
    assert table.columns["setting_value"].nullable is False


def test_only_one_configuration_version_can_be_published():
    index = _index_named("configuration_versions", "uq_configuration_versions_published")
    assert index.unique is True
    assert "status = 'PUBLISHED'" in str(index.dialect_options["postgresql"]["where"])
    assert "status = 'PUBLISHED'" in str(index.dialect_options["sqlite"]["where"])


def test_configuration_version_numbers_are_unique_and_snapshots_are_required():
    _unique_on("configuration_versions", {"version_no"})
    table = Base.metadata.tables["configuration_versions"]
    assert table.columns["config_snapshot"].nullable is False
    assert table.columns["status"].nullable is False


def test_configuration_version_pointers_are_nullable_foreign_keys():
    """A missing version must never orphan a tab, a row or an order."""
    for table, column in (
        ("component_tabs", "config_version_id"),
        ("service_order_component_rows", "config_version_id"),
        ("service_orders", "configuration_version_id"),
    ):
        target = Base.metadata.tables[table].columns[column]
        assert target.nullable is True, f"{table}.{column} must be nullable"
        assert {fk.column.table.name for fk in target.foreign_keys} == {"configuration_versions"}


def test_every_added_foreign_key_targets_an_existing_table():
    for table in ("currencies", "app_settings", "configuration_versions"):
        assert table in Base.metadata.tables
        for foreign_key in Base.metadata.tables[table].foreign_keys:
            assert foreign_key.column.table.name in Base.metadata.tables


def test_financial_amounts_stay_numeric_not_float():
    """Money must never be stored as a binary float."""
    for table, columns in (
        ("currencies", ()),
        ("financial_documents", ("total_amount", "subtotal_amount", "tax_amount", "paid_amount")),
        ("financial_document_lines", ("unit_price", "line_amount")),
        ("journal_entry_lines", ("debit_amount", "credit_amount", "base_debit_amount", "base_credit_amount")),
        ("payment_allocations", ()),
    ):
        for column in columns:
            column_type = Base.metadata.tables[table].columns[column].type
            assert column_type.__class__.__name__ == "Numeric", f"{table}.{column} is {column_type}"
            assert column_type.asdecimal is True, f"{table}.{column} must decode to Decimal"


def test_timestamps_are_timezone_aware_everywhere():
    """Naive timestamps would silently shift financial periods across timezones."""
    offenders: list[str] = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.name not in {"created_at", "updated_at", "deleted_at"}:
                continue
            if column.type.__class__.__name__ != "DateTime":
                continue
            if not column.type.timezone:
                offenders.append(f"{table.name}.{column.name}")
    assert not offenders, f"timestamps without a timezone: {sorted(offenders)}"
