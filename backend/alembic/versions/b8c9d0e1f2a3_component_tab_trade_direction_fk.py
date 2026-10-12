"""component_tabs: single trade direction FK, drop name_km/icon

Replaces the ``component_tab_trade_directions`` junction table with a single
``trade_direction_id`` column on ``component_tabs`` and removes the unused
``name_km`` and ``icon`` columns.

Revision ID: b8c9d0e1f2a3
Revises: f1a2b3c4d5e6
Create Date: 2026-10-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column("component_tabs", sa.Column("trade_direction_id", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_component_tabs_trade_direction_id"), "component_tabs", ["trade_direction_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_component_tabs_trade_direction_id_trade_directions"),
        "component_tabs",
        "trade_directions",
        ["trade_direction_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE component_tabs
        SET trade_direction_id = (
            SELECT MIN(ctd.trade_direction_id)
            FROM component_tab_trade_directions ctd
            WHERE ctd.tab_id = component_tabs.id
        )
        """
    )

    op.drop_index(op.f("ix_component_tab_trade_directions_trade_direction_id"), table_name="component_tab_trade_directions")
    op.drop_index(op.f("ix_component_tab_trade_directions_tab_id"), table_name="component_tab_trade_directions")
    op.drop_table("component_tab_trade_directions")

    op.drop_column("component_tabs", "name_km")
    op.drop_column("component_tabs", "icon")


def downgrade() -> None:
    op.add_column("component_tabs", sa.Column("name_km", sa.String(length=255), nullable=True))
    op.add_column("component_tabs", sa.Column("icon", sa.String(length=64), nullable=True))

    op.create_table(
        "component_tab_trade_directions",
        sa.Column("tab_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_direction_id", sa.BigInteger(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["tab_id"],
            ["component_tabs.id"],
            name=op.f("fk_component_tab_trade_directions_tab_id_component_tabs"),
            ondelete="CASCADE",
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

    op.drop_constraint(
        op.f("fk_component_tabs_trade_direction_id_trade_directions"), "component_tabs", type_="foreignkey"
    )
    op.drop_index(op.f("ix_component_tabs_trade_direction_id"), table_name="component_tabs")
    op.drop_column("component_tabs", "trade_direction_id")
