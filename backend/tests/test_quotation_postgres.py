"""PostgreSQL-only guarantee: two simultaneous conversions create one order.

The rest of the suite runs on in-memory SQLite, where writers are serialised, so
it cannot show what happens when two requests convert the same accepted revision
at the same moment. These tests need a disposable PostgreSQL database:

    $env:LCS_TEST_PG_HOST = "localhost"
    $env:LCS_TEST_PG_USER = "freight"
    $env:LCS_TEST_PG_PASSWORD = "<from infrastructure/.env>"
    $env:LCS_TEST_PG_DB = "lcs_verify"
    uv run pytest tests/test_quotation_postgres.py -q

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
from app.core.exceptions import Conflict
from app.modules.auth.models import User
from app.modules.operations.models import ServiceOrder
from app.modules.quotations import service as quotations
from app.modules.quotations.models import Quotation, QuotationConversion, QuotationRevision
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
        display_name="Concurrency Check",
        permissions=set(),
        is_platform_admin=True,
        request_id="concurrency-check",
    )


async def _accepted_revision(factory: async_sessionmaker[AsyncSession]) -> int:
    context = await _context(factory)
    async with factory() as session:
        record = await quotations.save_quotation(
            session,
            context,
            {
                "date": date.today().isoformat(),
                "customer": "Concurrency Customer",
                "direction": "Import",
                "currency": "USD",
                "pricingLines": [{"description": "Ocean freight", "quantity": 1, "unitPrice": 100}],
            },
        )
        quotation = await session.get(Quotation, int(record["id"]))
        revision = await session.get(QuotationRevision, int(record["revisionId"]))
        assert quotation is not None and revision is not None
        quotation.status = "ACCEPTED"
        revision.status = "ACCEPTED"
        await session.commit()
    return int(record["revisionId"])


async def _attempt(
    factory: async_sessionmaker[AsyncSession],
    context: RequestContext,
    revision_id: int,
    idempotency_key: str,
    barrier: asyncio.Barrier,
) -> dict | Conflict:
    async with factory() as session:
        await barrier.wait()
        try:
            return await quotations.convert_revision(session, context, revision_id, idempotency_key)
        except Conflict as refusal:
            return refusal


async def _counts(factory: async_sessionmaker[AsyncSession], revision_id: int) -> tuple[int, int]:
    async with factory() as session:
        orders = await session.scalar(
            select(func.count()).select_from(ServiceOrder).where(ServiceOrder.quotation_revision_id == revision_id)
        )
        conversions = await session.scalar(
            select(func.count())
            .select_from(QuotationConversion)
            .where(QuotationConversion.quotation_revision_id == revision_id)
        )
    return int(orders or 0), int(conversions or 0)


async def test_concurrent_conversions_create_exactly_one_service_order(pg_factory):
    revision_id = await _accepted_revision(pg_factory)
    context = await _context(pg_factory)
    barrier = asyncio.Barrier(2)

    results = await asyncio.gather(
        _attempt(pg_factory, context, revision_id, "concurrent-a", barrier),
        _attempt(pg_factory, context, revision_id, "concurrent-b", barrier),
    )

    succeeded = [result for result in results if isinstance(result, dict)]
    refused = [result for result in results if isinstance(result, Conflict)]
    assert len(succeeded) == 1, results
    assert len(refused) == 1, results

    orders, conversions = await _counts(pg_factory, revision_id)
    assert orders == 1
    assert conversions == 1

    async with pg_factory() as session:
        revision = await session.get(QuotationRevision, revision_id)
        quotation = await session.get(Quotation, revision.quotation_id if revision else 0)
    assert revision is not None and revision.status == "CONVERTED"
    assert quotation is not None and quotation.status == "CONVERTED"


async def test_concurrent_retries_with_the_same_key_return_one_order(pg_factory):
    revision_id = await _accepted_revision(pg_factory)
    context = await _context(pg_factory)
    barrier = asyncio.Barrier(2)

    results = await asyncio.gather(
        _attempt(pg_factory, context, revision_id, "double-click", barrier),
        _attempt(pg_factory, context, revision_id, "double-click", barrier),
    )

    assert all(isinstance(result, dict) for result in results), results
    assert results[0]["serviceOrderId"] == results[1]["serviceOrderId"]
    assert results[0]["serviceOrderNo"] == results[1]["serviceOrderNo"]

    orders, conversions = await _counts(pg_factory, revision_id)
    assert orders == 1
    assert conversions == 1


async def test_deleting_the_order_nulls_the_requotation_link(pg_factory):
    """ON DELETE SET NULL: dropping the job keeps the commercial history."""
    from sqlalchemy import text

    revision_id = await _accepted_revision(pg_factory)
    context = await _context(pg_factory)
    async with pg_factory() as session:
        converted = await quotations.convert_revision(session, context, revision_id, "delete-check")
    order_id = int(converted["serviceOrderId"])

    async with pg_factory() as session:
        requote = await quotations.create_quotation_from_service_order(session, context, str(order_id))
    assert requote["sourceServiceOrderId"] == str(order_id)

    async with pg_factory() as session:
        await session.execute(text("DELETE FROM service_orders WHERE id = :id"), {"id": order_id})
        await session.commit()

    async with pg_factory() as session:
        quotation = await session.get(Quotation, int(requote["id"]))
    assert quotation is not None, "deleting the order must not delete the re-quotation"
    assert quotation.source_service_order_id is None
