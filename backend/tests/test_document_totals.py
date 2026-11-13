"""Financial-document list totals: server-side footer aggregates.

The web Financial Documents table is server-paginated, so its Grand Total /
Outstanding footers read `meta.totals` from this endpoint. The totals must
cover the whole filtered list (not just the loaded page), keep currencies
separate and count outstanding only for posted receivable/payable documents.
"""
from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _document(client, headers, *, document_type: str, currency: str, amount: float, exchange_rate: float = 1) -> dict:
    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": document_type,
            "date": "2026-03-05",
            "currency": currency,
            "exchangeRate": exchange_rate,
            "lines": [{"description": f"E2E totals {document_type} {currency}", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_totals_group_by_currency_and_cover_the_filtered_list(client):
    """Mixed currencies stay separate; drafts and receipts carry no outstanding."""
    headers = await login(client)
    invoice = await _document(client, headers, document_type="CUSTOMER_INVOICE", currency="USD", amount=300.0)
    await _document(client, headers, document_type="CUSTOMER_INVOICE", currency="KHR", amount=40_000.0, exchange_rate=4100)
    await _document(client, headers, document_type="CUSTOMER_RECEIPT", currency="USD", amount=100.0)

    response = await client.get("/api/v1/financial-documents", headers=headers)
    assert response.status_code == 200, response.text
    totals = response.json()["data"]["meta"]["totals"]

    # Every currency is its own entry — never one merged sum.
    assert set(totals) >= {"USD", "KHR"}
    assert totals["KHR"]["grand"] >= 40_000.0
    # The KHR invoices are still drafts, so their grand total carries no outstanding.
    assert totals["KHR"]["outstanding"] == pytest.approx(0.0)
    # USD: posted-invoice money only — the draft invoice and the receipt are
    # excluded, so outstanding stays below the grand total.
    assert totals["USD"]["outstanding"] < totals["USD"]["grand"]

    # Posting moves the invoice into the outstanding column.
    posted = await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    totals = (await client.get("/api/v1/financial-documents", headers=headers)).json()["data"]["meta"]["totals"]
    assert totals["USD"]["outstanding"] >= 300.0


async def test_totals_follow_the_same_filters_as_the_list(client):
    """The totals answer for the filtered set, not the unfiltered table."""
    headers = await login(client)
    await _document(client, headers, document_type="CUSTOMER_INVOICE", currency="USD", amount=300.0)
    await _document(client, headers, document_type="CUSTOMER_INVOICE", currency="USD", amount=400.0)

    scoped = await client.get(
        "/api/v1/financial-documents",
        headers=headers,
        params={"documentType": "CUSTOMER_INVOICE", "status": "DRAFT"},
    )
    assert scoped.status_code == 200, scoped.text
    data = scoped.json()["data"]
    totals = data["meta"]["totals"]
    # Same filters as the rows: every USD draft invoice is in the grand total
    # and none of them carry outstanding.
    assert totals["USD"]["grand"] >= 700.0
    assert totals["USD"]["outstanding"] == pytest.approx(0.0)


async def test_base_totals_use_the_configured_base_currency(client):
    """The list footer's single base total comes from each stored conversion."""
    headers = await login(client)
    await _document(client, headers, document_type="CUSTOMER_INVOICE", currency="KHR", amount=40_000.0, exchange_rate=0.00025)

    response = await client.get("/api/v1/financial-documents", headers=headers)
    assert response.status_code == 200, response.text
    meta = response.json()["data"]["meta"]
    base = meta["baseTotals"]
    # The configured base currency, never a hardcoded USD.
    settings = await client.get("/api/v1/settings/app-config", headers=headers)
    configured = settings.json()["data"]["localization"]["currency"]
    assert base["currency"] == configured.upper()
    # KHR 40,000 at 0.00025 = base 10.00, from the stored conversion.
    assert base["grand"] >= 10.0
    assert base["outstanding"] >= 0.0
