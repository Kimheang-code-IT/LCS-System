"""Currency master data.

Covers the ``currencies`` endpoints. Every currency dropdown in the application
sources its options from this collection, so the round trip matters beyond the
master-data screen itself.

The FX rate editor was removed from the product, which also removed the
``currency_rates`` table (migration ``c1d2e3f4a5b7``). Postings have always
snapshotted the rate they used into ``financial_documents.exchange_rate`` and
``journal_entry_lines.exchange_rate``, so nothing about a posted amount depended on
that table.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _create_currency(client, headers, code: str, name: str = "Test Currency") -> dict:
    response = await client.post(
        "/api/v1/currencies", headers=headers, json={"code": code, "name": name, "status": "ACTIVE"}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_currency_master_round_trip(client):
    headers = await login(client)
    created = await _create_currency(client, headers, "KHR", "Cambodian Riel")
    assert created["code"] == "KHR"
    assert created["name"] == "Cambodian Riel"

    listed = await client.get("/api/v1/currencies", headers=headers)
    assert listed.status_code == 200, listed.text
    codes = [row["code"] for row in listed.json()["data"]["items"]]
    assert "KHR" in codes

    updated = await client.put(
        f"/api/v1/currencies/{created['id']}", headers=headers, json={"symbol": "riel"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["symbol"] == "riel"


async def test_duplicate_currency_code_is_rejected(client):
    headers = await login(client)
    await _create_currency(client, headers, "THB", "Thai Baht")
    duplicate = await client.post(
        "/api/v1/currencies", headers=headers, json={"code": "THB", "name": "Duplicate", "status": "ACTIVE"}
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "code" in duplicate.json()["field_errors"]


async def test_a_currency_can_be_deactivated_rather_than_deleted(client):
    """Currencies are referenced by documents, so deactivation is the safe route."""
    headers = await login(client)
    created = await _create_currency(client, headers, "SGD", "Singapore Dollar")

    deactivated = await client.put(
        f"/api/v1/currencies/{created['id']}", headers=headers, json={"status": "INACTIVE"}
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["status"].upper() == "INACTIVE"

    listed = await client.get("/api/v1/currencies", headers=headers, params={"page_size": 200})
    codes = {row["code"] for row in listed.json()["data"]["items"]}
    assert "SGD" in codes, "a deactivated currency stays listed for historical documents"


async def test_the_rate_store_is_routed_and_the_currency_master_survives(client):
    """Regression guard, rewritten when FX became a consumed feature.

    This guard used to assert the *unused* rate editor was gone: nothing read its
    table, so a document could not resolve a rate from it. The owner then asked
    for exchange rates to be consumed, so the store is back — and what has to hold
    now is the wiring, not the absence. `tests/test_multi_currency.py` proves that
    end to end (approved rows only, inverse pairs, the rate copied onto the
    document); here we pin only that the collection is routed again and that the
    currency master it pairs with is still served.
    """
    headers = await login(client)

    assert (await client.get("/api/v1/currencyRates", headers=headers)).status_code == 200
    assert (await client.get("/api/v1/currencies", headers=headers)).status_code == 200
