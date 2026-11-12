"""Internal Service Charges, generated document identity and component allocations.

Additive only: existing charges become CUSTOMER, cost fields default to zero,
generated_key is null for manual documents, and no stored financial amount is
rewritten.

Revision ID: c1a2b3d4e5f6
Revises: b5c9d1e4f2a7
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: str | None = "b5c9d1e4f2a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.add_column(
        "service_order_charges",
        sa.Column("charge_side", sa.String(length=16), nullable=False, server_default="CUSTOMER"),
    )
    op.add_column(
        "service_order_charges",
        sa.Column("supplier_party_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_service_order_charges_charge_side", "service_order_charges", ["charge_side"])
    op.create_index("ix_service_order_charges_supplier_party_id", "service_order_charges", ["supplier_party_id"])
    op.create_foreign_key(
        "fk_service_order_charges_supplier_party_id",
        "service_order_charges",
        "business_parties",
        ["supplier_party_id"],
        ["id"],
    )
    op.add_column(
        "service_order_charge_lines",
        sa.Column("cost_unit_price", sa.Numeric(19, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "service_order_charge_lines",
        sa.Column("cost_amount", sa.Numeric(19, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "financial_documents",
        sa.Column("generated_key", sa.String(length=160), nullable=True),
    )
    op.create_unique_constraint(
        "uq_financial_documents_generated_key",
        "financial_documents",
        ["generated_key"],
    )
    op.create_table(
        "financial_document_component_allocations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "financial_document_id",
            sa.BigInteger(),
            sa.ForeignKey("financial_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("container_id", sa.BigInteger(), nullable=True),
        sa.Column("allocated_amount", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "financial_document_id",
            "source_kind",
            "source_key",
            "container_id",
            name="uq_fin_component_allocation",
        ),
    )
    # PostgreSQL identifiers are limited to 63 characters; SQLAlchemy truncates
    # auto-generated names but an explicit Alembic name is validated as-is.
    op.create_index(
        "ix_fin_component_alloc_document_id",
        "financial_document_component_allocations",
        ["financial_document_id"],
    )
    op.create_foreign_key(
        "fk_fin_component_alloc_container",
        "financial_document_component_allocations",
        "service_order_containers",
        ["container_id"],
        ["id"],
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_constraint(
        "fk_fin_component_alloc_container",
        "financial_document_component_allocations",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_fin_component_alloc_document_id",
        table_name="financial_document_component_allocations",
    )
    op.drop_table("financial_document_component_allocations")
    op.drop_constraint("uq_financial_documents_generated_key", "financial_documents", type_="unique")
    op.drop_column("financial_documents", "generated_key")
    op.drop_column("service_order_charge_lines", "cost_amount")
    op.drop_column("service_order_charge_lines", "cost_unit_price")
    op.drop_constraint(
        "fk_service_order_charges_supplier_party_id",
        "service_order_charges",
        type_="foreignkey",
    )
    op.drop_index("ix_service_order_charges_supplier_party_id", table_name="service_order_charges")
    op.drop_index("ix_service_order_charges_charge_side", table_name="service_order_charges")
    op.drop_column("service_order_charges", "supplier_party_id")
    op.drop_column("service_order_charges", "charge_side")
