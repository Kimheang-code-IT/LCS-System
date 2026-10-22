"""Database-driven Place Roles and structured route stops.

The route stop used to store its role as free text and its location as an
optional place id plus ad-hoc text. This revision makes the role a real,
administrator-managed record and gives both route tables the reference columns
the forms now send:

* ``place_roles`` — code, name, description, display order and status. The
  starting roles are inserted as *data*; they are not a code-owned dropdown.
* ``place_role_places`` — an optional restriction of a place to a set of roles.
  A place with no rows is offered for every role.
* ``quotation_revision_places.place_role_id`` / ``planned_at``.
* ``service_order_places.place_role_id`` / ``planned_at`` / ``actual_at``.
* ``UNIQUE(parent, sequence_no)`` on both route tables, after renumbering any
  existing duplicate sequence values (the old conversion wrote three stops with
  ``sequence_no = 1``).

Historical data is preserved: the text snapshots ``place_role`` and ``free_text``
stay in place, are used to backfill the new ids where they match, and keep a
route printable when a role or place is later deactivated. Nothing is dropped on
upgrade.

Revision ID: b8d9e0f1a2b3
Revises: a7c1e2f3b4d5
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8d9e0f1a2b3"
down_revision: str | None = "a7c1e2f3b4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Starting configuration records. Administrators may rename, reorder, deactivate
#: or extend them through Master Data; the codes are seed identity only.
DEFAULT_PLACE_ROLES: tuple[tuple[str, str, str], ...] = (
    ("PICKUP", "Pickup", "Goods are collected at this location."),
    ("DROPOFF", "Drop-off", "Goods are handed over at this location."),
    ("ORIGIN", "Origin", "Start of the commercial transport route."),
    ("DESTINATION", "Destination", "End of the commercial transport route."),
    ("LOADING", "Loading", "Goods or containers are loaded here."),
    ("UNLOADING", "Unloading", "Goods or containers are unloaded here."),
    ("TRANSIT", "Transit", "An intermediate or border crossing point."),
    ("CUSTOMS", "Customs Clearance", "A customs office or clearance location."),
    ("DELIVERY", "Delivery", "Final delivery location."),
    ("RETURN", "Return Location", "Empty containers or equipment are returned here."),
)

#: Old route text that has no same-named default role but an unambiguous meaning.
_LEGACY_ROLE_ALIASES = {
    "PORT OF LOADING": "LOADING",
    "TRANSIT / BORDER": "TRANSIT",
    "BORDER": "TRANSIT",
    "PORT": "LOADING",
}


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _backfill_place_role(table: str) -> None:
    alias_cases = " ".join(
        f"WHEN '{legacy}' THEN '{code}'" for legacy, code in _LEGACY_ROLE_ALIASES.items()
    )
    op.execute(
        f"""
        UPDATE {table} AS rp
        SET place_role_id = pr.id
        FROM place_roles AS pr
        WHERE rp.place_role_id IS NULL
          AND pr.deleted_at IS NULL
          AND (
                upper(trim(rp.place_role)) = upper(pr.code)
             OR lower(trim(rp.place_role)) = lower(pr.name)
             OR pr.code = CASE upper(trim(rp.place_role)) {alias_cases} ELSE NULL END
          )
        """
    )


def _backfill_place(table: str) -> None:
    op.execute(
        f"""
        UPDATE {table} AS rp
        SET place_id = (
            SELECT p.id FROM places AS p
            WHERE p.deleted_at IS NULL
              AND (
                    lower(trim(p.name)) = lower(trim(rp.free_text))
                 OR p.code = trim(rp.free_text)
              )
            ORDER BY p.id
            LIMIT 1
        )
        WHERE rp.place_id IS NULL
          AND rp.free_text IS NOT NULL
          AND trim(rp.free_text) <> ''
        """
    )


def _renumber(table: str, parent: str) -> None:
    op.execute(
        f"""
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY {parent} ORDER BY sequence_no, id
            ) AS rn
            FROM {table}
        )
        UPDATE {table} AS target
        SET sequence_no = numbered.rn
        FROM numbered
        WHERE target.id = numbered.id
          AND target.sequence_no <> numbered.rn
        """
    )


def _backfill_quotation_planned_at() -> None:
    """Carry the old JSON route date into the new column.

    Before this revision a quotation route stop stored no planned date column;
    the date lived only in ``quotation_revisions.data.places[].plannedActual``
    (or ``planned``). The rows were written in the same order as that array, so
    the sequence matches. Values that are not an ISO date are left NULL.
    """
    op.execute(
        """
        UPDATE quotation_revision_places AS rp
        SET planned_at = parsed.planned_at
        FROM quotation_revisions AS r
        CROSS JOIN LATERAL (
            SELECT
                ordinality AS position,
                CASE
                    WHEN coalesce(entry ->> 'planned', entry ->> 'plannedActual')
                         ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                    THEN coalesce(entry ->> 'planned', entry ->> 'plannedActual')::timestamptz
                END AS planned_at
            FROM jsonb_array_elements(
                     coalesce(r.data::jsonb -> 'places', '[]'::jsonb)
                 ) WITH ORDINALITY AS route(entry, ordinality)
        ) AS parsed
        WHERE rp.quotation_revision_id = r.id
          AND rp.sequence_no = parsed.position
          AND rp.planned_at IS NULL
          AND parsed.planned_at IS NOT NULL
        """
    )


def upgrade() -> None:
    op.create_table(
        "place_roles",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            name=op.f("fk_place_roles_deleted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_roles")),
    )
    op.create_index(
        "uq_place_roles_code_active",
        "place_roles",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_place_roles_sort_order", "place_roles", ["sort_order"], unique=False)
    op.create_index(op.f("ix_place_roles_deleted_at"), "place_roles", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_place_roles_deleted_by_user_id"), "place_roles", ["deleted_by_user_id"], unique=False)

    place_roles = sa.table(
        "place_roles",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("sort_order", sa.Integer),
        sa.column("status", sa.String),
    )
    op.bulk_insert(
        place_roles,
        [
            {
                "code": code,
                "name": name,
                "description": description,
                "sort_order": (index + 1) * 10,
                "status": "ACTIVE",
            }
            for index, (code, name, description) in enumerate(DEFAULT_PLACE_ROLES)
        ],
    )

    op.create_table(
        "place_role_places",
        sa.Column("place_role_id", sa.BigInteger(), nullable=False),
        sa.Column("place_id", sa.BigInteger(), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["places.id"],
            name=op.f("fk_place_role_places_place_id_places"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["place_role_id"],
            ["place_roles.id"],
            name=op.f("fk_place_role_places_place_role_id_place_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_role_places")),
        sa.UniqueConstraint("place_role_id", "place_id", name="uq_place_role_places"),
    )
    op.create_index(
        op.f("ix_place_role_places_place_role_id"), "place_role_places", ["place_role_id"], unique=False
    )
    op.create_index(op.f("ix_place_role_places_place_id"), "place_role_places", ["place_id"], unique=False)

    # Route stops: the role becomes a reference while the text snapshot remains.
    op.add_column("quotation_revision_places", sa.Column("place_role_id", sa.BigInteger(), nullable=True))
    op.add_column("quotation_revision_places", sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_quotation_revision_places_place_role_id_place_roles"),
        "quotation_revision_places",
        "place_roles",
        ["place_role_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("service_order_places", sa.Column("place_role_id", sa.BigInteger(), nullable=True))
    op.add_column("service_order_places", sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("service_order_places", sa.Column("actual_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_service_order_places_place_role_id_place_roles"),
        "service_order_places",
        "place_roles",
        ["place_role_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for table in ("quotation_revision_places", "service_order_places"):
        _backfill_place_role(table)
        _backfill_place(table)
    _backfill_quotation_planned_at()
    _renumber("quotation_revision_places", "quotation_revision_id")
    _renumber("service_order_places", "service_order_id")

    op.create_unique_constraint(
        "uq_quotation_revision_places_sequence",
        "quotation_revision_places",
        ["quotation_revision_id", "sequence_no"],
    )
    op.create_unique_constraint(
        "uq_service_order_places_sequence",
        "service_order_places",
        ["service_order_id", "sequence_no"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_service_order_places_sequence", "service_order_places", type_="unique"
    )
    op.drop_constraint(
        "uq_quotation_revision_places_sequence", "quotation_revision_places", type_="unique"
    )
    op.drop_constraint(
        op.f("fk_service_order_places_place_role_id_place_roles"),
        "service_order_places",
        type_="foreignkey",
    )
    op.drop_column("service_order_places", "actual_at")
    op.drop_column("service_order_places", "planned_at")
    op.drop_column("service_order_places", "place_role_id")
    op.drop_constraint(
        op.f("fk_quotation_revision_places_place_role_id_place_roles"),
        "quotation_revision_places",
        type_="foreignkey",
    )
    op.drop_column("quotation_revision_places", "planned_at")
    op.drop_column("quotation_revision_places", "place_role_id")

    op.drop_index(op.f("ix_place_role_places_place_id"), table_name="place_role_places")
    op.drop_index(op.f("ix_place_role_places_place_role_id"), table_name="place_role_places")
    op.drop_table("place_role_places")
    op.drop_index(op.f("ix_place_roles_deleted_by_user_id"), table_name="place_roles")
    op.drop_index(op.f("ix_place_roles_deleted_at"), table_name="place_roles")
    op.drop_index("ix_place_roles_sort_order", table_name="place_roles")
    op.drop_index("uq_place_roles_code_active", table_name="place_roles")
    op.drop_table("place_roles")
