"""PostgreSQL-only guarantee: concurrent conversions of one charge create one draft.

SQLite serializes writers, so the bill-once race cannot be shown there. These
tests need a disposable PostgreSQL database (same convention as
``test_quotation_postgres.py``):

    $env:LCS_TEST_PG_HOST = "localhost"
    $env:LCS_TEST_PG_USER = "freight"
    $env:LCS_TEST_PG_PASSWORD = "<from infrastructure/.env>"
    $env:LCS_TEST_PG_DB = "lcs_verify3"
    uv run pytest tests/test_charge_conversion_postgres.py -q

The database must be empty and dedicated to this test: the fixture creates the
schema and seeds it. Nothing touches the application database.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.context import RequestContext
from app.core.database import Base
from app.modules.auth.models import User
from app.modules.finance.models import FinancialDocument, FinancialDocumentSource, JournalEntryLine
from app.modules.master_data.models import BusinessParty, TradeDirection
from app.modules.operations import service as operations
from app.modules.operations.models import ServiceOrder, ServiceOrderCharge
from tests.seed import ensure_seed_data, seed_demo_data

PG = {
    "host": os.environ.get("LCS_TEST_PG_HOST"),
    "user": os.environ.get("LCS_TEST_PG_USER"),
    "password": os.environ.get("LCS_TEST_PG_PASSWORD"),
    "db": os.environ.get("LCS_TEST_PG_DB"),
}
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not all(PG.values()), reason="set LCS_TEST_PG_* to a disposable PostgreSQL database"),
]


def _url() -> str:
    return (
        f"postgresql+asyncpg://{quote_plus(PG['user'] or '')}:{quote_plus(PG['password'] or '')}"
        f"@{PG['host']}:5432/{PG['db']}"
    )


@pytest_asyncio.fixture
async def pg_factory():
    engine = create_async_engine(_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # create_all applies the model's partial unique index on PostgreSQL too
        # (postgresql_where), so the tests exercise the migrated shape directly.
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await ensure_seed_data(session)
        await seed_demo_data(session)
        await session.commit()
    yield factory
    await engine.dispose()


async def _context(factory: async_sessionmaker[AsyncSession]) -> RequestContext:
    async with factory() as session:
        user_id = await session.scalar(select(User.id).order_by(User.id))
    assert user_id is not None, "the seed creates an administrator"
    return RequestContext(
        user_id=user_id,
        username="admin",
        email="admin@example.test",
        display_name="Bill Once Check",
        permissions=set(),
        is_platform_admin=True,
        request_id="bill-once-check",
    )


async def _issued_charge(factory: async_sessionmaker[AsyncSession]) -> ServiceOrderCharge:
    """One ACTIVE order with one issued 110 charge (2 x 50 + 10% tax), via the services."""
    context = await _context(factory)
    async with factory() as session:
        party_id = await session.scalar(select(BusinessParty.id).order_by(BusinessParty.id))
        direction_id = await session.scalar(select(TradeDirection.id).order_by(TradeDirection.id))
        order = ServiceOrder(
            service_order_no="BILLONCE-1",
            customer_party_id=party_id,
            trade_direction_id=direction_id,
            status="ACTIVE",
            currency_code="USD",
            data={},
        )
        session.add(order)
        await session.flush()
        order_id = order.id
        # Numbering is not the subject here: a caller-supplied number avoids the
        # allocate sequence so the fixture stays self-contained.
        charge = await operations.save_charge(
            session,
            context,
            {
                "documentDate": date.today().isoformat(),
                "currency": "USD",
                "chargeNo": "BILLONCE-C1",
                "lines": [{"description": "Ocean freight", "quantity": 2, "unitPrice": 50, "taxRate": 10}],
            },
            order_identifier=str(order_id),
        )
        await operations.issue_charge(session, context, int(charge["id"]))
    async with factory() as session:
        charge = await session.get(ServiceOrderCharge, int(charge["id"]))
    assert charge is not None and charge.status == "ISSUED"
    documents, sources, journals = await _counts(factory)
    assert documents == 0 and sources == 0 and journals == 0, "issuing stays isolated"
    return charge


async def _convert(
    factory: async_sessionmaker[AsyncSession],
    barrier: asyncio.Barrier,
    idempotency_key: str | None,
) -> dict | Exception:
    try:
        context = await _context(factory)
        async with factory() as session:
            charge_row = await session.scalar(select(ServiceOrderCharge.id).limit(1))
            await barrier.wait()
            return await operations.charge_to_invoice(session, context, charge_row, idempotency_key)
    except Exception as exc:  # noqa: BLE001 - the racing assertion reads the failure
        return exc


async def _counts(factory: async_sessionmaker[AsyncSession]) -> tuple[int, int, int]:
    async with factory() as session:
        documents = await session.scalar(select(func.count()).select_from(FinancialDocument))
        sources = await session.scalar(
            select(func.count())
            .select_from(FinancialDocumentSource)
            .where(FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE")
        )
        journals = await session.scalar(
            select(func.count()).select_from(JournalEntryLine).where(JournalEntryLine.service_order_id.is_not(None))
        )
    return int(documents or 0), int(sources or 0), int(journals or 0)


async def _rejects_race(factory: async_sessionmaker[AsyncSession]) -> None:
    documents, sources, journals = await _counts(factory)
    assert documents == 1 and sources == 1 and journals == 0


async def test_two_simultaneous_conversions_create_one_draft(pg_factory):
    barrier = asyncio.Barrier(2)
    await _issued_charge(pg_factory)

    results = await asyncio.gather(
        _convert(pg_factory, barrier, None),
        _convert(pg_factory, barrier, None),
    )

    assert all(isinstance(result, dict) for result in results), results
    assert results[0]["id"] == results[1]["id"], results
    await _rejects_race(pg_factory)


async def test_different_keys_still_convert_once(pg_factory):
    barrier = asyncio.Barrier(2)
    await _issued_charge(pg_factory)

    results = await asyncio.gather(
        _convert(pg_factory, barrier, "client-key-a"),
        _convert(pg_factory, barrier, "client-key-b"),
    )

    assert all(isinstance(result, dict) for result in results), results
    assert results[0]["id"] == results[1]["id"], results
    await _rejects_race(pg_factory)


async def test_the_same_key_concurrently_returns_one_result(pg_factory):
    barrier = asyncio.Barrier(2)
    await _issued_charge(pg_factory)

    results = await asyncio.gather(
        _convert(pg_factory, barrier, "double-click"),
        _convert(pg_factory, barrier, "double-click"),
    )

    assert all(isinstance(result, dict) for result in results), results
    assert results[0]["id"] == results[1]["id"], results
    await _rejects_race(pg_factory)


async def test_the_bill_once_index_refuses_a_second_source_link(pg_factory):
    """The database backstop: a second charge source link cannot be inserted."""
    from sqlalchemy.exc import IntegrityError

    await _issued_charge(pg_factory)
    context = await _context(pg_factory)
    async with pg_factory() as session:
        await operations.charge_to_invoice(session, context, await _first_charge_id(pg_factory))
    async with pg_factory() as session:
        document = await session.scalar(select(FinancialDocument.id).limit(1))
        session.add(FinancialDocumentSource(
            financial_document_id=document,
            source_type="SERVICE_ORDER_CHARGE",
            source_id=await _first_charge_id(pg_factory),
        ))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
    documents, sources, journals = await _counts(pg_factory)
    assert documents == 1 and sources == 1 and journals == 0


async def _first_charge_id(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        return int(await session.scalar(select(ServiceOrderCharge.id).limit(1)))
