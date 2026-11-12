"""Generated Service Order financial drafts: per-container invoices + supplier bills."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.modules.finance.models import FinancialDocument, FinancialDocumentComponentAllocation
from app.modules.operations.models import ServiceOrderCharge
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _customer_order(client, headers) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Generated Docs Customer",
            "direction": "Import",
            "currency": "USD",
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert quotation.status_code == 201, quotation.text
    revision_id = quotation.json()["data"]["revisionId"]
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    return converted.json()["data"]["serviceOrderId"]


async def _party_id(client, headers) -> str:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})
    return response.json()["data"]["items"][0]["id"]


async def test_finish_generates_per_container_invoices_and_supplier_bills_once(client, session_factory):
    headers = await login(client)
    order_id = await _customer_order(client, headers)
    party_id = await _party_id(client, headers)

    for number in ("GENBOX0001", "GENBOX0002"):
        created = await client.post(
            f"/api/v1/service-orders/{order_id}/containers",
            headers=headers,
            json={"containerNumber": number, "containerType": "20GP"},
        )
        assert created.status_code == 201, created.text

    customer_charge = await client.post(
        f"/api/v1/service-orders/{order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "feeLines": [
                {"description": "Shared customer charge", "quantity": 1, "unitAmount": 100, "feeType": "Freight"},
            ],
        },
    )
    assert customer_charge.status_code == 201, customer_charge.text
    customer_id = customer_charge.json()["data"]["id"]
    issued = await client.post(f"/api/v1/service-charges/{customer_id}/issue", headers=headers, json={})
    assert issued.status_code == 200, issued.text

    internal_charge = await client.post(
        f"/api/v1/service-orders/{order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "chargeSide": "INTERNAL",
            "supplierPartyId": party_id,
            "feeLines": [
                {
                    "description": "Internal additional",
                    "quantity": 1,
                    "unitAmount": 50,
                    "costUnitPrice": 30,
                    "feeType": "Freight",
                },
            ],
        },
    )
    assert internal_charge.status_code == 201, internal_charge.text
    assert internal_charge.json()["data"]["chargeSide"] == "INTERNAL"
    assert float(internal_charge.json()["data"]["costTotal"]) == 30

    refreshed = await client.post(
        f"/api/v1/service-orders/{order_id}/refresh-financial-documents", headers=headers, json={}
    )
    assert refreshed.status_code == 200, refreshed.text
    documents = refreshed.json()["data"]["documents"]
    invoices = [row for row in documents if row["type"] == "CUSTOMER_INVOICE"]
    bills = [row for row in documents if row["type"] == "SUPPLIER_BILL"]
    assert len(invoices) == 2
    assert len(bills) == 1

    async with session_factory() as session:
        invoice_rows = (
            await session.execute(select(FinancialDocument).where(FinancialDocument.generated_key.like(f"SO:{order_id}:CTR:%")))
        ).scalars().all()
        assert len(invoice_rows) == 2
        assert {row.generated_key for row in invoice_rows} == {
            f"SO:{order_id}:CTR:{invoice_rows[0].data.get('generatedContainerId')}:CUSTOMER_INVOICE",
            f"SO:{order_id}:CTR:{invoice_rows[1].data.get('generatedContainerId')}:CUSTOMER_INVOICE",
        }
        # 100 container pricing + 100 customer charge + 50 internal selling = 250,
        # split 125 / 125 across the two containers.
        assert sorted(float(row.total_amount or 0) for row in invoice_rows) == [125.0, 125.0]
        allocations = (
            await session.execute(
                select(FinancialDocumentComponentAllocation).where(
                    FinancialDocumentComponentAllocation.financial_document_id.in_([row.id for row in invoice_rows])
                )
            )
        ).scalars().all()
        assert round(sum(float(row.allocated_amount or 0) for row in allocations), 2) == 250.0

        bill = (
            await session.execute(
                select(FinancialDocument).where(FinancialDocument.generated_key == f"SO:{order_id}:SUP:{party_id}:USD:SUPPLIER_BILL")
            )
        ).scalars().one()
        assert float(bill.total_amount or 0) == 30.0

        internal_row = (
            await session.execute(select(ServiceOrderCharge).where(ServiceOrderCharge.id == int(internal_charge.json()["data"]["id"])))
        ).scalars().one()
        assert internal_row.charge_side == "INTERNAL"
        assert internal_row.supplier_party_id == int(party_id)

    # A second, manual invoice for a charge already carried by a generated
    # container invoice is refused.
    duplicate = await client.post(
        f"/api/v1/service-charges/{customer_id}/create-finance-invoice", headers=headers, json={}
    )
    assert duplicate.status_code == 409, duplicate.text

    # Retry/finish must reuse the same generated documents, not duplicate them.
    again = await client.post(
        f"/api/v1/service-orders/{order_id}/refresh-financial-documents", headers=headers, json={}
    )
    assert again.status_code == 200, again.text
    assert {row["id"] for row in again.json()["data"]["documents"]} == {row["id"] for row in documents}

    finished = await client.post(f"/api/v1/service-orders/{order_id}/finish", headers=headers, json={})
    assert finished.status_code == 200, finished.text
    assert len(finished.json()["data"].get("financialDocuments", {}).get("documents", [])) == 3


async def test_ordinary_save_does_not_generate_documents_and_posted_drafts_stay_immutable(client, session_factory):
    headers = await login(client)
    order_id = await _customer_order(client, headers)
    saved = await client.put(
        f"/api/v1/service-orders/{order_id}",
        headers=headers,
        json={"description": "ordinary save"},
    )
    assert saved.status_code == 200, saved.text

    async with session_factory() as session:
        generated = (
            await session.execute(
                select(FinancialDocument).where(FinancialDocument.generated_key.like(f"SO:{order_id}:%"))
            )
        ).scalars().all()
        assert generated == []

    created = await client.post(
        f"/api/v1/service-orders/{order_id}/refresh-financial-documents", headers=headers, json={}
    )
    assert created.status_code == 200, created.text
    first = created.json()["data"]["documents"][0]

    async with session_factory() as session:
        document = await session.get(FinancialDocument, int(first["id"]))
        assert document is not None
        document.status = "POSTED"
        document.total_amount = 999
        await session.commit()

    retried = await client.post(
        f"/api/v1/service-orders/{order_id}/refresh-financial-documents", headers=headers, json={}
    )
    assert retried.status_code == 200, retried.text
    assert any("POSTED" in warning for warning in retried.json()["data"]["warnings"])
    async with session_factory() as session:
        document = await session.get(FinancialDocument, int(first["id"]))
        assert float(document.total_amount or 0) == 999.0


async def test_internal_charge_cannot_be_issued_to_customer(client):
    headers = await login(client)
    order_id = await _customer_order(client, headers)
    party_id = await _party_id(client, headers)
    internal = await client.post(
        f"/api/v1/service-orders/{order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "chargeSide": "INTERNAL",
            "supplierPartyId": party_id,
            "feeLines": [{"description": "Internal", "quantity": 1, "unitAmount": 10, "costUnitPrice": 5}],
        },
    )
    assert internal.status_code == 201, internal.text
    issued = await client.post(
        f"/api/v1/service-charges/{internal.json()['data']['id']}/issue", headers=headers, json={}
    )
    assert issued.status_code == 409, issued.text
