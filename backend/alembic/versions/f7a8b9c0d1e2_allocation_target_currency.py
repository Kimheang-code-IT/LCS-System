"""Settlement amounts in the target document's currency.

A payment and the invoice it settles may be denominated in different currencies.
The allocation already stored the payment's currency and rate; it now also stores
the amount applied to the target document (target currency) and the realised
exchange difference in the base currency, so the invoice's ``paid_amount`` and
outstanding balance stay in its own document currency.

Additive only: existing rows were same-currency, so their target amount equals
the allocated amount and their difference is zero.

Revision ID: f7a8b9c0d1e2
Revises: c1a2b3d4e5f6
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "c1a2b3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_document_allocations",
        sa.Column("target_amount", sa.Numeric(19, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "financial_document_allocations",
        sa.Column("exchange_difference", sa.Numeric(19, 4), nullable=False, server_default="0"),
    )
    # Every allocation written before this migration was same-currency (the
    # service refused cross-currency), so the target amount is the allocated one.
    op.execute(
        "UPDATE financial_document_allocations SET target_amount = allocated_amount"
    )
    op.alter_column("financial_document_allocations", "target_amount", server_default=None)
    op.alter_column("financial_document_allocations", "exchange_difference", server_default=None)


def downgrade() -> None:
    op.drop_column("financial_document_allocations", "exchange_difference")
    op.drop_column("financial_document_allocations", "target_amount")
