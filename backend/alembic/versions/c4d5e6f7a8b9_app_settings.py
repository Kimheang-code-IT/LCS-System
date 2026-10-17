"""Keyed application settings table.

Settings were stored as one JSON blob per collection in ``module_records``
(``__app_info__`` and ``__app_config__``). This revision adds the ``app_settings``
table the 47-table proposal defines and copies those payloads into it, one row
per setting group, so a single group can be read, validated and written without
rewriting the whole document.

Additive only: the source ``module_records`` rows are left untouched, so
downgrading loses nothing and the old reader keeps working during a rolling
deploy.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.types import JSONType

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_INFO_COLLECTION = "__app_info__"
APP_CONFIG_COLLECTION = "__app_config__"
SETTINGS_RECORD_NO = "default"

# Setting groups carried by DEFAULT_APP_CONFIG in app/modules/settings/service.py.
# Listed explicitly so a payload that is missing a group still produces an empty
# row the service can fill from its code defaults.
CONFIG_GROUPS: tuple[str, ...] = (
    "general",
    "localization",
    "email",
    "telegram",
    "notifications",
    "security",
    "system",
    "backup",
)


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _app_settings_table() -> sa.Table:
    return sa.table(
        "app_settings",
        sa.column("setting_key", sa.String),
        sa.column("setting_group", sa.String),
        sa.column("setting_value", JSONType),
        sa.column("description", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("setting_key", sa.String(length=120), nullable=False),
        sa.Column("setting_group", sa.String(length=60), nullable=False),
        sa.Column("setting_value", JSONType, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], name=op.f("fk_app_settings_updated_by_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_settings")),
        sa.UniqueConstraint("setting_key", name="uq_app_settings_key"),
    )
    op.create_index("ix_app_settings_group", "app_settings", ["setting_group"], unique=False)

    _backfill_settings()


def _backfill_settings() -> None:
    """Copy the existing settings payloads into one row per group."""
    connection = op.get_bind()
    settings_table = _app_settings_table()

    def existing_keys() -> set[str]:
        return set(connection.execute(sa.select(settings_table.c.setting_key)).scalars().all())

    def insert(key: str, group: str, value: object, description: str) -> bool:
        if key in existing_keys():
            return False
        # created_at/updated_at are left to the column server defaults so the
        # statement stays portable across dialects.
        connection.execute(
            sa.insert(settings_table).values(
                setting_key=key,
                setting_group=group,
                setting_value=value,
                description=description,
            )
        )
        return True

    legacy_rows = connection.execute(
        sa.text(
            "SELECT collection, data FROM module_records "
            "WHERE collection IN (:info, :config) AND record_no = :record_no"
        ),
        {"info": APP_INFO_COLLECTION, "config": APP_CONFIG_COLLECTION, "record_no": SETTINGS_RECORD_NO},
    ).all()

    seen_config = False
    for collection, data in legacy_rows:
        payload = data if isinstance(data, dict) else {}
        if collection == APP_INFO_COLLECTION:
            insert("app_info", "app_info", payload, "Application identity, branding and support contacts.")
            continue
        seen_config = True
        for group in CONFIG_GROUPS:
            value = payload.get(group)
            insert(
                group,
                group,
                value if isinstance(value, dict) else {},
                f"Application settings group '{group}'.",
            )

    # A database that never had the legacy rows still needs an editable baseline
    # for app info; the remaining groups are created on first write.
    insert("app_info", "app_info", {}, "Application identity, branding and support contacts.")
    if not seen_config:
        for group in CONFIG_GROUPS:
            insert(group, group, {}, f"Application settings group '{group}'.")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_app_settings_group")
    op.execute("DROP TABLE IF EXISTS app_settings")
