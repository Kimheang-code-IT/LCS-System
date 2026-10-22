"""Allow editing and deleting *draft* configuration versions.

``a7c1e2f3b4d5`` made every configuration snapshot immutable and forbade every
delete, because publishing is the only lifecycle path that existed then. Draft
versions need the opposite guarantee: they are the editable candidate, while a
published or retired snapshot must never change.

The guard keeps the strict rule for non-draft rows and permits a draft to be
edited or discarded before it is published. Publishing a draft is an UPDATE
from ``DRAFT``, which this function also allows; once the row is ``PUBLISHED``
or ``RETIRED`` it becomes immutable again.

Revision ID: f2c3d4e5f6a7
Revises: b8d9e0f1a2b3
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f2c3d4e5f6a7"
down_revision: str | None = "b8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DRAFT_AWARE_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION fn_guard_configuration_version() RETURNS trigger AS $$
BEGIN
    IF current_setting('lcs.allow_financial_purge', true) = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;

    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'DRAFT' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'Published configuration versions cannot be deleted';
    END IF;

    -- A draft is an editable candidate. Publishing it moves it out of DRAFT,
    -- after which the immutable-snapshot rules below apply.
    IF OLD.status = 'DRAFT' THEN
        RETURN NEW;
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

PREVIOUS_TRIGGER_FUNCTION = """
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
    op.execute(DRAFT_AWARE_TRIGGER_FUNCTION)


def downgrade() -> None:
    op.execute(PREVIOUS_TRIGGER_FUNCTION)
