from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import event, func, select

from app.core.pagination import PageParams
from app.modules.auth.models import Role, User, UserRoleAssignment
from app.modules.auth.repository import AuthRepository
from app.modules.finance.models import FinancialDocument, FinancialDocumentLine
from app.modules.finance.repository import FinanceRepository
from app.modules.master_data.models import BusinessParty, Place, TradeDirection
from app.modules.master_data.repository import MasterDataRepository
from app.modules.quotations.models import Quotation, QuotationRevision
from app.modules.quotations.repository import QuotationRepository


class QueryCounter:
    def __init__(self, engine) -> None:
        self.engine = engine.sync_engine
        self.count = 0

    def _before_cursor_execute(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.count += 1

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._before_cursor_execute)
        return self

    def __exit__(self, *args) -> None:  # noqa: ANN002
        event.remove(self.engine, "before_cursor_execute", self._before_cursor_execute)


@pytest.mark.asyncio
async def test_auth_repository_batches_user_roles(session_factory, seeded, engine):
    async with session_factory() as session:
        users = list((await session.execute(select(User))).scalars().all())
        with QueryCounter(engine) as legacy:
            legacy_users = list((await session.execute(select(User))).scalars().all())
            for user in legacy_users:
                await session.execute(
                    select(Role.code)
                    .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
                    .where(
                        UserRoleAssignment.user_id == user.id,
                        UserRoleAssignment.expires_at.is_(None),
                    )
                )
        with QueryCounter(engine) as optimized:
            rows = await AuthRepository(session).users_with_role_codes()

    assert len(rows) == len(users)
    assert legacy.count == len(users) + 1
    assert optimized.count == 2


@pytest.mark.asyncio
async def test_quotation_repository_removes_latest_revision_n_plus_one(session_factory, seeded, engine):
    async with session_factory() as session:
        party = (await session.execute(select(BusinessParty).limit(1))).scalars().one()
        direction = (await session.execute(select(TradeDirection).limit(1))).scalars().one()
        for index in range(6):
            quotation = Quotation(
                quotation_no=f"Q-PERF-{index}",
                customer_party_id=party.id,
                trade_direction_id=direction.id,
                current_revision_no=1,
                status="DRAFT",
                data={},
            )
            session.add(quotation)
            await session.flush()
            session.add(
                QuotationRevision(
                    quotation_id=quotation.id,
                    revision_no=1,
                    status="DRAFT",
                    quotation_date=date.today(),
                    currency_code="USD",
                )
            )
        await session.commit()

        page = PageParams(page_size=20, q="Q-PERF")
        repository = QuotationRepository(session)
        with QueryCounter(engine) as legacy:
            rows, _ = await repository.page(page, status=None)
            await repository.conversion_map([row.id for row in rows])
            await repository.party_names([row.customer_party_id for row in rows])
            for row in rows:
                await repository.latest_revision(row.id)
        with QueryCounter(engine) as optimized:
            rows, _ = await repository.page(page, status=None)
            await repository.conversion_map([row.id for row in rows])
            await repository.party_names([row.customer_party_id for row in rows])
            revisions = await repository.latest_revisions([row.id for row in rows])

    assert len(revisions) == 6
    assert legacy.count == 4 + len(rows)
    assert optimized.count == 5


@pytest.mark.asyncio
async def test_finance_repository_batches_document_lines(session_factory, seeded, engine):
    async with session_factory() as session:
        for index in range(6):
            document = FinancialDocument(
                document_no=f"INV-PERF-{index}",
                document_type="CUSTOMER_INVOICE",
                document_date=date.today(),
                status="DRAFT",
                currency_code="USD",
                data={},
            )
            session.add(document)
            await session.flush()
            session.add(
                FinancialDocumentLine(
                    financial_document_id=document.id,
                    line_no=1,
                    description="Freight",
                )
            )
        await session.commit()

        page = PageParams(page_size=20, q="INV-PERF")
        repository = FinanceRepository(session)
        with QueryCounter(engine) as legacy:
            documents, _ = await repository.document_page(page)
            for document in documents:
                await repository.document_lines([document.id])
        with QueryCounter(engine) as optimized:
            documents, _ = await repository.document_page(page)
            lines = await repository.document_lines([document.id for document in documents])

    assert len(lines) == 6
    assert legacy.count == 2 + len(documents)
    assert optimized.count == 3


@pytest.mark.asyncio
async def test_repository_does_not_commit_independently(session_factory, seeded):
    async with session_factory() as session:
        repository = MasterDataRepository(session)
        repository.add(Place(code="ROLLBACK", name="Rollback Test", status="ACTIVE"))
        await session.flush()
        await session.rollback()
        count = await session.scalar(select(func.count()).select_from(Place).where(Place.code == "ROLLBACK"))

    assert count == 0
