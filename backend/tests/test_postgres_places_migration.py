"""PostgreSQL migration rehearsal for Places data preservation.

The default suite runs on SQLite, which cannot exercise PostgreSQL foreign keys,
JSONB updates or the destructive-revision guard. Run this test against a
disposable PostgreSQL server where the test user may CREATE DATABASE:

    LCS_TEST_POSTGRES_URL=postgresql://user:password@localhost:5432/postgres \
      uv run pytest tests/test_postgres_places_migration.py -q

The test creates and drops randomly named databases. It never modifies the
database named in the URL; that URL is only used as a maintenance connection for
CREATE/DROP DATABASE.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from alembic.config import Config

from alembic import command
from app.core.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = "a9b8c7d6e5f4"
HEAD_REVISION = "b4c5d6e7f8a9"

EXPECTED_PLACES_FKS = {
    "fk_place_role_places_place_id_places",
    "fk_quotation_revision_places_place_id_places",
    "fk_service_order_movements_destination_place_id_places",
    "fk_service_order_movements_origin_place_id_places",
    "fk_service_order_places_place_id_places",
}

EXPECTED_LEGACY_COLUMNS = {
    ("quotation_revision_places", "place_id"),
    ("service_order_movements", "destination_place_id"),
    ("service_order_movements", "origin_place_id"),
    ("service_order_places", "place_id"),
}

EXPECTED_PLACES_COLUMNS = {
    "id",
    "code",
    "name",
    "description",
    "address",
    "status",
    "created_at",
    "updated_at",
    "deleted_at",
    "deleted_by_user_id",
}

pytestmark = pytest.mark.skipif(
    not os.environ.get("LCS_TEST_POSTGRES_URL"),
    reason="set LCS_TEST_POSTGRES_URL to a disposable PostgreSQL maintenance database",
)


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _sqlalchemy_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    raise ValueError("LCS_TEST_POSTGRES_URL must be a PostgreSQL URL")


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, parts.fragment))


def _maintenance_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.path or parts.path == "/":
        return urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment))
    return url


async def _create_database(admin_url: str, name: str) -> None:
    conn = await asyncpg.connect(_asyncpg_url(admin_url))
    try:
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


async def _drop_database(admin_url: str, name: str) -> None:
    conn = await asyncpg.connect(_asyncpg_url(admin_url))
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            name,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        await conn.close()


def _alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def _run_alembic(db_url: str, action: str, revision: str) -> None:
    original = settings.database_url
    settings.database_url = _sqlalchemy_url(db_url)
    try:
        config = _alembic_config()
        if action == "upgrade":
            command.upgrade(config, revision)
        elif action == "downgrade":
            command.downgrade(config, revision)
        else:
            raise ValueError(action)
    finally:
        settings.database_url = original


async def _seed_places(db_url: str) -> dict[str, object]:
    conn = await asyncpg.connect(_asyncpg_url(db_url))
    try:
        role_id = await conn.fetchval("SELECT id FROM place_roles ORDER BY id LIMIT 1")
        assert role_id is not None
        referenced = await conn.fetchrow(
            """
            INSERT INTO places (code, name, description, address, status)
            VALUES ('P-TEST-1', 'Port One', 'referenced place', '1 Dock Road', 'ACTIVE')
            RETURNING id
            """
        )
        unreferenced = await conn.fetchrow(
            """
            INSERT INTO places (code, name, description, address, status)
            VALUES ('P-TEST-2', 'Unreferenced Yard', 'unreferenced place', '2 Yard Road', 'ACTIVE')
            RETURNING id
            """
        )
        await conn.execute(
            "INSERT INTO place_role_places (place_role_id, place_id) VALUES ($1, $2)",
            role_id,
            referenced["id"],
        )
        return {
            "referenced_id": referenced["id"],
            "unreferenced_id": unreferenced["id"],
        }
    finally:
        await conn.close()


async def _seed_references(db_url: str, place_id: int) -> None:
    """Seed route stops and movements that reference Places.

    One stop/movement starts blank (the migration must fill it from Places) and
    one already has manual text (the migration must not overwrite it).
    """
    conn = await asyncpg.connect(_asyncpg_url(db_url))
    try:
        role_id = await conn.fetchval("SELECT id FROM place_roles ORDER BY id LIMIT 1")
        assert role_id is not None
        party_id = await conn.fetchval(
            """
            INSERT INTO business_parties (party_code, legal_name, status)
            VALUES ('T-PARTY-1', 'Test Customer', 'ACTIVE')
            RETURNING id
            """
        )
        direction_id = await conn.fetchval(
            """
            INSERT INTO trade_directions (code, name, status)
            VALUES ('T-IMP', 'Import', 'ACTIVE')
            RETURNING id
            """
        )
        quotation_id = await conn.fetchval(
            """
            INSERT INTO quotations
                (quotation_no, customer_party_id, trade_direction_id, current_revision_no, status, data)
            VALUES ('T-Q-1', $1, $2, 1, 'DRAFT', '{}'::jsonb)
            RETURNING id
            """,
            party_id,
            direction_id,
        )
        revision_id = await conn.fetchval(
            """
            INSERT INTO quotation_revisions
                (quotation_id, revision_no, status, quotation_date, currency_code,
                 subtotal_amount, discount_amount, tax_amount, total_amount, data)
            VALUES ($1, 1, 'DRAFT', '2026-01-01', 'USD', 0, 0, 0, 0, '{}'::jsonb)
            RETURNING id
            """,
            quotation_id,
        )
        await conn.execute(
            """
            INSERT INTO quotation_revision_places
                (quotation_revision_id, place_role_id, place_id, place_role, sequence_no, free_text)
            VALUES
                ($1, $2, $3, 'ORIGIN', 1, ''),
                ($1, $2, $3, 'DESTINATION', 2, 'Manual Quotation Stop')
            """,
            revision_id,
            role_id,
            place_id,
        )
        service_order_id = await conn.fetchval(
            """
            INSERT INTO service_orders
                (service_order_no, quotation_revision_id, customer_party_id,
                 trade_direction_id, status, currency_code, data)
            VALUES ('T-SO-1', $1, $2, $3, 'DRAFT', 'USD', '{}'::jsonb)
            RETURNING id
            """,
            revision_id,
            party_id,
            direction_id,
        )
        await conn.execute(
            """
            INSERT INTO service_order_places
                (service_order_id, place_role_id, place_id, place_role, sequence_no, free_text, is_actual)
            VALUES
                ($1, $2, $3, 'ORIGIN', 1, '', false),
                ($1, $2, $3, 'DESTINATION', 2, 'Manual Service Stop', false)
            """,
            service_order_id,
            role_id,
            place_id,
        )
        await conn.execute(
            """
            INSERT INTO service_order_movements
                (service_order_id, sequence_no, origin_place_id, destination_place_id, status, data)
            VALUES
                ($1, 1, $2, $2, 'PLANNED', '{}'::jsonb),
                ($1, 2, $2, $2, 'PLANNED',
                 '{"originPlace": "Manual Origin", "destinationPlace": ""}'::jsonb)
            """,
            service_order_id,
            place_id,
        )
    finally:
        await conn.close()


async def _seed_finance(db_url: str) -> None:
    """Seed a balanced draft journal so the financial totals are non-zero."""
    conn = await asyncpg.connect(_asyncpg_url(db_url))
    try:
        accounts = await conn.fetch(
            """
            INSERT INTO chart_of_accounts
                (account_code, account_name, account_type, normal_balance, is_postable, status)
            VALUES
                ('T-CASH', 'Test Cash', 'ASSET', 'DEBIT', true, 'ACTIVE'),
                ('T-REVENUE', 'Test Revenue', 'REVENUE', 'CREDIT', true, 'ACTIVE')
            RETURNING id, account_code
            """
        )
        account_ids = {row["account_code"]: row["id"] for row in accounts}
        period_id = await conn.fetchval(
            """
            INSERT INTO accounting_periods
                (period_year, period_month, start_date, end_date, status)
            VALUES (2026, 1, '2026-01-01', '2026-01-31', 'OPEN')
            RETURNING id
            """
        )
        entry_id = await conn.fetchval(
            """
            INSERT INTO journal_entries
                (entry_no, entry_type, entry_date, posting_date, accounting_period_id,
                 status, description, debit_total, credit_total, data)
            VALUES ('T-JE-1', 'MANUAL', '2026-01-15', '2026-01-15', $1,
                    'DRAFT', 'Places migration test', 100, 100, '{}'::jsonb)
            RETURNING id
            """,
            period_id,
        )
        await conn.execute(
            """
            INSERT INTO journal_entry_lines
                (journal_entry_id, line_no, account_id, description,
                 debit_amount, credit_amount, currency_code, exchange_rate,
                 base_debit_amount, base_credit_amount)
            VALUES
                ($1, 1, $2, 'debit', 100, 0, 'USD', 1, 100, 0),
                ($1, 2, $3, 'credit', 0, 100, 'USD', 1, 0, 100)
            """,
            entry_id,
            account_ids["T-CASH"],
            account_ids["T-REVENUE"],
        )
    finally:
        await conn.close()


async def _snapshot(db_url: str) -> dict[str, object]:
    conn = await asyncpg.connect(_asyncpg_url(db_url))
    try:
        places = [
            dict(row)
            for row in await conn.fetch(
                "SELECT code, name, description, address, status FROM places ORDER BY code"
            )
        ]
        links = await conn.fetchval("SELECT count(*) FROM place_role_places")
        place_columns = {
            row["column_name"]
            for row in await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'places'
                """
            )
        }
        place_indexes = {
            row["indexname"]
            for row in await conn.fetch(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'places'"
            )
        }
        columns = {
            (row["table_name"], row["column_name"])
            for row in await conn.fetch(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND (
                    (table_name = 'quotation_revision_places' AND column_name = 'place_id')
                    OR (table_name = 'service_order_places' AND column_name = 'place_id')
                    OR (table_name = 'service_order_movements' AND column_name = 'origin_place_id')
                    OR (table_name = 'service_order_movements' AND column_name = 'destination_place_id')
                  )
                """
            )
        }
        place_fks = {
            row["conname"]
            for row in await conn.fetch(
                """
                SELECT conname
                FROM pg_constraint
                WHERE contype = 'f' AND confrelid = 'public.places'::regclass
                """
            )
        }
        business_counts = {}
        for table in (
            "quotations",
            "quotation_revisions",
            "service_orders",
            "financial_documents",
            "journal_entries",
        ):
            business_counts[table] = await conn.fetchval(f"SELECT count(*) FROM {table}")
        financial = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(debit_amount), 0) AS debit,
                   COALESCE(SUM(credit_amount), 0) AS credit
            FROM journal_entry_lines
            """
        )
        quotation_stops = [
            dict(row)
            for row in await conn.fetch(
                """
                SELECT place_role, sequence_no, free_text, place_id
                FROM quotation_revision_places
                ORDER BY sequence_no
                """
            )
        ]
        service_stops = [
            dict(row)
            for row in await conn.fetch(
                """
                SELECT place_role, sequence_no, free_text, place_id
                FROM service_order_places
                ORDER BY sequence_no
                """
            )
        ]
        movements = [
            {
                "sequence_no": row["sequence_no"],
                "origin_place_id": row["origin_place_id"],
                "destination_place_id": row["destination_place_id"],
                "data": json.loads(row["data"]) if isinstance(row["data"], str) else row["data"],
            }
            for row in await conn.fetch(
                """
                SELECT sequence_no, origin_place_id, destination_place_id, data
                FROM service_order_movements
                ORDER BY sequence_no
                """
            )
        ]
        return {
            "places": places,
            "links": links,
            "place_columns": place_columns,
            "place_indexes": place_indexes,
            "legacy_columns": columns,
            "place_fks": place_fks,
            "business_counts": business_counts,
            "financial": dict(financial),
            "quotation_stops": quotation_stops,
            "service_stops": service_stops,
            "movements": movements,
            "head": await conn.fetchval("SELECT version_num FROM alembic_version"),
        }
    finally:
        await conn.close()


async def _simulate_destructive_c3d4(db_url: str) -> None:
    conn = await asyncpg.connect(_asyncpg_url(db_url))
    try:
        await conn.execute(
            """
            ALTER TABLE quotation_revision_places DROP COLUMN place_id;
            ALTER TABLE service_order_places DROP COLUMN place_id;
            ALTER TABLE service_order_movements
                DROP COLUMN origin_place_id,
                DROP COLUMN destination_place_id;
            DROP TABLE place_role_places;
            DROP TABLE places;
            UPDATE alembic_version SET version_num = 'c3d4e5f6a7b8';
            """
        )
    finally:
        await conn.close()


def _new_database_name() -> str:
    suffix = uuid.uuid4().hex[:12]
    name = f"lcs_places_test_{suffix}"
    assert re.fullmatch(r"[a-z0-9_]+", name)
    return name


def test_places_survive_upgrade_and_downgrade():
    admin_url = _maintenance_url(os.environ["LCS_TEST_POSTGRES_URL"])
    db_name = _new_database_name()
    db_url = _with_database(admin_url, db_name)
    asyncio.run(_create_database(admin_url, db_name))
    try:
        _run_alembic(db_url, "upgrade", BASE_REVISION)
        seeded = asyncio.run(_seed_places(db_url))
        asyncio.run(_seed_references(db_url, seeded["referenced_id"]))
        asyncio.run(_seed_finance(db_url))
        before = asyncio.run(_snapshot(db_url))
        assert before["quotation_stops"] == [
            {
                "place_role": "ORIGIN",
                "sequence_no": 1,
                "free_text": "",
                "place_id": seeded["referenced_id"],
            },
            {
                "place_role": "DESTINATION",
                "sequence_no": 2,
                "free_text": "Manual Quotation Stop",
                "place_id": seeded["referenced_id"],
            },
        ]
        assert before["movements"][0]["data"] == {}
        assert before["movements"][1]["data"] == {
            "originPlace": "Manual Origin",
            "destinationPlace": "",
        }

        _run_alembic(db_url, "upgrade", "head")
        after = asyncio.run(_snapshot(db_url))

        assert after["head"] == HEAD_REVISION
        assert after["places"] == before["places"]
        assert after["links"] == before["links"] == 1
        assert EXPECTED_PLACES_COLUMNS <= after["place_columns"]
        assert "uq_places_code_active" in after["place_indexes"]
        assert after["legacy_columns"] == EXPECTED_LEGACY_COLUMNS
        assert after["place_fks"] == EXPECTED_PLACES_FKS
        assert after["business_counts"] == before["business_counts"]
        assert after["financial"] == before["financial"]
        assert after["financial"]["debit"] == after["financial"]["credit"]
        assert after["financial"]["debit"] > 0
        assert after["quotation_stops"] == [
            {
                "place_role": "ORIGIN",
                "sequence_no": 1,
                "free_text": "Port One",
                "place_id": seeded["referenced_id"],
            },
            {
                "place_role": "DESTINATION",
                "sequence_no": 2,
                "free_text": "Manual Quotation Stop",
                "place_id": seeded["referenced_id"],
            },
        ]
        assert after["service_stops"] == [
            {
                "place_role": "ORIGIN",
                "sequence_no": 1,
                "free_text": "Port One",
                "place_id": seeded["referenced_id"],
            },
            {
                "place_role": "DESTINATION",
                "sequence_no": 2,
                "free_text": "Manual Service Stop",
                "place_id": seeded["referenced_id"],
            },
        ]
        assert after["movements"][0]["data"] == {
            "originPlace": "Port One",
            "destinationPlace": "Port One",
        }
        assert after["movements"][1]["data"] == {
            "originPlace": "Manual Origin",
            "destinationPlace": "Port One",
        }
        assert seeded["referenced_id"] != seeded["unreferenced_id"]

        _run_alembic(db_url, "downgrade", BASE_REVISION)
        rolled_back = asyncio.run(_snapshot(db_url))
        assert rolled_back["places"] == before["places"]
        assert rolled_back["links"] == before["links"]
        assert rolled_back["legacy_columns"] == EXPECTED_LEGACY_COLUMNS
        assert rolled_back["place_fks"] == EXPECTED_PLACES_FKS
        assert rolled_back["quotation_stops"] == after["quotation_stops"]
        assert rolled_back["movements"] == after["movements"]
        assert rolled_back["financial"] == after["financial"]
        assert rolled_back["head"] == BASE_REVISION
    finally:
        asyncio.run(_drop_database(admin_url, db_name))


def test_guard_refuses_a_database_that_already_lost_places():
    admin_url = _maintenance_url(os.environ["LCS_TEST_POSTGRES_URL"])
    db_name = _new_database_name()
    db_url = _with_database(admin_url, db_name)
    asyncio.run(_create_database(admin_url, db_name))
    try:
        _run_alembic(db_url, "upgrade", BASE_REVISION)
        asyncio.run(_simulate_destructive_c3d4(db_url))

        with pytest.raises(RuntimeError, match="Places data structures are missing"):
            _run_alembic(db_url, "upgrade", "head")
    finally:
        asyncio.run(_drop_database(admin_url, db_name))
