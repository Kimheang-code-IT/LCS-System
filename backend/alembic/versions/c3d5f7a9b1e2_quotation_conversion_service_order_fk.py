"""Quotation conversion ledger: service_order FK (RESTRICT).

``quotation_conversions.service_order_id`` was unique but not declared as a
foreign key, so only application code guaranteed it pointed at a real order.
The conversion ledger is written in the same transaction as the order it
records, and the order-delete path clears the ledger row explicitly, so every
existing row already references a live order. This migration:

* refuses to run (with an actionable message) if orphan rows exist — it never
  deletes data to make the constraint fit;
* adds a ``ON DELETE RESTRICT`` FK, so a rogue direct delete can never leave a
  dangling conversion behind. The application keeps its existing deletion
  behaviour by removing the ledger row in the same transaction.

Revision ID: c3d5f7a9b1e2
Revises: a7f3c9e21d84
Create Date: 2026-11-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d5f7a9b1e2"
down_revision: str | None = "a7f3c9e21d84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "fk_quotation_conversions_service_order"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite test databases build the FK from the ORM metadata directly.
        return
    orphans = bind.execute(
        sa.text(
            "select count(*) from quotation_conversions qc "
            "left join service_orders so on so.id = qc.service_order_id "
            "where so.id is null"
        )
    ).scalar_one()
    if orphans:
        raise RuntimeError(
            f"quotation_conversions has {orphans} row(s) whose service_order_id has no "
            "service_orders row. Review and repair them manually (restore the order or "
            "archive the conversion), then re-run this migration; no data was changed."
        )
    op.create_foreign_key(
        CONSTRAINT,
        "quotation_conversions",
        "service_orders",
        ["service_order_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_constraint(CONSTRAINT, "quotation_conversions", type_="foreignkey")
