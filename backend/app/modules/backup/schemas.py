"""Request schema for restoring a backup.

The typed confirmation and the table allow-list are request-shape checks; the
restore itself still matches table names against the models it discovers, so an
unknown name cannot be used as SQL.
"""

from __future__ import annotations

from app.core.validation import INVALID_TYPE, CrossFieldRule, FieldSpec, RecordSchema


def _tables_is_a_list(values: dict) -> tuple[str, str, str] | None:
    tables = values.get("tables")
    if tables is None or isinstance(tables, list):
        return None
    return "tables", INVALID_TYPE, "Provide a list of table names."


RESTORE_BACKUP_SCHEMA = RecordSchema(
    (
        FieldSpec("confirm", required=True, min_length=1, max_length=32),
        FieldSpec("tables", kind="json"),
    ),
    cross_field=(CrossFieldRule(("tables",), _tables_is_a_list),),
    reject_unknown=True,
)
