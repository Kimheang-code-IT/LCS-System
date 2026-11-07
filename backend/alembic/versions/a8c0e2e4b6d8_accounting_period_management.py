"""Accounting period management: custom names, descriptions and range guards.

Additive upgrade for custom period management:

- ``name``/``description`` columns for user-created periods (generated months
  keep NULL and fall back to a label derived from ``start_date`` — no historical
  data is rewritten).
- Legacy status label normalisation: the retired ``REOPENED`` spelling (the
  label the pre-policy form wrote; the posting paths and the status policy both
  read Open) becomes ``OPEN``. Timestamps and user references are untouched.
- A PostgreSQL overlap guard (EXCLUDE on ``daterange``) that refuses any two
  periods whose date ranges intersect, as the service-level check also does.
  ``btree_gist`` is required for the range exclusion; it is created here so the
  constraint works on any restored database.

Revision ID: a8c0e2e4b6d8
Revises: f4a4b5c6d7e8
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c0e2e4b6d8"
down_revision: str | None = "f4a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounting_periods", sa.Column("name", sa.String(length=120), nullable=True))
    op.add_column("accounting_periods", sa.Column("description", sa.String(length=2_000), nullable=True))
    # Normalize every retired status label the posting paths already treated as
    # open. Only the label changes; neither dates, stamps nor postings move.
    op.execute("UPDATE accounting_periods SET status = 'OPEN' WHERE status NOT IN ('DRAFT', 'OPEN', 'CLOSED')")
    # Legacy status label normalisation
    # (applied first so any new constraint sees a valid vocabulary).
    op.execute("UPDATE accounting_periods SET status = 'OPEN' WHERE status NOT IN ('DRAFT', 'OPEN', 'CLOSED')")
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # An EXCLUDE constraint, not a unique index: GiST cannot back a unique
    # index, but the range exclusion (ranges never intersect) is a constraint.
    op.execute(
        """
        ALTER TABLE accounting_periods
        ADD CONSTRAINT uq_periods_no_overlap
        EXCLUDE USING gist (daterange(start_date, end_date, '[]') WITH &&)
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        op.drop_column("accounting_periods", "description")
        op.drop_column("accounting_periods", "name")
        return
    op.execute("ALTER TABLE accounting_periods DROP CONSTRAINT IF EXISTS uq_periods_no_overlap")
    # btree_gist stays: a shared extension is never dropped because other
    # objects could depend on it.
    op.drop_column("accounting_periods", "description")
    op.drop_column("accounting_periods", "name")