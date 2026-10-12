"""drop transport asset registration country

Transport assets no longer store a registration country.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("transport_assets", "registration_country_code")


def downgrade() -> None:
    op.add_column("transport_assets", sa.Column("registration_country_code", sa.String(length=2), nullable=True))
