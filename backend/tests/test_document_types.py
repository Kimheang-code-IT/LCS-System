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


async def test_status_policy_toggles_a_document_type_with_an_audit_row(client, session_factory):
    """The row "..." menu's Activate/Deactivate runs through the shared endpoint.

    Deactivation is the only way to retire a type, so historical documents keep
    their reference and the financial guard still refuses new documents.
    """
    from app.modules.audit.models import AuditEvent

    headers = await login(client)
    created = await _create_type(client, headers, code="TOGGLE_TYPE")

    policy = (await client.get("/api/v1/documentTypes/status-policy", headers=headers)).json()["data"]
    assert [item["action"] for item in policy["transitions"]["ACTIVE"]] == ["deactivate"]

    off = await client.post(
        f"/api/v1/documentTypes/{created['id']}/status", headers=headers, json={"status": "INACTIVE"}
    )
    assert off.status_code == 200, off.text
    assert off.json()["data"]["status"] == "INACTIVE"
    listed = (await client.get("/api/v1/documentTypes?q=TOGGLE_TYPE", headers=headers)).json()["data"]["items"]
    assert [row["status"] for row in listed] == ["INACTIVE"]

    async with session_factory() as session:
        events = list(
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.entity_type == "documentTypes",
                        AuditEvent.entity_id == created["id"],
                    )
                )
            ).scalars().all()
        )
    assert [event.event_type for event in events] == ["STATUS_CHANGED"]
    assert events[0].action == "deactivate"

    on = await client.post(
        f"/api/v1/documentTypes/{created['id']}/status", headers=headers, json={"status": "ACTIVE"}
    )
    assert on.status_code == 200, on.text
    assert on.json()["data"]["status"] == "ACTIVE"


