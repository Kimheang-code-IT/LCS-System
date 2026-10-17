"""Reusable deletion policy.

Deleting a row that other rows still reference destroys history: a posted journal
would lose its account, a document would lose its party, a restored archive record
would point at nothing. Every delete path therefore has to ask two questions:

1. May this record be deleted at all right now? (Module-specific lifecycle rule —
   a posted document may not, a draft may.)
2. Is anything still pointing at it? (This module.)

The reference scan is deliberately generic — it walks the SQLAlchemy metadata rather
than naming tables — so a new foreign key automatically becomes a blocker without
anyone remembering to update a list. Module lifecycle rules stay in the module
service; this module never overrides them.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict

# Tombstone and audit tables are append-only history *about* a record, not live
# dependents, so they must never block a deletion.
_NON_BLOCKING_TABLES = frozenset({"archive_records", "audit_events"})


async def dependent_references(session: AsyncSession, row: Any) -> list[str]:
    """Return ``"<table> (<count>)"`` for every foreign key still pointing at ``row``.

    Reads the mapper metadata, so the result is always in step with the schema.
    """
    from app.core.database import Base

    table_name = row.__table__.name
    found: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name in _NON_BLOCKING_TABLES or table.name == table_name:
            # A self-reference is still a real dependency, but it is reported by
            # the caller's own module rule (a chart of accounts parent, for
            # example, is handled where the hierarchy is understood). Skipping it
            # here avoids reporting the row against itself.
            continue
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table.name != table_name or foreign_key.column.name != "id":
                continue
            count = await session.scalar(
                select(func.count()).select_from(table).where(foreign_key.parent == row.id)
            )
            if count:
                found.append(f"{table.name} ({count})")
    return sorted(set(found))


async def ensure_deletable(
    session: AsyncSession,
    row: Any,
    *,
    label: str,
    code: str = "DELETE_BLOCKED_BY_REFERENCES",
    detail: str | None = None,
) -> None:
    """Raise ``Conflict`` when ``row`` is still referenced by another table.

    The message names the referencing tables so an operator can see what has to be
    dealt with instead of guessing, and the caller's ``code`` distinguishes one
    module's rule from another's.
    """
    references = await dependent_references(session, row)
    if not references:
        return
    reason = f"{label} is still referenced by {', '.join(references)}."
    if detail:
        reason = f"{reason} {detail}"
    raise Conflict(code, reason)


async def require_inactive(status_value: Any, *, label: str, code: str = "RECORD_ACTIVE") -> None:
    """Refuse to delete a record that is still active.

    Mirrors the master-data rule (``REFERENCE_ACTIVE``): deactivate first, then
    delete, so a delete is always a deliberate second step.
    """
    if str(status_value or "").strip().upper() == "ACTIVE":
        raise Conflict(
            code,
            f"Active {label} cannot be deleted. Deactivate the record first.",
        )
