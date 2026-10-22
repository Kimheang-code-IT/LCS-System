"""Independent display layouts for component groups inside a tab.

A Component Group was rendered from its own ``render_mode``, so every tab that
reused the group had to show it the same way. This revision moves the layout to
the group's *assignment* on a tab (``component_tab_groups``), which is what lets
one tab hold a form-only group, a table-only group and a form-and-table group at
the same time.

Additive and non-destructive:

* ``component_tab_groups.display_mode`` — form_only | table_only |
  form_and_table.
* ``component_tab_groups.data_cardinality`` — single | multiple.
* ``component_tab_groups.form_columns`` — 1..4.
* ``component_tab_groups.show_group_title`` / ``editable`` / ``collapsible`` /
  ``default_expanded``.
* ``component_group_attributes.is_visible`` — column/field visibility.

Existing rows are backfilled from the group's legacy ``render_mode`` (``form``
becomes form_only/single, ``table`` becomes table_only/multiple), so every
existing tab renders exactly as before. Nothing is dropped, and downgrading
only removes the new columns.

Revision ID: e3f4a5b6c7d9
Revises: d2e3f4a5b6c8
Create Date: 2026-10-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e3f4a5b6c7d9"
down_revision: str | None = "d2e3f4a5b6c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("component_tab_groups", sa.Column("display_mode", sa.String(length=20), nullable=True))
    op.add_column("component_tab_groups", sa.Column("data_cardinality", sa.String(length=20), nullable=True))
    op.add_column("component_tab_groups", sa.Column("form_columns", sa.Integer(), nullable=True))
    op.add_column("component_tab_groups", sa.Column("show_group_title", sa.Boolean(), nullable=True))
    op.add_column("component_tab_groups", sa.Column("editable", sa.Boolean(), nullable=True))
    op.add_column("component_tab_groups", sa.Column("collapsible", sa.Boolean(), nullable=True))
    op.add_column("component_tab_groups", sa.Column("default_expanded", sa.Boolean(), nullable=True))

    op.add_column(
        "component_group_attributes",
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # Backfill the layout every existing assignment already rendered with.
    op.execute(
        sa.text(
            "UPDATE component_tab_groups AS ctg "
            "SET display_mode = CASE WHEN LOWER(cg.render_mode) = 'form' THEN 'form_only' ELSE 'table_only' END, "
            "    data_cardinality = CASE WHEN LOWER(cg.render_mode) = 'form' THEN 'single' ELSE 'multiple' END, "
            "    form_columns = 3, "
            "    show_group_title = TRUE, "
            "    editable = TRUE, "
            "    collapsible = FALSE, "
            "    default_expanded = TRUE "
            "FROM component_groups AS cg "
            "WHERE cg.id = ctg.group_id"
        )
    )

    # NULL stays allowed: a row inserted outside the service inherits the legacy
    # group default at read time instead of failing to insert.
    op.create_check_constraint(
        op.f("ck_component_tab_groups_display_mode"),
        "component_tab_groups",
        "display_mode IS NULL OR display_mode IN ('form_only', 'table_only', 'form_and_table')",
    )
    op.create_check_constraint(
        op.f("ck_component_tab_groups_data_cardinality"),
        "component_tab_groups",
        "data_cardinality IS NULL OR data_cardinality IN ('single', 'multiple')",
    )
    op.create_check_constraint(
        op.f("ck_component_tab_groups_form_columns"),
        "component_tab_groups",
        "form_columns IS NULL OR (form_columns BETWEEN 1 AND 4)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_component_tab_groups_form_columns"), "component_tab_groups", type_="check")
    op.drop_constraint(op.f("ck_component_tab_groups_data_cardinality"), "component_tab_groups", type_="check")
    op.drop_constraint(op.f("ck_component_tab_groups_display_mode"), "component_tab_groups", type_="check")

    op.drop_column("component_group_attributes", "is_visible")
    for column in (
        "default_expanded",
        "collapsible",
        "editable",
        "show_group_title",
        "form_columns",
        "data_cardinality",
        "display_mode",
    ):
        op.drop_column("component_tab_groups", column)
