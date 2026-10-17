"""Link a posted journal to the posting rule that produced it.

Every journal already carries the accounts and amounts it was posted with, so
posted history survives a rule change. What it did *not* carry was *which* rule
produced it — the resolution was snapshotted into ``journal_entries.data`` as a
human-readable blob, which cannot be joined, indexed or guarded.

This revision promotes that link to a real column with a foreign key:

* ``journal_entries.posting_rule_id`` → ``posting_rules.id``, plus an index for
  the "which documents posted through this rule?" query;
* it is written by ``post_document`` from the resolver's own result, so it is
  authoritative rather than parsed back out of JSON;
* it deliberately has **no** ``ON DELETE`` action. Deleting a rule that posted
  something would destroy the link, and ``app/core/deletion.py`` now reports
  ``journal_entries`` as a blocking reference automatically, because the scan
  walks the metadata rather than a hand-maintained list. A superseded rule is
  deactivated, never deleted.

The backfill reads the snapshot written by the previous form of this work, so a
database that already holds journals keeps its rule attribution. It is a no-op
where no snapshot exists, which is the normal case for a database that has not
run this feature yet. Existing rows are never rewritten beyond this one column.

Additive only — no existing column is altered or dropped.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-10-15
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
# Revision 6 in docs/15_migration_and_rollback_guide.md.
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "fk_journal_entries_posting_rule_id_posting_rules"
INDEX = "ix_journal_entries_posting_rule_id"


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column("posting_rule_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        CONSTRAINT,
        "journal_entries",
        "posting_rules",
        ["posting_rule_id"],
        ["id"],
    )
    op.create_index(INDEX, "journal_entries", ["posting_rule_id"], unique=False)
    _backfill_from_snapshot(op.get_bind())


def downgrade() -> None:
    op.drop_index(INDEX, table_name="journal_entries")
    op.drop_constraint(CONSTRAINT, "journal_entries", type_="foreignkey")
    op.drop_column("journal_entries", "posting_rule_id")


def _backfill_from_snapshot(bind: sa.Connection) -> None:
    """Adopt the rule id previously recorded only inside ``journal_entries.data``.

    Reading through the connected driver means the JSON arrives as a ``dict`` on
    PostgreSQL (JSONB) and as a ``str`` on SQLite (plain JSON), so both are
    handled. A rule id that no longer exists is skipped rather than allowed to
    violate the new foreign key: the journal keeps its accounts either way, which
    is the part that actually matters.
    """
    known_rules = {row[0] for row in bind.execute(sa.text("SELECT id FROM posting_rules")).fetchall()}
    if not known_rules:
        return
    updates: list[dict[str, int]] = []
    for entry_id, data in bind.execute(sa.text("SELECT id, data FROM journal_entries")).fetchall():
        payload = data
        if isinstance(payload, (str, bytes)):
            try:
                payload = json.loads(payload)
            except ValueError:
                continue
        if not isinstance(payload, dict):
            continue
        raw = payload.get("ruleId")
        if raw in (None, ""):
            continue
        try:
            rule_id = int(raw)
        except (TypeError, ValueError):
            continue
        if rule_id in known_rules:
            updates.append({"entry_id": entry_id, "rule_id": rule_id})
    if updates:
        bind.execute(
            sa.text("UPDATE journal_entries SET posting_rule_id = :rule_id WHERE id = :entry_id"),
            updates,
        )