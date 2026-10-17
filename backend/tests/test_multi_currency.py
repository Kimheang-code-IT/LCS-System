"""Multi-currency: the rate store, the conversion, and what a posting keeps.

The rules these tests pin, in the order the requirements state them:

* a document in the company's base currency always carries rate 1, and the rate
  field is not part of it;
* a document in another currency resolves its rate from the approved rate store
  (in either direction of the pair), or takes the one the operator typed;
* zero, negative, unparseable and missing rates are refused — defaulting to 1
  would mis-state every converted amount;
* the converted amounts are stored on the document, rounded with the currency's
  configured precision;
* posting snapshots the rate onto the journal lines and leaves the document's
  stored conversion untouched afterwards, whatever the rate store does later;
* a multi-currency journal must balance in the base currency as well as its own;
* an allocation between documents booked at different rates reports the exchange
  difference it realises;
* an invoice generated from a charge keeps the charge's currency, applies its own
  approved rate, and never rewrites the source charge.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.modules.master_data.models import BusinessParty
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _party(session) -> int:
    party = (
        await session.execute(select(BusinessParty).where(BusinessParty.party_code == "CUST-001"))
    ).scalars().first()
    return int(party.id)


async def _rate(
    client,
    headers,
    from_code: str,
    to_code: str,
    rate: float | str,
    *,
    effective: str = "2026-01-01",
    status: str = "APPROVED",
) -> dict:
    response = await client.post(
        "/api/v1/currencyRates",
        headers=headers,
        json={
            "fromCurrencyCode": from_code,
            "toCurrencyCode": to_code,
            "effectiveDate": effective,
            "rate": rate,
            "status": status,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _create(client, headers, payload: dict) -> dict:
    response = await client.post("/api/v1/financial-documents", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _detail(client, headers, document_id) -> dict:
    response = await client.get(f"/api/v1/financial-documents/{document_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _post(client, headers, document_id) -> dict:
    response = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _invoice(party_id: int, **extra) -> dict:
    return {
        "documentType": "CUSTOMER_INVOICE",
        "date": "2026-03-01",
        "partyId": party_id,
        "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        **extra,
    }


async def test_a_document_in_the_base_currency_always_carries_rate_one(client, session_factory, seeded):
    """Requirement 3: same currency -> the rate is 1, whatever a client sends."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)

    # Base currency in the test installation is USD; a client sending a rate for a
    # USD document is ignored by design.
    detail = await _detail(client, headers, (
        await _create(client, headers, _invoice(party_id, currency="USD", exchangeRate=5))
    )["id"])

    assert detail["currency"] == "USD"
    assert detail["exchangeRate"] == 1
    assert detail["baseCurrency"] == "USD"
    assert detail["baseTotalAmount"] == pytest.approx(100.0)


async def test_a_foreign_currency_resolves_an_approved_rate_from_the_store(client, session_factory, seeded):
    """Requirement 4: the latest approved rate is applied when the client omits one."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)
    # 1 USD = 4000 KHR. A KHR document converts the other way: 1 / 4000.
    await _rate(client, headers, "USD", "KHR", 4000)

    created = await _create(client, headers, _invoice(party_id, currency="KHR"))
    detail = await _detail(client, headers, created["id"])

    assert detail["exchangeRate"] == pytest.approx(0.00025)
    assert detail["baseCurrency"] == "USD"
    assert detail["total"] == pytest.approx(100.0)
    assert detail["baseTotalAmount"] == pytest.approx(0.03)
    assert detail["currencyPrecision"] == 2


async def test_a_directly_quoted_pair_is_used_as_stored(client, session_factory, seeded):
    """The store's own direction wins when the pair exists both ways round."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)
    await _rate(client, headers, "USD", "KHR", 4000)
    await _rate(client, headers, "KHR", "USD", 0.00026)

    detail = await _detail(client, headers, (
        await _create(client, headers, _invoice(party_id, currency="KHR"))
    )["id"])

    # 1 KHR = 0.00026 USD is quoted directly, so it is not inverted.
    assert detail["exchangeRate"] == pytest.approx(0.00026)


async def test_only_an_approved_rate_is_applied(client, session_factory, seeded):
    """A pending rate is a draft: it must not value anybody's document."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)
    await _rate(client, headers, "USD", "KHR", 4000, status="PENDING")

    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json=_invoice(party_id, currency="KHR"),
    )

    assert response.status_code == 422, response.text
    assert response.json()["field_errors"]["exchangeRate"]


async def test_a_missing_rate_is_refused_rather_than_defaulted_to_one(client, session_factory, seeded):
    """Requirement 8: no rate and no approved pair is an error, not a silent 1."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)

    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json=_invoice(party_id, currency="KHR"),
    )

    assert response.status_code == 422, response.text
    assert "exchangeRate" in response.json()["field_errors"]


