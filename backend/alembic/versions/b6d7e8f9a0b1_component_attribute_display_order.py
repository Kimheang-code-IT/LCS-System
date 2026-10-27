"""Component attribute catalog display order.

The Component Attributes screen edits one flat catalog, so it needs an order of
its own. Group membership order is unchanged: it lives on
``component_group_attributes.display_order`` and still decides how a reusable
attribute is rendered inside a group.

Additive only. Existing rows default to 0, so their relative order falls back to
label (the list endpoint's stable tiebreaker) until an administrator reorders
them.

Revision ID: b6d7e8f9a0b1
Revises: f5a6b7c8d9e0
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b6d7e8f9a0b1"
down_revision: str | None = "f5a6b7c8d9e0"
# See docs/11_deployment_and_security.md §8.
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "component_attributes",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("component_attributes", "display_order")
