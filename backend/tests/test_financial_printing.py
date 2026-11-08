from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.modules.finance.models import DocumentSequence, FinancialDocument, FinancialDocumentLine, JournalEntry
from app.modules.master_data.models import (
    BusinessParty,
    BusinessPartyRole,
    ContainerType,
    Currency,
    PartyRole,
    TradeDirection,
)
from app.modules.operations.models import ServiceOrder, ServiceOrderContainer
from tests.conftest import login


async def fixture_invoice(session_factory, *, tax=Decimal("0"), code="CUSTOMER_INVOICE"):
    async with session_factory() as session:
        session.add(Currency(code="USD", name="US Dollar", decimal_places=2, status="ACTIVE"))
        company = BusinessParty(party_code="PRINT-COMPANY", legal_name="Synthetic Logistics Co.", status="ACTIVE")
        session.add(company)
        await session.flush()
        role = (await session.execute(select(PartyRole).where(PartyRole.code == "COMPANY"))).scalars().one()
        session.add(BusinessPartyRole(business_party_id=company.id, party_role_id=role.id))
        customer = (await session.execute(select(BusinessParty).where(BusinessParty.party_code == "CUST-001"))).scalars().first()
        direction = (await session.execute(select(TradeDirection))).scalars().first()
        kind = (await session.execute(select(ContainerType))).scalars().first()
        order = ServiceOrder(service_order_no="PRINT-SO", customer_party_id=customer.id, trade_direction_id=direction.id,
                             currency_code="USD", status="ACTIVE", data={"houseNo": "HOUSE-PRINT", "etd": ""})
        session.add(order)
        await session.flush()
        boxes = [ServiceOrderContainer(service_order_id=order.id, container_type_id=kind.id, container_number=n)
                 for n in ("ABCU1234567", "MSCU7654321")]
        session.add_all(boxes)
        await session.flush()
        amounts = [Decimal(n) for n in ("150", "20", "180", "25", "10")]
        document = FinancialDocument(document_no="PRINT-INV", document_type="CUSTOMER_INVOICE", document_date=date(2026, 4, 1),
                                     status="POSTED", party_id=customer.id, service_order_id=order.id, currency_code="USD",
                                     subtotal_amount=sum(amounts), discount_amount=0, tax_amount=tax * len(amounts),
                                     total_amount=sum(amounts) + tax * len(amounts), paid_amount=0,
                                     data={"documentTypeCode": code})
        session.add(document)
        await session.flush()
        for i, amount in enumerate(amounts):
            session.add(FinancialDocumentLine(financial_document_id=document.id, line_no=i+1,
                description=f"Stored fee {i+1}", quantity=1, unit_price=amount, discount_amount=0,
                tax_rate=0, tax_amount=tax, line_amount=amount + tax, service_order_id=order.id,
                service_order_container_id=boxes[i // 2].id if i < 4 else None))
        await session.commit()
        return document.id, [box.id for box in boxes]


async def snapshot(session_factory):
    async with session_factory() as session:
        return {
            "documents": (await session.execute(select(FinancialDocument.id, FinancialDocument.status,
                FinancialDocument.total_amount, FinancialDocument.paid_amount, FinancialDocument.posting_date))).all(),
            "journals": (await session.execute(select(func.count()).select_from(JournalEntry))).scalar_one(),
            "sequences": (await session.execute(select(DocumentSequence.id, DocumentSequence.last_value))).all(),
        }


async def test_consolidated_and_same_type_container_breakdowns_are_read_only(client, session_factory):
    headers = await login(client)
    doc, boxes = await fixture_invoice(session_factory)
    before = await snapshot(session_factory)
    source = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers)
    assert source.status_code == 200, source.text
    data = source.json()["data"]
    assert len(data["model"]["lines"]) == 5
    assert Decimal(data["model"]["totals"]["grandTotal"]) == 385
    assert {row["id"] for row in data["containers"]} == {str(n) for n in boxes}
    assert data["model"]["document"]["number"] == "PRINT-INV"
    assert not data["taxInvoiceEligible"]
    assert data["model"]["document"]["titleKey"] == "freight.print.title.invoice"
    for _ in range(2):
        for box, total in zip(boxes, (170, 205), strict=True):
            response = await client.get(f"/api/v1/financial-documents/{doc}/print-data",
                headers=headers, params={"template": "debit-note", "containerId": box})
            assert response.status_code == 200, response.text
            model = response.json()["data"]["model"]
            assert len(model["lines"]) == 2
            assert Decimal(model["totals"]["balance"]) == total
            assert model["isContainerBreakdown"] is True
            assert model["document"]["number"] == "PRINT-INV"
            assert "Stored fee 5" not in [line["description"] for line in model["lines"]]
    assert await snapshot(session_factory) == before


@pytest.mark.parametrize("params", [
    {"template": "debit-note"}, {"template": "debit-note", "containerId": 999999},
    {"template": "tax-invoice", "containerId": 1}, {"template": "unknown"},
])
async def test_invalid_or_ambiguous_selection_is_refused(client, session_factory, params):
    headers = await login(client)
    doc, _ = await fixture_invoice(session_factory)
    before = await snapshot(session_factory)
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers, params=params)
    assert response.status_code == 422, response.text
    assert await snapshot(session_factory) == before


async def test_explicit_tax_classification_and_stored_tax_are_preserved(client, session_factory):
    headers = await login(client)
    doc, _ = await fixture_invoice(session_factory, tax=Decimal("3.25"), code="TAX_INVOICE")
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["taxInvoiceEligible"] is True
    assert Decimal(data["model"]["totals"]["taxAmount"]) == Decimal("16.25")
    assert Decimal(data["model"]["totals"]["taxRate"]) == 0  # No invented 10% label.
    assert Decimal(data["model"]["totals"]["grandTotal"]) == Decimal("401.25")


async def test_stored_total_mismatch_and_cross_order_container_are_blocked(client, session_factory):
    headers = await login(client)
    doc, boxes = await fixture_invoice(session_factory)
    async with session_factory() as session:
        document = await session.get(FinancialDocument, doc)
        document.total_amount += 1
        await session.commit()
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers)
    assert response.status_code == 422
    async with session_factory() as session:
        document = await session.get(FinancialDocument, doc)
        document.total_amount -= 1
        box = await session.get(ServiceOrderContainer, boxes[0])
        source = await session.get(ServiceOrder, box.service_order_id)
        other = ServiceOrder(service_order_no="FOREIGN-SO", customer_party_id=source.customer_party_id,
                             trade_direction_id=source.trade_direction_id, currency_code="USD")
        session.add(other)
        await session.flush()
        box.service_order_id = other.id
        await session.commit()
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers)
    assert response.status_code == 422


