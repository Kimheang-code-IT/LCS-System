from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _first_party(client, headers, *, role: str | None = None) -> dict:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    if role:
        items = [row for row in items if role.lower() in {str(r).lower() for r in row.get("roles") or []}]
    assert items, "expected at least one business party"
    return items[0]


async def _create_quotation(client, headers, payload: dict) -> dict:
    body = {"date": date.today().isoformat(), "direction": "Import", "currency": "USD", **payload}
    response = await client.post("/api/v1/quotations", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_quotation_stores_customer_party_id(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    created = await _create_quotation(client, headers, {"customerPartyId": party["id"], "amount": 1000})
    assert created["customerPartyId"] == str(party["id"])
    assert created["customer"] == party["legalName"]

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["customerPartyId"] == str(party["id"])
    assert data["customer"] == party["legalName"]


async def test_quotation_rejects_unknown_customer_party_id(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={"date": date.today().isoformat(), "direction": "Import", "currency": "USD", "customerPartyId": 999999},
    )
    assert response.status_code == 422, response.text
    assert "customerPartyId" in response.json()["field_errors"]


async def test_two_new_customers_saved_in_the_same_second_do_not_collide(client):
    """Regression: the placeholder party code was unique only per second.

    ``resolve_party_by_name`` stamped ``P-YYMMDDHHMMSS``, so two quotations for
    two brand-new customers saved back to back raised a UNIQUE violation on the
    active ``party_code`` index instead of creating the second customer.
    """
    headers = await login(client)
    created = [
        await _create_quotation(client, headers, {"customer": name, "amount": 25})
        for name in ("Same Second Customer A", "Same Second Customer B")
    ]
    assert created[0]["customerPartyId"] != created[1]["customerPartyId"], (
        "each new customer must get its own business party"
    )

    codes = []
    for row in created:
        party = await client.get(f"/api/v1/businessParties/{row['customerPartyId']}", headers=headers)
        assert party.status_code == 200, party.text
        codes.append(party.json()["data"]["partyCode"])
    assert len(set(codes)) == 2, f"party codes must be unique, got {codes}"


async def test_quotation_update_switches_customer_party(client):
    headers = await login(client)
    parties = (await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})).json()["data"]["items"]
    assert len(parties) >= 2
    first, second = parties[0], parties[1]

    created = await _create_quotation(client, headers, {"customerPartyId": first["id"]})
    updated = await client.put(
        f"/api/v1/quotations/{created['id']}",
        headers=headers,
        json={"customerPartyId": second["id"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["customer"] == second["legalName"]

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.json()["data"]["customerPartyId"] == str(second["id"])


async def test_revision_history_preserves_original_and_opens_draft(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"], "amount": 500})

    sent = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/send", headers=headers, json={})
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["revisionStatus"] == "SENT"

    revision = await client.post(f"/api/v1/quotations/{created['id']}/revisions", headers=headers, json={})
    assert revision.status_code == 201, revision.text
    assert revision.json()["data"]["revisionNo"] >= 2
    assert revision.json()["data"]["status"] == "Draft"

    history = await client.get(f"/api/v1/quotations/{created['id']}/revisions", headers=headers)
    assert history.status_code == 200, history.text
    items = history.json()["data"]
    assert [row["revisionNo"] for row in items] == sorted([row["revisionNo"] for row in items], reverse=True)
    statuses = {row["revisionNo"]: row["rawStatus"] for row in items}
    assert statuses[1] == "SENT", "the original sent revision must be preserved"
    assert statuses[items[0]["revisionNo"]] == "DRAFT"
    assert items[0]["isCurrent"] is True


async def test_delete_is_blocked_once_quotation_has_service_order(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"], "amount": 750})

    sent = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/send", headers=headers, json={})
    assert sent.status_code == 200, sent.text
    accepted = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/accept", headers=headers, json={})
    assert accepted.status_code == 200, accepted.text
    converted = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text

    blocked = await client.request(
        "DELETE", "/api/v1/quotations", headers=headers, json={"ids": [created["id"]]}
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "QUOTATION_HAS_SERVICE_ORDER"


async def test_draft_quotation_can_be_deleted(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"]})

    removed = await client.request(
        "DELETE", "/api/v1/quotations", headers=headers, json={"ids": [created["id"]]}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 1

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 404, fetched.text
