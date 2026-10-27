"""document_types soft-delete attribution

Revision ID: f6a7b8c9d0e1
Revises: b2c3d4e5f6a7b8
Create Date: 2026-10-24

The DocumentType model carries SoftDeleteMixin, whose ``deleted_by_user_id``
column and indexes are read by every ORM query. The migration that created the
table only shipped ``deleted_at``, so any migrated database fails selects on the
table (UndefinedColumnError) and every page that loads document types 500s.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "b2c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_types", sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_document_types_deleted_by_user_id_users",
        "document_types",
        "users",
        ["deleted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_document_types_deleted_at", "document_types", ["deleted_at"], unique=False)
    op.create_index(
        "ix_document_types_deleted_by_user_id", "document_types", ["deleted_by_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_document_types_deleted_by_user_id", table_name="document_types")
    op.drop_index("ix_document_types_deleted_at", table_name="document_types")
    op.drop_constraint("fk_document_types_deleted_by_user_id_users", "document_types", type_="foreignkey")
    op.drop_column("document_types", "deleted_by_user_id")
