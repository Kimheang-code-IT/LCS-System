"""Unified service charges: standalone charges and combined invoicing.

Standalone charges live in the same ``service_order_charges`` table with a NULL
order link and their own customer party; combined invoicing drafts ONE finance
document from several issued charges, each keeping its own bill-once source row.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _party_id(client, headers) -> str:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})
    return response.json()["data"]["items"][0]["id"]


async def _standalone_charge(client, headers, party_id: str, *, currency: str = "USD", amount: int = 25) -> dict:
    response = await client.post(
        "/api/v1/service-charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": currency,
            "customerPartyId": party_id,
            "lines": [{"description": "Standalone service", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _order_charge(client, headers, service_order_id: str, *, amount: int = 40) -> dict:
    response = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [{"description": "Order service", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _issue(client, headers, charge_id: str) -> None:
    issued = await client.post(f"/api/v1/service-charges/{charge_id}/issue", headers=headers, json={})
    assert issued.status_code == 200, issued.text


async def test_a_standalone_charge_needs_no_service_order(client):
    headers = await login(client)
    party_id = await _party_id(client, headers)

    created = await _standalone_charge(client, headers, party_id)
    assert created["serviceOrderId"] in (None, "")
    assert created["customerPartyId"] == party_id
    assert created["customer"], "the charge carries its own customer"

    # The standalone scope lists it; the order scope does not.
    standalone = await client.get("/api/v1/service-charges", headers=headers, params={"scope": "standalone"})
    assert any(row["id"] == created["id"] for row in standalone.json()["data"]["items"])

    edited = await client.put(
        f"/api/v1/service-charges/{created['id']}",
        headers=headers,
        json={"id": created["id"], "lines": [{"description": "Edited", "quantity": 2, "unitPrice": 30}]},
    )
    assert edited.status_code == 200, edited.text
    assert float(edited.json()["data"]["amount"]) == 60


async def test_a_standalone_charge_accepts_a_company_name(client):
    """Name-only clients (and the party picker without an id) resolve a party —
    never the misleading 'Must be a company id.' error."""
    headers = await login(client)

    created = await client.post(
        "/api/v1/service-charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "customer": "Standalone Name Customer",
            "lines": [{"description": "Service", "quantity": 1, "unitPrice": 15}],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert body["serviceOrderId"] in (None, "")
    assert body["customerPartyId"], "a real party is resolved from the name"
    assert body["customer"] == "Standalone Name Customer"

    # A party is still mandatory: nothing to resolve means a clean field error.
    missing = await client.post(
        "/api/v1/service-charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [{"description": "Service", "quantity": 1, "unitPrice": 15}],
        },
    )
    assert missing.status_code == 422, missing.text
    assert "customerPartyId" in missing.json()["field_errors"]


async def test_linked_charges_are_listed_per_scope_and_keep_the_order_customer(client):
    headers = await login(client)
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Scope Customer",
            "direction": "Import",
            "currency": "USD",
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    revision_id = quotation.json()["data"]["revisionId"]
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    order_id = converted.json()["data"]["serviceOrderId"]
    linked = await _order_charge(client, headers, order_id)
    assert linked["customer"], "the linked charge shows the order's customer"

    standalone = await client.get("/api/v1/service-charges", headers=headers, params={"scope": "standalone"})
    assert not any(row["id"] == linked["id"] for row in standalone.json()["data"]["items"])
    everything = await client.get("/api/v1/service-charges", headers=headers, params={"scope": "all"})
    assert any(row["id"] == linked["id"] for row in everything.json()["data"]["items"])

    # A standalone charge cannot borrow a container of an order it is not on.
    bad = await client.post(
        "/api/v1/service-charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "customerPartyId": await _party_id(client, headers),
            "lines": [{"description": "X", "quantity": 1, "unitPrice": 1, "containerId": 999999}],
        },
    )
    assert bad.status_code == 422, bad.text


async def test_an_invoiced_charge_can_no_longer_be_deleted(client):
    headers = await login(client)
    party_id = await _party_id(client, headers)
    charge = await _standalone_charge(client, headers, party_id)
    await _issue(client, headers, charge["id"])
    invoiced = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice", headers=headers, json={}
    )
    assert invoiced.status_code == 201, invoiced.text

    removed = await client.request("DELETE", "/api/v1/service-charges", headers=headers, json={"ids": [charge["id"]]})
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 0, "an invoiced charge is the invoice's source and stays"

    kept = await client.get(f"/api/v1/service-charges/{charge['id']}", headers=headers)
    assert kept.status_code == 200, kept.text


async def _combined(client, headers, ids: list[str], key: str | None = None):
    request_headers = {**headers, **({"Idempotency-Key": key} if key else {})}
    return await client.post("/api/v1/service-charges/combined-invoice", headers=request_headers, json={"ids": ids})


async def test_combined_invoice_links_every_selected_charge_once(client, session_factory):
    from sqlalchemy import select

    from app.modules.finance.models import FinancialDocumentSource

    headers = await login(client)
    party_id = await _party_id(client, headers)
    first = await _standalone_charge(client, headers, party_id, amount=25)
    second = await _standalone_charge(client, headers, party_id, amount=40)
    third = await _standalone_charge(client, headers, party_id, amount=30)
    for charge in (first, second, third):
        await _issue(client, headers, charge["id"])

    document = await _combined(client, headers, [first["id"], second["id"], third["id"]], key="combined-1")
    assert document.status_code == 201, document.text
    body = document.json()["data"]
    assert float(body["total"]) == 95
    assert float(body["subtotal"]) == 95
    assert body["rawStatus"] == "DRAFT", "the combined invoice is a finance draft, not a posting"

    async with session_factory() as session:
        sources = (
            await session.execute(
                select(FinancialDocumentSource).where(FinancialDocumentSource.financial_document_id == int(body["id"]))
            )
        ).scalars().all()
        assert {source.source_id for source in sources} == {int(first["id"]), int(second["id"]), int(third["id"])}

    # Every source charge now shows the same invoice reference.
    for charge in (first, second, third):
        fetched = await client.get(f"/api/v1/service-charges/{charge['id']}", headers=headers)
        assert fetched.json()["data"]["financialDocumentId"] == body["id"]

    # Retry with the same key is a replay; a second attempt without one refuses.
    replay = await _combined(client, headers, [first["id"], second["id"], third["id"]], key="combined-1")
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"]["id"] == body["id"]
    repeat = await _combined(client, headers, [first["id"]])
    assert repeat.status_code == 409, repeat.text


async def test_combined_invoice_rejects_mixed_selections(client):
    headers = await login(client)
    party_id = await _party_id(client, headers)
    same_party = await _standalone_charge(client, headers, party_id, amount=10)
    other_currency = await _standalone_charge(client, headers, party_id, amount=20, currency="EUR")
    for charge in (same_party, other_currency):
        await _issue(client, headers, charge["id"])

    mixed_currency = await _combined(client, headers, [same_party["id"], other_currency["id"]])
    assert mixed_currency.status_code == 422, mixed_currency.text

    # A different customer is refused (a second party must exist to select it).
    parties = (await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 2})).json()["data"]["items"]
    if len(parties) > 1:
        other_party = await _standalone_charge(client, headers, parties[1]["id"], amount=5)
        await _issue(client, headers, other_party["id"])
        mixed_customer = await _combined(client, headers, [same_party["id"], other_party["id"]])
        assert mixed_customer.status_code == 422, mixed_customer.text

    draft = await _standalone_charge(client, headers, party_id, amount=7)
    unissued = await _combined(client, headers, [same_party["id"], draft["id"]])
    assert unissued.status_code == 409, unissued.text
