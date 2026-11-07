"""Service-order movement sequence uniqueness.

The movement save service already reports a duplicate sequence as ``DUPLICATE_SEQUENCE``
and its docstring claims the pair is unique, but the table never received the backstop
two siblings (route stops, container numbers) carry. Two concurrent movements could
therefore pass the service-level clash check and persist a duplicate sequence. Additive:
create the named unique constraint (the dev/verified databases hold no duplicate
sequence per order) and drop it again in downgrade.

Revision ID: c0d1e2f3a4b5
Revises: a8c0e2e4b6d8
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: str | None = "a8c0e2e4b6d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_service_order_movements_sequence", "service_order_movements", ["service_order_id", "sequence_no"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_service_order_movements_sequence", "service_order_movements", type_="unique")
