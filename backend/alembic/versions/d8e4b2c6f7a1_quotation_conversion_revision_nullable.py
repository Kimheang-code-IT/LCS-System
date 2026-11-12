"""Direct service-order creates are recorded in the conversion ledger.

``save_service_order`` writes a ``quotation_conversions`` row for every new
order so a retried create with the same ``Idempotency-Key`` is answered with
the order it already made. Orders created *without* a quotation have no
revision to point at, so the column becomes nullable; quotation-based rows
keep their revision link and nothing else changes.

Revision ID: d8e4b2c6f7a1
Revises: c3d5f7a9b1e2
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e4b2c6f7a1"
down_revision: str | None = "c3d5f7a9b1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite test databases build the column from the ORM metadata directly.
        return
    op.alter_column(
        "quotation_conversions",
        "quotation_revision_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "quotation_conversions",
        "quotation_revision_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
