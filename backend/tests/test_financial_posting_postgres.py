"""PostgreSQL-only guarantee: concurrent postings of one invoice create one journal.

SQLite serializes writers, so the post race cannot be shown there — same
convention as ``test_quotation_postgres.py`` / ``test_charge_conversion_postgres.py``:

    $env:LCS_TEST_PG_HOST = "localhost"
    $env:LCS_TEST_PG_USER = "freight"
    $env:LCS_TEST_PG_PASSWORD = "<from infrastructure/.env>"
    $env:LCS_TEST_PG_DB = "lcs_verify5"
    uv run pytest tests/test_financial_posting_postgres.py -q

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
from app.modules.finance import service as finance_service
from app.modules.finance.models import (
    FinancialDocument,
    FinancialDocumentPosting,
    JournalEntry,
    JournalEntryLine,
)
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
        f"@{PG['host']}:{os.environ.get('LCS_TEST_PG_PORT', '5432')}/{PG['db']}"
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
        display_name="Posting Race Check",
        permissions=set(),
        is_platform_admin=True,
        request_id="posting-race-check",
    )


async def _draft_invoice(factory: async_sessionmaker[AsyncSession]) -> int:
    """One eligible DRAFT customer invoice (500 USD, no tax) built through the service."""
    context = await _context(factory)
    async with factory() as session:
        payload = {
            "documentType": "CUSTOMER_INVOICE",
            "documentDate": date.today().isoformat(),
            "partyId": await _party_id(factory),
            "currency": "USD",
            "lines": [{"description": "Ocean freight", "quantity": 1, "unitPrice": 500}],
        }
        save = await finance_service.save_document(session, context, payload)
        document_id = int(save["id"])
    async with factory() as session:
        document = await session.get(FinancialDocument, document_id)
    assert document is not None and document.status == "DRAFT"
    return document_id


async def _party_id(factory: async_sessionmaker[AsyncSession]) -> int:
    from sqlalchemy import text

    async with factory() as session:
        row = (await session.execute(text("SELECT id FROM business_parties LIMIT 1"))).first()
    assert row is not None, "the seed creates a business party"
    return int(row[0])


async def _post(factory: async_sessionmaker[AsyncSession], barrier: asyncio.Barrier) -> dict | Exception:
    try:
        context = await _context(factory)
        async with factory() as session:
            document_id = await session.scalar(select(FinancialDocument.id).limit(1))
            await barrier.wait()
            await finance_service.post_document(session, context, document_id)
            document = await session.get(FinancialDocument, document_id)
            assert document is not None
            return finance_service.document_payload(
                document, document.data or {}, await finance_service._document_lines(session, document.id)
            )
    except Exception as exc:  # noqa: BLE001 - the racing assertion reads failures
        return exc


async def _counts(factory: async_sessionmaker[AsyncSession]) -> tuple[int, int, int]:
    async with factory() as session:
        documents = await session.scalar(
            select(func.count()).select_from(FinancialDocument).where(FinancialDocument.status == "POSTED")
        )
        journals = await session.scalar(select(func.count()).select_from(JournalEntry))
        links = await session.scalar(select(func.count()).select_from(FinancialDocumentPosting))
        journals_total = (await session.execute(select(JournalEntryLine))).scalars().all()
        debit = sum(line.debit_amount for line in journals_total)
        credit = sum(line.credit_amount for line in journals_total)
        assert debit == credit == 500, (debit, credit)
    return int(documents or 0), int(journals or 0), int(links or 0)


async def test_two_simultaneous_posts_create_one_journal(pg_factory):
    barrier = asyncio.Barrier(2)
    await _draft_invoice(pg_factory)

    results = await asyncio.gather(
        _post(pg_factory, barrier),
        _post(pg_factory, barrier),
    )

    assert all(isinstance(result, dict) for result in results), results
    assert all(result["rawStatus"] == "POSTED" for result in results), results
    documents, journals, links = await _counts(pg_factory)
    assert (documents, journals, links) == (1, 1, 1), "one posting, atomically"


async def test_a_posted_document_replays_without_a_second_journal(pg_factory):
    document_id = await _draft_invoice(pg_factory)
    context = await _context(pg_factory)

    async with pg_factory() as session:
        posted = await finance_service.post_document(session, context, document_id)
    async with pg_factory() as session:
        replay = await finance_service.post_document(session, context, document_id)

    assert posted["id"] == replay["id"] == str(document_id)
    documents, journals, links = await _counts(pg_factory)
    assert (documents, journals, links) == (1, 1, 1), "the replay must not double-post"
