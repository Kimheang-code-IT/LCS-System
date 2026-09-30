"""component attributes, groups and tabs

Replaces the component-template/attribute model with a reusable
Attribute -> Group -> Tab configuration. Old component tables are dropped.

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-30 10:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # Drop the superseded component tables (dependency order).
    op.drop_index(op.f("ix_service_component_values_component_id"), table_name="service_component_values")
    op.drop_table("service_component_values")
    op.drop_index(op.f("ix_service_order_components_service_order_id"), table_name="service_order_components")
    op.drop_index(op.f("ix_service_order_components_component_status"), table_name="service_order_components")
    op.drop_table("service_order_components")
    op.drop_table("trade_direction_components")
    op.drop_table("template_attributes")
    op.drop_table("component_templates")
    op.drop_table("component_groups")

    op.create_table(
        "component_attributes",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("label_km", sa.String(length=255), nullable=True),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=True),
        sa.Column("reference_type", sa.String(length=32), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("default_value", sa.String(length=255), nullable=True),
        sa.Column("placeholder", sa.String(length=255), nullable=True),
        sa.Column("width", sa.String(length=16), nullable=True),
        sa.Column("options", _json(), nullable=False),
        sa.Column("validation_rules", _json(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_attributes")),
        sa.UniqueConstraint("code", name=op.f("uq_component_attributes_code")),
    )

    op.create_table(
        "component_groups",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_km", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("render_mode", sa.String(length=16), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_groups")),
        sa.UniqueConstraint("code", name=op.f("uq_component_groups_code")),
    )

    op.create_table(
        "component_group_attributes",
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("attribute_id", sa.BigInteger(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=True),
        sa.Column("width", sa.String(length=16), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["group_id"], ["component_groups.id"], name=op.f("fk_component_group_attributes_group_id_component_groups"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["attribute_id"],
            ["component_attributes.id"],
            name=op.f("fk_component_group_attributes_attribute_id_component_attributes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_group_attributes")),
        sa.UniqueConstraint("group_id", "attribute_id", name="uq_component_group_attributes_group_attr"),
    )
    op.create_index(op.f("ix_component_group_attributes_group_id"), "component_group_attributes", ["group_id"], unique=False)
    op.create_index(
        op.f("ix_component_group_attributes_attribute_id"), "component_group_attributes", ["attribute_id"], unique=False
    )

    op.create_table(
        "component_tabs",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_km", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_tabs")),
        sa.UniqueConstraint("code", name=op.f("uq_component_tabs_code")),
    )

    op.create_table(
        "component_tab_groups",
        sa.Column("tab_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tab_id"], ["component_tabs.id"], name=op.f("fk_component_tab_groups_tab_id_component_tabs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["component_groups.id"], name=op.f("fk_component_tab_groups_group_id_component_groups"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_tab_groups")),
        sa.UniqueConstraint("tab_id", "group_id", name="uq_component_tab_groups_tab_group"),
    )
    op.create_index(op.f("ix_component_tab_groups_tab_id"), "component_tab_groups", ["tab_id"], unique=False)
    op.create_index(op.f("ix_component_tab_groups_group_id"), "component_tab_groups", ["group_id"], unique=False)

    op.create_table(
        "component_tab_trade_directions",
        sa.Column("tab_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_direction_id", sa.BigInteger(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tab_id"], ["component_tabs.id"], name=op.f("fk_component_tab_trade_directions_tab_id_component_tabs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trade_direction_id"],
            ["trade_directions.id"],
            name=op.f("fk_component_tab_trade_directions_trade_direction_id_trade_directions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_tab_trade_directions")),
        sa.UniqueConstraint("tab_id", "trade_direction_id", name="uq_component_tab_directions_tab_direction"),
    )
    op.create_index(
        op.f("ix_component_tab_trade_directions_tab_id"), "component_tab_trade_directions", ["tab_id"], unique=False
    )
    op.create_index(
        op.f("ix_component_tab_trade_directions_trade_direction_id"),
        "component_tab_trade_directions",
        ["trade_direction_id"],
        unique=False,
    )

    op.create_table(
        "service_order_component_rows",
        sa.Column("service_order_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("values", _json(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["service_order_id"],
            ["service_orders.id"],
            name=op.f("fk_service_order_component_rows_service_order_id_service_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["component_groups.id"],
            name=op.f("fk_service_order_component_rows_group_id_component_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_service_order_component_rows_created_by_user_id_users")),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], name=op.f("fk_service_order_component_rows_updated_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_order_component_rows")),
    )
    op.create_index(
        op.f("ix_service_order_component_rows_service_order_id"), "service_order_component_rows", ["service_order_id"], unique=False
    )
    op.create_index(op.f("ix_service_order_component_rows_group_id"), "service_order_component_rows", ["group_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_service_order_component_rows_group_id"), table_name="service_order_component_rows")
    op.drop_index(op.f("ix_service_order_component_rows_service_order_id"), table_name="service_order_component_rows")
    op.drop_table("service_order_component_rows")
    op.drop_index(op.f("ix_component_tab_trade_directions_trade_direction_id"), table_name="component_tab_trade_directions")
    op.drop_index(op.f("ix_component_tab_trade_directions_tab_id"), table_name="component_tab_trade_directions")
    op.drop_table("component_tab_trade_directions")
    op.drop_index(op.f("ix_component_tab_groups_group_id"), table_name="component_tab_groups")
    op.drop_index(op.f("ix_component_tab_groups_tab_id"), table_name="component_tab_groups")
    op.drop_table("component_tab_groups")
    op.drop_table("component_tabs")
    op.drop_index(op.f("ix_component_group_attributes_attribute_id"), table_name="component_group_attributes")
    op.drop_index(op.f("ix_component_group_attributes_group_id"), table_name="component_group_attributes")
    op.drop_table("component_group_attributes")
    op.drop_table("component_groups")
    op.drop_table("component_attributes")

    # Recreate the superseded component tables.
    op.create_table(
        "component_groups",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("show_on_job_workspace", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_groups")),
        sa.UniqueConstraint("code", name=op.f("uq_component_groups_code")),
    )
    op.create_table(
        "component_templates",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_repeatable", sa.Boolean(), nullable=False),
        sa.Column("instance_mode", sa.String(length=20), nullable=False),
        sa.Column("minimum_instances", sa.Integer(), nullable=True),
        sa.Column("maximum_instances", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component_templates")),
        sa.UniqueConstraint("code", "version", name="uq_component_templates_code_version"),
    )
    op.create_table(
        "template_attributes",
        sa.Column("template_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_repeatable", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("validation_rules", _json(), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["template_id"], ["component_templates.id"], name=op.f("fk_template_attributes_template_id_component_templates"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_template_attributes")),
        sa.UniqueConstraint("template_id", "code", name="uq_template_attributes_template_code"),
    )
    op.create_table(
        "trade_direction_components",
        sa.Column("trade_direction_id", sa.BigInteger(), nullable=False),
        sa.Column("component_group_id", sa.BigInteger(), nullable=False),
        sa.Column("component_template_id", sa.BigInteger(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_repeatable", sa.Boolean(), nullable=False),
        sa.Column("instance_mode_override", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["component_group_id"], ["component_groups.id"], name=op.f("fk_trade_direction_components_component_group_id_component_groups")
        ),
        sa.ForeignKeyConstraint(
            ["component_template_id"], ["component_templates.id"], name=op.f("fk_trade_direction_components_component_template_id_component_templates")
        ),
        sa.ForeignKeyConstraint(
            ["trade_direction_id"], ["trade_directions.id"], name=op.f("fk_trade_direction_components_trade_direction_id_trade_directions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_direction_components")),
        sa.UniqueConstraint("trade_direction_id", "component_template_id", name="uq_tdc_direction_template"),
    )
    op.create_table(
        "service_order_components",
        sa.Column("service_order_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_direction_component_id", sa.BigInteger(), nullable=True),
        sa.Column("component_group_id", sa.BigInteger(), nullable=True),
        sa.Column("component_template_id", sa.BigInteger(), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("component_status", sa.String(length=20), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_repeatable", sa.Boolean(), nullable=False),
        sa.Column("instance_mode", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("completed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data", _json(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], name=op.f("fk_service_order_components_completed_by_user_id_users")),
        sa.ForeignKeyConstraint(
            ["component_group_id"], ["component_groups.id"], name=op.f("fk_service_order_components_component_group_id_component_groups")
        ),
        sa.ForeignKeyConstraint(
            ["component_template_id"],
            ["component_templates.id"],
            name=op.f("fk_service_order_components_component_template_id_component_templates"),
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_service_order_components_created_by_user_id_users")),
        sa.ForeignKeyConstraint(
            ["service_order_id"], ["service_orders.id"], name=op.f("fk_service_order_components_service_order_id_service_orders"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trade_direction_component_id"],
            ["trade_direction_components.id"],
            name=op.f("fk_service_order_components_trade_direction_component_id_trade_direction_components"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_order_components")),
    )
    op.create_index(op.f("ix_service_order_components_component_status"), "service_order_components", ["component_status"], unique=False)
    op.create_index(op.f("ix_service_order_components_service_order_id"), "service_order_components", ["service_order_id"], unique=False)
    op.create_table(
        "service_component_values",
        sa.Column("component_id", sa.BigInteger(), nullable=False),
        sa.Column("template_attribute_id", sa.BigInteger(), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Numeric(precision=19, scale=6), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("value_reference_type", sa.String(length=64), nullable=True),
        sa.Column("value_reference_id", sa.BigInteger(), nullable=True),
        sa.Column("value_json", _json(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["component_id"], ["service_order_components.id"], name=op.f("fk_service_component_values_component_id_service_order_components"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["template_attribute_id"], ["template_attributes.id"], name=op.f("fk_service_component_values_template_attribute_id_template_attributes")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_component_values")),
        sa.UniqueConstraint("component_id", "template_attribute_id", name="uq_service_component_values_attr"),
    )
    op.create_index(op.f("ix_service_component_values_component_id"), "service_component_values", ["component_id"], unique=False)
