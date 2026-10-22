"""Request schema for the shared record-status endpoint."""

from __future__ import annotations

from app.core.validation import FieldSpec, RecordSchema

STATUS_CHANGE_SCHEMA = RecordSchema(
    (
        FieldSpec("status", required=True, min_length=1, max_length=32),
        FieldSpec("reason", max_length=2_000, aliases=("notes", "note")),
    ),
    reject_unknown=True,
)
