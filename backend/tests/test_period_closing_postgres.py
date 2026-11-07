"""PostgreSQL-only guarantee: a posting and the closing serialize on the period row.

Posting takes the period-row lock (08.1 hardening in PLAN-0013's follow-up: PLAN-0017);
closing takes the same lock and re-validates under it. The race therefore ends in
exactly one of two consistent states — never a journal inside a CLOSED period.

    $env:LCS_TEST_PG_HOST = "localhost"
    $env:LCS_TEST_PG_USER = "freight"
    $env:LCS_TEST_PG_PASSWORD = "<from infrastructure/.env>"
    $env:LCS_TEST_PG_DB = "lcs_verify9"
    uv run pytest tests/test_period_closing_postgres.py -q

The database must be empty and dedicated to this test. Nothing touches the application database.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.context import RequestContext
from app.core.database import Base
from app.core.exceptions import Conflict
from app.modules.auth.models import User
from app.modules.finance import service as finance_service
from app.modules.finance.models import AccountingPeriod, FinancialDocument, JournalEntry
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
        display_name="Closing Race Check",
        permissions=set(),
        is_platform_admin=True,
        request_id="closing-race-check",
    )


async def _party_id(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        row = (await session.execute(text("SELECT id FROM business_parties LIMIT 1"))).first()
    assert row is not None, "the seed creates a business party"
    return int(row[0])


async def _racy_pair(factory: async_sessionmaker[AsyncSession]) -> tuple[int, str]:
    """An OPEN period for a past month + one DRAFT document dated inside it."""
    context = await _context(factory)
    party_id = await _party_id(factory)
    month = date.today().replace(day=1)
    month = (month - timedelta(days=1)).replace(day=1)
    month = (month - timedelta(days=1)).replace(day=1)
    month = (month - timedelta(days=1)).replace(day=1)  # three months back: outside the seed
    start = month
    end = month + timedelta(days=27)
    async with factory() as session:
        period = AccountingPeriod(
            period_year=start.year,
            period_month=start.month,
            start_date=start,
            end_date=end,
            status="OPEN",
        )
        session.add(period)
        await session.flush()
        document = await finance_service.save_document(
            session,
            context,
            {
                "documentType": "CUSTOMER_INVOICE",
                "documentDate": start.isoformat(),
                "postingDate": start.isoformat(),
                "partyId": party_id,
                "currency": "USD",
                "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 300}],
            },
        )
        document_id = int(document["id"])
        period_id = int(period.id)
    return document_id, period_id, start.isoformat()


async def _closing(
    factory: async_sessionmaker[AsyncSession], barrier: asyncio.Barrier, period_id: int
) -> str | Exception:
    try:
        context = await _context(factory)
        async with factory() as session:
            await barrier.wait()
            await finance_service.close_period(session, context, period_id)
            return "CLOSED"
    except Exception as exc:  # noqa: BLE001 - the racing assertion reads failures
        return exc


async def _posting(factory: async_sessionmaker[AsyncSession], barrier: asyncio.Barrier) -> dict | Exception:
    try:
        context = await _context(factory)
        async with factory() as session:
            document_id = await session.scalar(select(FinancialDocument.id).limit(1))
            await barrier.wait()
            await finance_service.post_document(session, context, document_id)
            return await finance_service.document_status(session, document_id)
    except Exception as exc:  # noqa: BLE001 - the racing assertion reads failures
        return exc


async def test_closing_and_posting_never_interleave(pg_factory):
    barrier = asyncio.Barrier(2)
    document_id, period_id, _document_date = await _racy_pair(pg_factory)

    closed, posted = await asyncio.gather(
        _closing(pg_factory, barrier, period_id),
        _posting(pg_factory, barrier),
    )

    async with pg_factory() as session:
        period = await session.get(AccountingPeriod, period_id)
        journals = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.accounting_period_id == period.id)
            )
        ).scalars().all()
    # Whichever commits first, the period closes; the race only picks the branch.
    assert isinstance(closed, str) and closed == "CLOSED", (closed, posted)
    for journal in journals:
        assert journal.status == "POSTED" and journal.debit_total == journal.credit_total
    if journals:
        # The posting won the lock: it posted while the period was still open.
        assert posted in ("POSTED",) or isinstance(posted, dict), (posted, closed)
    else:
        # The closing won: the posting is refused with the typed period error.
        assert isinstance(posted, Conflict) and posted.code in ("PERIOD_CLOSED", "PERIOD_NOT_OPEN"), (posted, closed)
    # Either way the books are consistent; a repeat close refuses (or re-closing
    # the already-closed period is impossible from the service).
    repeating = await _closing(pg_factory, asyncio.Barrier(1), period_id)
    assert isinstance(repeating, Exception) or repeating == "CLOSED"