@pytest.mark.parametrize("rate", [0, -1, "abc", "0", "-0.5"])
async def test_zero_negative_and_unparseable_rates_are_rejected(client, session_factory, seeded, rate):
    """Requirement 8: every unusable rate is refused at the API boundary."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)

    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json=_invoice(party_id, currency="KHR", exchangeRate=rate),
    )

    assert response.status_code == 422, response.text
    assert response.json()["field_errors"]["exchangeRate"]


async def test_the_rate_the_operator_typed_wins_over_the_store(client, session_factory, seeded):
    """Requirement 4: manual entry is allowed for users who may edit the document."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)
    await _rate(client, headers, "USD", "KHR", 4000)

    detail = await _detail(client, headers, (
        await _create(client, headers, _invoice(party_id, currency="KHR", exchangeRate=0.0004))
    )["id"])

    assert detail["exchangeRate"] == pytest.approx(0.0004)
    assert detail["baseTotalAmount"] == pytest.approx(0.04)


async def test_a_posted_document_keeps_its_rate_and_base_amounts(client, session_factory, seeded):
    """Requirements 9 and 10: the conversion is stored, and posting freezes it."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)
    created = await _create(
        client, headers, _invoice(party_id, currency="KHR", exchangeRate=0.00025)
    )
    await _post(client, headers, created["id"])

    # A new approved rate afterwards must not reach a posted document...
    await _rate(client, headers, "USD", "KHR", 2000)
    posted = await _detail(client, headers, created["id"])

    assert posted["status"] == "Posted"
    assert posted["exchangeRate"] == pytest.approx(0.00025)
    assert posted["baseTotalAmount"] == pytest.approx(0.03)
    assert posted["journalId"]

    # ...and the document cannot be edited at all, so the stored rate cannot drift.
    blocked = await client.put(
        f"/api/v1/financial-documents/{created['id']}",
        headers=headers,
        json={"date": "2026-03-02", "exchangeRate": 0.5},
    )
    assert blocked.status_code in (400, 409, 422), blocked.text
    assert (await _detail(client, headers, created["id"]))["exchangeRate"] == pytest.approx(0.00025)


async def test_currency_precision_rounds_the_converted_amount(client, session_factory, seeded):
    """Requirement 14: precision is configuration, not a hardcoded two decimals."""
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)
    # The Riel has no minor unit; the master says so, and the conversion obeys it.
    created_currency = await client.post(
        "/api/v1/currencies",
        headers=headers,
        json={"code": "KHR", "name": "Cambodian Riel", "decimalPlaces": 0, "status": "ACTIVE"},
    )
    assert created_currency.status_code == 201, created_currency.text
    assert created_currency.json()["data"]["decimalPlaces"] == 0

    detail = await _detail(client, headers, (
        await _create(client, headers, _invoice(party_id, currency="KHR", exchangeRate=0.00025))
    )["id"])

    # 100 KHR * 0.00025 = 0.025 USD, rounded to whole Riel-denominated dollars.
    assert detail["currencyPrecision"] == 0
    assert detail["baseTotalAmount"] == pytest.approx(0.0)


async def test_a_journal_must_also_balance_in_the_base_currency(client, session_factory, seeded):
    """The database guard balances the *own* amounts of a journal's lines; a
    journal must balance in the base currency too, which that guard cannot see.

    Two lines of 100 USD at different rates cancel in their own currency — the
    PostgreSQL guard accepts them — while their converted amounts do not.
    """
    headers = await login(client)
    inconsistent = await client.post(
        "/api/v1/journal-entries",
        headers=headers,
        json={
            "entryDate": "2026-03-01",
            "postingDate": "2026-03-01",
            "description": "Same amounts, two rates",
            "lines": [
                {"accountCode": "1100", "debitAmount": 100, "currency": "USD", "exchangeRate": 1},
                {"accountCode": "4010", "creditAmount": 100, "currency": "USD", "exchangeRate": 0.5},
            ],
        },
    )
    assert inconsistent.status_code == 201, inconsistent.text

    posted = await client.post(
        f"/api/v1/journal-entries/{inconsistent.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 409, posted.text
    assert posted.json()["code"] == "JOURNAL_UNBALANCED"
    assert "base-currency" in posted.json()["message"]

    # One consistent rate balances both ways and posts.
    balanced = await client.post(
        "/api/v1/journal-entries",
        headers=headers,
        json={
            "entryDate": "2026-03-01",
            "postingDate": "2026-03-01",
            "description": "One rate",
            "lines": [
                {"accountCode": "1100", "debitAmount": 100, "currency": "USD", "exchangeRate": 1},
                {"accountCode": "4010", "creditAmount": 100, "currency": "USD", "exchangeRate": 1},
            ],
        },
    )
    assert balanced.status_code == 201, balanced.text
    accepted = await client.post(
        f"/api/v1/journal-entries/{balanced.json()['data']['id']}/post", headers=headers, json={}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["status"] == "POSTED"


async def test_a_journal_stays_single_currency_by_design(client, session_factory, seeded):
    """A journal whose lines are in different currencies is refused.

    ``fn_validate_journal_post`` compares the own-currency sums, so the database
    itself requires a journal's lines to agree in their own amounts; the service
    keeps that rule so SQLite tests and PostgreSQL production agree. Multi-currency
    *documents* convert through their rate and post one journal per document, which
    is where the base-currency amounts come from.
    """
    headers = await login(client)
    response = await client.post(
        "/api/v1/journal-entries",
        headers=headers,
        json={
            "entryDate": "2026-03-01",
            "postingDate": "2026-03-01",
            "description": "Two currencies in one journal",
            "lines": [
                {"accountCode": "1100", "debitAmount": 100, "currency": "USD", "exchangeRate": 1},
                {"accountCode": "4010", "creditAmount": 400000, "currency": "KHR", "exchangeRate": 0.00025},
            ],
        },
    )
    assert response.status_code == 201, response.text

    posted = await client.post(
        f"/api/v1/journal-entries/{response.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 409, posted.text
    assert posted.json()["code"] == "JOURNAL_UNBALANCED"


async def test_an_allocation_reports_the_exchange_difference_it_realises(client, session_factory, seeded):
    """Requirement 13: the two sides are valued at the rates their documents were
    booked at, so a settlement realises an exchange gain or loss.

    The figures are the stored (rounded) base amounts, which is what the ledger
    holds: 1,000,000 KHR invoiced at 1 USD = 4000 KHR is 250.00 USD, the same
    amount received at 1 USD = 3333.33 KHR is 300.00 USD, so 50.00 USD of the
    receipt settles nothing and is the realised difference.
    """
    headers = await login(client)
    async with session_factory() as session:
        party_id = await _party(session)
    invoice = await _create(client, headers, _invoice(
        party_id,
        currency="KHR",
        exchangeRate=0.00025,
        lines=[{"description": "Freight", "quantity": 1, "unitPrice": 1000000}],
    ))
    receipt = await _create(client, headers, {
        "documentType": "CUSTOMER_RECEIPT",
        "date": "2026-03-05",
        "partyId": party_id,
        "currency": "KHR",
        "exchangeRate": 0.0003,
        "lines": [{"description": "Received", "quantity": 1, "unitPrice": 1000000}],
    })
    await _post(client, headers, invoice["id"])
    await _post(client, headers, receipt["id"])

    response = await client.post(
        f"/api/v1/financial-documents/{receipt['id']}/allocate",
        headers=headers,
        json={"target_document_id": int(invoice["id"]), "amount": 1000000, "allocated_currency_code": "KHR"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    assert data["paymentBaseAmount"] == pytest.approx(300.0)
    assert data["targetBaseAmount"] == pytest.approx(250.0)
    assert data["exchangeDifference"] == pytest.approx(50.0)

    # The same figures are visible from both documents, each naming the other side.
    from_receipt = (await _detail(client, headers, receipt["id"]))["allocations"][0]
    assert from_receipt["exchangeDifference"] == pytest.approx(50.0)
    assert from_receipt["paymentBaseAmount"] == pytest.approx(300.0)
    assert from_receipt["invoiceBaseAmount"] == pytest.approx(250.0)
    from_invoice = (await _detail(client, headers, invoice["id"]))["allocations"][0]
    assert from_invoice["exchangeDifference"] == pytest.approx(50.0)


async def test_an_invoice_generated_from_a_charge_keeps_the_currency_and_takes_its_own_rate(
    client, session_factory, seeded
):
    """Requirement 12: the source keeps its currency, the invoice resolves its rate."""
    headers = await login(client)
    await _rate(client, headers, "USD", "KHR", 4000)

    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Multi Currency Customer",
            "direction": "Import",
            "currency": "KHR",
            "amount": 100,
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert quotation.status_code == 201, quotation.text
    revision_id = quotation.json()["data"]["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})).status_code == 200
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    service_order_id = converted.json()["data"]["serviceOrderId"]

    charge = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "KHR",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert charge.status_code == 201, charge.text
    charge_id = charge.json()["data"]["id"]

    issued = await client.post(f"/api/v1/service-charges/{charge_id}/issue", headers=headers, json={})
    assert issued.status_code == 200, issued.text
    invoice_id = issued.json()["data"]["financialDocumentId"]
    invoice = await _detail(client, headers, invoice_id)

    assert invoice["currency"] == "KHR", "the invoice keeps the source currency"
    assert invoice["exchangeRate"] == pytest.approx(0.00025), "it applies its own approved rate"
    assert invoice["baseTotalAmount"] == pytest.approx(0.03)

    # The historical source still says exactly what it said before.
    source = await client.get(f"/api/v1/service-charges/{charge_id}", headers=headers)
    assert source.status_code == 200, source.text
    assert source.json()["data"]["currency"] == "KHR"
    assert source.json()["data"]["total"] == pytest.approx(100)
