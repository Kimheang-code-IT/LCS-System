"""Service charge line amounts must survive the round trip.

The charge line editor exposes the tax **rate** under the `taxRate` key, while the
API serializer emitted it under `tax`. ``save_charge`` read only `tax`, so the rate
a user typed was silently discarded: the server stored zero tax while the form
showed a taxed total, and the invoice created from the charge carried no tax at
all. Both keys are now accepted, with the error reported against the key the client
actually sent.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _service_order(client, headers) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Charge Tax Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": 500,
        },
    )
    assert quotation.status_code == 201, quotation.text
    revision_id = quotation.json()["data"]["revisionId"]
    assert (
        await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    ).status_code == 200
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    return converted.json()["data"]["serviceOrderId"]


async def _create_charge(client, headers, order_id: str, line: dict) -> dict:
    response = await client.post(
        f"/api/v1/service-orders/{order_id}/charges",
        headers=headers,
        json={"documentDate": date.today().isoformat(), "currency": "USD", "lines": [line]},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_tax_rate_supplied_as_taxRate_is_stored(client):
    """The key the charge line editor writes must be honoured."""
    headers = await login(client)
    order_id = await _service_order(client, headers)

    charge = await _create_charge(
        client,
        headers,
        order_id,
        {"description": "Freight", "quantity": 2, "unitPrice": 100, "taxRate": 10},
    )

    assert charge["subtotal"] == 200.0, charge
    assert charge["tax"] == 20.0, f"10% of 200 must be stored as tax, got {charge['tax']}"
    assert charge["total"] == 220.0, charge


async def test_tax_rate_supplied_as_tax_still_works(client):
    """Backward compatibility: the older key keeps working."""
    headers = await login(client)
    order_id = await _service_order(client, headers)

    charge = await _create_charge(
        client,
        headers,
        order_id,
        {"description": "Freight", "quantity": 2, "unitPrice": 100, "tax": 10},
    )

    assert charge["tax"] == 20.0, charge
    assert charge["total"] == 220.0, charge


async def test_taxRate_wins_when_both_keys_are_present(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    charge = await _create_charge(
        client,
        headers,
        order_id,
        {"description": "Freight", "quantity": 2, "unitPrice": 100, "taxRate": 5, "tax": 50},
    )

    assert charge["tax"] == 10.0, f"the explicit taxRate must win, got {charge['tax']}"
    assert charge["total"] == 210.0, charge


async def test_saved_charge_round_trips_the_tax_rate(client):
    """Re-reading a charge must return the rate under the key the editor reads."""
    headers = await login(client)
    order_id = await _service_order(client, headers)

    charge = await _create_charge(
        client,
        headers,
        order_id,
        {"description": "Freight", "quantity": 1, "unitPrice": 300, "taxRate": 7.5},
    )

    fetched = await client.get(f"/api/v1/service-charges/{charge['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()["data"]
    line = body["feeLines"][0]

    assert line["tax"] == 7.5, f"the rate must round-trip, got {line['tax']}"
    assert line["taxAmount"] == 22.5, f"7.5% of 300 is 22.5, got {line['taxAmount']}"


async def test_an_out_of_range_tax_rate_is_rejected_on_the_key_that_was_sent(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    rejected = await client.post(
        f"/api/v1/service-orders/{order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100, "taxRate": 250}],
        },
    )
    assert rejected.status_code == 422, rejected.text
    assert "lines.0.taxRate" in rejected.json()["field_errors"], rejected.json()["field_errors"]


async def test_issued_charge_invoice_carries_the_tax(client):
    """The defect reached finance: the invoice must include the tax the user saw."""
    headers = await login(client)
    order_id = await _service_order(client, headers)

    charge = await _create_charge(
        client,
        headers,
        order_id,
        {"description": "Freight", "quantity": 1, "unitPrice": 200, "taxRate": 10},
    )
    issued = await client.post(
        f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={}
    )
    assert issued.status_code == 200, issued.text

    invoice_id = issued.json()["data"]["financialDocumentId"]
    invoice = await client.get(f"/api/v1/financial-documents/{invoice_id}", headers=headers)
    assert invoice.status_code == 200, invoice.text
    body = invoice.json()["data"]

    assert body["subtotal"] == 200.0, body
    assert body["tax"] == 20.0, f"the invoice must carry the charge tax, got {body['tax']}"
    assert body["total"] == 220.0, body