async def test_status_change_needs_the_manage_permission(client):
    headers = await login(client)
    created = await _create_type(client, headers, code="GUARDED_TYPE")
    viewer = await login(client, "ops.pp")

    # The policy is already filtered for the caller, so the menu offers nothing.
    policy = (await client.get("/api/v1/documentTypes/status-policy", headers=viewer)).json()["data"]
    assert policy["transitions"] == {}

    # Hiding the action is not the guard: the endpoint refuses the write too.
    refused = await client.post(
        f"/api/v1/documentTypes/{created['id']}/status", headers=viewer, json={"status": "INACTIVE"}
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "ACCESS_DENIED"

    unchanged = (await client.get(f"/api/v1/documentTypes/{created['id']}", headers=headers)).json()["data"]
    assert unchanged["status"] == "ACTIVE"


async def test_created_by_reports_system_only_for_verified_seeded_rows(client, session_factory):
    """Seeded canonical rows read as System; anything else keeps its evidence."""
    from app.modules.master_data.models import DocumentType
    from app.modules.master_data.service import ensure_vocabulary_creation_audit

    headers = await login(client)
    async with session_factory() as session:
        session.add(
            DocumentType(
                code="SUPPLIER_PAYMENT",
                name="Supplier Payment",
                category="FINANCE",
                accounting_behavior="SUPPLIER_PAYMENT",
                available_in=["financial_documents"],
            )
        )
        await session.commit()
        # Startup attribution already ran; a row seeded later is picked up by the
        # same idempotent pass.
        await ensure_vocabulary_creation_audit(session)
        await session.commit()

    rows = (await client.get("/api/v1/documentTypes?page_size=200", headers=headers)).json()["data"]["items"]
    assert {row["code"]: row["createdBy"] for row in rows}["SUPPLIER_PAYMENT"] == "System"

    await _create_type(client, headers, code="ATTRIBUTED_TYPE")
    created_rows = (await client.get("/api/v1/documentTypes?q=ATTRIBUTED_TYPE", headers=headers)).json()["data"]["items"]
    assert created_rows[0]["createdBy"] and created_rows[0]["createdBy"] != "System"

    # A row with no creation evidence is never given a fabricated creator.
    async with session_factory() as session:
        session.add(
            DocumentType(
                code="LEGACY_TYPE",
                name="Legacy Type",
                category="FINANCE",
                accounting_behavior="CUSTOMER_INVOICE",
                available_in=["financial_documents"],
            )
        )
        await session.commit()
    legacy = (await client.get("/api/v1/documentTypes?q=LEGACY_TYPE", headers=headers)).json()["data"]["items"]
    assert legacy[0]["createdBy"] is None


async def test_archive_lifecycle_for_a_custom_document_type(client, session_factory):
    """Deactivated custom types archive into the central archive and restore.

    Archive is a soft delete driven by the collection's own guards: an active
    row is refused (REFERENCE_ACTIVE) and a canonical type is refused
    (SYSTEM_DOCUMENT_TYPE), so only a retired custom type can land in the
    archive. Lifecycle status is preserved untouched across the round trip.
    """
    from app.modules.audit.models import AuditEvent

    headers = await login(client)
    created = await _create_type(client, headers, code="ARCHIVE_ME", name="Archive Me")
    deactivated = await client.patch(
        f"/api/v1/documentTypes/{created['id']}", headers=headers, json={"status": "INACTIVE"}
    )
    assert deactivated.status_code == 200, deactivated.text

    archived = await client.request(
        "DELETE", "/api/v1/documentTypes", json={"ids": [created["id"]]}, headers=headers
    )
    assert archived.status_code == 200, archived.text

    # The active list no longer offers it, so it cannot be picked for a new document.
    listed = (await client.get("/api/v1/documentTypes?q=ARCHIVE_ME", headers=headers)).json()["data"]["items"]
    assert listed == []

    row = (
        await client.get(
            "/api/v1/archive", params={"entity_type": "documentTypes", "q": "Archive Me"}, headers=headers
        )
    ).json()["data"]["items"][0]
    assert row["entityType"] == "documentTypes"
    assert row["deletedBy"] == "Demo Administrator"

    again = await client.request(
        "DELETE", "/api/v1/documentTypes", json={"ids": [created["id"]]}, headers=headers
    )
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "ALREADY_ARCHIVED"

    restored = await client.post(f"/api/v1/archive/documentTypes/{created['id']}/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    fetched = (await client.get(f"/api/v1/documentTypes/{created['id']}", headers=headers)).json()["data"]
    # Restoring brings the row back with the lifecycle status it was retired in.
    assert fetched["status"] == "INACTIVE"

    # A second archive + restore collides with a reused unique code.
    archived2 = await client.request(
        "DELETE", "/api/v1/documentTypes", json={"ids": [created["id"]]}, headers=headers
    )
    assert archived2.status_code == 200, archived2.text
    reused = await _create_type(client, headers, code="ARCHIVE_ME", name="Archive Me Again")
    assert reused["id"] != created["id"]
    conflict = await client.post(f"/api/v1/archive/documentTypes/{created['id']}/restore", headers=headers)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "RESTORE_CONFLICT"
    still_gone = (await client.get("/api/v1/documentTypes?q=ARCHIVE_ME%20Again", headers=headers)).json()["data"]["items"]
    assert [item["id"] for item in still_gone] == [reused["id"]]

    async with session_factory() as session:
        actions = list(
            (
                await session.execute(
                    select(AuditEvent.action).where(
                        AuditEvent.entity_type == "documentTypes",
                        AuditEvent.entity_id == int(created["id"]),
                        AuditEvent.event_type == "ARCHIVE",
                    )
                )
            ).scalars()
        )
        assert "DELETE" in actions and "RESTORE" in actions


async def test_document_type_archive_needs_the_manage_permission(client):
    headers = await login(client)
    created = await _create_type(client, headers, code="ARCHIVE_PERMISSION")
    await client.patch(f"/api/v1/documentTypes/{created['id']}", headers=headers, json={"status": "INACTIVE"})
    viewer = await login(client, "ops.pp")

    refused = await client.request(
        "DELETE", "/api/v1/documentTypes", json={"ids": [created["id"]]}, headers=viewer
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "ACCESS_DENIED"
    listed = (await client.get("/api/v1/documentTypes?q=ARCHIVE_PERMISSION", headers=headers)).json()["data"]["items"]
    assert [item["id"] for item in listed] == [created["id"]]
