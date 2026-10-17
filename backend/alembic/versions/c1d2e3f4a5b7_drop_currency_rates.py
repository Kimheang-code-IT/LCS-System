"""Drop ``currency_rates``.

The currency-rate editor was removed from the product: the FX page, its master-data
collection and everything that read it are gone. What remains is the currency master
itself (``currencies``), which every currency dropdown in the application uses.

Why a separate revision rather than editing ``b3c4d5e6f7a8``: that revision is part
of the deployed chain, and rewriting an applied revision changes its checksum for
every environment that already ran it. A new revision keeps the history honest and
gives the drop a real ``downgrade()``.

Effect on data: none that matters. ``currency_rates`` only ever held manually
entered conversion rates, and no posting reads it — every posting snapshots the rate
it actually used into ``financial_documents.exchange_rate`` and
``journal_entry_lines.exchange_rate``, with the base-currency amounts beside them.
Dropping the table therefore cannot change a single posted amount. The
``downgrade()`` recreates the table empty, which is the most a rollback can honestly
restore.

Revision ID: c1d2e3f4a5b7
Revises: b0c1d2e3f4a5
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b7"
down_revision: str | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_currency_rates_lookup")
    # The pair/date uniqueness is an index; older databases may still hold it as a
    # UniqueConstraint, so drop whichever form exists before dropping the table.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE currency_rates DROP CONSTRAINT IF EXISTS uq_currency_rates_pair_date")
        op.execute("DROP INDEX IF EXISTS uq_currency_rates_pair_date")
        op.execute("DROP INDEX IF EXISTS ix_currency_rates_deleted_by_user_id")
        op.execute("DROP INDEX IF EXISTS ix_currency_rates_deleted_at")
    op.execute("DROP TABLE IF EXISTS currency_rates")


def downgrade() -> None:
    op.create_table(
        "currency_rates",
        sa.Column("from_currency_id", sa.BigInteger(), nullable=False),
        sa.Column("to_currency_id", sa.BigInteger(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=19, scale=8), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("rate > 0", name=op.f("ck_currency_rates_rate_positive")),
        sa.CheckConstraint("from_currency_id <> to_currency_id", name=op.f("ck_currency_rates_distinct_pair")),
        sa.ForeignKeyConstraint(
            ["from_currency_id"], ["currencies.id"], name=op.f("fk_currency_rates_from_currency_id_currencies")
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            name=op.f("fk_currency_rates_deleted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_currency_id"], ["currencies.id"], name=op.f("fk_currency_rates_to_currency_id_currencies")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_currency_rates")),
    )
    op.create_index(op.f("ix_currency_rates_deleted_at"), "currency_rates", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_currency_rates_deleted_by_user_id"), "currency_rates", ["deleted_by_user_id"], unique=False
    )
    op.create_index(
        "uq_currency_rates_pair_date",
        "currency_rates",
        ["from_currency_id", "to_currency_id", "effective_date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_currency_rates_lookup",
        "currency_rates",
        ["from_currency_id", "to_currency_id", "effective_date"],
        unique=False,
    )
