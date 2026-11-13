"""Order-scoped financial reads and retry-safe manual entry creation."""
from datetime import date

import pytest

from tests.conftest import login
from tests.test_job_finance_entries import _create_entry, _service_order

pytestmark = pytest.mark.asyncio


async def test_order_filter_covers_all_types_and_pagination(client):
    headers = await login(client)
    order, party = await _service_order(client, headers)
    other, _ = await _service_order(client, headers)
    first = await _create_entry(client, headers, order, party, 11)
    expense = await _create_entry(client, headers, order, party, 7, "OTHER_EXPENSE")
    await _create_entry(client, headers, other, party, 99)
    ids = set()
    for page in (1, 2):
        response = await client.get("/api/v1/financial-documents", headers=headers, params={
            "service_order_id": order, "page": page, "page_size": 1,
        })
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["meta"]["total"] == 2
        assert all(row["serviceOrderId"] == order for row in data["items"])
        ids.update(row["id"] for row in data["items"])
    assert ids == {first["id"], expense["id"]}


@pytest.mark.parametrize("kind", ["CUSTOMER_RECEIPT", "OTHER_EXPENSE"])
async def test_entry_retry_returns_original_and_rejects_changed_payload(client, kind):
    headers = await login(client)
    order, party = await _service_order(client, headers)
    accounts = (await client.get("/api/v1/financial-accounts", headers=headers)).json()["data"]["items"]
    payload = {
        "documentType": kind, "serviceOrderId": order, "partyId": party,
        "date": date.today().isoformat(), "currency": "USD",
        "financialAccountId": accounts[0]["id"], "paymentMethod": "Bank Transfer",
        "lines": [{"description": "Retry-safe entry", "quantity": 1, "unitPrice": 50}],
    }
    keyed = {**headers, "Idempotency-Key": f"order-entry-{kind}"}
    created = await client.post("/api/v1/financial-documents", headers=keyed, json=payload)
    assert created.status_code == 201, created.text
    doc = created.json()["data"]
    assert doc["status"] == "Draft"
    assert "_creationKey" not in doc and "_creationDigest" not in doc
    replay = await client.post("/api/v1/financial-documents", headers=keyed, json=payload)
    assert replay.json()["data"]["id"] == doc["id"]
    changed = await client.post("/api/v1/financial-documents", headers=keyed, json={**payload, "description": "Different"})
    assert changed.status_code == 409, changed.text
    posted = await client.post(f"/api/v1/financial-documents/{doc['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    replay = await client.post("/api/v1/financial-documents", headers=keyed, json=payload)
    assert replay.json()["data"]["id"] == doc["id"]
    assert replay.json()["data"]["status"] == "Posted"
    refused = await client.put(f"/api/v1/financial-documents/{doc['id']}", headers=headers, json=payload)
    assert refused.status_code == 409, refused.text
    scoped = (await client.get("/api/v1/financial-documents", headers=headers, params={"service_order_id": order})).json()["data"]
    assert scoped["meta"]["total"] == 1


async def test_failed_create_does_not_consume_key_and_reserved_fields_cannot_be_spoofed(client):
    headers = await login(client)
    order, party = await _service_order(client, headers)
    payload = {
        "documentType": "OTHER_EXPENSE", "serviceOrderId": order, "partyId": party,
        "date": date.today().isoformat(), "currency": "USD",
        "lines": [{"description": "Invalid", "quantity": 1, "unitPrice": -1}],
    }
    keyed = {**headers, "Idempotency-Key": "retry-after-validation"}
    refused = await client.post("/api/v1/financial-documents", headers=keyed, json=payload)
    assert refused.status_code == 422, refused.text
    payload["lines"][0]["unitPrice"] = 10
    accepted = await client.post("/api/v1/financial-documents", headers=keyed, json=payload)
    assert accepted.status_code == 201, accepted.text
    spoofed = await client.post("/api/v1/financial-documents", headers=headers, json={
        **payload, "_creationKey": "spoof", "_creationDigest": "spoof",
    })
    assert spoofed.status_code == 201, spoofed.text
    assert "_creationKey" not in spoofed.json()["data"]
