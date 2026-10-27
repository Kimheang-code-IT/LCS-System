"""Configuration version lifecycle: activation, rollback lineage and hashes.

Publishing already froze a snapshot. This revision adds the metadata the history
screen and rollback flow need without introducing a second version table:

* ``scope`` / ``origin`` — today every version is ``GLOBAL`` and either a
  ``PUBLISH`` or a ``ROLLBACK``; the columns leave room for direction-scoped
  publishing later.
* ``source_version_id`` — the version a rollback copied.
* ``snapshot_schema_version`` / ``content_hash`` — lets a reader detect a
  snapshot produced by an older builder and compare content without trusting
  JSON key order.
* ``activated_at`` / ``activated_by_user_id`` — the last activation event. The
  original ``published_*`` fields remain unchanged when a version is reactivated.
* PostgreSQL guards that make the snapshot columns immutable and forbid deleting
  a version. Status and activation metadata remain mutable, which is what
  activation needs.

Everything is additive. Downgrading removes only the columns, indexes, trigger
and function this revision created; published snapshots themselves are untouched
by the schema downgrade.

Revision ID: a7c1e2f3b4d5
Revises: e3f4a5b6c7d9
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7c1e2f3b4d5"
down_revision: str | None = "e3f4a5b6c7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONFIGURATION_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION fn_guard_configuration_version() RETURNS trigger AS $$
BEGIN
    IF current_setting('lcs.allow_financial_purge', true) = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Published configuration versions cannot be deleted';
    END IF;

    IF OLD.version_no IS DISTINCT FROM NEW.version_no
       OR OLD.scope IS DISTINCT FROM NEW.scope
       OR OLD.origin IS DISTINCT FROM NEW.origin
       OR OLD.change_note IS DISTINCT FROM NEW.change_note
       OR OLD.config_snapshot::text IS DISTINCT FROM NEW.config_snapshot::text
       OR OLD.snapshot_schema_version IS DISTINCT FROM NEW.snapshot_schema_version
       OR OLD.content_hash IS DISTINCT FROM NEW.content_hash
       OR OLD.source_version_id IS DISTINCT FROM NEW.source_version_id
       OR OLD.published_at IS DISTINCT FROM NEW.published_at
       OR OLD.published_by_user_id IS DISTINCT FROM NEW.published_by_user_id THEN
        RAISE EXCEPTION 'Published configuration snapshots are immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.add_column(
        "configuration_versions",
        sa.Column("scope", sa.String(length=32), nullable=False, server_default=sa.text("'GLOBAL'")),
    )
    op.add_column(
        "configuration_versions",
        sa.Column("origin", sa.String(length=20), nullable=False, server_default=sa.text("'PUBLISH'")),
    )
    op.add_column(
        "configuration_versions",
        sa.Column("snapshot_schema_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("configuration_versions", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("configuration_versions", sa.Column("source_version_id", sa.BigInteger(), nullable=True))
    op.add_column("configuration_versions", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("configuration_versions", sa.Column("activated_by_user_id", sa.BigInteger(), nullable=True))

    op.create_foreign_key(
        op.f("fk_configuration_versions_source_version_id_configuration_versions"),
        "configuration_versions",
        "configuration_versions",
        ["source_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_configuration_versions_activated_by_user_id_users"),
        "configuration_versions",
        "users",
        ["activated_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_configuration_versions_source_version_id"),
        "configuration_versions",
        ["source_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_configuration_versions_scope_status",
        "configuration_versions",
        ["scope", "status"],
        unique=False,
    )

    op.execute(CONFIGURATION_TRIGGER_FUNCTION)
    op.execute("DROP TRIGGER IF EXISTS trg_guard_configuration_version ON configuration_versions")
    op.execute(
        "CREATE TRIGGER trg_guard_configuration_version "
        "BEFORE UPDATE OR DELETE ON configuration_versions "
        "FOR EACH ROW EXECUTE FUNCTION fn_guard_configuration_version()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_guard_configuration_version ON configuration_versions")
    op.execute("DROP FUNCTION IF EXISTS fn_guard_configuration_version()")

    op.drop_index("ix_configuration_versions_scope_status", table_name="configuration_versions")
    op.drop_index(op.f("ix_configuration_versions_source_version_id"), table_name="configuration_versions")
    op.drop_constraint(
        op.f("fk_configuration_versions_activated_by_user_id_users"),
        "configuration_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_configuration_versions_source_version_id_configuration_versions"),
        "configuration_versions",
        type_="foreignkey",
    )
    op.drop_column("configuration_versions", "activated_by_user_id")
    op.drop_column("configuration_versions", "activated_at")
    op.drop_column("configuration_versions", "source_version_id")
    op.drop_column("configuration_versions", "content_hash")
    op.drop_column("configuration_versions", "snapshot_schema_version")
    op.drop_column("configuration_versions", "origin")
    op.drop_column("configuration_versions", "scope")
