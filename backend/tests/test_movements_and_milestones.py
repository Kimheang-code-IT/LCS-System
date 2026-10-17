"""Service order movements and milestones.

Both tables existed in the schema but had no service or endpoints, so the
capability was unreachable. These tests cover the APIs added on top of them.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _service_order(client, headers, status: str = "ACTIVE") -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Movement Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": 100,
        },
    )
    assert quotation.status_code == 201, quotation.text
    revision_id = quotation.json()["data"]["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})).status_code == 200
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    order_id = converted.json()["data"]["serviceOrderId"]
    if status != "ACTIVE":
        assert (
            await client.post(f"/api/v1/service-orders/{order_id}/finish", headers=headers, json={})
        ).status_code == 200
        updated = await client.put(
            f"/api/v1/service-orders/{order_id}", headers=headers, json={"status": status}
        )
        assert updated.status_code == 200, updated.text
    return order_id


async def test_movements_are_created_sequenced_and_updated(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    first = await client.post(
        f"/api/v1/service-orders/{order_id}/movements",
        headers=headers,
        json={"status": "IN_TRANSIT", "plannedDeparture": "2026-03-01T08:00:00Z", "notes": "Leg one"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["sequenceNo"] == 1
    assert first.json()["data"]["status"] == "IN_TRANSIT"
    assert first.json()["data"]["notes"] == "Leg one"

    second = await client.post(f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={})
    assert second.status_code == 201, second.text
    assert second.json()["data"]["sequenceNo"] == 2

    movement_id = first.json()["data"]["id"]
    updated = await client.post(
        f"/api/v1/service-orders/{order_id}/movements",
        headers=headers,
        json={"id": movement_id, "status": "ARRIVED", "actualArrival": "2026-03-02T10:30:00Z"},
    )
    assert updated.status_code == 201, updated.text
    assert updated.json()["data"]["status"] == "ARRIVED"
    assert updated.json()["data"]["actualArrival"] is not None

    listed = await client.get(f"/api/v1/service-orders/{order_id}/movements", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [row["sequenceNo"] for row in listed.json()["data"]] == [1, 2]


async def test_duplicate_movement_sequence_is_rejected(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    assert (
        await client.post(
            f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={"sequenceNo": 1}
        )
    ).status_code == 201

    conflict = await client.post(
        f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={"sequenceNo": 1}
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "DUPLICATE_SEQUENCE"


async def test_invalid_movement_timestamp_is_rejected(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    rejected = await client.post(
        f"/api/v1/service-orders/{order_id}/movements",
        headers=headers,
        json={"plannedDeparture": "not-a-date"},
    )
    assert rejected.status_code == 422, rejected.text
    assert "plannedDeparture" in rejected.json()["field_errors"]


async def test_movement_renumber_onto_an_existing_sequence_is_rejected(client):
    """(service_order_id, sequence_no) is unique; a clash must be a 409, not a 500."""
    headers = await login(client)
    order_id = await _service_order(client, headers)

    first = await client.post(f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={})
    second = await client.post(f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={})
    assert first.status_code == 201 and second.status_code == 201

    clash = await client.post(
        f"/api/v1/service-orders/{order_id}/movements",
        headers=headers,
        json={"id": second.json()["data"]["id"], "sequenceNo": 1},
    )
    assert clash.status_code == 409, clash.text
    assert clash.json()["code"] == "DUPLICATE_SEQUENCE"

    # Renumbering onto a free sequence still works.
    free = await client.post(
        f"/api/v1/service-orders/{order_id}/movements",
        headers=headers,
        json={"id": second.json()["data"]["id"], "sequenceNo": 9},
    )
    assert free.status_code == 201, free.text
    assert free.json()["data"]["sequenceNo"] == 9


async def test_movements_can_be_deleted(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)
    created = await client.post(f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={})
    assert created.status_code == 201, created.text

    removed = await client.request(
        "DELETE",
        f"/api/v1/service-orders/{order_id}/movements",
        headers=headers,
        json={"ids": [created.json()["data"]["id"]]},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 1

    listed = await client.get(f"/api/v1/service-orders/{order_id}/movements", headers=headers)
    assert listed.json()["data"] == []


async def test_milestones_are_created_progressed_and_deleted(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    created = await client.post(
        f"/api/v1/service-orders/{order_id}/milestones",
        headers=headers,
        json={"milestoneCode": "booking confirmed", "plannedAt": "2026-03-01T08:00:00Z"},
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert body["milestoneCode"] == "BOOKING_CONFIRMED", "codes are normalised"
    assert body["milestoneName"] == "Booking Confirmed", "a name is derived when omitted"
    assert body["status"] == "PENDING"

    progressed = await client.post(
        f"/api/v1/service-orders/{order_id}/milestones",
        headers=headers,
        json={"id": body["id"], "status": "COMPLETED", "actualAt": "2026-03-01T09:00:00Z", "notes": "Done"},
    )
    assert progressed.status_code == 201, progressed.text
    assert progressed.json()["data"]["status"] == "COMPLETED"
    assert progressed.json()["data"]["notes"] == "Done"

    removed = await client.request(
        "DELETE",
        f"/api/v1/service-orders/{order_id}/milestones",
        headers=headers,
        json={"ids": [body["id"]]},
    )
    assert removed.status_code == 200, removed.text
    assert (await client.get(f"/api/v1/service-orders/{order_id}/milestones", headers=headers)).json()["data"] == []


async def test_duplicate_milestone_code_is_rejected_and_the_code_is_immutable(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    created = await client.post(
        f"/api/v1/service-orders/{order_id}/milestones", headers=headers, json={"milestoneCode": "DEPARTED"}
    )
    assert created.status_code == 201, created.text

    duplicate = await client.post(
        f"/api/v1/service-orders/{order_id}/milestones", headers=headers, json={"milestoneCode": "DEPARTED"}
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_MILESTONE"

    renamed = await client.post(
        f"/api/v1/service-orders/{order_id}/milestones",
        headers=headers,
        json={"id": created.json()["data"]["id"], "milestoneCode": "ARRIVED"},
    )
    assert renamed.status_code == 409, renamed.text
    assert renamed.json()["code"] == "MILESTONE_CODE_IMMUTABLE"


async def test_unknown_milestone_status_falls_back_to_pending(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    created = await client.post(
        f"/api/v1/service-orders/{order_id}/milestones",
        headers=headers,
        json={"milestoneCode": "ODD", "status": "something else"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["status"] == "PENDING"


async def test_inactive_service_orders_reject_operational_edits(client):
    headers = await login(client)
    order_id = await _service_order(client, headers, status="INACTIVE")

    movement = await client.post(f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={})
    assert movement.status_code == 409, movement.text

    milestone = await client.post(
        f"/api/v1/service-orders/{order_id}/milestones", headers=headers, json={"milestoneCode": "X"}
    )
    assert milestone.status_code == 409, milestone.text


async def test_movements_and_milestones_are_not_public(client):
    """Reads are permission-gated; an anonymous caller must never see a job.

    ``login()`` leaves the HttpOnly access cookie on the shared test client, so
    the cookie jar is cleared first — otherwise this would silently test an
    authenticated request.
    """
    headers = await login(client)
    order_id = await _service_order(client, headers)
    assert (
        await client.post(f"/api/v1/service-orders/{order_id}/movements", headers=headers, json={})
    ).status_code == 201

    client.cookies.clear()
    response = await client.get(f"/api/v1/service-orders/{order_id}/movements")
    assert response.status_code in {401, 403}, response.text

    milestones = await client.get(f"/api/v1/service-orders/{order_id}/milestones")
    assert milestones.status_code in {401, 403}, milestones.text
