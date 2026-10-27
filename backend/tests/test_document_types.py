"""The Document Types master: custom labels over canonical accounting behaviours.

Operators may add their own document types, but every row must resolve to one of
the canonical accounting behaviours before it can be used on a financial
document or a posting rule, so a new label can never invent a posting rule.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.modules.master_data.models import BusinessParty
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _create_type(client, headers, **extra) -> dict:
    payload = {
        "code": "TAX_INVOICE_CUSTOM",
        "name": "Tax Invoice (Custom)",
        "category": "FINANCE",
        "accountingBehavior": "CUSTOMER_INVOICE",
        "availableIn": ["financial_documents", "service_order_finance"],
        **extra,
    }
    response = await client.post("/api/v1/documentTypes", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_custom_type_roundtrips_and_resolves(client, session_factory):
    headers = await login(client)
    created = await _create_type(client, headers)
    fetched = await client.get(f"/api/v1/documentTypes/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["code"] == "TAX_INVOICE_CUSTOM"
    assert data["accountingBehavior"] == "CUSTOMER_INVOICE"
    assert data["availableIn"] == ["financial_documents", "service_order_finance"]
    assert data["status"] == "ACTIVE"


async def test_custom_type_must_reference_a_canonical_behaviour(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/documentTypes",
        headers=headers,
        json={
            "code": "MY_BEHAVIOUR",
            "name": "Invented Behaviour",
            "category": "FINANCE",
            "accountingBehavior": "MY_THING",
            "availableIn": ["financial_documents"],
        },
    )
    assert response.status_code == 422, response.text
    assert "accountingBehavior" in response.json()["field_errors"]


async def test_duplicate_active_code_is_a_field_error(client):
    headers = await login(client)
    await _create_type(client, headers)
    duplicate = await client.post(
        "/api/v1/documentTypes",
        headers=headers,
        json={
            "code": "TAX_INVOICE_CUSTOM",
            "name": "Second Tax Invoice",
            "category": "FINANCE",
            "accountingBehavior": "CUSTOMER_INVOICE",
            "availableIn": ["financial_documents"],
        },
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "code" in duplicate.json()["field_errors"]


async def test_canonical_row_is_immutable_and_undeletable(client):
    headers = await login(client)
    canonical = await _create_type(
        client,
        headers,
        code="CUSTOMER_INVOICE",
        name="Customer Invoice",
    )

    changed = await client.patch(
        f"/api/v1/documentTypes/{canonical['id']}",
        headers=headers,
        json={"accountingBehavior": "OTHER_INCOME"},
    )
    assert changed.status_code == 422, changed.text

    deactivated = await client.patch(
        f"/api/v1/documentTypes/{canonical['id']}", headers=headers, json={"status": "INACTIVE"}
    )
    assert deactivated.status_code == 200, deactivated.text
    deleted = await client.delete(f"/api/v1/documentTypes/{canonical['id']}", headers=headers)
    assert deleted.status_code == 409, deleted.text
    assert deleted.json()["code"] == "SYSTEM_DOCUMENT_TYPE"


async def test_financial_document_resolves_the_master_type(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party = (
            await session.execute(select(BusinessParty).where(BusinessParty.party_code == "CUST-001"))
        ).scalars().first()
    custom = await _create_type(client, headers)

    created = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentTypeId": custom["id"],
            "date": "2026-03-01",
            "partyId": int(party.id),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["documentType"] == "CUSTOMER_INVOICE"
    assert data["documentTypeId"] == str(custom["id"])
    assert data["documentTypeName"] == "Tax Invoice (Custom)"
    assert data["documentTypeCode"] == "TAX_INVOICE_CUSTOM"


async def test_inactive_type_is_refused_on_a_financial_document(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party = (
            await session.execute(select(BusinessParty).where(BusinessParty.party_code == "CUST-001"))
        ).scalars().first()
    custom = await _create_type(client, headers)
    deactivated = await client.patch(
        f"/api/v1/documentTypes/{custom['id']}", headers=headers, json={"status": "INACTIVE"}
    )
    assert deactivated.status_code == 200, deactivated.text

    created = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentTypeId": custom["id"],
            "date": "2026-03-01",
            "partyId": int(party.id),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert created.status_code == 422, created.text
    assert "documentTypeId" in created.json()["field_errors"]


async def test_operations_officer_can_view_but_not_manage(client):
    headers = await login(client, "ops.pp")
    listed = await client.get("/api/v1/documentTypes", headers=headers)
    assert listed.status_code == 200, listed.text
    created = await client.post(
        "/api/v1/documentTypes",
        headers=headers,
        json={
            "code": "NO_RIGHT",
            "name": "No Right",
            "category": "FINANCE",
            "accountingBehavior": "CUSTOMER_INVOICE",
            "availableIn": ["financial_documents"],
        },
    )
    assert created.status_code == 403, created.text
    assert created.json()["code"] == "ACCESS_DENIED"
