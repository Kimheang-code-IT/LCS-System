from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_login_rejects_bad_password(client):
    response = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


async def test_login_returns_user_and_permissions(client):
    response = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Passw0rd!"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["email"] == "admin@example.test"
    assert data["access_token"]


async def test_business_party_roles(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={
            "partyCode": "SUP-100",
            "legalName": "Global Carriers Ltd",
            "roles": ["Carrier", "Supplier"],
            "phone": "012345678",
            "country": "KH",
        },
    )
    assert response.status_code == 201, response.text
    party = response.json()["data"]
    assert set(party["roles"]) == {"Carrier", "Supplier"}

    listed = await client.get("/api/v1/businessParties", headers=headers, params={"q": "Global"})
    assert listed.status_code == 200
    assert listed.json()["data"]["meta"]["total"] >= 1


async def test_permissions_are_enforced(client):
    ops_headers = await login(client, "ops.pp")
    response = await client.get("/api/v1/financial-documents", headers=ops_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"


async def test_quotation_lifecycle_and_conversion(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Unit Test Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": 1500,
            "containerRequirements": [{"containerType": "40HC", "quantity": 1}],
            "pricingLines": [
                {"description": "Freight", "quantity": 1, "unitPrice": 1300},
                {"description": "Customs", "quantity": 1, "unitPrice": 200},
            ],
        },
    )
    assert created.status_code == 201, created.text
    quotation = created.json()["data"]
    assert quotation["quotationNo"].startswith("Q")
    revision_id = quotation["revisionId"]

    sent = await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    assert sent.status_code == 200
    assert sent.json()["data"]["revisionStatus"] == "SENT"

    accepted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    assert accepted.status_code == 200
    assert accepted.json()["data"]["revisionStatus"] == "ACCEPTED"

    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    service_order_id = converted.json()["data"]["serviceOrderId"]
    assert service_order_id

    second = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert second.status_code == 409

    return service_order_id


async def test_service_order_components_and_containers(client):
    headers = await login(client)
    service_order_id = await test_quotation_lifecycle_and_conversion(client)

    container = await client.post(
        f"/api/v1/service-orders/{service_order_id}/containers",
        headers=headers,
        json={"containerTypeId": 1, "containerNumber": "MSCU1234567", "grossWeightKg": 20000},
    )
    assert container.status_code == 201, container.text
    assert container.json()["data"]["containerNumber"] == "MSCU1234567"

    # Components created from the trade-direction config on conversion are listable.
    converted_components = await client.get("/api/v1/service-order-components", headers=headers)
    assert converted_components.status_code == 200, converted_components.text
    converted_items = converted_components.json()["data"]["items"]
    assert any(item["groupCode"] == "CUSTOMS" and item["jobNo"] for item in converted_items)

    duplicate = await client.post(
        f"/api/v1/service-orders/{service_order_id}/containers",
        headers=headers,
        json={"containerTypeId": 1, "containerNumber": "MSCU1234567"},
    )
    assert duplicate.status_code == 409

    component = await client.post(
        f"/api/v1/service-orders/{service_order_id}/components",
        headers=headers,
        json={"templateCode": "CUSTOMS_CLEARANCE", "groupCode": "CUSTOMS", "required": True},
    )
    assert component.status_code == 201, component.text
    component_id = component.json()["data"]["id"]
    assert component.json()["data"]["groupCode"] == "CUSTOMS"
    assert component.json()["data"]["jobNo"]

    listed_components = await client.get("/api/v1/service-order-components", headers=headers, params={"page_size": 200})
    assert listed_components.status_code == 200, listed_components.text
    listed_items = listed_components.json()["data"]["items"]
    assert any(item["id"] == component_id and item["groupCode"] == "CUSTOMS" for item in listed_items)

    values = await client.put(
        f"/api/v1/service-order-components/{component_id}/values",
        headers=headers,
        json={"values": [{"code": "declaration_no", "value_text": "DEC-001"}]},
    )
    assert values.status_code == 200, values.text
    assert values.json()["data"]["values"][0]["value_text"] == "DEC-001"

    completed = await client.post(f"/api/v1/service-order-components/{component_id}/complete", headers=headers, json={})
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "COMPLETED"


