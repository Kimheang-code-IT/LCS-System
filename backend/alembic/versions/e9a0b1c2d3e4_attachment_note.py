"""Add a free-text note to an attachment.

The Files tab needs an operator note per uploaded file. The value is optional and
independent of the file itself, so it is a nullable column on ``attachments``
rather than a column on every link target.

Revision ID: e9a0b1c2d3e4
Revises: d8f9a0b1c2d3
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e9a0b1c2d3e4"
down_revision: str | None = "d8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attachments", sa.Column("note", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("attachments", "note")
