"""Preserve the Places master and its historical references.

Places are no longer exposed as a master-data collection, but dropping the
table would delete operator-entered codes, names, addresses and the historical
foreign keys on route stops and movements. This revision is deliberately
non-destructive: it only fills the printable text snapshots that the new
route-stop UI reads. The table, the Place Role mapping and the legacy columns
stay in place for at least this release; removal is deferred to a later
expand/migrate/contract release after a verified backup and a data-retention
decision.

Databases that already applied the earlier destructive form of this revision
are detected by ``d4e5f6a7b8c9``, which aborts with restore instructions instead
of pretending the lost master data still exists.

Revision ID: c3d4e5f6a7b8
Revises: a9b8c7d6e5f4
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep the displayed location text before any future contract phase. These
    # statements only fill blanks, so re-running them is safe.
    op.execute(
        """
        UPDATE quotation_revision_places AS r
        SET free_text = p.name
        FROM places AS p
        WHERE r.place_id = p.id
          AND (r.free_text IS NULL OR btrim(r.free_text) = '')
        """
    )
    op.execute(
        """
        UPDATE service_order_places AS r
        SET free_text = p.name
        FROM places AS p
        WHERE r.place_id = p.id
          AND (r.free_text IS NULL OR btrim(r.free_text) = '')
        """
    )
    op.execute(
        """
        UPDATE service_order_movements AS m
        SET data = COALESCE(m.data, '{}'::jsonb) || jsonb_strip_nulls(
            jsonb_build_object(
                'originPlace', CASE
                    WHEN m.origin_place_id IS NOT NULL
                     AND COALESCE(btrim(m.data->>'originPlace'), '') = ''
                    THEN (SELECT p.name FROM places AS p WHERE p.id = m.origin_place_id)
                END,
                'destinationPlace', CASE
                    WHEN m.destination_place_id IS NOT NULL
                     AND COALESCE(btrim(m.data->>'destinationPlace'), '') = ''
                    THEN (SELECT p.name FROM places AS p WHERE p.id = m.destination_place_id)
                END
            )
        )
        WHERE m.origin_place_id IS NOT NULL OR m.destination_place_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # No schema or data change to undo. Keeping this a no-op is intentional:
    # downgrading must not drop Places either.
    pass
