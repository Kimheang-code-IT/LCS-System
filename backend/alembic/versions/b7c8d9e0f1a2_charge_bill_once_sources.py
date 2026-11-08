"""Service-charge bill-once: source-link uniqueness + conversion idempotency keys.

The charge → finance-draft conversion relies on an app-level "existing source row"
check that a race can bypass on PostgreSQL: two simultaneous conversions of one
issued charge may both pass the check and create two drafts. The order-level
invoice path (``create_invoice_from_service_order``) already treats any
``SERVICE_ORDER_CHARGE`` source row as "already invoiced", so the database can
enforce the same invariant directly: at most one source link per source charge.
An ``idempotency_key`` column (same pattern as ``financial_document_allocations``)
makes a replayed conversion return its earlier document and refuses key reuse for
a different source.

Additive: new nullable column + a partial unique index on charge-sourced links
only (other source types keep their current multiplicity). No existing row can
violate either rule — a second relationship for one charge has never been legal.

Revision ID: b7c8d9e0f1a2
Revises: c0d1e2f3a4b5
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "c0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("financial_document_sources", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    if op.get_bind().dialect.name != "postgresql":
        # The partial index is the PostgreSQL guarantee; on other dialects the
        # model-level sqlite_where index (create_all paths) covers tests.
        return
    op.create_index(
        "uq_fin_doc_source_charge",
        "financial_document_sources",
        ["source_type", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_type = 'SERVICE_ORDER_CHARGE'"),
    )


def downgrade() -> None:
    op.drop_column("financial_document_sources", "idempotency_key")
    op.drop_index("uq_fin_doc_source_charge", table_name="financial_document_sources")
