from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _first_party(client, headers, *, role: str | None = None) -> dict:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    if role:
        items = [row for row in items if role.lower() in {str(r).lower() for r in row.get("roles") or []}]
    assert items, "expected at least one business party"
    return items[0]


async def _create_quotation(client, headers, payload: dict) -> dict:
    body = {"date": date.today().isoformat(), "direction": "Import", "currency": "USD", **payload}
    response = await client.post("/api/v1/quotations", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest.mark.parametrize("direction", ["Import", "Export", "Transit"])
async def test_a_quotation_saves_for_each_configured_trade_direction(client, direction):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    created = await _create_quotation(client, headers, {
        "customerPartyId": party["id"],
        "direction": direction,
    })
    assert created["direction"] == direction


async def test_a_new_quotation_needs_a_business_party_and_trade_direction(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    missing_party = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={"date": date.today().isoformat(), "direction": "Import", "currency": "USD"},
    )
    assert missing_party.status_code == 422, missing_party.text
    assert "customerPartyId" in missing_party.json()["field_errors"]

    missing_direction = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={"date": date.today().isoformat(), "customerPartyId": party["id"], "currency": "USD"},
    )
    assert missing_direction.status_code == 422, missing_direction.text
    assert "direction" in missing_direction.json()["field_errors"]


async def test_valid_until_cannot_precede_the_quotation_date(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": "2026-10-20",
            "validUntil": "2026-10-19",
            "customerPartyId": party["id"],
            "direction": "Import",
            "currency": "USD",
        },
    )
    assert response.status_code == 422, response.text
    assert "validUntil" in response.json()["field_errors"]


async def test_the_backend_recomputes_quotation_totals_and_rounds_lines(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    created = await _create_quotation(client, headers, {
        "customerPartyId": party["id"],
        # A stale/browser-computed total must never win over the lines.
        "amount": 9999,
        "pricingLines": [
            {"description": "Freight", "quantity": 3, "unitPrice": 10.005},
            {"description": "Handling", "quantity": 1, "unitPrice": 0.335},
        ],
    })

    assert created["subtotal"] == 30.36
    assert created["total"] == 30.36
    assert created["amount"] == 30.36

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"]["amount"] == 30.36


async def test_a_line_tax_rate_derives_the_quotation_tax_and_is_validated(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    created = await _create_quotation(client, headers, {
        "customerPartyId": party["id"],
        "pricingLines": [
            {"description": "Freight", "quantity": 2, "unitPrice": 100, "discountAmount": 20, "taxRate": 10},
        ],
    })
    assert created["subtotal"] == 200
    assert created["discount"] == 20
    assert created["tax"] == 18
    assert created["total"] == 198

    rejected = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customerPartyId": party["id"],
            "direction": "Import",
            "currency": "USD",
            "pricingLines": [
                {"description": "Freight", "quantity": 1, "unitPrice": 100, "taxRate": 150},
            ],
        },
    )
    assert rejected.status_code == 422, rejected.text


async def test_quotation_stores_customer_party_id(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    created = await _create_quotation(client, headers, {"customerPartyId": party["id"], "amount": 1000})
    assert created["customerPartyId"] == str(party["id"])
    assert created["customer"] == party["legalName"]

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["customerPartyId"] == str(party["id"])
    assert data["customer"] == party["legalName"]


async def test_quotation_accepts_a_company_role_party(client):
    """A party saved only as a Company is a valid quotation customer.

    The form's party selector is labelled "Company" and offers both the
    ``Customer`` and ``Company`` roles (``CUSTOMER_PARTY_ROLES`` in
    ``frontend/app/utils/freight/reference-options.ts``). The backend must keep
    accepting such a party, or selecting one would still fail on save.
    """
    headers = await login(client)
    created_party = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "CO-ONLY-001", "legalName": "Company Only Trading Ltd.", "roles": ["Company"], "status": "ACTIVE"},
    )
    assert created_party.status_code == 201, created_party.text
    party_id = created_party.json()["data"]["id"]

    created = await _create_quotation(client, headers, {"customerPartyId": party_id, "amount": 400})
    assert created["customerPartyId"] == str(party_id)
    assert created["customer"] == "Company Only Trading Ltd."


