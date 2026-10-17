"""Published configuration versions for the dynamic Service Order form.

Tabs, groups and attributes are edited in place, so an edit would otherwise
change how already-saved Service Order component rows read. This revision adds
``configuration_versions``, the ``config_version_id`` stamp on the rows that
participate in a published configuration, and a ``configuration_version_id`` on
``service_orders``.

The backfill publishes one version built from the *current* live configuration
and stamps every existing tab, component row and service order with it. Nothing
is recomputed: existing orders keep their values and simply gain a reproducible
pointer to the layout they were captured under.

Additive only — no existing column is altered or dropped.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.types import JSONType
from app.modules.master_data.config_snapshot import attribute_entry, build_snapshot, group_entry, tab_entry

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASELINE_NOTE = (
    "Baseline published automatically when configuration versioning was introduced. "
    "Captures the configuration in force before the first manual publish."
)


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "configuration_versions",
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("config_snapshot", JSONType, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_configuration_versions_published_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuration_versions")),
        sa.UniqueConstraint("version_no", name="uq_configuration_versions_no"),
    )
    op.create_index(
        op.f("ix_configuration_versions_status"), "configuration_versions", ["status"], unique=False
    )
    # At most one version may be the live one.
    op.create_index(
        "uq_configuration_versions_published",
        "configuration_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED'"),
    )

    for table in ("component_tabs", "service_order_component_rows", "service_orders"):
        column = "configuration_version_id" if table == "service_orders" else "config_version_id"
        op.add_column(table, sa.Column(column, sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_{column}_configuration_versions"),
            table,
            "configuration_versions",
            [column],
            ["id"],
            ondelete="SET NULL",
        )

    _publish_baseline()


def _publish_baseline() -> None:
    """Publish the current configuration as version 1 and stamp participants."""
    connection = op.get_bind()
    tab_rows = connection.execute(
        sa.text(
            "SELECT id, code, name, trade_direction_id, display_order FROM component_tabs "
            "WHERE is_active AND NOT is_archived ORDER BY display_order, id"
        )
    ).mappings().all()
    if not tab_rows:
        # Nothing configured yet: leave the pointer columns empty. The first
        # publish from the admin UI creates version 1.
        return

    group_rows = connection.execute(
        sa.text(
            "SELECT cg.id, cg.code, cg.name, cg.name_km, cg.render_mode, cg.display_order, "
            "       ctg.tab_id, ctg.display_order AS tab_display_order "
            "FROM component_tab_groups ctg "
            "JOIN component_groups cg ON cg.id = ctg.group_id "
            "WHERE ctg.status = 'ACTIVE' AND cg.is_active AND NOT cg.is_archived "
            "ORDER BY ctg.display_order, cg.id"
        )
    ).mappings().all()
    attribute_rows = connection.execute(
        sa.text(
            "SELECT ca.id, ca.code, ca.label, ca.label_km, ca.data_type, ca.input_type, ca.reference_type, "
            "       ca.is_required, ca.default_value, ca.placeholder, ca.options, ca.validation_rules, "
            "       cga.group_id, cga.is_required AS override_required, cga.display_order AS membership_order "
            "FROM component_group_attributes cga "
            "JOIN component_attributes ca ON ca.id = cga.attribute_id "
            "WHERE cga.status = 'ACTIVE' AND ca.status = 'ACTIVE' "
            "ORDER BY cga.display_order, ca.id"
        )
    ).mappings().all()

    attributes_by_group: dict[object, list[dict]] = {}
    for row in attribute_rows:
        attributes_by_group.setdefault(row["group_id"], []).append(
            attribute_entry(row, {"is_required": row["override_required"], "display_order": row["membership_order"]})
        )

    groups_by_tab: dict[object, list[dict]] = {}
    for row in group_rows:
        groups_by_tab.setdefault(row["tab_id"], []).append(
            group_entry(row, attributes_by_group.get(row["id"], []), row["tab_display_order"])
        )

    tabs = [tab_entry(row, groups_by_tab.get(row["id"], [])) for row in tab_rows]
    snapshot = build_snapshot(tabs)

    versions = sa.table(
        "configuration_versions",
        sa.column("version_no", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("change_note", sa.Text()),
        sa.column("config_snapshot", JSONType),
        sa.column("published_at", sa.DateTime()),
    )
    version_id = connection.execute(
        sa.insert(versions)
        .values(
            version_no=1,
            status="PUBLISHED",
            change_note=BASELINE_NOTE,
            config_snapshot=snapshot,
            published_at=sa.func.current_timestamp(),
        )
        .returning(sa.literal_column("id"))
    ).scalar_one()

    connection.execute(
        sa.text("UPDATE component_tabs SET config_version_id = :version WHERE config_version_id IS NULL"),
        {"version": version_id},
    )
    connection.execute(
        sa.text(
            "UPDATE service_order_component_rows SET config_version_id = :version "
            "WHERE config_version_id IS NULL"
        ),
        {"version": version_id},
    )
    connection.execute(
        sa.text(
            "UPDATE service_orders SET configuration_version_id = :version "
            "WHERE configuration_version_id IS NULL"
        ),
        {"version": version_id},
    )


def downgrade() -> None:
    for table in ("component_tabs", "service_order_component_rows", "service_orders"):
        column = "configuration_version_id" if table == "service_orders" else "config_version_id"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_{column}_configuration_versions")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")

    op.execute("DROP INDEX IF EXISTS uq_configuration_versions_published")
    op.execute("DROP INDEX IF EXISTS ix_configuration_versions_status")
    op.execute("DROP TABLE IF EXISTS configuration_versions")
