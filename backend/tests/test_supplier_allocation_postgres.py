"""PostgreSQL-only guarantee: concurrent allocations cannot over-settle.

Two allocations racing the same Payment balance must resolve to one success and
one typed refusal — never a negative balance. Same convention as the other
`test_*_postgres.py` files:

    $env:LCS_TEST_PG_HOST = "localhost"
    $env:LCS_TEST_PG_USER = "freight"
    $env:LCS_TEST_PG_PASSWORD = "<from infrastructure/.env>"
    $env:LCS_TEST_PG_DB = "lcs_verify8"
    uv run pytest tests/test_supplier_allocation_postgres.py -q

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
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.context import RequestContext
from app.core.database import Base
from app.core.exceptions import Conflict
from app.modules.auth.models import User
from app.modules.finance import service as finance_service
from app.modules.finance.models import FinancialDocument, FinancialDocumentAllocation
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
        display_name="Allocation Race Check",
        permissions=set(),
        is_platform_admin=True,
        request_id="allocation-race-check",
    )


async def _party_id(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        row = (await session.execute(text("SELECT id FROM business_parties LIMIT 1"))).first()
    assert row is not None, "the seed creates a business party"
    return int(row[0])


async def _posted_pair(factory: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    """An bill of 500 and one Payment of 200, both posted through the services."""
    context = await _context(factory)
    party_id = await _party_id(factory)
    async with factory() as session:
        bill = await finance_service.save_document(
            session,
            context,
            {
                "documentType": "SUPPLIER_BILL",
                "documentDate": date.today().isoformat(),
                "partyId": party_id,
                "currency": "USD",
                "lines": [{"description": "Ocean freight", "quantity": 1, "unitPrice": 500}],
            },
        )
        payment = await finance_service.save_document(
            session,
            context,
            {
                "documentType": "SUPPLIER_PAYMENT",
                "documentDate": date.today().isoformat(),
                "partyId": party_id,
                "currency": "USD",
                "lines": [{"description": "Payment", "quantity": 1, "unitPrice": 200}],
            },
        )
        bill_id, payment_id = int(bill["id"]), int(payment["id"])
    async with factory() as session:
        await finance_service.post_document(session, context, bill_id)
        await finance_service.post_document(session, context, payment_id)
    return payment_id, bill_id


async def _allocate(
    factory: async_sessionmaker[AsyncSession],
    payment_id: int,
    bill_id: int,
    amount: int,
    barrier: asyncio.Barrier,
) -> dict | Exception:
    try:
        context = await _context(factory)
        async with factory() as session:
            await barrier.wait()
            return await finance_service.allocate_payment(
                session, context, payment_id, {"target_document_id": bill_id, "amount": 200}
            )
    except Exception as exc:  # noqa: BLE001 - the racing assertion reads failures
        return exc


async def test_two_simultaneous_allocations_cannot_exceed_the_balance(pg_factory):
    """Test I: a 200 Payment cannot settle 400, however the requests interleave."""
    barrier = asyncio.Barrier(2)
    payment_id, bill_id = await _posted_pair(pg_factory)

    results = await asyncio.gather(
        _allocate(pg_factory, payment_id, bill_id, 200, barrier),
        _allocate(pg_factory, payment_id, bill_id, 200, barrier),
    )

    accepted = [result for result in results if isinstance(result, dict)]
    refused = [result for result in results if isinstance(result, Conflict)]
    assert len(accepted) == 1 and len(refused) == 1, results
    assert refused[0].code == "ALLOCATION_EXCEEDS_BALANCE"

    async with pg_factory() as session:
        bill = await session.get(FinancialDocument, bill_id)
        payment = await session.get(FinancialDocument, payment_id)
        allocations = (
            await session.execute(
                select(func.count()).select_from(FinancialDocumentAllocation).where(
                    FinancialDocumentAllocation.payment_document_id == payment_id
                )
            )
        ).scalar()
    assert int(bill.paid_amount) == 200, "the bill is settled once, exactly"
    assert int(payment.paid_amount) == 200
    assert int(allocations) == 1
    assert int(bill.total_amount) - int(bill.paid_amount) == 300


async def test_a_retry_with_the_same_key_replays_the_first_allocation(pg_factory):
    payment_id, bill_id = await _posted_pair(pg_factory)
    context = await _context(pg_factory)

    async with pg_factory() as session:
        await finance_service.allocate_payment(
            session,
            context,
            payment_id,
            {"target_document_id": bill_id, "amount": 200},
            "settle-once",
        )
    async with pg_factory() as session:
        replay = await finance_service.allocate_payment(
            session,
            context,
            payment_id,
            {"target_document_id": bill_id, "amount": 200},
            "settle-once",
        )

    assert replay["idempotentReplay"] is True
    assert replay["allocatedAmount"] == 200
    async with pg_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(FinancialDocumentAllocation).where(
                FinancialDocumentAllocation.payment_document_id == payment_id
            )
        )
    assert int(count) == 1




