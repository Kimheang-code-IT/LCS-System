"""Write APIs validate their payloads and answer with the standard envelope.

Every case here asserts three things at once: the HTTP status, the legacy
``field_errors`` map the existing form renderer reads, and the coded ``errors``
array newer clients consume. A test that only checked the status could pass
while the message pointed at the wrong input.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


def _codes(body: dict) -> dict[str, str]:
    return {item["field"]: item["code"] for item in body.get("errors", [])}


async def test_validation_envelope_names_every_required_field(client):
    headers = await login(client)
    response = await client.post("/api/v1/businessParties", headers=headers, json={})
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body["field_errors"]) == {"partyCode", "legalName"}
    codes = _codes(body)
    assert codes["partyCode"] == "REQUIRED"
    assert codes["legalName"] == "REQUIRED"


async def test_invalid_email_and_overlong_text_are_field_errors(client):
    headers = await login(client)
    bad_email = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "VAL-MAIL", "legalName": "Valid Mail Ltd.", "roles": ["Customer"], "email": "not-an-email"},
    )
    assert bad_email.status_code == 422, bad_email.text
    assert _codes(bad_email.json())["email"] == "INVALID_FORMAT"

    long_name = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "VAL-LONG", "legalName": "x" * 300, "roles": ["Customer"]},
    )
    assert long_name.status_code == 422, long_name.text
    assert _codes(long_name.json())["legalName"] == "TOO_LONG"


async def test_currency_code_must_have_three_letters(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/currencies", headers=headers, json={"code": "US", "name": "US Dollar"}
    )
    assert response.status_code == 422, response.text
    assert _codes(response.json())["code"] == "TOO_SHORT"


async def test_currency_rate_must_be_positive(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/currencyRates",
        headers=headers,
        json={
            "fromCurrencyCode": "USD",
            "toCurrencyCode": "KHR",
            "effectiveDate": "2026-01-01",
            "rate": 0,
            "status": "PENDING",
        },
    )
    assert response.status_code == 422, response.text
    assert _codes(response.json())["rate"] == "OUT_OF_RANGE"


async def test_duplicate_party_code_is_a_coded_field_error(client):
    headers = await login(client)
    payload = {"partyCode": "VAL-DUP", "legalName": "Duplicate Ltd.", "roles": ["Customer"]}
    created = await client.post("/api/v1/businessParties", headers=headers, json=payload)
    assert created.status_code == 201, created.text

    duplicate = await client.post(
        "/api/v1/businessParties", headers=headers, json={**payload, "legalName": "Another Ltd."}
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "partyCode" in duplicate.json()["field_errors"]
    assert _codes(duplicate.json())["partyCode"] == "DUPLICATE"


async def test_partial_update_keeps_unchanged_required_fields(client):
    headers = await login(client)
    created = (
        await client.post(
            "/api/v1/businessParties",
            headers=headers,
            json={"partyCode": "VAL-PATCH", "legalName": "Patch Ltd.", "roles": ["Customer"]},
        )
    ).json()["data"]

    updated = await client.put(
        f"/api/v1/businessParties/{created['id']}",
        headers=headers,
        json={"displayName": "Patched display"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["legalName"] == "Patch Ltd."
    assert updated.json()["data"]["partyCode"] == "VAL-PATCH"


async def test_chart_of_account_requires_a_name_and_refuses_a_duplicate_code(client):
    headers = await login(client)
    missing = await client.post(
        "/api/v1/chart-of-accounts",
        headers=headers,
        json={"accountCode": "VAL-1000", "accountType": "ASSET", "normalBalance": "DEBIT"},
    )
    assert missing.status_code == 422, missing.text
    assert _codes(missing.json())["accountName"] == "REQUIRED"

    payload = {
        "accountCode": "VAL-2000",
        "accountName": "Validation Account",
        "accountType": "ASSET",
        "normalBalance": "DEBIT",
    }
    assert (await client.post("/api/v1/chart-of-accounts", headers=headers, json=payload)).status_code == 201
    duplicate = await client.post("/api/v1/chart-of-accounts", headers=headers, json=payload)
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_ACCOUNT_CODE"
    assert "accountCode" in duplicate.json()["field_errors"]


async def test_financial_account_requires_a_ledger_and_refuses_a_second_link(client):
    headers = await login(client)
    missing = await client.post(
        "/api/v1/financial-accounts", headers=headers, json={"accountName": "No ledger"}
    )
    assert missing.status_code == 422, missing.text
    assert _codes(missing.json())["ledgerCode"] == "REQUIRED"

    ledger = await client.post(
        "/api/v1/chart-of-accounts",
        headers=headers,
        json={
            "accountCode": "VAL-FIN-1",
            "accountName": "Validation Settlement Ledger",
            "accountType": "ASSET",
            "normalBalance": "DEBIT",
        },
    )
    assert ledger.status_code == 201, ledger.text

    created = await client.post(
        "/api/v1/financial-accounts",
        headers=headers,
        json={"ledgerCode": "VAL-FIN-1", "accountName": "Validation Cash", "accountType": "Cash", "currency": "USD"},
    )
    assert created.status_code == 201, created.text

    duplicate = await client.post(
        "/api/v1/financial-accounts",
        headers=headers,
        json={"ledgerCode": "VAL-FIN-1", "accountName": "Another Cash", "currency": "USD"},
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_LEDGER_ACCOUNT"


async def _party_id(client, headers) -> str:
    parties = (await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})).json()["data"]["items"]
    return parties[0]["id"]


async def test_document_lines_are_validated_on_the_cell(client):
    headers = await login(client)
    party_id = await _party_id(client, headers)
    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "lines": [{"description": "Freight", "quantity": 0, "unitAmount": 100}],
        },
    )
    assert response.status_code == 422, response.text
    assert "lines.0.quantity" in response.json()["field_errors"]
    assert _codes(response.json())["lines.0.quantity"] == "OUT_OF_RANGE"

    precise = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "lines": [{"description": "Freight", "quantity": 1, "unitAmount": "10.12345"}],
        },
    )
    assert precise.status_code == 422, precise.text
    assert "decimal places" in precise.json()["field_errors"]["lines.0.unitPrice"]
    assert _codes(precise.json())["lines.0.unitPrice"] == "INVALID_PRECISION"


async def test_client_amount_is_ignored_and_unit_amount_tax_amount_are_accepted(client):
    headers = await login(client)
    party_id = await _party_id(client, headers)
    created = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "lines": [
                {
                    "description": "Freight",
                    "quantity": 1,
                    "unitAmount": 100,
                    "taxAmount": 10,
                    # A manipulated total must not change what the server stores.
                    "amount": 9999,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert float(body["total"]) == pytest.approx(110.0)
    assert float(body["tax"]) == pytest.approx(10.0)
    line = body["lines"][0]
    assert float(line["unitPrice"]) == pytest.approx(100.0)
    assert float(line["unitAmount"]) == pytest.approx(100.0)


async def _service_order_job_no(client, headers) -> str:
    party = (
        await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})
    ).json()["data"]["items"][0]
    order = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"customer": party["legalName"], "direction": "Import", "currency": "USD"},
    )
    assert order.status_code == 201, order.text
    return order.json()["data"]["jobNo"]


async def test_movement_and_milestone_values_are_refused_on_their_cell(client):
    headers = await login(client)
    job_no = await _service_order_job_no(client, headers)

    bad_sequence = await client.post(
        f"/api/v1/service-orders/{job_no}/movements",
        headers=headers,
        json={"sequenceNo": "abc", "status": "PLANNED"},
    )
    assert bad_sequence.status_code == 422, bad_sequence.text
    assert "sequenceNo" in bad_sequence.json()["field_errors"]

    bad_time = await client.post(
        f"/api/v1/service-orders/{job_no}/movements",
        headers=headers,
        json={"plannedDeparture": "not-a-timestamp", "status": "PLANNED"},
    )
    assert bad_time.status_code == 422, bad_time.text
    assert "plannedDeparture" in bad_time.json()["field_errors"]

    bad_milestone = await client.post(
        f"/api/v1/service-orders/{job_no}/milestones",
        headers=headers,
        json={"milestoneCode": "BOOKED", "sequenceNo": "first"},
    )
    assert bad_milestone.status_code == 422, bad_milestone.text
    assert "sequenceNo" in bad_milestone.json()["field_errors"]


async def test_service_charge_accepts_fee_lines_with_their_tax_amount(client):
    headers = await login(client)
    job_no = await _service_order_job_no(client, headers)

    charge = await client.post(
        "/api/v1/service-charges",
        headers=headers,
        json={
            "jobNo": job_no,
            "documentType": "SERVICE_NOTE",
            "feeLines": [
                {"description": "Freight", "quantity": 1, "unitAmount": 100, "taxAmount": 10},
            ],
        },
    )
    assert charge.status_code == 201, charge.text
    body = charge.json()["data"]
    assert float(body["total"]) == pytest.approx(110.0)
    assert float(body["feeLines"][0]["unitAmount"]) == pytest.approx(100.0)
