"""simplify place

Places keep only code / name / description / address / status. Remove the
country, category and parent-place fields.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "b6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_places_parent_place_id_places", "places", type_="foreignkey")
    op.drop_column("places", "parent_place_id")
    op.drop_column("places", "place_category")
    op.drop_column("places", "country_code")


def downgrade() -> None:
    op.add_column("places", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column(
        "places",
        sa.Column("place_category", sa.String(length=64), nullable=False, server_default="City"),
    )
    op.add_column("places", sa.Column("parent_place_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_places_parent_place_id_places", "places", "places", ["parent_place_id"], ["id"]
    )