async def _create_and_post_invoice(client, headers, service_order_id: str, amount: float = 1500.0) -> dict:
    charge = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={
            "documentType": "SERVICE_NOTE",
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert charge.status_code == 201, charge.text
    charge_id = charge.json()["data"]["id"]

    issued = await client.post(f"/api/v1/service-charges/{charge_id}/issue", headers=headers, json={})
    assert issued.status_code == 200

    invoice = await client.post(f"/api/v1/service-charges/{charge_id}/create-finance-invoice", headers=headers, json={})
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["data"]["id"]

    posted = await client.post(f"/api/v1/financial-documents/{invoice_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] == "Posted"
    return posted.json()["data"]


async def test_service_charge_to_invoice_and_posting(client):
    headers = await login(client)
    service_order_id = await test_quotation_lifecycle_and_conversion(client)
    document = await _create_and_post_invoice(client, headers, service_order_id)

    journals = await client.get("/api/v1/journal-entries", headers=headers)
    assert journals.status_code == 200
    items = journals.json()["data"]["items"]
    assert items
    for entry in items:
        assert entry["debitTotal"] == entry["creditTotal"]
    return document


async def test_payment_allocation_and_receivables(client):
    headers = await login(client)
    invoice = await test_service_charge_to_invoice_and_posting(client)

    receipt = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_RECEIPT",
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "partyId": invoice["partyId"],
            "lines": [{"description": "Payment", "quantity": 1, "unitPrice": 500}],
        },
    )
    assert receipt.status_code == 201, receipt.text
    receipt_id = receipt.json()["data"]["id"]

    posted = await client.post(f"/api/v1/financial-documents/{receipt_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    allocation = await client.post(
        f"/api/v1/financial-documents/{receipt_id}/allocate",
        headers=headers,
        json={"target_document_id": int(invoice["id"]), "amount": 500, "allocated_currency_code": "USD"},
    )
    assert allocation.status_code == 200, allocation.text
    assert allocation.json()["data"]["allocatedAmount"] == 500

    over = await client.post(
        f"/api/v1/financial-documents/{receipt_id}/allocate",
        headers=headers,
        json={"target_document_id": int(invoice["id"]), "amount": 999999, "allocated_currency_code": "USD"},
    )
    assert over.status_code == 409

    receivables = await client.get("/api/v1/reports/receivables", headers=headers)
    assert receivables.status_code == 200
    rows = receivables.json()["data"]
    assert any(row["balance"] == pytest.approx(1000.0) for row in rows)


async def test_document_reversal(client):
    headers = await login(client)
    invoice = await test_service_charge_to_invoice_and_posting(client)
    reversal = await client.post(
        f"/api/v1/financial-documents/{invoice['id']}/reverse",
        headers=headers,
        json={"reason": "Customer dispute"},
    )
    assert reversal.status_code == 201, reversal.text
    assert reversal.json()["data"]["status"] == "Reversed"

    journals = await client.get("/api/v1/journal-entries", headers=headers)
    entries = journals.json()["data"]["items"]
    assert any(entry["entryType"] == "REVERSAL" for entry in entries)
    for entry in entries:
        assert entry["debitTotal"] == entry["creditTotal"]


