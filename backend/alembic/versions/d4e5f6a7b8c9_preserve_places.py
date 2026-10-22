"""Guard the Places data structures against the previously destructive revision.

``c3d4e5f6a7b8`` used to drop ``places``, ``place_role_places`` and the four
foreign-key columns on route stops and movements. It is now non-destructive, but
a database that already ran the old form is already missing the data. This
revision does not fabricate empty master data: it checks the structures and
aborts with restore instructions. A verified pre-deployment dump is the only
safe recovery for such a database.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUIRED_TABLES = ("places", "place_role_places")
REQUIRED_COLUMNS = (
    ("quotation_revision_places", "place_id"),
    ("service_order_places", "place_id"),
    ("service_order_movements", "origin_place_id"),
    ("service_order_movements", "destination_place_id"),
)


def _missing_places_objects() -> list[str]:
    bind = op.get_bind()
    missing: list[str] = []

    for table in REQUIRED_TABLES:
        exists = bind.execute(
            sa.text("SELECT to_regclass(:relation) IS NOT NULL"),
            {"relation": f"public.{table}"},
        ).scalar()
        if not exists:
            missing.append(table)

    for table, column in REQUIRED_COLUMNS:
        exists = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                  AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).scalar()
        if not exists:
            missing.append(f"{table}.{column}")

    return missing


def upgrade() -> None:
    missing = _missing_places_objects()
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "Places data structures are missing: "
            f"{joined}. This database already applied the destructive form of "
            "c3d4e5f6a7b8. Automatic repair cannot recover the deleted Places "
            "rows or their role links. Restore the pre-deployment dump to a "
            "separate database, verify places, place_role_places and the route "
            "references, then restore production only after accepting the loss "
            "of writes made since that dump. Do not continue this migration "
            "against a database whose Places data is missing."
        )


def downgrade() -> None:
    # A guard has no schema or data change to undo.
    pass
