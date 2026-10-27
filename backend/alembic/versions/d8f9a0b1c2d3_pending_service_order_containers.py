"""Allow a prepared service-order container to exist before its number is known.

A container expanded from a quotation requirement is a real row with a type, a
link to the requirement and its weights, but no number until the box is
collected. Storing a placeholder number would break the uniqueness constraint
and print a fake identifier, so the column becomes nullable instead. PostgreSQL
treats NULLs as distinct in a unique constraint, so
``uq_service_order_containers_number`` still guarantees that no two containers
share a real number.

Revision ID: d8f9a0b1c2d3
Revises: c7e8f9a0b1c2
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8f9a0b1c2d3"
down_revision: str | None = "c7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "service_order_containers",
        "container_number",
        existing_type=sa.String(length=32),
        nullable=True,
    )


def downgrade() -> None:
    # The NOT NULL column cannot represent a prepared row. Those rows were never
    # numbered, so dropping them loses no operator-entered identifier; a numbered
    # container is untouched.
    op.execute("DELETE FROM service_order_containers WHERE container_number IS NULL")
    op.alter_column(
        "service_order_containers",
        "container_number",
        existing_type=sa.String(length=32),
        nullable=False,
    )