async def test_dynamic_service_order_tabs_workflow(client):
    headers = await login(client)
    service_order_id = await test_quotation_lifecycle_and_conversion(client)

    bootstrap = await client.get(f"/api/v1/service-orders/{service_order_id}/dynamic-tabs", headers=headers)
    assert bootstrap.status_code == 200, bootstrap.text
    data = bootstrap.json()["data"]
    tabs = {tab["code"]: tab for tab in data["tabs"]}
    for code in ("invoice", "packing-list", "shipment-registration", "bill", "customs", "transport"):
        assert code in tabs, code
    invoice = tabs["invoice"]
    invoice_tab_id = invoice["id"]
    assert {column["fieldKey"] for column in invoice["columns"]} >= {"invoice_no", "invoice_date", "seller", "status"}
    assert "business_party" in data["references"]

    rows_url = f"/api/v1/service-orders/{service_order_id}/dynamic-tabs/{invoice_tab_id}/rows"

    missing = await client.post(rows_url, headers=headers, json={"values": {"invoice_date": "2026-09-15"}})
    assert missing.status_code == 422
    assert "invoice_no" in missing.json()["field_errors"]

    bad_date = await client.post(
        rows_url, headers=headers, json={"values": {"invoice_no": "INV-001", "invoice_date": "not-a-date"}}
    )
    assert bad_date.status_code == 422
    assert "invoice_date" in bad_date.json()["field_errors"]

    bad_amount = await client.post(
        rows_url,
        headers=headers,
        json={"values": {"invoice_no": "INV-001", "invoice_date": "2026-09-15", "invoice_amount": "abc"}},
    )
    assert bad_amount.status_code == 422
    assert "invoice_amount" in bad_amount.json()["field_errors"]

    bad_select = await client.post(
        rows_url,
        headers=headers,
        json={"values": {"invoice_no": "INV-001", "invoice_date": "2026-09-15", "status": "Bogus"}},
    )
    assert bad_select.status_code == 422
    assert "status" in bad_select.json()["field_errors"]

    created = await client.post(
        rows_url,
        headers=headers,
        json={"values": {"invoice_no": "INV-001", "invoice_date": "2026-09-15", "invoice_amount": 500, "status": "Paid"}},
    )
    assert created.status_code == 201, created.text
    row_id = created.json()["data"]["id"]

    bulk = await client.post(
        rows_url.replace("/rows", "/rows/bulk"),
        headers=headers,
        json={
            "rows": [
                {"id": row_id, "values": {"invoice_no": "INV-001", "invoice_date": "2026-09-15", "status": "Paid"}},
                {"values": {"invoice_no": "INV-002", "invoice_date": "2026-09-16", "invoice_amount": 700, "status": "Pending"}},
            ]
        },
    )
    assert bulk.status_code == 200, bulk.text
    assert len(bulk.json()["data"]["items"]) == 2

    refreshed = await client.get(f"/api/v1/service-orders/{service_order_id}/dynamic-tabs", headers=headers)
    invoice_after = next(tab for tab in refreshed.json()["data"]["tabs"] if tab["code"] == "invoice")
    assert len(invoice_after["rows"]) == 2

    # --- Configuration workflow: add a new tab + columns ------------------
    tab = await client.post(
        "/api/v1/service-order-tabs", headers=headers, json={"code": "inspection", "name": "Inspection", "sortOrder": 70}
    )
    assert tab.status_code == 201, tab.text
    inspection_tab_id = tab.json()["data"]["id"]

    required_column = await client.post(
        f"/api/v1/service-order-tabs/{inspection_tab_id}/columns",
        headers=headers,
        json={"fieldKey": "inspection_no", "label": "Inspection No.", "fieldType": "text", "isRequired": True},
    )
    assert required_column.status_code == 201, required_column.text
    required_column_id = required_column.json()["data"]["id"]
    status_column = await client.post(
        f"/api/v1/service-order-tabs/{inspection_tab_id}/columns",
        headers=headers,
        json={"fieldKey": "status", "label": "Status", "fieldType": "select", "options": ["Pending", "Passed", "Failed"]},
    )
    status_column_id = status_column.json()["data"]["id"]

    activated = await client.get(f"/api/v1/service-orders/{service_order_id}/dynamic-tabs", headers=headers)
    assert any(entry["code"] == "inspection" for entry in activated.json()["data"]["tabs"])

    inspection_rows_url = f"/api/v1/service-orders/{service_order_id}/dynamic-tabs/{inspection_tab_id}/rows"
    first = await client.post(
        inspection_rows_url, headers=headers, json={"values": {"inspection_no": "INS-1", "status": "Passed"}}
    )
    assert first.status_code == 201, first.text

    bad_option = await client.post(
        inspection_rows_url, headers=headers, json={"values": {"inspection_no": "INS-2", "status": "Nope"}}
    )
    assert bad_option.status_code == 422

    disabled = await client.patch(
        f"/api/v1/service-order-columns/{status_column_id}", headers=headers, json={"isActive": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["isActive"] is False

    archived_column = await client.delete(f"/api/v1/service-order-columns/{required_column_id}", headers=headers)
    assert archived_column.status_code == 200
    assert archived_column.json()["data"]["archived"] is True

    unused_column = await client.post(
        f"/api/v1/service-order-tabs/{inspection_tab_id}/columns",
        headers=headers,
        json={"fieldKey": "temp_field", "label": "Temp"},
    )
    hard_deleted_column = await client.delete(
        f"/api/v1/service-order-columns/{unused_column.json()['data']['id']}", headers=headers
    )
    assert hard_deleted_column.json()["data"]["archived"] is False

    historical = await client.get(f"/api/v1/service-orders/{service_order_id}/dynamic-tabs", headers=headers)
    inspection_entry = next(tab for tab in historical.json()["data"]["tabs"] if tab["code"] == "inspection")
    assert len(inspection_entry["rows"]) == 1
    assert inspection_entry["rows"][0]["values"].get("inspection_no") == "INS-1"

    archived_tab = await client.delete(f"/api/v1/service-order-tabs/{inspection_tab_id}", headers=headers)
    assert archived_tab.json()["data"]["archived"] is True

    unused_tab = await client.post(
        "/api/v1/service-order-tabs", headers=headers, json={"code": "temp-tab", "name": "Temp Tab"}
    )
    hard_deleted_tab = await client.delete(
        f"/api/v1/service-order-tabs/{unused_tab.json()['data']['id']}", headers=headers
    )
    assert hard_deleted_tab.json()["data"]["archived"] is False


async def test_generic_records_encrypt_credentials(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/companies",
        headers=headers,
        json={"code": "C-100", "name": "ACME Factory", "credentialReference": "SuperSecret", "status": "Active"},
    )
    assert created.status_code == 201, created.text
    payload = created.json()["data"]
    assert payload["credentialReference"] == "********"

    fetched = await client.get(f"/api/v1/companies/{payload['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["data"]["credentialReference"] == "********"

    listed = await client.get("/api/v1/companies", headers=headers)
    assert listed.status_code == 200


async def test_consistency_guardrails(client):
    headers = await login(client)
    # A sent quotation revision cannot be mutated by creating a revision and editing in place.
    created = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={"date": date.today().isoformat(), "customer": "Immutable Customer", "direction": "Export"},
    )
    quotation = created.json()["data"]
    revision_id = quotation["revisionId"]
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})

    revised = await client.post(f"/api/v1/quotations/{quotation['id']}/revisions", headers=headers, json={})
    assert revised.status_code == 201
    assert revised.json()["data"]["revisionNo"] >= 2

    audit = await client.get("/api/v1/audit-events", headers=headers)
    assert audit.status_code == 200
    assert audit.json()["data"]["meta"]["total"] > 0
