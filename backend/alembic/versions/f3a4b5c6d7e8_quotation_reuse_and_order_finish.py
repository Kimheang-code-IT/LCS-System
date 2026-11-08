"""Allow one quotation revision to create many service orders; stamp Finish.

A quotation is now a reusable commercial reference: the one-to-one uniqueness on
``quotation_conversions.quotation_revision_id`` is dropped, so repeated creation
of service orders from the same quotation keeps its conversion ledger instead of
being refused. ``service_order_id`` stays unique — one ledger row per order,
historical rows untouched.

Service orders gain ``finished_at`` / ``finished_by_user_id`` so the Finish
action records who completed the job and when.

Revision ID: f3a4b5c6d7e8
Revises: b4c5d6e7f8a9
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "service_orders",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "service_orders",
        sa.Column(
            "finished_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.drop_constraint("uq_quotation_conversions_quotation_revision_id", "quotation_conversions", type_="unique")
    op.create_index(
        "ix_quotation_conversions_revision",
        "quotation_conversions",
        ["quotation_revision_id"],
    )


def downgrade() -> None:
    # Multiple conversions per revision cannot be represented one-to-one again;
    # only the newest row per revision survives the downgrade round trip.
    op.execute(
        """
        DELETE FROM quotation_conversions a
        USING quotation_conversions b
        WHERE a.quotation_revision_id = b.quotation_revision_id AND a.id < b.id
        """
    )
    op.drop_index("ix_quotation_conversions_revision", table_name="quotation_conversions")
    op.create_unique_constraint(
        "uq_quotation_conversions_quotation_revision_id",
        "quotation_conversions",
        ["quotation_revision_id"],
    )
    op.drop_column("service_orders", "finished_by_user_id")
    op.drop_column("service_orders", "finished_at")