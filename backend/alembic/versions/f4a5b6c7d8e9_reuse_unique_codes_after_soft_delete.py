"""reuse unique codes after soft delete

Archived (soft-deleted) master-data rows kept their codes because the unique
constraints ignored ``deleted_at``. That blocked creating a new record with a
code that a deleted record still held, even though the archive/restore logic
treats uniqueness as active-only. Replace the unconditional constraints with
partial unique indexes scoped to ``deleted_at IS NULL``.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, constraint_name, index_name, columns)
ACTIVE_UNIQUE = (
    ("business_parties", "uq_business_parties_party_code", "uq_business_parties_party_code_active", ["party_code"]),
    ("business_parties", "uq_business_parties_vat_tin", "uq_business_parties_vat_tin_active", ["vat_tin"]),
    ("places", "uq_places_code", "uq_places_code_active", ["code"]),
    ("trade_directions", "uq_trade_directions_code", "uq_trade_directions_code_active", ["code"]),
    ("container_types", "uq_container_types_code", "uq_container_types_code_active", ["code"]),
    ("transport_types", "uq_transport_types_code", "uq_transport_types_code_active", ["code"]),
    ("fee_types", "uq_fee_types_code", "uq_fee_types_code_active", ["code"]),
    ("transport_assets", "uq_transport_assets_asset_code", "uq_transport_assets_asset_code_active", ["asset_code"]),
    (
        "transport_assets",
        "uq_transport_assets_type_identity",
        "uq_transport_assets_type_identity_active",
        ["transport_type_id", "identity"],
    ),
)


def upgrade() -> None:
    for table, constraint, index, columns in ACTIVE_UNIQUE:
        op.drop_constraint(constraint, table, type_="unique")
        op.create_index(
            index,
            table,
            columns,
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )


def downgrade() -> None:
    for table, constraint, index, columns in reversed(ACTIVE_UNIQUE):
        op.drop_index(index, table_name=table)
        op.create_unique_constraint(constraint, table, columns)
