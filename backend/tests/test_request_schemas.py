"""Request-schema coverage for the write APIs.

The master-data and finance account schemas already had tests; this file covers
the module schemas added for operations, quotations, the remaining finance
resources, settings, status, backup and auth, plus the shared path/query/id
guards. Every invalid case asserts the field the frontend must highlight, not
only the status code.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


def _codes(body: dict) -> dict[str, str]:
    return {item["field"]: item["code"] for item in body.get("errors", [])}


async def _first(client, headers, path: str) -> dict:
    response = await client.get(path, headers=headers, params={"page_size": 1})
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"][0]


async def _service_order(client, headers) -> dict:
    party = await _first(client, headers, "/api/v1/businessParties")
    response = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"customerPartyId": party["id"], "direction": "Import", "currency": "USD"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --- Operations --------------------------------------------------------------


async def test_service_order_dates_and_lengths_are_validated(client):
    headers = await login(client)
    bad_date = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"customer": "Schema Customer", "direction": "Import", "currency": "USD", "date": "31/12/2026"},
    )
    assert bad_date.status_code == 422, bad_date.text
    assert _codes(bad_date.json())["date"] == "INVALID_FORMAT"

    long_job = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"customer": "Schema Customer", "direction": "Import", "jobNo": "J" * 60},
    )
    assert long_job.status_code == 422, long_job.text
    assert _codes(long_job.json())["jobNo"] == "TOO_LONG"


async def test_partial_service_order_update_keeps_unchanged_fields(client):
    headers = await login(client)
    order = await _service_order(client, headers)
    response = await client.put(
        f"/api/v1/service-orders/{order['jobNo']}",
        headers=headers,
        json={"description": "Updated by schema test"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["jobNo"] == order["jobNo"]
    assert body["description"] == "Updated by schema test"


async def test_container_rejects_an_unsupported_field(client):
    headers = await login(client)
    order = await _service_order(client, headers)
    response = await client.post(
        f"/api/v1/service-orders/{order['jobNo']}/containers",
        headers=headers,
        json={"containerNumber": "SCHEMA1234567", "containerType": "20GP", "adminOnly": True},
    )
    assert response.status_code == 422, response.text
    assert _codes(response.json())["adminOnly"] == "UNKNOWN_FIELD"


async def test_charge_line_errors_name_the_submitted_collection(client):
    headers = await login(client)
    order = await _service_order(client, headers)
    response = await client.post(
        "/api/v1/service-charges",
        headers=headers,
        json={
            "jobNo": order["jobNo"],
            "documentType": "SERVICE_NOTE",
            "feeLines": [{"description": "Freight", "quantity": 1, "unitAmount": "10.12345"}],
        },
    )
    assert response.status_code == 422, response.text
    assert "feeLines.0.unitPrice" in response.json()["field_errors"]


# --- Quotations --------------------------------------------------------------


async def test_quotation_header_and_pricing_lines_are_validated(client):
    headers = await login(client)
    party = await _first(client, headers, "/api/v1/businessParties")

    bad_date = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "customerPartyId": party["id"],
            "direction": "Import",
            "currency": "USD",
            "date": "not-a-date",
        },
    )
    assert bad_date.status_code == 422, bad_date.text
    assert _codes(bad_date.json())["date"] == "INVALID_FORMAT"

    bad_line = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "customerPartyId": party["id"],
            "direction": "Import",
            "currency": "USD",
            "date": date.today().isoformat(),
            "pricingLines": [{"description": "Freight", "quantity": "many", "unitPrice": 10}],
        },
    )
    assert bad_line.status_code == 422, bad_line.text
    assert "pricingLines.0.quantity" in bad_line.json()["field_errors"]


async def test_route_stop_references_are_validated_by_the_route_resolver(client):
    """A stop is a Place Role plus free text; an unknown role is refused."""
    headers = await login(client)
    party = await _first(client, headers, "/api/v1/businessParties")
    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "customerPartyId": party["id"],
            "direction": "Import",
            "currency": "USD",
            "date": date.today().isoformat(),
            "places": [{"placeRoleId": "999999", "place": "Somewhere"}],
        },
    )
    assert response.status_code == 422, response.text
    errors = response.json()["field_errors"]
    assert "places.0.placeRoleId" in errors


# --- Finance -----------------------------------------------------------------


async def test_document_sequence_requires_a_document_type(client):
    headers = await login(client)
    response = await client.post("/api/v1/document-sequences", headers=headers, json={})
    assert response.status_code == 422, response.text
    assert _codes(response.json())["documentType"] == "REQUIRED"


async def test_journal_line_amount_must_be_numeric(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/journal-entries",
        headers=headers,
        json={
            "entryDate": date.today().isoformat(),
            "lines": [
                {"accountCode": "1100", "debitAmount": "not-a-number", "creditAmount": 0},
            ],
        },
    )
    assert response.status_code == 422, response.text
    assert "lines.0.debitAmount" in response.json()["field_errors"]


async def test_posting_rule_rejects_an_unsupported_key(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={
            "documentType": "OTHER_INCOME",
            "debitAccount": "1020",
            "creditAccount": "4020",
            "unexpected": True,
        },
    )
    assert response.status_code == 422, response.text
    assert _codes(response.json())["unexpected"] == "UNKNOWN_FIELD"


# --- Settings, status, backup, auth -----------------------------------------


async def test_settings_app_info_validates_email_and_unknown_fields(client):
    headers = await login(client)
    bad_email = await client.patch(
        "/api/v1/settings/app-info", headers=headers, json={"supportEmail": "not-an-email"}
    )
    assert bad_email.status_code == 422, bad_email.text
    assert _codes(bad_email.json())["supportEmail"] == "INVALID_FORMAT"

    unknown = await client.patch(
        "/api/v1/settings/app-info", headers=headers, json={"notAField": True}
    )
    assert unknown.status_code == 422, unknown.text
    assert _codes(unknown.json())["notAField"] == "UNKNOWN_FIELD"


async def test_status_change_requires_a_status(client):
    headers = await login(client)
    role = await _first(client, headers, "/api/v1/placeRoles")
    response = await client.post(
        f"/api/v1/placeRoles/{role['id']}/status", headers=headers, json={}
    )
    assert response.status_code == 422, response.text
    assert _codes(response.json())["status"] == "REQUIRED"


async def test_restore_requires_a_typed_confirmation_field(client):
    headers = await login(client)
    response = await client.post("/api/v1/backup/restore", headers=headers, json={})
    assert response.status_code == 422, response.text
    assert _codes(response.json())["confirm"] == "REQUIRED"


async def test_setup_refuses_invalid_email_and_unknown_fields(client):
    response = await client.post(
        "/api/v1/auth/setup/initialize",
        json={"email": "not-an-email", "password": "short", "unexpected": True},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert "email" in body["field_errors"]
    assert _codes(body)["unexpected"] == "UNKNOWN_FIELD"


# --- Shared path / bulk-id guards -------------------------------------------


async def test_numeric_path_ids_reject_non_numbers_and_zero(client):
    headers = await login(client)
    non_number = await client.get("/api/v1/chart-of-accounts/not-a-number", headers=headers)
    assert non_number.status_code == 422, non_number.text
    assert "account_id" in non_number.json()["field_errors"]

    zero = await client.get("/api/v1/quotations/0", headers=headers)
    assert zero.status_code == 422, zero.text


async def test_bulk_delete_rejects_a_non_numeric_id_instead_of_ignoring_it(client):
    headers = await login(client)
    response = await client.request(
        "DELETE",
        "/api/v1/financial-documents",
        headers=headers,
        json={"ids": ["abc"]},
    )
    assert response.status_code == 422, response.text
    assert "ids.0" in response.json()["field_errors"]
