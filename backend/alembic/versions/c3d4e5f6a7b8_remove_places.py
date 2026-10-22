"""Remove the Places master and its route/movement references.

Places are no longer a master-data collection: a route stop keeps its Place Role
and a free-text location. Before the table is dropped, the selected place name is
copied into the route-stop ``free_text`` snapshot and the movement origin and
destination names are copied into the movement ``data`` JSON, so existing
documents keep the location text they showed.

Revision ID: c3d4e5f6a7b8
Revises: a9b8c7d6e5f4
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep the displayed location text before the reference disappears.
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
                'originPlace', (SELECT p.name FROM places AS p WHERE p.id = m.origin_place_id),
                'destinationPlace', (SELECT p.name FROM places AS p WHERE p.id = m.destination_place_id)
            )
        )
        WHERE m.origin_place_id IS NOT NULL OR m.destination_place_id IS NOT NULL
        """
    )

    op.drop_constraint(
        "fk_quotation_revision_places_place_id_places",
        "quotation_revision_places",
        type_="foreignkey",
    )
    op.drop_column("quotation_revision_places", "place_id")
    op.drop_constraint(
        "fk_service_order_places_place_id_places",
        "service_order_places",
        type_="foreignkey",
    )
    op.drop_column("service_order_places", "place_id")
    op.drop_constraint(
        "fk_service_order_movements_origin_place_id_places",
        "service_order_movements",
        type_="foreignkey",
    )
    op.drop_column("service_order_movements", "origin_place_id")
    op.drop_constraint(
        "fk_service_order_movements_destination_place_id_places",
        "service_order_movements",
        type_="foreignkey",
    )
    op.drop_column("service_order_movements", "destination_place_id")

    op.drop_table("place_role_places")
    op.drop_table("places")


def downgrade() -> None:
    op.create_table(
        "places",
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            name=op.f("fk_places_deleted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_places")),
    )
    op.create_index("uq_places_code_active", "places", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_places_deleted_at", "places", ["deleted_at"], unique=False)
    op.create_index("ix_places_deleted_by_user_id", "places", ["deleted_by_user_id"], unique=False)

    op.create_table(
        "place_role_places",
        sa.Column("place_role_id", sa.BigInteger(), nullable=False),
        sa.Column("place_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
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
    op.create_index("ix_place_role_places_place_id", "place_role_places", ["place_id"], unique=False)
    op.create_index("ix_place_role_places_place_role_id", "place_role_places", ["place_role_id"], unique=False)

    op.add_column("quotation_revision_places", sa.Column("place_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_quotation_revision_places_place_id_places",
        "quotation_revision_places",
        "places",
        ["place_id"],
        ["id"],
    )
    op.add_column("service_order_places", sa.Column("place_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_service_order_places_place_id_places",
        "service_order_places",
        "places",
        ["place_id"],
        ["id"],
    )
    op.add_column("service_order_movements", sa.Column("origin_place_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_service_order_movements_origin_place_id_places",
        "service_order_movements",
        "places",
        ["origin_place_id"],
        ["id"],
    )
    op.add_column("service_order_movements", sa.Column("destination_place_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_service_order_movements_destination_place_id_places",
        "service_order_movements",
        "places",
        ["destination_place_id"],
        ["id"],
    )
