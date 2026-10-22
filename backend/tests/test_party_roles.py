"""Dynamic Party Roles and the business-party role assignment.

Party Roles replace the hardcoded Customer/Supplier/Company dropdown. The role
vocabulary is configuration data, assignments are a many-to-many relation, and a
role that a party still holds is deactivated rather than deleted.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _role(client, headers, code: str, name: str, **extra) -> dict:
    response = await client.post(
        "/api/v1/partyRoles",
        headers=headers,
        json={"code": code, "name": name, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _party(client, headers, code: str, **extra) -> dict:
    response = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": code, "legalName": f"Party {code}", **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_party_role_crud_search_filter_and_unique_code_and_name(client):
    headers = await login(client)
    first = await _role(client, headers, "shipper", "Shipper")
    await _role(client, headers, "CONSIGNEE", "Consignee")

    # Codes are upper-cased; a lower-case spelling is the same code.
    duplicate_code = await client.post(
        "/api/v1/partyRoles", headers=headers, json={"code": "SHIPPER", "name": "Different Name"}
    )
    assert duplicate_code.status_code == 422, duplicate_code.text
    assert "code" in duplicate_code.json()["field_errors"]

    duplicate_name = await client.post(
        "/api/v1/partyRoles", headers=headers, json={"code": "OTHER_CODE", "name": "Shipper"}
    )
    assert duplicate_name.status_code == 422, duplicate_name.text
    assert "name" in duplicate_name.json()["field_errors"]

    updated = await client.put(
        f"/api/v1/partyRoles/{first['id']}",
        headers=headers,
        json={"name": "Exporter", "description": "Ships the goods.", "status": "INACTIVE"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Exporter"
    assert updated.json()["data"]["status"] == "INACTIVE"

    searched = await client.get("/api/v1/partyRoles", headers=headers, params={"q": "Exporter"})
    assert [row["code"] for row in searched.json()["data"]["items"]] == ["SHIPPER"]

    inactive = await client.get("/api/v1/partyRoles", headers=headers, params={"status": "INACTIVE"})
    assert all(row["status"] == "INACTIVE" for row in inactive.json()["data"]["items"])
    assert "SHIPPER" in [row["code"] for row in inactive.json()["data"]["items"]]

    listed = await client.get("/api/v1/partyRoles", headers=headers, params={"page_size": 200})
    names = [row["name"] for row in listed.json()["data"]["items"]]
    assert names.index("Consignee") < names.index("Exporter"), "default order is by name"


async def test_party_role_status_policy_and_deactivation(client):
    headers = await login(client)
    role = await _role(client, headers, "STATUS_ROLE", "Status Role")

    policy = await client.get("/api/v1/partyRoles/status-policy", headers=headers)
    assert policy.status_code == 200, policy.text
    body = policy.json()["data"]
    assert body["statuses"] == ["ACTIVE", "INACTIVE"]
    assert body["transitions"]["ACTIVE"][0]["to"] == "INACTIVE"

    changed = await client.post(
        f"/api/v1/partyRoles/{role['id']}/status",
        headers=headers,
        json={"status": "INACTIVE"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["status"] == "INACTIVE"


async def test_party_role_writes_require_permission(client):
    headers = await login(client)
    sales = await login(client, "sales")

    denied = await client.post(
        "/api/v1/partyRoles", headers=sales, json={"code": "DENIED_ROLE", "name": "Denied Role"}
    )
    assert denied.status_code == 403, denied.text

    role = await _role(client, headers, "PERM_ROLE", "Permission Role")
    denied_update = await client.put(
        f"/api/v1/partyRoles/{role['id']}", headers=sales, json={"name": "Escalated"}
    )
    assert denied_update.status_code == 403, denied_update.text
    denied_delete = await client.delete(f"/api/v1/partyRoles/{role['id']}", headers=sales)
    assert denied_delete.status_code == 403, denied_delete.text

    # Active records are never deleted; deactivate, then archive.
    blocked = await client.delete(f"/api/v1/partyRoles/{role['id']}", headers=headers)
    assert blocked.status_code == 409, blocked.text
    await client.put(f"/api/v1/partyRoles/{role['id']}", headers=headers, json={"status": "INACTIVE"})
    archived = await client.delete(f"/api/v1/partyRoles/{role['id']}", headers=headers)
    assert archived.status_code == 200, archived.text


async def test_party_holds_several_roles_and_a_rename_is_reflected_everywhere(client):
    headers = await login(client)
    customer = await _role(client, headers, "BUYER", "Buyer")
    supplier = await _role(client, headers, "VENDOR", "Vendor")

    party = await _party(
        client,
        headers,
        "ROLE-PARTY-1",
        roleIds=[customer["id"], customer["id"], supplier["id"]],
    )
    # Duplicate ids are collapsed, and names come back for display.
    assert party["roles"] == ["Buyer", "Vendor"]
    assert party["roleIds"] == [customer["id"], supplier["id"]]

    fetched = await client.get(f"/api/v1/businessParties/{party['id']}", headers=headers)
    assert fetched.json()["data"]["roles"] == ["Buyer", "Vendor"]
    assert fetched.json()["data"]["roleIds"] == [customer["id"], supplier["id"]]

    renamed = await client.put(
        f"/api/v1/partyRoles/{customer['id']}", headers=headers, json={"name": "Consignee"}
    )
    assert renamed.status_code == 200, renamed.text
    after_rename = await client.get(f"/api/v1/businessParties/{party['id']}", headers=headers)
    assert after_rename.json()["data"]["roles"] == ["Consignee", "Vendor"]

    # Replace the assignment from the form.
    replaced = await client.put(
        f"/api/v1/businessParties/{party['id']}",
        headers=headers,
        json={"roleIds": [supplier["id"]]},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["roles"] == ["Vendor"]

    # The pre-migration payload (role names) keeps working.
    legacy = await _party(client, headers, "ROLE-PARTY-2", roles=["Customer"])
    assert legacy["roles"] == ["Customer"]
    assert len(legacy["roleIds"]) == 1

    unknown = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "ROLE-PARTY-3", "legalName": "Unknown Role", "roleIds": ["999999"]},
    )
    assert unknown.status_code == 422, unknown.text
    assert "roleIds" in unknown.json()["field_errors"]

    empty = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "ROLE-PARTY-4", "legalName": "No Role", "roleIds": []},
    )
    assert empty.status_code == 422, empty.text
    assert "roleIds" in empty.json()["field_errors"]


async def test_assigned_role_cannot_be_deleted_even_when_inactive(client):
    headers = await login(client)
    role = await _role(client, headers, "IN_USE_ROLE", "In Use Role")
    other = await _role(client, headers, "SPARE_ROLE", "Spare Role")
    party = await _party(client, headers, "ROLE-PARTY-5", roleIds=[role["id"]])

    await client.put(f"/api/v1/partyRoles/{role['id']}", headers=headers, json={"status": "INACTIVE"})
    # The inactive role is still readable on the party.
    still = await client.get(f"/api/v1/businessParties/{party['id']}", headers=headers)
    assert still.json()["data"]["roles"] == ["In Use Role"]

    blocked = await client.delete(f"/api/v1/partyRoles/{role['id']}", headers=headers)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "PARTY_ROLE_IN_USE"

    swapped = await client.put(
        f"/api/v1/businessParties/{party['id']}", headers=headers, json={"roleIds": [other["id"]]}
    )
    assert swapped.status_code == 200, swapped.text
    archived = await client.delete(f"/api/v1/partyRoles/{role['id']}", headers=headers)
    assert archived.status_code == 200, archived.text