async def test_quotation_keeps_a_typed_company_name(client):
    """The company name is editable: a typed name must survive the party lookup.

    Selecting a business party still supplies a default company name, but the
    operator may override it and the override is what the record carries.
    """
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    typed = "Typed Company Name Co., Ltd."

    created = await _create_quotation(
        client, headers, {"customerPartyId": party["id"], "customer": typed, "amount": 250}
    )
    assert created["customer"] == typed
    assert created["customerPartyId"] == str(party["id"])

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"]["customer"] == typed

    # A blank name still falls back to the linked party's legal name.
    updated = await client.put(
        f"/api/v1/quotations/{created['id']}",
        headers=headers,
        json={"customerPartyId": party["id"], "customer": ""},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["customer"] == party["legalName"]


async def test_quotation_accepts_a_supplier_role_party(client):
    """Any role is a valid quotation party; only existence and ACTIVE are checked.

    The party selector offers every Business Party role (see
    ``REFERENCE_SELECT_SOURCES.customerPartyId`` in
    ``frontend/app/utils/freight/reference-options.ts``), so the backend must
    accept a supplier-only party too, or selecting one would fail on save.
    """
    headers = await login(client)
    created_party = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "SUP-ONLY-001", "legalName": "Supplier Only Trading Ltd.", "roles": ["Supplier"], "status": "ACTIVE"},
    )
    assert created_party.status_code == 201, created_party.text
    party_id = created_party.json()["data"]["id"]

    created = await _create_quotation(client, headers, {"customerPartyId": party_id, "amount": 300})
    assert created["customerPartyId"] == str(party_id)
    assert created["customer"] == "Supplier Only Trading Ltd."


async def test_quotation_rejects_an_inactive_customer_party(client):
    """``status`` is the only narrowing the party selector applies, and save agrees."""
    headers = await login(client)
    created_party = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "INACTIVE-001", "legalName": "Dormant Trading Ltd.", "roles": ["Customer"], "status": "INACTIVE"},
    )
    assert created_party.status_code == 201, created_party.text
    party_id = created_party.json()["data"]["id"]

    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "direction": "Import",
            "currency": "USD",
            "customerPartyId": party_id,
            "amount": 100,
        },
    )
    assert response.status_code == 422, response.text
    assert "customerPartyId" in response.json()["field_errors"]


async def test_quotation_rejects_unknown_customer_party_id(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={"date": date.today().isoformat(), "direction": "Import", "currency": "USD", "customerPartyId": 999999},
    )
    assert response.status_code == 422, response.text
    assert "customerPartyId" in response.json()["field_errors"]


