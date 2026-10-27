"""transport asset identity types and capacity

The transport-asset identity vocabulary becomes administrator-managed master data
(``transport_asset_identity_types``), seeded as configuration with the same rows
provision_baseline inserts: applicability links to a transport type where one
matches, ``NULL`` meaning the identity type suits every type. Assets also gain
an optional display name and capacity value/unit/status extension support.

Revision ID: e1f2a3b4c5d6
Revises: c3d4e5f6a7b8
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transport_assets", sa.Column("asset_name", sa.String(length=255), nullable=True))
    op.add_column("transport_assets", sa.Column("capacity_value", sa.Numeric(12, 3), nullable=True))
    op.add_column("transport_assets", sa.Column("capacity_unit", sa.String(length=32), nullable=True))
    op.create_table(
        "transport_asset_identity_types",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("transport_type_id", sa.BigInteger(), sa.ForeignKey("transport_types.id"), nullable=True),
        sa.Column("identity_label", sa.String(length=128), nullable=True),
        sa.Column("identity_placeholder", sa.String(length=128), nullable=True),
        sa.Column("validation_pattern", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index(
        "uq_transport_asset_identity_types_name_active",
        "transport_asset_identity_types",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    _seed_identity_types()


def _seed_identity_types() -> None:
    """Seed the vocabulary as data, matching the startup ``provision_baseline``.

    One source of truth: the rows come from ``DEFAULT_IDENTITY_TYPES`` in the
    master-data service. Applicability links to the transport type whose code or
    name contains a keyword — a name-less fresh database keeps every row
    unlinked, so nothing an admin configured at boot is ever discarded.
    """
    from sqlalchemy import text as sql_text

    from app.modules.master_data.service import DEFAULT_IDENTITY_TYPES

    bind = op.get_bind()
    types = [
        (row[0], f"{row[1]} {row[2]}".upper())
        for row in bind.execute(sql_text("SELECT id, code, name FROM transport_types")).fetchall()
    ]

    def link(keywords: tuple[str, ...] | None) -> int | None:
        if keywords is None:
            return None
        for type_id, haystack in types:
            if any(keyword in haystack for keyword in keywords):
                return type_id
        return None

    existing = {row[0] for row in bind.execute(sql_text("SELECT name FROM transport_asset_identity_types")).fetchall()}
    for name, keywords, identity_label, placeholder, pattern in DEFAULT_IDENTITY_TYPES:
        if name in existing:
            continue
        bind.execute(
            sql_text(
                "INSERT INTO transport_asset_identity_types "
                "(name, transport_type_id, identity_label, identity_placeholder, validation_pattern, status) "
                "VALUES (:name, :transport_type_id, :identity_label, :identity_placeholder, :validation_pattern, 'ACTIVE')"
            ),
            {
                "name": name,
                "transport_type_id": link(keywords),
                "identity_label": identity_label,
                "identity_placeholder": placeholder,
                "validation_pattern": pattern,
            },
        )


def downgrade() -> None:
    op.drop_index("uq_transport_asset_identity_types_name_active", table_name="transport_asset_identity_types")
    op.drop_table("transport_asset_identity_types")
    op.drop_column("transport_assets", "capacity_unit")
    op.drop_column("transport_assets", "capacity_value")
    op.drop_column("transport_assets", "asset_name")
