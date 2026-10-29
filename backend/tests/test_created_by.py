"""Creator attribution in the main list payloads.

The creator must come from the authenticated request context, survive another
user editing the record, and never be spoofed by a client-supplied field.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

ADMIN_NAME = "Demo Administrator"


async def test_list_payloads_report_the_creator_and_resist_spoofing(client):
    admin = await login(client)
    parties = await client.get("/api/v1/businessParties", headers=admin, params={"page_size": 1})
    party_id = parties.json()["data"]["items"][0]["id"]

    created = await client.post(
        "/api/v1/quotations",
        headers=admin,
        json={
            "date": date.today().isoformat(),
            "customerPartyId": party_id,
            "direction": "Import",
            "currency": "USD",
            # A client must not be able to choose the creator.
            "createdBy": "Spoofed User",
            "createdByUserId": 999999,
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert created.status_code == 201, created.text
    quotation = created.json()["data"]
    quotation_id = quotation["id"]
    revision_id = quotation["revisionId"]

    listed = await client.get("/api/v1/quotations", headers=admin, params={"page_size": 200})
    row = next(item for item in listed.json()["data"]["items"] if item["id"] == quotation_id)
    assert row["createdBy"] == ADMIN_NAME

    # Another user authoring the next revision must not change the quotation's creator.
    sales = await login(client, "sales")
    revision = await client.post(f"/api/v1/quotations/{quotation_id}/revisions", headers=sales, json={})
    assert revision.status_code == 201, revision.text
    after_edit = await client.get("/api/v1/quotations", headers=admin, params={"page_size": 200})
    edited = next(item for item in after_edit.json()["data"]["items"] if item["id"] == quotation_id)
    assert edited["createdBy"] == ADMIN_NAME

    # Service order, charge and finance document carry their own creator.
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=admin, json={})
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=admin, json={})
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=admin, json={})
    assert converted.status_code == 201, converted.text
    service_order_id = converted.json()["data"]["serviceOrderId"]

    orders = await client.get("/api/v1/service-orders", headers=admin, params={"page_size": 200})
    order = next(item for item in orders.json()["data"]["items"] if item["id"] == service_order_id)
    assert order["createdBy"] == ADMIN_NAME

    charge = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=admin,
        json={
            "documentType": "SERVICE_NOTE",
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert charge.status_code == 201, charge.text
    charge_id = charge.json()["data"]["id"]

    charges = await client.get("/api/v1/service-charges", headers=admin, params={"page_size": 200})
    charge_row = next(item for item in charges.json()["data"]["items"] if item["id"] == charge_id)
    assert charge_row["createdBy"] == ADMIN_NAME

    await client.post(f"/api/v1/service-charges/{charge_id}/issue", headers=admin, json={})
    invoice = await client.post(
        f"/api/v1/service-charges/{charge_id}/create-finance-invoice", headers=admin, json={}
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["data"]["id"]

    documents = await client.get("/api/v1/financial-documents", headers=admin, params={"page_size": 200})
    document = next(item for item in documents.json()["data"]["items"] if item["id"] == invoice_id)
    assert document["createdBy"] == ADMIN_NAME
    assert document["serviceOrderId"] == service_order_id

    posted = await client.post(f"/api/v1/financial-documents/{invoice_id}/post", headers=admin, json={})
    assert posted.status_code == 200, posted.text

    journals = await client.get("/api/v1/journal-entries", headers=admin, params={"page_size": 200})
    entries = journals.json()["data"]["items"]
    assert entries, "posting the invoice creates a journal entry"
    entry = next((item for item in entries if item.get("sourceDocumentId") == invoice_id), entries[0])
    assert entry["createdBy"] == ADMIN_NAME
    assert entry["createdAt"], "the journal list exposes the original creation timestamp"
    assert entry["entryNo"]

    created_user = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "creator.check",
            "displayName": "Creator Check",
            "email": "creator.check@example.com",
            "password": "Passw0rd!",
            "status": "Active",
            "role": "SALES",
        },
    )
    assert created_user.status_code == 201, created_user.text
    users = await client.get("/api/v1/users", headers=admin, params={"page_size": 200})
    user_row = next(item for item in users.json()["data"] if item["username"] == "creator.check")
    assert user_row["createdBy"] == ADMIN_NAME
    assert user_row["createdAt"]

    fee = await client.post(
        "/api/v1/feeTypes",
        headers=admin,
        json={"code": "CREATOR-TEST", "name": "Creator Test Fee"},
    )
    assert fee.status_code == 201, fee.text
    fee_id = fee.json()["data"]["id"]
    fees = await client.get("/api/v1/feeTypes", headers=admin, params={"page_size": 200})
    fee_row = next(item for item in fees.json()["data"]["items"] if item["id"] == fee_id)
    assert fee_row["createdBy"] == ADMIN_NAME
    assert fee_row["createdAt"]
