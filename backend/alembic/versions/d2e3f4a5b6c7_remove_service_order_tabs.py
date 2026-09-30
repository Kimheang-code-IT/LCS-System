"""remove service order tabs

The Service Order Tabs subsystem is superseded by component tabs
(attributes -> groups -> tabs). Drops its config and row tables.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-30 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.drop_index(op.f("ix_service_order_tab_rows_tab_config_id"), table_name="service_order_tab_rows")
    op.drop_index(op.f("ix_service_order_tab_rows_service_order_id"), table_name="service_order_tab_rows")
    op.drop_table("service_order_tab_rows")
    op.drop_index(op.f("ix_service_order_column_configs_tab_id"), table_name="service_order_column_configs")
    op.drop_table("service_order_column_configs")
    op.drop_table("service_order_tab_configs")


def downgrade() -> None:
    op.create_table(
        "service_order_tab_configs",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_km", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("allow_multiple_rows", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_order_tab_configs")),
        sa.UniqueConstraint("code", name="uq_so_tab_configs_code"),
    )
    op.create_table(
        "service_order_column_configs",
        sa.Column("tab_id", sa.BigInteger(), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("label_km", sa.String(length=255), nullable=True),
        sa.Column("field_type", sa.String(length=32), nullable=False),
        sa.Column("reference_type", sa.String(length=32), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("show_in_summary", sa.Boolean(), nullable=False),
        sa.Column("width", sa.String(length=16), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("default_value", sa.String(length=255), nullable=True),
        sa.Column("placeholder", sa.String(length=255), nullable=True),
        sa.Column("validation_rules", _json(), nullable=False),
        sa.Column("options", _json(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["tab_id"], ["service_order_tab_configs.id"], name=op.f("fk_service_order_column_configs_tab_id_service_order_tab_configs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_order_column_configs")),
        sa.UniqueConstraint("tab_id", "field_key", name="uq_so_column_configs_tab_key"),
    )
    op.create_index(op.f("ix_service_order_column_configs_tab_id"), "service_order_column_configs", ["tab_id"], unique=False)
    op.create_table(
        "service_order_tab_rows",
        sa.Column("service_order_id", sa.BigInteger(), nullable=False),
        sa.Column("tab_config_id", sa.BigInteger(), nullable=False),
        sa.Column("tab_code", sa.String(length=64), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("values", _json(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_service_order_tab_rows_created_by_user_id_users")),
        sa.ForeignKeyConstraint(
            ["service_order_id"], ["service_orders.id"], name=op.f("fk_service_order_tab_rows_service_order_id_service_orders"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tab_config_id"], ["service_order_tab_configs.id"], name=op.f("fk_service_order_tab_rows_tab_config_id_service_order_tab_configs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], name=op.f("fk_service_order_tab_rows_updated_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_order_tab_rows")),
    )
    op.create_index(op.f("ix_service_order_tab_rows_service_order_id"), "service_order_tab_rows", ["service_order_id"], unique=False)
    op.create_index(op.f("ix_service_order_tab_rows_tab_config_id"), "service_order_tab_rows", ["tab_config_id"], unique=False)
