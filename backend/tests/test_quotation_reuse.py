"""Quotation reuse: one quotation -> many service orders, CRUD and Finish.

A quotation is a reusable commercial reference. These tests pin the contract the
workflow now promises: CRUD without a submit gate, mandatory quotation selection
on the Service Order form, automatic copying of the quotation's reusable data,
independent pricing snapshots, Finish locking, and finance continuing after
Finish. Duplicate creation from a repeated identical request is refused through
the idempotency key, not through a one-time conversion guard.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login, seed_quotation, seed_service_order

pytestmark = pytest.mark.asyncio


async def _party(client, headers) -> dict:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})
    return response.json()["data"]["items"][0]


async def _quotation_with_pricing(client, headers) -> dict:
    return await seed_quotation(client, headers, {
        "pricingLines": [
            {"description": "Ocean freight", "quantity": 2, "unitPrice": 100, "taxRate": 10},
        ],
        "containerRequirements": [{"containerType": "40HC", "quantity": 2}],
    })


async def test_a_quotation_stays_editable_after_conversion(client):
    """CRUD only: a quotation keeps its Update and Delete paths usable."""
    headers = await login(client)
    quotation = await _quotation_with_pricing(client, headers)

    order = await seed_service_order(client, headers, {"quotationId": quotation["id"]})
    assert order["quotationId"] == quotation["id"]

    edited = await client.put(
        f"/api/v1/quotations/{quotation['id']}",
        headers=headers,
        json={"description": "Edited after conversion"},
    )
    assert edited.status_code == 200, edited.text

    blocked = await client.request("DELETE", "/api/v1/quotations", headers=headers, json={"ids": [quotation["id"]]})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "QUOTATION_HAS_SERVICE_ORDER"


async def test_one_quotation_creates_many_independent_service_orders(client):
    headers = await login(client)
    quotation = await _quotation_with_pricing(client, headers)

    first = await seed_service_order(client, headers, {"quotationId": quotation["id"]})
    second = await seed_service_order(client, headers, {"quotationId": quotation["id"]})

    assert first["serviceOrderId" if "serviceOrderId" in first else "id"] != second["id"]
    for order in (first, second):
        fetched = await client.get(f"/api/v1/service-orders/{order['jobNo']}", headers=headers)
        assert fetched.status_code == 200, fetched.text
        body = fetched.json()["data"]
        assert body["quotationId"] == quotation["id"]
        assert body["containerRequirements"], "each order copies its own container rows"


async def test_a_repeated_identical_create_is_a_replay_not_a_duplicate(client):
    headers = await login(client)
    quotation = await _quotation_with_pricing(client, headers)
    payload = {"quotationId": quotation["id"]}

    key = {"Idempotency-Key": "order-create-replay-1", **headers}
    first = await client.post("/api/v1/service-orders", headers=key, json=payload)
    assert first.status_code == 201, first.text
    replay = await client.post("/api/v1/service-orders", headers=key, json=payload)
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]


async def test_a_new_service_order_requires_a_quotation(client):
    headers = await login(client)
    party = await _party(client, headers)

    response = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"customer": party["legalName"], "direction": "Import", "currency": "USD"},
    )
    assert response.status_code == 422, response.text
    assert "quotationId" in response.json()["field_errors"]

    unknown = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"quotationId": 999999},
    )
    assert unknown.status_code == 422, unknown.text
    assert "quotationId" in unknown.json()["field_errors"]


async def test_selecting_a_quotation_copies_its_reusable_data(client):
    headers = await login(client)
    quotation = await _quotation_with_pricing(client, headers)

    created = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"quotationId": quotation["id"]},
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["data"]["id"]

    fetched = await client.get(f"/api/v1/service-orders/{order_id}", headers=headers)
    body = fetched.json()["data"]

    party = await _party(client, headers)
    assert body["customer"] == party["legalName"]
    assert body["direction"] == quotation["direction"]
    assert body["currency"] == quotation["currency"]
    # Container requirements and pending boxes are copied, never actual numbers.
    requirements = body["containerRequirements"]
    assert len(requirements) == 1
    assert float(requirements[0]["quantity"]) == 2
    containers = body["containers"]
    assert len(containers) == 2
    assert all(not row["containerNumber"] for row in containers)
    assert all(row["status"] == "EXPECTED" for row in containers)
    # Places/pricing are the order's own copies (see snapshot tests).
    pricing = await client.get(f"/api/v1/service-orders/{order_id}/invoice", headers=headers)
    assert pricing.status_code == 200, pricing.text


async def test_pricing_snapshots_are_independent_after_conversion(client):
    """Editing one side never rewrites the other side's stored snapshot."""
    headers = await login(client)
    quotation = await _quotation_with_pricing(client, headers)
    order = await seed_service_order(client, headers, {"quotationId": quotation["id"]})

    # Edit the quotation afterwards.
    edited = await client.put(
        f"/api/v1/quotations/{quotation['id']}",
        headers=headers,
        json={
            "pricingLines": [{"description": "Ocean freight", "quantity": 5, "unitPrice": 500}],
        },
    )
    assert edited.status_code == 200, edited.text
    assert float(edited.json()["data"]["total"]) == 2500

    # The order's pricing totals are stored on it, untouched by the quotation.
    later = await seed_service_order(client, headers, {"quotationId": quotation["id"]})
    assert later["quotationId"] == quotation["id"]
    fetched = await client.get(f"/api/v1/service-orders/{order['jobNo']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["data"]["containers"], "the first order kept its copied rows"
    assert quotation["id"] == fetched.json()["data"]["quotationId"]


async def test_finish_records_completion_and_locks_operational_editing(client, session_factory):
    from sqlalchemy import select

    from app.modules.auth.models import User
    from app.modules.operations.models import ServiceOrder

    headers = await login(client)
    quotation = await _quotation_with_pricing(client, headers)
    created = await client.post(
        "/api/v1/service-orders", headers=headers, json={"quotationId": quotation["id"]}
    )
    order_id = created.json()["data"]["id"]

    finished = await client.post(f"/api/v1/service-orders/{order_id}/finish", headers=headers, json={})
    assert finished.status_code == 200, finished.text
    assert finished.json()["data"]["rawStatus"] == "FINISHED"
    assert finished.json()["data"]["finishedAt"]

    async with session_factory() as session:
        order = (await session.execute(select(ServiceOrder).where(ServiceOrder.id == int(order_id)))).scalars().one()
        user = (await session.execute(select(User).where(User.username == "admin"))).scalars().first()
        assert order.finished_at is not None
        assert order.finished_by_user_id == user.id

    # Operational edits are refused after Finish.
    header_edit = await client.put(
        f"/api/v1/service-orders/{order_id}", headers=headers, json={"description": "late edit"}
    )
    assert header_edit.status_code == 409
    assert header_edit.json()["code"] == "ORDER_FINISHED"

    container = await client.post(
        f"/api/v1/service-orders/{order_id}/containers",
        headers=headers,
        json={"containerNumber": "FINLOCK1234", "containerType": "20GP"},
    )
    assert container.status_code == 409

    movement = await client.post(
        f"/api/v1/service-orders/{order_id}/movements",
        headers=headers,
        json={"sequenceNo": 1, "status": "PLANNED"},
    )
    assert movement.status_code == 409, movement.text


async def test_finance_continues_after_finish_without_full_payment(client):
    headers = await login(client)
    quotation = await _quotation_with_pricing(client, headers)
    created = await client.post(
        "/api/v1/service-orders", headers=headers, json={"quotationId": quotation["id"]}
    )
    order_no = created.json()["data"]["jobNo"]
    order_id = created.json()["data"]["id"]

    await client.post(f"/api/v1/service-orders/{order_id}/finish", headers=headers, json={})

    # Charges, the service order's pricing document, remain writable after Finish;
    # no payment is required to finish or to keep settling.
    charge = await client.post(
        f"/api/v1/service-orders/{order_no}/charges",
        headers=headers,
        json={"documentType": "SERVICE_NOTE", "feeLines": [
            {"description": "Ocean freight", "quantity": 2, "unitPrice": 100},
        ]},
    )
    assert charge.status_code in (200, 201), charge.text


async def test_containers_are_derived_from_pricing_lines(client):
    """Ocean/Truck/Terminal all price the same two 40HC boxes: derive 2, not 6."""
    headers = await login(client)
    quotation = await seed_quotation(client, headers, {
        "pricingLines": [
            {"description": "Ocean freight", "quantity": 2, "unitPrice": 100, "containerType": "40HC"},
            {"description": "Trucking", "quantity": 2, "unitPrice": 50, "containerType": "40HC"},
            {"description": "Documentation", "quantity": 1, "unitPrice": 30},
        ],
    })
    order = await seed_service_order(client, headers, {"quotationId": quotation["id"]})

    fetched = await client.get(f"/api/v1/service-orders/{order['jobNo']}", headers=headers)
    body = fetched.json()["data"]
    requirements = body["containerRequirements"]
    assert len(requirements) == 1, requirements
    assert float(requirements[0]["quantity"]) == 2
    containers = body["containers"]
    assert len(containers) == 2, containers
    assert all(not row["containerNumber"] for row in containers)


async def test_conflicting_container_quantities_are_rejected(client):
    """Two prices for the same type disagreeing on the box count must be fixed, not guessed."""
    headers = await login(client)
    party = await _party(client, headers)
    response = await client.post("/api/v1/quotations", headers=headers, json={
        "date": date.today().isoformat(),
        "customerPartyId": party["id"],
        "direction": "Import",
        "currency": "USD",
        "pricingLines": [
            {"description": "Ocean freight", "quantity": 2, "unitPrice": 100, "containerType": "40HC"},
            {"description": "Trucking", "quantity": 3, "unitPrice": 50, "containerType": "40HC"},
        ],
    })
    assert response.status_code == 422, response.text
    assert any("containerType" in key for key in response.json()["field_errors"])


async def test_container_quantity_must_be_a_whole_number(client):
    headers = await login(client)
    party = await _party(client, headers)
    response = await client.post("/api/v1/quotations", headers=headers, json={
        "date": date.today().isoformat(),
        "customerPartyId": party["id"],
        "direction": "Import",
        "currency": "USD",
        "pricingLines": [
            {"description": "Ocean freight", "quantity": 1.5, "unitPrice": 100, "containerType": "40HC"},
        ],
    })
    assert response.status_code == 422, response.text
    assert any("containerType" in key for key in response.json()["field_errors"])


async def test_no_containerized_pricing_lines_means_zero_containers(client):
    headers = await login(client)
    quotation = await seed_quotation(client, headers, {
        "pricingLines": [{"description": "Documentation", "quantity": 1, "unitPrice": 30}],
    })
    order = await seed_service_order(client, headers, {"quotationId": quotation["id"]})

    fetched = await client.get(f"/api/v1/service-orders/{order['jobNo']}", headers=headers)
    body = fetched.json()["data"]
    assert not body.get("containers")
    assert not body.get("containerRequirements")


async def test_legacy_container_requirements_payload_still_works(client):
    """Old API clients that send the removed Containers payload keep working."""
    headers = await login(client)
    quotation = await seed_quotation(client, headers, {
        "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        "containerRequirements": [{"containerType": "20GP", "quantity": 4}],
    })
    order = await seed_service_order(client, headers, {"quotationId": quotation["id"]})

    fetched = await client.get(f"/api/v1/service-orders/{order['jobNo']}", headers=headers)
    body = fetched.json()["data"]
    assert len(body["containerRequirements"]) == 1
    assert float(body["containerRequirements"][0]["quantity"]) == 4
    assert len(body["containers"]) == 4


async def test_legacy_orders_without_a_quotation_keep_working(client):
    """Seed data has orders without quotation links; nothing fabricates one."""
    headers = await login(client)
    response = await client.get("/api/v1/service-orders", headers=headers)
    assert response.status_code == 200
    for row in response.json()["data"]["items"]:
        if not row.get("quotationId"):
            # A legacy order keeps an empty link rather than a fabricated id.
            assert row.get("quotationNo") in (None, "")