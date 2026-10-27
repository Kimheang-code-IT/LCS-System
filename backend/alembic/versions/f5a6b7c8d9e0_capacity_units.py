"""capacity units

The transport-asset capacity unit becomes administrator-managed master data
(``capacity_units``), replacing the old free-text ``capacity_unit`` input with
the same activate/deactivate rule as every other reference list. Rows are seeded
from ``DEFAULT_CAPACITY_UNITS`` in the master-data service — the same rows
``provision_baseline`` inserts, so the two writers cannot drift. The column
stays a string storing the unit code, so no existing row is rewritten and a
rollback simply drops the new table.

Revision ID: f5a6b7c8d9e0
Revises: e1f2a3b4c5d6
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capacity_units",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index(
        "uq_capacity_units_code_active",
        "capacity_units",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    _seed_capacity_units()


def _seed_capacity_units() -> None:
    """Seed the unit list as data, matching the startup ``provision_baseline``."""
    from sqlalchemy import text as sql_text

    from app.modules.master_data.service import DEFAULT_CAPACITY_UNITS

    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(sql_text("SELECT code FROM capacity_units")).fetchall()}
    for code, name in DEFAULT_CAPACITY_UNITS:
        if code in existing:
            continue
        bind.execute(
            sql_text(
                "INSERT INTO capacity_units (code, name, status) VALUES (:code, :name, 'ACTIVE')"
            ),
            {"code": code, "name": name},
        )


def downgrade() -> None:
    op.drop_index("uq_capacity_units_code_active", table_name="capacity_units")
    op.drop_table("capacity_units")
