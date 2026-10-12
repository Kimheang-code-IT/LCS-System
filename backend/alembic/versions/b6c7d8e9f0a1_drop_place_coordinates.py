"""drop place coordinates

Places no longer store latitude / longitude.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("places", "latitude")
    op.drop_column("places", "longitude")


def downgrade() -> None:
    op.add_column("places", sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column("places", sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True))
