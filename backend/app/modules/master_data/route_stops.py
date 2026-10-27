"""Place-role aware route stops, shared by quotations and service orders.

A route stop records *which configured role* the stop plays and a free-text
location. The role is validated against the live configuration here, so the
quotation form and the service-order form cannot drift apart:

* a role must exist, and must be active for a **new** stop;
* a role that already belongs to this document stays valid after it is
  deactivated, which is what keeps historical routes readable and editable;
* the submitted order wins over any client-supplied sequence number, so a
  duplicate sequence can never be stored.

The text snapshots (``place_role`` / ``free_text``) are kept beside the id so a
printed route never depends on the role still being active.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailed
from app.core.validation import FieldSpec, RecordSchema, validate_line_items
from app.modules.master_data.models import PlaceRole

#: A route stop as the forms submit it. ``planned``/``actual`` accept an ISO date
#: or date-time; the repository columns are timestamps.
ROUTE_STOP_SCHEMA = RecordSchema(
    (
        FieldSpec("placeRoleId", kind="reference", aliases=("place_role_id",)),
        FieldSpec("placeRole", max_length=64, aliases=("place_role",)),
        FieldSpec("place", max_length=500, aliases=("freeText", "free_text")),
        FieldSpec(
            "planned",
            kind="datetime",
            aliases=("plannedAt", "planned_at", "plannedActual", "planned_actual"),
        ),
        FieldSpec("actual", kind="datetime", aliases=("actualAt", "actual_at")),
        FieldSpec("notes", max_length=2_000),
    ),
    readonly=("id", "sequence", "sequenceNo", "createdAt", "updatedAt"),
)

#: Keys that mean the operator has actually started the row. The route editor
#: keeps a trailing blank row for data entry, and that row is not part of the
#: document. Any entered value counts, so a half-filled row is validated (and its
#: missing references are reported) instead of silently disappearing on save.
_ROUTE_ROW_KEYS = ("placeRoleId", "placeRole", "place", "freeText", "planned", "plannedActual", "actual", "notes")


def route_row_started(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    return any(str(row.get(key) or "").strip() for key in _ROUTE_ROW_KEYS)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


async def _role_for(session: AsyncSession, value: Any) -> PlaceRole | None:
    """Resolve a role reference, including an archived row.

    Archived rows stay resolvable so a route that already points at one remains
    readable and saveable; the status check below refuses them for a new stop.
    """
    role_id = _as_int(value)
    if role_id is not None:
        return await session.get(PlaceRole, role_id)
    text = str(value or "").strip()
    if not text:
        return None
    return (
        await session.execute(
            select(PlaceRole).where(or_(PlaceRole.code == text, PlaceRole.name == text))
        )
    ).scalars().first()


async def resolve_route_stops(
    session: AsyncSession,
    rows: Any,
    *,
    field: str = "places",
    existing_rows: dict[int, int | None] | None = None,
) -> list[dict[str, Any]]:
    """Validate and normalise route rows into storable stop dictionaries.

    ``existing_rows`` maps the id of every already-saved stop to its stored
    ``place_role_id``. A row that round-trips that id may keep an inactive role;
    a new row (no id) must select an active record, and editing an existing row
    to a different inactive role is refused. Errors are keyed
    ``places.<row>.<column>`` so the table can show each one under its input.
    """
    known = existing_rows or {}
    supplied = [row for row in (rows or []) if route_row_started(row)]
    items = validate_line_items(supplied, ROUTE_STOP_SCHEMA, field=field)

    errors: dict[str, str] = {}
    resolved: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        submitted_id = _as_int(item.get("id"))
        row_id = submitted_id if submitted_id in known else None
        stored_role_id = known.get(row_id)

        role_ref = item.get("placeRoleId") or item.get("placeRole")
        role = await _role_for(session, role_ref)
        if role is None:
            key = f"{field}.{index}.placeRoleId"
            errors[key] = "Required." if role_ref in (None, "") else "Choose a valid place role."
        elif str(role.status or "").upper() != "ACTIVE" and stored_role_id != role.id:
            errors[f"{field}.{index}.placeRoleId"] = "This place role is inactive."

        # A stop must say where it happens; a role without a location cannot be
        # printed as a route. Historical rows stay readable, but editing one now
        # asks for the missing location.
        place = str(item.get("place") or "").strip()
        if not place:
            errors[f"{field}.{index}.place"] = "Required."

        resolved.append(
            {
                "row_id": row_id,
                "place_role_id": role.id if role is not None else None,
                "place_role": (role.name if role is not None else str(item.get("placeRole") or ""))[:32],
                "place": place[:500],
                "planned_at": item.get("planned"),
                "actual_at": item.get("actual"),
                "notes": item.get("notes"),
            }
        )

    if errors:
        raise ValidationFailed("Please correct the route stops.", errors)
    return resolved


async def save_route_stops(
    session: AsyncSession,
    *,
    model: Any,
    parent_field: str,
    parent_id: int,
    rows: Any,
    field: str = "places",
) -> list[dict[str, Any]]:
    """Validate the submitted route and persist it in place.

    Existing rows are updated rather than deleted and re-created, so a row id
    stays stable across saves. That stability is what lets a later save keep an
    already-deactivated role: the row still identifies itself as the historical
    stop. Rows the operator removed from the list are deleted explicitly. The
    returned payloads carry the stored ids.
    """
    existing = list(
        (
            await session.execute(
                select(model).where(getattr(model, parent_field) == parent_id)
            )
        ).scalars().all()
    )
    by_id = {int(row.id): row for row in existing}
    stops = await resolve_route_stops(
        session,
        rows,
        field=field,
        existing_rows={int(row.id): row.place_role_id for row in existing},
    )

    # Reordering swaps sequence numbers, and the unique constraint is checked
    # per statement, so park every existing row on a unique temporary negative
    # sequence before assigning the final 1..n order.
    if existing:
        for row in existing:
            row.sequence_no = -int(row.id)
        await session.flush()

    kept: set[int] = set()
    used: set[int] = set()
    result: list[Any] = []
    for index, stop in enumerate(stops):
        row_id = stop.get("row_id")
        row = by_id.get(int(row_id)) if row_id and int(row_id) not in used else None
        if row is None:
            row = model(**{parent_field: parent_id})
            session.add(row)
        if row_id:
            used.add(int(row_id))
        row.place_role_id = stop["place_role_id"]
        row.place_role = stop["place_role"]
        row.sequence_no = index + 1
        row.planned_at = stop["planned_at"]
        row.free_text = stop["place"]
        row.notes = stop["notes"]
        if "actual_at" in model.__table__.columns:
            row.actual_at = stop["actual_at"]
            row.is_actual = stop["actual_at"] is not None
        if row.id is not None:
            kept.add(int(row.id))
        result.append(row)

    for row_id, row in by_id.items():
        if row_id not in kept:
            await session.delete(row)

    await session.flush()
    return await route_stop_payloads(session, result)


def route_stop_payload(
    *,
    sequence: int,
    place_role_id: int | None,
    place_role: str | None,
    place_role_name: str | None = None,
    place: str | None,
    planned_at: datetime | None = None,
    actual_at: datetime | None = None,
    notes: str | None = None,
    row_id: int | None = None,
) -> dict[str, Any]:
    """The API shape of one route stop, for both document types."""

    def iso(value: datetime | None) -> str:
        return value.isoformat() if value is not None else ""

    return {
        "id": str(row_id) if row_id is not None else None,
        "sequence": sequence,
        "sequenceNo": sequence,
        "placeRoleId": str(place_role_id) if place_role_id is not None else None,
        "placeRole": place_role or "",
        "placeRoleName": place_role_name or place_role or "",
        "place": place or "",
        "planned": iso(planned_at),
        "actual": iso(actual_at),
        "notes": notes or "",
    }


async def route_stop_payloads(session: AsyncSession, rows: list[Any]) -> list[dict[str, Any]]:
    """Serialise stored route rows, resolving the live role label.

    The snapshot column still supplies the text when the reference was cleared, so
    a route saved before the place-role master existed remains readable.
    """
    if not rows:
        return []
    role_ids = {int(row.place_role_id) for row in rows if getattr(row, "place_role_id", None)}
    roles = {
        int(role.id): role
        for role in (
            await session.execute(select(PlaceRole).where(PlaceRole.id.in_(role_ids)))
        ).scalars().all()
    } if role_ids else {}

    payloads: list[dict[str, Any]] = []
    for row in rows:
        role = roles.get(int(row.place_role_id)) if getattr(row, "place_role_id", None) else None
        payloads.append(
            route_stop_payload(
                row_id=int(row.id),
                sequence=int(row.sequence_no or 0) or (len(payloads) + 1),
                place_role_id=row.place_role_id,
                place_role=role.name if role is not None else row.place_role,
                place_role_name=role.name if role is not None else row.place_role,
                place=row.free_text,
                planned_at=getattr(row, "planned_at", None),
                actual_at=getattr(row, "actual_at", None),
                notes=row.notes,
            )
        )
    return payloads
