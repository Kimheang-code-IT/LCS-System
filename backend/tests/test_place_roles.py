"""Dynamic Place Roles and the shared route-stop contract.

Place Roles are configuration records, not a code-owned vocabulary. A route stop
is a role plus a free-text location. These tests cover the administrator
workflow, the reference validation used by both route tabs, and the historical
guarantee: deactivating or archiving a role keeps an existing route readable and
saveable while a *new* selection of the inactive role is refused.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _party(client, headers) -> dict:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"][0]


async def _role(client, headers, code: str, name: str | None = None, **extra) -> dict:
    response = await client.post(
        "/api/v1/placeRoles",
        headers=headers,
        json={"code": code, "name": name or code.title(), "sortOrder": 10, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _quotation(client, headers, places: list[dict]) -> dict:
    party = await _party(client, headers)
    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "direction": "Import",
            "currency": "USD",
            "customerPartyId": party["id"],
            "amount": 500,
            "places": places,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _converted_service_order(client, headers, places: list[dict]) -> tuple[dict, dict]:
    quotation = await _quotation(client, headers, places)
    revision_id = quotation["revisionId"]
    sent = await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    assert sent.status_code == 200, sent.text
    accepted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    assert accepted.status_code == 200, accepted.text
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    order_id = converted.json()["data"]["serviceOrderId"]
    order = await client.get(f"/api/v1/service-orders/{order_id}", headers=headers)
    assert order.status_code == 200, order.text
    return quotation, order.json()["data"]


async def test_place_role_crud_display_order_and_unique_code(client):
    headers = await login(client)
    later = await _role(client, headers, "ZZ_LATER", "Later Role", sortOrder=90)
    first = await _role(client, headers, "AA_FIRST", "First Role", sortOrder=5)

    listed = await client.get("/api/v1/placeRoles", headers=headers, params={"page_size": 200})
    assert listed.status_code == 200, listed.text
    codes = [row["code"] for row in listed.json()["data"]["items"]]
    assert codes.index(first["code"]) < codes.index(later["code"])
    assert codes.index("AA_FIRST") < codes.index("PICKUP"), "sort_order drives the default order"

    duplicate = await client.post(
        "/api/v1/placeRoles",
        headers=headers,
        json={"code": "AA_FIRST", "name": "Duplicate", "sortOrder": 1},
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "code" in duplicate.json()["field_errors"]

    # Codes are normalised to upper case, so a lower-case spelling is the same code.
    case_duplicate = await client.post(
        "/api/v1/placeRoles",
        headers=headers,
        json={"code": "aa_first", "name": "Case duplicate", "sortOrder": 1},
    )
    assert case_duplicate.status_code == 422, case_duplicate.text
    assert "code" in case_duplicate.json()["field_errors"]

    updated = await client.put(
        f"/api/v1/placeRoles/{first['id']}",
        headers=headers,
        json={"name": "Renamed Role", "sortOrder": 7, "status": "INACTIVE"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Renamed Role"
    assert updated.json()["data"]["sortOrder"] == 7
    assert updated.json()["data"]["status"] == "INACTIVE"

    searched = await client.get("/api/v1/placeRoles", headers=headers, params={"q": "Renamed"})
    assert [row["code"] for row in searched.json()["data"]["items"]] == ["AA_FIRST"]
    filtered = await client.get("/api/v1/placeRoles", headers=headers, params={"status": "INACTIVE"})
    assert all(row["status"] == "INACTIVE" for row in filtered.json()["data"]["items"])


async def test_place_role_writes_require_permission(client):
    headers = await login(client)
    sales = await login(client, "sales")

    denied_create = await client.post(
        "/api/v1/placeRoles",
        headers=sales,
        json={"code": "DENIED", "name": "Denied", "sortOrder": 1},
    )
    assert denied_create.status_code == 403, denied_create.text

    role = await _role(client, headers, "PERM_TARGET", "Permission Target")
    denied_update = await client.put(
        f"/api/v1/placeRoles/{role['id']}",
        headers=sales,
        json={"name": "Escalated"},
    )
    assert denied_update.status_code == 403, denied_update.text
    denied_delete = await client.delete(f"/api/v1/placeRoles/{role['id']}", headers=sales)
    assert denied_delete.status_code == 403, denied_delete.text

    # An active role is never hard-deleted; deactivate first, then archive.
    blocked = await client.delete(f"/api/v1/placeRoles/{role['id']}", headers=headers)
    assert blocked.status_code == 409, blocked.text
    await client.put(f"/api/v1/placeRoles/{role['id']}", headers=headers, json={"status": "INACTIVE"})
    archived = await client.delete(f"/api/v1/placeRoles/{role['id']}", headers=headers)
    assert archived.status_code == 200, archived.text


async def test_route_stop_stores_the_role_and_free_text_location(client):
    headers = await login(client)
    role = await _role(client, headers, "FREE_TEXT_ROLE", "Free Text Role")

    quotation = await _quotation(
        client,
        headers,
        [{"placeRoleId": role["id"], "place": "Phnom Penh Port", "notes": "typed location"}],
    )
    stop = quotation["places"][0]
    assert stop["placeRoleId"] == role["id"]
    assert stop["placeRole"] == "Free Text Role"
    assert stop["place"] == "Phnom Penh Port"
    assert "placeId" not in stop

    # A location is helpful but not required: the role alone still describes a
    # planned stop, and the row may be filled in later.
    role_only = await _quotation(client, headers, [{"placeRoleId": role["id"]}])
    assert role_only["places"][0]["place"] == ""


async def test_inactive_roles_are_refused_for_new_stops_but_history_stays_readable(client):
    headers = await login(client)
    role = await _role(client, headers, "LIFECYCLE_ROLE", "Lifecycle Role")

    quotation = await _quotation(
        client,
        headers,
        [{"placeRoleId": role["id"], "place": "Lifecycle Yard", "notes": "original"}],
    )

    deactivated_role = await client.put(
        f"/api/v1/placeRoles/{role['id']}", headers=headers, json={"status": "INACTIVE"}
    )
    assert deactivated_role.status_code == 200, deactivated_role.text

    # Reading a historical route is unaffected by deactivation.
    fetched = await client.get(f"/api/v1/quotations/{quotation['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    stop = fetched.json()["data"]["places"][0]
    assert stop["placeRole"] == "Lifecycle Role"
    assert stop["place"] == "Lifecycle Yard"
    assert stop["placeRoleId"] == role["id"]

    # Saving the existing row (it carries its id) is allowed; adding a new row
    # with the inactive role is not.
    kept = await client.put(
        f"/api/v1/quotations/{quotation['id']}",
        headers=headers,
        json={
            "places": [
                {
                    "id": stop["id"],
                    "placeRoleId": role["id"],
                    "place": "Lifecycle Yard",
                    "notes": "kept",
                }
            ]
        },
    )
    assert kept.status_code == 200, kept.text
    kept_stop = kept.json()["data"]["places"][0]
    assert kept_stop["id"] == stop["id"], "saving must update the row, not replace its id"

    # Archiving the now-inactive role (the only deletion route) keeps the
    # historical stop readable and saveable through its own id.
    archived_role = await client.delete(f"/api/v1/placeRoles/{role['id']}", headers=headers)
    assert archived_role.status_code == 200, archived_role.text

    still_readable = await client.get(f"/api/v1/quotations/{quotation['id']}", headers=headers)
    archived_stop = still_readable.json()["data"]["places"][0]
    assert archived_stop["placeRole"] == "Lifecycle Role"
    assert archived_stop["place"] == "Lifecycle Yard"

    kept_archived = await client.put(
        f"/api/v1/quotations/{quotation['id']}",
        headers=headers,
        json={
            "places": [
                {"id": stop["id"], "placeRoleId": role["id"], "place": "Lifecycle Yard", "notes": "archived but kept"}
            ]
        },
    )
    assert kept_archived.status_code == 200, kept_archived.text
    assert kept_archived.json()["data"]["places"][0]["id"] == stop["id"]

    added = await client.put(
        f"/api/v1/quotations/{quotation['id']}",
        headers=headers,
        json={
            "places": [
                {"id": stop["id"], "placeRoleId": role["id"], "place": "Lifecycle Yard"},
                {"placeRoleId": role["id"], "place": "New Yard"},
            ]
        },
    )
    assert added.status_code == 422, added.text
    errors = added.json()["field_errors"]
    assert "places.1.placeRoleId" in errors


async def test_conversion_copies_route_rows_and_both_sides_stay_editable(client):
    headers = await login(client)
    pickup = await _role(client, headers, "CONV_PICKUP", "Conv Pickup")
    customs = await _role(client, headers, "CONV_CUSTOMS", "Conv Customs")

    quotation, order = await _converted_service_order(client, headers, [
        {
            "placeRoleId": pickup["id"],
            "place": "Conv Origin",
            "planned": "2026-10-22T09:00",
            "notes": "pick first",
        },
        {
            "placeRoleId": customs["id"],
            "place": "Conv Border",
            "planned": "2026-10-22T13:00",
        },
    ])

    assert [row["place"] for row in order["places"]] == ["Conv Origin", "Conv Border"]
    assert [row["sequence"] for row in order["places"]] == [1, 2]

    # The service order gets its own actual time and can drop a stop.
    edited = await client.put(
        f"/api/v1/service-orders/{order['id']}",
        headers=headers,
        json={
            "places": [
                {
                    "placeRoleId": pickup["id"],
                    "place": "Conv Origin",
                    "planned": "2026-10-22T09:00",
                    "actual": "2026-10-22T09:15",
                    "notes": "picked up",
                },
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    assert len(edited.json()["data"]["places"]) == 1

    order_again = await client.get(f"/api/v1/service-orders/{order['id']}", headers=headers)
    order_stop = order_again.json()["data"]["places"][0]
    assert order_stop["actual"].startswith("2026-10-22T09:15")
    assert order_stop["notes"] == "picked up"

    # The quotation is untouched: the two documents own separate rows.
    quotation_again = await client.get(f"/api/v1/quotations/{quotation['id']}", headers=headers)
    quotation_stops = quotation_again.json()["data"]["places"]
    assert len(quotation_stops) == 2
    assert quotation_stops[0]["actual"] == ""
    assert quotation_stops[0]["notes"] == "pick first"


async def test_route_sequence_is_renumbered_from_the_submitted_order(client):
    headers = await login(client)
    role = await _role(client, headers, "SEQ_ROLE", "Sequence Role")
    _, order = await _converted_service_order(client, headers, [])

    saved = await client.put(
        f"/api/v1/service-orders/{order['id']}",
        headers=headers,
        json={
            "places": [
                {"sequence": 9, "placeRoleId": role["id"], "place": "Sequence Place One"},
                {"sequence": 9, "placeRoleId": role["id"], "place": "Sequence Place Two"},
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    rows = saved.json()["data"]["places"]
    assert [row["sequence"] for row in rows] == [1, 2]
    first_id, second_id = rows[0]["id"], rows[1]["id"]

    # Reordering swaps the stored rows in place; the unique sequence constraint
    # must not fail on the temporary duplicate and the row ids must survive.
    reordered = await client.put(
        f"/api/v1/service-orders/{order['id']}",
        headers=headers,
        json={"places": [rows[1], rows[0]]},
    )
    assert reordered.status_code == 200, reordered.text
    reordered_rows = reordered.json()["data"]["places"]
    assert [row["id"] for row in reordered_rows] == [second_id, first_id]
    assert [row["sequence"] for row in reordered_rows] == [1, 2]
    assert [row["place"] for row in reordered_rows] == ["Sequence Place Two", "Sequence Place One"]

    reloaded = await client.get(f"/api/v1/service-orders/{order['id']}", headers=headers)
    assert [row["sequence"] for row in reloaded.json()["data"]["places"]] == [1, 2]
