"""Multi-currency: a consumed exchange-rate store and base-currency amounts.

Three additive changes, all reversible:

* ``currencies.decimal_places`` — a currency's own precision, so a converted
  amount is rounded the way the currency is actually denominated (KHR and JPY to
  0 decimals, rather than a forced 2).
* ``currency_rates`` — the approved-rate store a document resolves from. An
  earlier revision (``c1d2e3f4a5b7``) dropped this table because nothing consumed
  it; this is the version the document form and the invoice generator read, keyed
  by ISO codes so it matches every ``currency_code`` column, with a
  PENDING -> APPROVED -> INACTIVE lifecycle and one row per pair and effective
  date.
* ``financial_documents.base_*`` — the converted amounts and the base currency the
  document was booked in, so a total reads in the company currency without
  re-deriving it, and a posted document keeps saying which base currency it was
  posted against.

Backfill: ``base_* = amount * exchange_rate`` for every existing document — the
exact arithmetic ``post_document`` used — so the stored converted amounts agree
with the journal lines already in the ledger. ``base_currency_code`` is left NULL
for those rows: the base currency in force when they were written was a setting
that may since have changed, and inventing one would be worse than the payload
reporting the current base for them.

Revision ID: d2e3f4a5b6c8
Revises: c1d2e3f4a5b7
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2e3f4a5b6c8"
down_revision: str | None = "c1d2e3f4a5b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "currencies",
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
    )

    op.create_table(
        "currency_rates",
        sa.Column("from_currency_code", sa.String(length=3), nullable=False),
        sa.Column("to_currency_code", sa.String(length=3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=19, scale=8), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("rate > 0", name=op.f("ck_currency_rates_rate_positive")),
        sa.CheckConstraint(
            "from_currency_code <> to_currency_code",
            name=op.f("ck_currency_rates_distinct_pair"),
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            name=op.f("fk_currency_rates_deleted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_currency_rates")),
    )
    op.create_index(op.f("ix_currency_rates_deleted_at"), "currency_rates", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_currency_rates_deleted_by_user_id"), "currency_rates", ["deleted_by_user_id"], unique=False
    )
    # Active-only uniqueness, matching `active_unique_index` in the model: a
    # deleted row must not block re-entering the same pair and date.
    op.create_index(
        "uq_currency_rates_pair_date",
        "currency_rates",
        ["from_currency_code", "to_currency_code", "effective_date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_currency_rates_lookup",
        "currency_rates",
        ["from_currency_code", "to_currency_code", "effective_date", "status"],
        unique=False,
    )

    op.add_column(
        "financial_documents", sa.Column("base_currency_code", sa.String(length=3), nullable=True)
    )
    for column in (
        "base_subtotal_amount",
        "base_discount_amount",
        "base_tax_amount",
        "base_total_amount",
    ):
        op.add_column(
            "financial_documents",
            sa.Column(column, sa.Numeric(precision=19, scale=4), nullable=False, server_default="0"),
        )

    # The arithmetic `post_document` performs, so the stored converted amounts
    # agree with the journal lines already written for these documents.
    op.execute(
        "UPDATE financial_documents SET "
        "base_subtotal_amount = COALESCE(subtotal_amount, 0) * COALESCE(exchange_rate, 1), "
        "base_discount_amount = COALESCE(discount_amount, 0) * COALESCE(exchange_rate, 1), "
        "base_tax_amount = COALESCE(tax_amount, 0) * COALESCE(exchange_rate, 1), "
        "base_total_amount = COALESCE(total_amount, 0) * COALESCE(exchange_rate, 1)"
    )


def downgrade() -> None:
    op.drop_column("financial_documents", "base_total_amount")
    op.drop_column("financial_documents", "base_tax_amount")
    op.drop_column("financial_documents", "base_discount_amount")
    op.drop_column("financial_documents", "base_subtotal_amount")
    op.drop_column("financial_documents", "base_currency_code")

    op.execute("DROP INDEX IF EXISTS ix_currency_rates_lookup")
    op.execute("DROP INDEX IF EXISTS uq_currency_rates_pair_date")
    op.execute("DROP INDEX IF EXISTS ix_currency_rates_deleted_by_user_id")
    op.execute("DROP INDEX IF EXISTS ix_currency_rates_deleted_at")
    op.execute("DROP TABLE IF EXISTS currency_rates")

    op.drop_column("currencies", "decimal_places")
