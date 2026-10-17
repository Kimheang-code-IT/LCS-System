"""Currency master data and effective-dated FX rates.

Adds the two master-data tables the 47-table proposal has and the 59-table
design lacked (``currencies``, ``currency_rates``) and backfills the currency
codes that already appear in the schema.

Additive only: no existing table, column or row is modified. The monetary
columns keep their ``currency_code`` strings for backward compatibility, so
downgrading this revision cannot lose or reinterpret a single amount.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ISO defaults from app/core/localization.py SUPPORTED_CURRENCIES, plus the
# currency codes that appear in seeded/legacy module records. Anything already
# stored under an unknown code is still inserted, named after its own code, so
# no existing amount becomes unresolvable.
DEFAULT_CURRENCIES: tuple[tuple[str, str, str], ...] = (
    ("USD", "US Dollar", "$"),
    ("KHR", "Cambodian Riel", "៛"),
    ("THB", "Thai Baht", "฿"),
    ("VND", "Vietnamese Dong", "₫"),
    ("SGD", "Singapore Dollar", "S$"),
    ("EUR", "Euro", "€"),
    ("GBP", "Pound Sterling", "£"),
    ("JPY", "Japanese Yen", "¥"),
    ("CNY", "Chinese Yuan", "¥"),
)

# The ``currency_code``/``currency`` columns that hold a currency string today.
CURRENCY_SOURCES: tuple[tuple[str, str], ...] = (
    ("financial_documents", "currency_code"),
    ("financial_accounts", "currency_code"),
    ("journal_entry_lines", "currency_code"),
    ("service_orders", "currency_code"),
    ("service_order_pricing", "currency_code"),
    ("service_order_charges", "currency_code"),
    ("quotation_revisions", "currency_code"),
    ("financial_document_allocations", "allocated_currency_code"),
)


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _currencies_table() -> sa.Table:
    return sa.table(
        "currencies",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("symbol", sa.String),
        sa.column("description", sa.Text),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )


def upgrade() -> None:
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=True),
        sa.Column("numeric_code", sa.String(length=3), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            name=op.f("fk_currencies_deleted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_currencies")),
    )
    op.create_index(op.f("ix_currencies_deleted_at"), "currencies", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_currencies_deleted_by_user_id"), "currencies", ["deleted_by_user_id"], unique=False)
    op.create_index(
        "uq_currencies_code_active", "currencies", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL")
    )

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

    _backfill_currencies()


def _backfill_currencies() -> None:
    """Seed the ISO currencies and every currency code already stored."""
    connection = op.get_bind()
    postgres = connection.dialect.name == "postgresql"
    currencies = _currencies_table()

    rows: list[dict[str, object]] = [
        {"code": code, "name": name, "symbol": symbol, "status": "ACTIVE"}
        for code, name, symbol in DEFAULT_CURRENCIES
    ]
    known = {row["code"] for row in rows}

    if postgres:
        select_parts = [
            f"SELECT DISTINCT upper({column}) AS code FROM {table} "
            f"WHERE {column} IS NOT NULL AND btrim({column}) <> ''"
            for table, column in CURRENCY_SOURCES
        ]
        # Currency rows previously stored as generic module records keep their
        # user-entered name/symbol/description instead of being overwritten.
        legacy = connection.execute(
            sa.text(
                "SELECT data->>'code' AS code, data->>'name' AS name, data->>'symbol' AS symbol, "
                "data->>'description' AS description FROM module_records "
                "WHERE collection = 'currencies' AND coalesce(data->>'code', '') <> ''"
            )
        ).all()
        for code, name, symbol, description in legacy:
            normalized = str(code).strip().upper()[:3]
            if normalized in known:
                continue
            known.add(normalized)
            rows.append(
                {
                    "code": normalized,
                    "name": name or normalized,
                    "symbol": symbol,
                    "description": description,
                    "status": "ACTIVE",
                }
            )

        found = connection.execute(sa.text(" UNION ".join(select_parts))).scalars().all()
    else:  # pragma: no cover - migrations run against PostgreSQL
        found = []

    for value in found:
        normalized = str(value).strip().upper()[:3]
        if normalized in known:
            continue
        known.add(normalized)
        rows.append({"code": normalized, "name": normalized, "symbol": None, "status": "ACTIVE"})

    for row in rows:
        exists = connection.execute(
            sa.select(sa.literal(1)).select_from(currencies).where(currencies.c.code == row["code"])
        ).first()
        if exists:
            continue
        # created_at/updated_at come from the column server defaults.
        connection.execute(sa.insert(currencies).values(**row))


def _drop_rate_pair_uniqueness() -> None:
    """Drop the pair/date uniqueness in whichever form it exists.

    PostgreSQL implements a UniqueConstraint *as* an index owned by a constraint,
    so ``DROP INDEX`` alone fails on a database that ran the earlier (constraint)
    form of this revision. Handle both shapes so the rollback is safe either way.
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE currency_rates DROP CONSTRAINT IF EXISTS uq_currency_rates_pair_date")
        op.execute("DROP INDEX IF EXISTS uq_currency_rates_pair_date")
    else:  # pragma: no cover - migrations run against PostgreSQL
        op.drop_index("uq_currency_rates_pair_date", table_name="currency_rates")


def downgrade() -> None:
    # IF EXISTS keeps the rollback safe on a database that applied an earlier
    # form of this revision, where some of these objects may not exist yet.
    op.execute("DROP INDEX IF EXISTS ix_currency_rates_lookup")
    _drop_rate_pair_uniqueness()
    op.execute("DROP INDEX IF EXISTS ix_currency_rates_deleted_by_user_id")
    op.execute("DROP INDEX IF EXISTS ix_currency_rates_deleted_at")
    op.execute("DROP TABLE IF EXISTS currency_rates")
    op.execute("DROP INDEX IF EXISTS uq_currencies_code_active")
    op.execute("DROP INDEX IF EXISTS ix_currencies_deleted_by_user_id")
    op.execute("DROP INDEX IF EXISTS ix_currencies_deleted_at")
    op.execute("DROP TABLE IF EXISTS currencies")