async def test_permission_and_not_found(client, session_factory):
    doc, _ = await fixture_invoice(session_factory)
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data")
    assert response.status_code == 401
    denied = await login(client, "sales")
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=denied)
    assert response.status_code == 403, response.text
    headers = await login(client)
    response = await client.get("/api/v1/financial-documents/999999/print-data", headers=headers)
    assert response.status_code == 404


async def test_discount_draft_and_distinct_base_precision(client, session_factory):
    headers = await login(client)
    doc, _ = await fixture_invoice(session_factory)
    async with session_factory() as session:
        session.add(Currency(code="JPY", name="Japanese Yen", decimal_places=0, status="ACTIVE"))
        document = await session.get(FinancialDocument, doc)
        document.status = "DRAFT"
        document.currency_code = "JPY"
        document.base_currency_code = "USD"
        document.exchange_rate = Decimal("0.04")
        document.base_total_amount = Decimal("15.00")
        document.discount_amount = Decimal("10")
        document.total_amount = Decimal("375")
        line = (await session.execute(select(FinancialDocumentLine).where(
            FinancialDocumentLine.financial_document_id == doc).order_by(FinancialDocumentLine.line_no))).scalars().first()
        line.discount_amount = Decimal("10")
        line.line_amount -= Decimal("10")
        await session.commit()
    before = await snapshot(session_factory)
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers)
    assert response.status_code == 200, response.text
    model = response.json()["data"]["model"]
    assert model["watermark"] == "DRAFT"
    assert model["precision"] == 0
    assert model["totals"]["localPrecision"] == 2
    assert Decimal(model["totals"]["discount"]) == 10
    assert Decimal(model["totals"]["grandTotal"]) == 375
    assert Decimal(model["totals"]["grandTotalLocal"]) == 15
    assert await snapshot(session_factory) == before


@pytest.mark.parametrize("status", ["CANCELLED", "REVERSED"])
async def test_ineligible_status_is_refused(client, session_factory, status):
    headers = await login(client)
    doc, _ = await fixture_invoice(session_factory)
    async with session_factory() as session:
        document = await session.get(FinancialDocument, doc)
        document.status = status
        await session.commit()
    before = await snapshot(session_factory)
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers)
    assert response.status_code == 422
    assert await snapshot(session_factory) == before


async def test_single_container_zero_lines_and_no_container_fallback(client, session_factory):
    headers = await login(client)
    doc, boxes = await fixture_invoice(session_factory)
    async with session_factory() as session:
        document = await session.get(FinancialDocument, doc)
        document.subtotal_amount = document.total_amount = Decimal("0")
        lines = (await session.execute(select(FinancialDocumentLine).where(
            FinancialDocumentLine.financial_document_id == doc))).scalars().all()
        for line in lines:
            line.unit_price = line.line_amount = Decimal("0")
            if line.service_order_container_id == boxes[1]:
                line.service_order_container_id = None
        await session.commit()
    before = await snapshot(session_factory)
    source = await client.get(f"/api/v1/financial-documents/{doc}/print-data", headers=headers)
    assert source.status_code == 200, source.text
    assert len(source.json()["data"]["model"]["lines"]) == 5
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data",
        headers=headers, params={"template": "debit-note"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["selectedContainerId"] == str(boxes[0])
    assert len(data["model"]["lines"]) == 2
    assert Decimal(data["model"]["totals"]["balance"]) == 0
    assert await snapshot(session_factory) == before
    async with session_factory() as session:
        lines = (await session.execute(select(FinancialDocumentLine).where(
            FinancialDocumentLine.financial_document_id == doc))).scalars().all()
        for line in lines:
            line.service_order_container_id = None
        await session.commit()
    response = await client.get(f"/api/v1/financial-documents/{doc}/print-data",
        headers=headers, params={"template": "debit-note"})
    assert response.status_code == 422  # Never fall back to all shared lines.

