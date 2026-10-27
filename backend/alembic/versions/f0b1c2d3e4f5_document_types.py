"""Create the Document Types master and seed the canonical financial types.

Custom types may only reference a canonical accounting behaviour, so journal and
allocation logic keeps reading the canonical codes while the UI can use
business-specific labels.

Revision ID: f0b1c2d3e4f5
Revises: e9a0b1c2d3e4
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f0b1c2d3e4f5"
down_revision: str | None = "e9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FINANCE_MODULES = ["financial_documents", "service_order_finance", "posting_rules"]
_SEED = (
    ("CUSTOMER_INVOICE", "Customer Invoice", "FINANCE", _FINANCE_MODULES),
    ("CREDIT_NOTE", "Customer Credit Note", "FINANCE", _FINANCE_MODULES),
    ("SUPPLIER_BILL", "Supplier Bill", "FINANCE", _FINANCE_MODULES),
    ("SUPPLIER_CREDIT_NOTE", "Supplier Credit Note", "FINANCE", _FINANCE_MODULES),
    ("CUSTOMER_RECEIPT", "Customer Receipt", "FINANCE", _FINANCE_MODULES),
    ("SUPPLIER_PAYMENT", "Supplier Payment", "FINANCE", _FINANCE_MODULES),
    ("OTHER_INCOME", "Other Income", "FINANCE", _FINANCE_MODULES),
    ("OTHER_EXPENSE", "Other Expense", "FINANCE", _FINANCE_MODULES),
    ("TRANSFER", "Transfer", "FINANCE", ["financial_documents", "posting_rules"]),
    ("ADJUSTMENT", "Adjustment", "FINANCE", ["financial_documents", "posting_rules"]),
)


def upgrade() -> None:
    op.create_table(
        "document_types",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="FINANCE"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("accounting_behavior", sa.String(length=64), nullable=False),
        sa.Column("posting_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("available_in", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_document_types_code_active",
        "document_types",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.bulk_insert(
        sa.table(
            "document_types",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("category", sa.String),
            sa.column("accounting_behavior", sa.String),
            sa.column("posting_required", sa.Boolean),
            sa.column("available_in", sa.JSON),
            sa.column("status", sa.String),
        ),
        [
            {
                "code": code,
                "name": name,
                "category": category,
                "accounting_behavior": code,
                "posting_required": True,
                "available_in": modules,
                "status": "ACTIVE",
            }
            for code, name, category, modules in _SEED
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_document_types_code_active", table_name="document_types")
    op.drop_table("document_types")
