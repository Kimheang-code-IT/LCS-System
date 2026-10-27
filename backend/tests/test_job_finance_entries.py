"""Service-order finance tab: manual financial entries, no automatic charge import."""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _party_id(client, headers) -> str:
    parties = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})
    return parties.json()["data"]["items"][0]["id"]


async def _service_order(client, headers) -> tuple[str, str]:
    party_id = await _party_id(client, headers)
    created = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customerPartyId": party_id,
            "direction": "Import",
            "currency": "USD",
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert created.status_code == 201, created.text
    revision_id = created.json()["data"]["revisionId"]
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    return converted.json()["data"]["serviceOrderId"], party_id


async def _create_entry(client, headers, order_id: str, party_id: str, amount: float, doc_type: str = "CUSTOMER_INVOICE") -> dict:
    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": doc_type,
            "date": date.today().isoformat(),
            "documentDate": date.today().isoformat(),
            "description": "Manual finance entry",
            "partyId": party_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "lines": [{"description": "Manual finance entry", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_finance_tab_does_not_create_or_import_records(client):
    headers = await login(client)
    order_id, _party = await _service_order(client, headers)
    before = await client.get("/api/v1/financial-documents", headers=headers, params={"page_size": 200})
    count = len(before.json()["data"]["items"])
    after = await client.get("/api/v1/financial-documents", headers=headers, params={"page_size": 200})
    assert len(after.json()["data"]["items"]) == count
    assert order_id
    assert all(
        row.get("documentType") != "CUSTOMER_INVOICE" or row.get("serviceOrderId") != order_id
        for row in after.json()["data"]["items"]
    ), "conversion must not create an invoice for the order"


async def test_manual_entry_is_linked_to_the_order_and_stays_a_draft(client):
    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    entry = await _create_entry(client, headers, order_id, party_id, 250)
    assert entry["status"] == "Draft"
    assert entry["serviceOrderId"] == order_id
    assert entry["paidAmount"] == 0

    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    assert all(row.get("sourceDocumentId") != entry["id"] for row in journals.json()["data"]["items"]), (
        "saving a draft must not post a journal"
    )


async def test_manual_entry_validates_order_party_and_amount(client):
    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)

    missing_order = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "serviceOrderId": "999999",
            "currency": "USD",
            "lines": [{"description": "x", "quantity": 1, "unitPrice": 10}],
        },
    )
    assert missing_order.status_code == 422, missing_order.text

    zero = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "lines": [{"description": "x", "quantity": 1, "unitPrice": 0}],
        },
    )
    assert zero.status_code == 422, zero.text


async def test_customer_receipt_allocates_partially(client):
    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    invoice = await _create_entry(client, headers, order_id, party_id, 1000)
    posted = await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    accounts = await client.get("/api/v1/financial-accounts", headers=headers, params={"page_size": 1})
    account_id = accounts.json()["data"]["items"][0]["id"]
    receipt = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_RECEIPT",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "financialAccountId": account_id,
            "lines": [{"description": "Partial receipt", "quantity": 1, "unitPrice": 600}],
        },
    )
    assert receipt.status_code == 201, receipt.text
    receipt_id = receipt.json()["data"]["id"]
    receipt_posted = await client.post(
        f"/api/v1/financial-documents/{receipt_id}/post", headers=headers, json={}
    )
    assert receipt_posted.status_code == 200, receipt_posted.text

    allocated = await client.post(
        f"/api/v1/financial-documents/{receipt_id}/allocate",
        headers=headers,
        json={"target_document_id": invoice["id"], "amount": 600},
    )
    assert allocated.status_code == 200, allocated.text

    refreshed = await client.get(f"/api/v1/financial-documents/{invoice['id']}", headers=headers)
    data = refreshed.json()["data"]
    assert data["total"] == 1000
    assert data["paidAmount"] == 600
    assert data["outstanding"] == 400
