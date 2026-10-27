"""Trace a quotation back to the service order it was re-quoted from.

A quotation created from an existing service order is a new commercial offer, so
it needs its own identity but must stay attributable to the job that prompted it.
The column is nullable: every quotation created directly stays NULL, and it is
``ON DELETE SET NULL`` because deleting an order must not delete commercial
history.

Revision ID: c7e8f9a0b1c2
Revises: b6d7e8f9a0b1
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7e8f9a0b1c2"
down_revision: str | None = "b6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quotations", sa.Column("source_service_order_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_quotations_source_service_order_id_service_orders"),
        "quotations",
        "service_orders",
        ["source_service_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_quotations_source_service_order_id"),
        "quotations",
        ["source_service_order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quotations_source_service_order_id"), table_name="quotations")
    op.drop_constraint(
        op.f("fk_quotations_source_service_order_id_service_orders"),
        "quotations",
        type_="foreignkey",
    )
    op.drop_column("quotations", "source_service_order_id")
