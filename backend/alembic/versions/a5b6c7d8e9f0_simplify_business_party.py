"""simplify business party

Business parties are plain reference records: roles are stored on the party
itself and the party no longer carries a country. Remove the child tables
``party_roles`` / ``party_places``, drop ``country_code`` and add ``roles``.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("party_roles")
    op.drop_table("party_places")
    op.drop_column("business_parties", "country_code")
    op.add_column(
        "business_parties",
        sa.Column("roles", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("business_parties", "roles")
    op.add_column("business_parties", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.create_table(
        "party_places",
        sa.Column("party_id", sa.BigInteger(), nullable=False),
        sa.Column("place_id", sa.BigInteger(), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["party_id"], ["business_parties.id"], name="fk_party_places_party_id_business_parties", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], name="fk_party_places_place_id_places"),
        sa.PrimaryKeyConstraint("party_id", "place_id", "relationship_type", name="pk_party_places"),
    )
    op.create_table(
        "party_roles",
        sa.Column("party_id", sa.BigInteger(), nullable=False),
        sa.Column("role_type", sa.String(length=50), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["party_id"], ["business_parties.id"], name="fk_party_roles_party_id_business_parties", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("party_id", "role_type", name="pk_party_roles"),
    )
