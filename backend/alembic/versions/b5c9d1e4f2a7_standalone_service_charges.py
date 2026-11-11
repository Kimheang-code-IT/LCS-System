"""Standalone service charges: nullable order link, own customer party.

``service_order_charges.service_order_id`` was NOT NULL: every charge lived
under a service order. Charges that are created without an order now stay
top-level, so the column becomes nullable and the charge carries its own
``customer_party_id`` (NULL for existing rows — they keep inheriting the
order's party at invoice time, so nothing is backfilled and no data changes).

Revision ID: b5c9d1e4f2a7
Revises: d8e4b2c6f7a1
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b5c9d1e4f2a7"
down_revision: str | None = "d8e4b2c6f7a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite test databases build the columns from the ORM metadata directly.
        return
    op.alter_column(
        "service_order_charges",
        "service_order_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.add_column(
        "service_order_charges",
        sa.Column("customer_party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_service_order_charges_customer_party_id",
        "service_order_charges",
        ["customer_party_id"],
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_index("ix_service_order_charges_customer_party_id", table_name="service_order_charges")
    op.drop_column("service_order_charges", "customer_party_id")
    op.alter_column(
        "service_order_charges",
        "service_order_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