async def _transport_type(client, headers, name: str) -> dict:
    response = await client.get("/api/v1/transportTypes", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    for row in response.json()["data"]["items"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"expected transport type {name!r} in the seeded master data")


async def test_quotation_pricing_line_stores_a_transport_type_id(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    transport = await _transport_type(client, headers, "Truck")

    created = await _create_quotation(
        client,
        headers,
        {
            "customerPartyId": party["id"],
            "pricingLines": [
                {"containerType": "40HC", "transportBy": transport["id"], "quantity": 1, "unitPrice": 100},
            ],
        },
    )
    assert created["pricingLines"][0]["transportBy"] == str(transport["id"])

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["data"]["pricingLines"][0]["transportBy"] == str(transport["id"])


async def test_quotation_pricing_line_can_change_its_transport_type(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    truck = await _transport_type(client, headers, "Truck")
    air = await _transport_type(client, headers, "Air")

    created = await _create_quotation(
        client,
        headers,
        {
            "customerPartyId": party["id"],
            "pricingLines": [
                {"containerType": "40HC", "transportBy": truck["id"], "quantity": 1, "unitPrice": 100},
            ],
        },
    )
    updated = await client.put(
        f"/api/v1/quotations/{created['id']}",
        headers=headers,
        json={
            "pricingLines": [
                {"containerType": "40HC", "transportBy": air["id"], "quantity": 2, "unitPrice": 100},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    line = updated.json()["data"]["pricingLines"][0]
    assert line["transportBy"] == str(air["id"])
    assert line["quantity"] == 2


async def test_sent_quotation_revision_keeps_the_transport_type_when_edited(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    truck = await _transport_type(client, headers, "Truck")
    air = await _transport_type(client, headers, "Air")

    created = await _create_quotation(
        client,
        headers,
        {
            "customerPartyId": party["id"],
            "pricingLines": [
                {"containerType": "40HC", "transportBy": truck["id"], "quantity": 1, "unitPrice": 100},
            ],
        },
    )
    sent = await client.post(
        f"/api/v1/quotation-revisions/{created['revisionId']}/send",
        headers=headers,
        json={},
    )
    assert sent.status_code == 200, sent.text

    updated = await client.put(
        f"/api/v1/quotations/{created['id']}",
        headers=headers,
        json={
            "pricingLines": [
                {"containerType": "40HC", "transportBy": air["id"], "quantity": 1, "unitPrice": 100},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["revisionId"] != created["revisionId"]
    assert data["pricingLines"][0]["transportBy"] == str(air["id"])


async def test_quotation_pricing_line_rejects_an_unknown_transport_type_id(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")

    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "direction": "Import",
            "currency": "USD",
            "customerPartyId": party["id"],
            "pricingLines": [{"containerType": "40HC", "transportBy": 999999, "quantity": 1, "unitPrice": 100}],
        },
    )
    assert response.status_code == 422, response.text
    assert "pricingLines.0.transportBy" in response.json()["field_errors"]


async def test_quotation_pricing_line_accepts_legacy_transport_names(client):
    """Quotations saved before the By select was database-driven stored a name."""
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    truck = await _transport_type(client, headers, "Truck")

    created = await _create_quotation(
        client,
        headers,
        {
            "customerPartyId": party["id"],
            "pricingLines": [
                {"containerType": "40HC", "transportBy": "Truck", "quantity": 1, "unitPrice": 100},
                {"containerType": "40HC", "transportBy": "Sea", "quantity": 1, "unitPrice": 50},
            ],
        },
    )
    assert created["pricingLines"][0]["transportBy"] == str(truck["id"])
    # No ``Sea`` master row is seeded; the legacy label must survive a save.
    assert created["pricingLines"][1]["transportBy"] == "Sea"


async def test_two_new_customers_saved_in_the_same_second_do_not_collide(client):
    """Regression: the placeholder party code was unique only per second.

    ``resolve_party_by_name`` stamped ``P-YYMMDDHHMMSS``, so two quotations for
    two brand-new customers saved back to back raised a UNIQUE violation on the
    active ``party_code`` index instead of creating the second customer.
    """
    headers = await login(client)
    created = [
        await _create_quotation(client, headers, {"customer": name, "amount": 25})
        for name in ("Same Second Customer A", "Same Second Customer B")
    ]
    assert created[0]["customerPartyId"] != created[1]["customerPartyId"], (
        "each new customer must get its own business party"
    )

    codes = []
    for row in created:
        party = await client.get(f"/api/v1/businessParties/{row['customerPartyId']}", headers=headers)
        assert party.status_code == 200, party.text
        codes.append(party.json()["data"]["partyCode"])
    assert len(set(codes)) == 2, f"party codes must be unique, got {codes}"


async def test_quotation_update_switches_customer_party(client):
    headers = await login(client)
    parties = (await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})).json()["data"]["items"]
    assert len(parties) >= 2
    first, second = parties[0], parties[1]

    created = await _create_quotation(client, headers, {"customerPartyId": first["id"]})
    updated = await client.put(
        f"/api/v1/quotations/{created['id']}",
        headers=headers,
        json={"customerPartyId": second["id"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["customer"] == second["legalName"]

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.json()["data"]["customerPartyId"] == str(second["id"])


async def _route_reference(client, headers, *, code: str = "PICKUP") -> dict:
    """A configured Place Role for a route stop."""
    roles = await client.get("/api/v1/placeRoles", headers=headers, params={"page_size": 200})
    assert roles.status_code == 200, roles.text
    role = next((row for row in roles.json()["data"]["items"] if row["code"] == code), None)
    if role is None:
        created = await client.post(
            "/api/v1/placeRoles",
            headers=headers,
            json={"code": code, "name": code.title(), "sortOrder": 10},
        )
        assert created.status_code == 201, created.text
        role = created.json()["data"]
    return role


async def test_a_route_stop_stores_the_selected_role_and_free_text_location(client):
    """The route stop references the live Place Roles master and keeps typed text."""
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    role = await _route_reference(client, headers)

    created = await _create_quotation(client, headers, {
        "customerPartyId": party["id"],
        "amount": 800,
        "places": [
            {
                "placeRoleId": role["id"],
                "place": "Phnom Penh Autonomous Port",
                "planned": "2026-10-21T08:30",
                "notes": "Gate 2",
            },
        ],
    })
    route = created["places"]
    assert route[0]["placeRoleId"] == role["id"]
    assert "placeId" not in route[0]
    assert route[0]["placeRole"] == role["name"]
    assert route[0]["place"] == "Phnom Penh Autonomous Port"
    assert route[0]["planned"].startswith("2026-10-21T08:30")
    assert route[0]["notes"] == "Gate 2"

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    reloaded = fetched.json()["data"]["places"][0]
    assert reloaded["placeRoleId"] == role["id"]
    assert reloaded["place"] == "Phnom Penh Autonomous Port"


async def test_a_route_stop_needs_a_role(client):
    """A missing or unknown role is reported on the row that is missing it."""
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    role = await _route_reference(client, headers)

    async def _save(places: list[dict]):
        return await client.post(
            "/api/v1/quotations",
            headers=headers,
            json={
                "date": date.today().isoformat(),
                "direction": "Import",
                "currency": "USD",
                "customerPartyId": party["id"],
                "amount": 100,
                "places": places,
            },
        )

    without_role = await _save([{"placeRoleId": "", "place": "Somewhere"}])
    assert without_role.status_code == 422, without_role.text
    assert "places.0.placeRoleId" in without_role.json()["field_errors"]

    unknown_role = await _save([{"placeRoleId": "999999", "place": "Somewhere"}])
    assert unknown_role.status_code == 422, unknown_role.text
    assert "places.0.placeRoleId" in unknown_role.json()["field_errors"]

    # A new stop needs a location; the role alone is not a printable route.
    role_only = await _save([{"placeRoleId": role["id"]}])
    assert role_only.status_code == 422, role_only.text
    assert "places.0.place" in role_only.json()["field_errors"]


async def test_revision_history_preserves_original_and_opens_draft(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"], "amount": 500})

    sent = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/send", headers=headers, json={})
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["revisionStatus"] == "SENT"

    revision = await client.post(f"/api/v1/quotations/{created['id']}/revisions", headers=headers, json={})
    assert revision.status_code == 201, revision.text
    assert revision.json()["data"]["revisionNo"] >= 2
    assert revision.json()["data"]["status"] == "Draft"

    history = await client.get(f"/api/v1/quotations/{created['id']}/revisions", headers=headers)
    assert history.status_code == 200, history.text
    items = history.json()["data"]
    assert [row["revisionNo"] for row in items] == sorted([row["revisionNo"] for row in items], reverse=True)
    statuses = {row["revisionNo"]: row["rawStatus"] for row in items}
    assert statuses[1] == "SENT", "the original sent revision must be preserved"
    assert statuses[items[0]["revisionNo"]] == "DRAFT"
    assert items[0]["isCurrent"] is True


async def test_delete_is_blocked_once_quotation_has_service_order(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"], "amount": 750})

    sent = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/send", headers=headers, json={})
    assert sent.status_code == 200, sent.text
    accepted = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/accept", headers=headers, json={})
    assert accepted.status_code == 200, accepted.text
    converted = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text

    blocked = await client.request(
        "DELETE", "/api/v1/quotations", headers=headers, json={"ids": [created["id"]]}
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "QUOTATION_HAS_SERVICE_ORDER"


async def test_draft_quotation_can_be_deleted(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"]})

    removed = await client.request(
        "DELETE", "/api/v1/quotations", headers=headers, json={"ids": [created["id"]]}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 1

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 404, fetched.text


async def _accepted_order(client, headers, pricing_lines: list[dict] | None = None) -> tuple[dict, str]:
    """Create, accept and convert a quotation; return (quotation, order id)."""
    created = await _create_quotation(
        client,
        headers,
        {
            "customer": "Re-quote Customer",
            "places": [
                {"placeRole": "ORIGIN", "place": "Bangkok"},
                {"placeRole": "DESTINATION", "place": "Phnom Penh"},
            ],
            "containerRequirements": [
                {"containerType": "40HC", "quantity": 2, "grossWeightKg": 15250.5, "remarks": "Reefer"},
            ],
            "pricingLines": pricing_lines
            if pricing_lines is not None
            else [
                {
                    "description": "Ocean freight",
                    "quantity": 2,
                    "unitPrice": 100,
                    "unit": "CTR",
                    "discount": 10,
                    "tax": 5,
                }
            ],
        },
    )
    revision_id = created["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})).status_code == 200
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    return created, converted.json()["data"]["serviceOrderId"]


async def test_requotation_from_a_service_order_creates_a_new_draft(client):
    headers = await login(client)
    quotation, order_id = await _accepted_order(client, headers)

    created = await client.post(f"/api/v1/quotations/from-service-order/{order_id}", headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()["data"]

    assert body["id"] != quotation["id"], "a re-quotation is a new record, not a revision of the old one"
    assert body["rawStatus"] == "DRAFT"
    assert body["sourceServiceOrderId"] == order_id
    assert body["sourceServiceOrderNo"]
    assert body["customerPartyId"] == quotation["customerPartyId"]
    assert body["currency"] == "USD"

    lines = body.get("pricingLines") or []
    assert len(lines) == 1, body
    assert lines[0]["description"] == "Ocean freight"
    assert float(lines[0]["quantity"]) == 2
    assert float(lines[0]["unitPrice"]) == 100

    places = body.get("places") or []
    assert [row["place"] for row in places] == ["Bangkok", "Phnom Penh"], places
    assert {row["placeRole"] for row in places} == {"Origin", "Destination"}

    containers = body.get("containerRequirements") or []
    assert len(containers) == 1, containers
    assert containers[0]["containerTypeId"].isdigit()
    assert float(containers[0]["quantity"]) == 2
    assert float(containers[0]["grossWeightKg"]) == 15250.5
    assert containers[0]["remarks"] == "Reefer"
    # 2 x 100 - 10 discount + 5 tax, carried across unchanged.
    assert float(body["total"]) == 195.0

    original = await client.get(f"/api/v1/quotations/{quotation['id']}", headers=headers)
    assert original.status_code == 200, original.text
    assert original.json()["data"]["rawStatus"] == "CONVERTED"


async def test_requotation_leaves_the_service_order_untouched(client):
    headers = await login(client)
    _, order_id = await _accepted_order(client, headers)

    before = await client.get(f"/api/v1/service-orders/{order_id}", headers=headers)
    assert before.status_code == 200, before.text

    created = await client.post(f"/api/v1/quotations/from-service-order/{order_id}", headers=headers)
    assert created.status_code == 201, created.text

    after = await client.get(f"/api/v1/service-orders/{order_id}", headers=headers)
    assert after.status_code == 200, after.text
    # Byte-identical: a re-quotation reads the order and changes nothing on it.
    assert after.json()["data"] == before.json()["data"]


async def test_requotation_needs_a_real_service_order(client):
    headers = await login(client)

    response = await client.post("/api/v1/quotations/from-service-order/999999", headers=headers)
    assert response.status_code == 404, response.text


async def test_requotation_is_refused_without_the_permission(client):
    headers = await login(client)
    _, order_id = await _accepted_order(client, headers)
    finance_headers = await login(client, "finance")

    denied = await client.post(f"/api/v1/quotations/from-service-order/{order_id}", headers=finance_headers)
    assert denied.status_code == 403, denied.text


async def test_container_requirements_are_persisted_and_returned(client, session_factory):
    from sqlalchemy import select

    from app.modules.quotations.models import QuotationRevisionContainer

    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(
        client,
        headers,
        {
            "customerPartyId": party["id"],
            "containerRequirements": [
                {"containerType": "40HC", "quantity": 2, "grossWeightKg": 15250.5, "remarks": "One reefer"},
            ],
        },
    )

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    rows = fetched.json()["data"]["containerRequirements"]
    assert len(rows) == 1, rows
    assert rows[0]["quantity"] in (2, "2", 2.0, "2.000")
    assert float(rows[0]["grossWeightKg"]) == 15250.5
    assert rows[0]["remarks"] == "One reefer"

    # The API echo is not proof of persistence: the revision child table is what
    # a clone, a print and a re-quotation read.
    async with session_factory() as session:
        stored = (
            await session.execute(
                select(QuotationRevisionContainer).where(
                    QuotationRevisionContainer.quotation_revision_id == int(created["revisionId"])
                )
            )
        ).scalars().all()
    assert len(stored) == 1, stored
    assert float(stored[0].quantity) == 2
    assert float(stored[0].gross_weight_kg) == 15250.5
    assert stored[0].remarks == "One reefer"


async def test_only_an_accepted_revision_can_be_converted(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"]})

    refused = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/convert", headers=headers, json={})
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "INVALID_STATE_TRANSITION"

    finance_headers = await login(client, "finance")
    denied = await client.post(f"/api/v1/quotation-revisions/{created['revisionId']}/convert", headers=finance_headers, json={})
    assert denied.status_code == 403, denied.text


async def test_conversion_replays_the_same_idempotency_key(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"], "amount": 300})
    revision_id = created["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})).status_code == 200

    key = {"Idempotency-Key": "convert-replay-1", **headers}
    first = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=key, json={})
    assert first.status_code == 201, first.text
    replay = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=key, json={})

    assert replay.status_code == 201, replay.text
    assert replay.json()["data"]["serviceOrderId"] == first.json()["data"]["serviceOrderId"]


async def test_submitted_workflow_converts_without_send_or_accept(client):
    """DRAFT -> SUBMITTED -> CONVERTED is the whole active workflow.

    Submit is idempotent, conversion runs straight from SUBMITTED (no Sent or
    Accepted step any more), and a repeated conversion is still refused.
    """
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"]})

    submitted = await client.post(
        f"/api/v1/quotation-revisions/{created['revisionId']}/submit", headers=headers, json={}
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "Submitted"
    assert submitted.json()["data"]["revisionStatus"] == "SUBMITTED"

    # A repeated submission is a replay, not a second transition.
    replayed = await client.post(
        f"/api/v1/quotation-revisions/{created['revisionId']}/submit", headers=headers, json={}
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["revisionStatus"] == "SUBMITTED"

    converted = await client.post(
        f"/api/v1/quotation-revisions/{created['revisionId']}/convert", headers=headers, json={}
    )
    assert converted.status_code == 201, converted.text
    assert converted.json()["data"]["status"] == "Converted"

    duplicate = await client.post(
        f"/api/v1/quotation-revisions/{created['revisionId']}/convert", headers=headers, json={}
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_CONVERSION"


async def test_submit_and_convert_need_their_permissions(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"]})
    viewer = await login(client, "ops.pp")

    refused = await client.post(
        f"/api/v1/quotation-revisions/{created['revisionId']}/submit", headers=viewer, json={}
    )
    assert refused.status_code == 403, refused.text

    # The published policy is filtered to the caller, so the row menu offers
    # nothing a view-only account could run.
    policy = (await client.get("/api/v1/quotations/status-policy", headers=viewer)).json()["data"]
    assert policy["transitions"] == {}

    fetched = await client.get(f"/api/v1/quotations/{created['id']}", headers=headers)
    assert fetched.json()["data"]["status"] == "Draft"


async def test_a_submitted_revision_rejects_other_transitions(client):
    headers = await login(client)
    party = await _first_party(client, headers, role="Customer")
    created = await _create_quotation(client, headers, {"customerPartyId": party["id"]})
    revision_id = created["revisionId"]
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/submit", headers=headers, json={})

    # A submitted revision is frozen: only convert (or cancel/legacy send-accept
    # paths) run on it; editing in place is refused by the same immutability rule.
    sent = await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    assert sent.status_code == 409, sent.text

    # Editing in place is refused: the immutability rule clones a fresh draft
    # revision instead of touching the submitted (historical) one.
    edited = await client.put(f"/api/v1/quotations/{created['id']}", headers=headers, json={"description": "x"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["revisionStatus"] == "DRAFT"
