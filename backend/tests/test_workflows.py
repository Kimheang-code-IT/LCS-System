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

    duplicate = await client.post(
        f"/api/v1/service-orders/{service_order_id}/containers",
        headers=headers,
        json={"containerTypeId": 1, "containerNumber": "MSCU1234567"},
    )
    assert duplicate.status_code == 409

    # Component tabs are configured per trade direction; the seed assigns the
    # Customs tab (a table-mode group) to both IMPORT and EXPORT.
    tabs = await client.get(f"/api/v1/service-orders/{service_order_id}/component-tabs", headers=headers)
    assert tabs.status_code == 200, tabs.text
    tab_items = tabs.json()["data"]["tabs"]
    assert any(tab["code"] == "CUSTOMS" for tab in tab_items)
    customs = next(tab for tab in tab_items if tab["code"] == "CUSTOMS")
    group = customs["groups"][0]
    assert group["code"] == "CUSTOMS"
    assert group["renderMode"] == "table"
    assert {attribute["code"] for attribute in group["attributes"]} >= {
        "declaration_no",
        "clearance_date",
        "duty_amount",
    }

    rows_url = f"/api/v1/service-orders/{service_order_id}/component-tabs/groups/{group['id']}/rows/bulk"

    missing = await client.post(rows_url, headers=headers, json={"rows": [{"values": {"clearance_date": "2026-09-15"}}]})
    assert missing.status_code == 422, missing.text
    assert "1.declaration_no" in missing.json()["field_errors"]

    saved = await client.post(
        rows_url,
        headers=headers,
        json={"rows": [{"values": {"declaration_no": "DEC-001", "clearance_date": "2026-09-15", "duty_amount": 120}}]},
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["data"]["items"]) == 1

    refreshed = await client.get(f"/api/v1/service-orders/{service_order_id}/component-tabs", headers=headers)
    customs_after = next(tab for tab in refreshed.json()["data"]["tabs"] if tab["code"] == "CUSTOMS")
    assert len(customs_after["groups"][0]["rows"]) == 1


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


async def test_service_order_single_invoice_from_charges(client):
    headers = await login(client)
    service_order_id = await test_quotation_lifecycle_and_conversion(client)

    first = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={
            "documentType": "SERVICE_NOTE",
            "documentDate": "2026-09-15",
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["feeLines"][0]["description"] == "Freight"
    assert first.json()["data"]["total"] == 100

    second = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={"lines": [{"description": "Documentation", "quantity": 2, "unitPrice": 25}]},
    )
    assert second.status_code == 201, second.text

    listed = await client.get(f"/api/v1/service-orders/{service_order_id}/charges", headers=headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()["data"]) == 2

    invoice = await client.post(f"/api/v1/service-orders/{service_order_id}/invoice", headers=headers)
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["data"]["id"]
    assert invoice.json()["data"]["total"] == 150

    # Only one invoice per service order: a second call returns the same document.
    again = await client.post(f"/api/v1/service-orders/{service_order_id}/invoice", headers=headers)
    assert again.status_code == 201, again.text
    assert again.json()["data"]["id"] == invoice_id

    fetched = await client.get(f"/api/v1/service-orders/{service_order_id}/invoice", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"]["id"] == invoice_id

    listed_after = await client.get(f"/api/v1/service-orders/{service_order_id}/charges", headers=headers)
    assert all(row["financialDocumentId"] == invoice_id for row in listed_after.json()["data"])


async def test_service_order_finish(client):
    headers = await login(client)
    service_order_id = await test_quotation_lifecycle_and_conversion(client)

    finished = await client.post(f"/api/v1/service-orders/{service_order_id}/finish", headers=headers)
    assert finished.status_code == 200, finished.text
    assert finished.json()["data"]["status"] == "Finished"
    assert finished.json()["data"]["rawStatus"] == "FINISHED"

    again = await client.post(f"/api/v1/service-orders/{service_order_id}/finish", headers=headers)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["status"] == "Finished"


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


async def test_user_create_exposes_role_and_normalizes_status(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/users",
        headers=headers,
        # The UI posts camelCase keys, an explicit auto-generated user code and a
        # display-case status.
        json={
            "username": "new.user",
            "displayName": "New User",
            "email": "new.user@example.com",
            "userCode": "NEW-USER",
            "role": "AUDITOR",
            "status": "Active",
            "password": "Passw0rd!",
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["userCode"] == "NEW-USER"
    assert data["role"] == "AUDITOR"
    assert data["status"] == "ACTIVE"

    detail = await client.get(f"/api/v1/users/{data['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["role"] == "AUDITOR"

    updated = await client.put(
        f"/api/v1/users/{data['id']}", headers=headers, json={"role": "SALES_OFFICER"}
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["role"] == "SALES_OFFICER"

    # A display-case status must not block authentication.
    relogin = await client.post("/api/v1/auth/login", json={"username": "new.user", "password": "Passw0rd!"})
    assert relogin.status_code == 200, relogin.text


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
