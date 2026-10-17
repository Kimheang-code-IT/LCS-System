"""Database-driven posting rules: priority, description and a priority guarantee.

``posting_rules`` already decides which debit/credit/tax accounts a financial
document posts through, and the service already rejected a second *active* rule
for the same document type and fee type. Two things were missing:

* **priority** — an administrator needs to say that one rule outranks another
  without deactivating the loser, and the resolver needs a declared order rather
  than an insertion order. The resolver takes the highest priority in the most
  specific tier that matches.
* **a concurrency guarantee** — the duplicate check was a read-then-write, so two
  concurrent requests could both pass it and both commit. A partial unique index
  makes the database the final arbiter.

The index is keyed on ``(document_type, COALESCE(fee_type_id, 0), priority)``
over active rows, *not* on ``(document_type, COALESCE(fee_type_id, 0))``. A
scope-wide index would have made priority meaningless — two active rules for one
scope could never coexist, so there would be nothing to prioritise. Keying on
the triple states the real invariant: **within one scope, two active rules may
exist, but they may not share a priority**, because then the resolver would have
no defensible winner. Inactive rows are excluded so a replacement can sit beside
the rule it replaces.

This weakens the constraint relative to the old service-level check, so it cannot
fail on an existing database: every row that satisfied "one active rule per
scope" also satisfies "one active rule per scope *and* priority".

``description`` is the administrator's own note about why a rule exists, shown in
the Posting Rules screen.

Additive only — no existing column is altered or dropped. ``priority`` defaults
to 0, which preserves today's behaviour (insertion order) exactly.

Revision ID: f8a9b0c1d2e3
Revises: e6f7a8b9c0d1
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e6f7a8b9c0d1"
# Revision 5 in docs/15_migration_and_rollback_guide.md.
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "posting_rules",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "posting_rules",
        sa.Column("description", sa.Text(), nullable=True),
    )
    # Resolution always filters by document type and status, then orders by
    # priority: without this the resolver degrades to a sequential scan as the
    # rule table grows.
    op.create_index(
        "ix_posting_rules_resolution",
        "posting_rules",
        ["document_type", "status", "priority"],
        unique=False,
    )
    # Concurrency guard. COALESCE folds the NULL "document default" rule into the
    # same key space as a fee-specific one.
    op.create_index(
        "uq_posting_rules_active_priority",
        "posting_rules",
        ["document_type", sa.text("COALESCE(fee_type_id, 0)"), "priority"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_posting_rules_active_priority", table_name="posting_rules")
    op.drop_index("ix_posting_rules_resolution", table_name="posting_rules")
    op.drop_column("posting_rules", "description")
    op.drop_column("posting_rules", "priority")