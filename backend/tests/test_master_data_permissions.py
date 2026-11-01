"""Per-screen permission matrices for the three master data screens (S01).

MOD-024 Party Roles, MOD-030 Asset Identity Types, MOD-031 Capacity Units.
The narrow accounts below are built from existing catalog codes only — the
per-screen page codes (``master.party_roles.*`` and ``master.transport_assets.*``)
and the legacy ``master.reference`` aggregate — mirroring the backend collection
guards (``master_data.router._COLLECTION_PAGE_PREFIX``) and the status policy.
``master.transport_assets.*`` covers the two vocabulary collections because they
share the transport-assets matrix page; it does not cover Party Roles.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

PASSWORD = "Passw0rd!"


async def _narrow_account(client, code: str, permissions: list[str]) -> dict:
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": code, "name": code.title(), "permissions": permissions},
    )
    assert role.status_code == 201, role.text
    username = f"user.{code.lower()}"
    user = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": username,
            "displayName": code.title(),
            "email": f"{code.lower()}@example.com",
            "password": PASSWORD,
            "roleCode": code,
        },
    )
    assert user.status_code == 201, user.text
    return await login(client, username, PASSWORD)


async def test_view_codes_per_collection_and_legacy(client):
    assets = await _narrow_account(client, "ASSET_VIEW", ["master.transport_assets.view"])
    roles = await _narrow_account(client, "PR_VIEW", ["master.party_roles.view"])
    legacy = await _narrow_account(client, "LEGACY_VIEW", ["master.reference.view"])

    # The transport-assets view code covers its two vocabulary collections...
    for base in ("transportAssets", "transportAssetIdentityTypes", "capacityUnits"):
        response = await client.get(f"/api/v1/{base}", headers=assets)
        assert response.status_code == 200, response.text
    # ...but not Party Roles, which has its own page code.
    assert (await client.get("/api/v1/partyRoles", headers=assets)).status_code == 403

    assert (await client.get("/api/v1/partyRoles", headers=roles)).status_code == 200, "party page code denied"
    for base in ("transportAssetIdentityTypes", "capacityUnits"):
        assert (await client.get(f"/api/v1/{base}", headers=roles)).status_code == 403, base

    for base in ("partyRoles", "transportAssetIdentityTypes", "capacityUnits"):
        assert (await client.get(f"/api/v1/{base}", headers=legacy)).status_code == 200, base


async def test_view_does_not_imply_create_or_manage(client):
    viewer = await _narrow_account(client, "LEGACY_VIEW_ONLY", ["master.reference.view"])

    for base in ("partyRoles", "transportAssetIdentityTypes", "capacityUnits"):
        denied = await client.post(
            f"/api/v1/{base}", headers=viewer, json={"code": "NOPE", "name": "Nope"}
        )
        assert denied.status_code == 403, f"{base}: {denied.text}"

    # The refusals left no rows behind.
    headers = await login(client)
    for base in ("partyRoles", "transportAssetIdentityTypes", "capacityUnits"):
        listed = await client.get(f"/api/v1/{base}", headers=headers)
        assert all(
            row["code" if base != "transportAssetIdentityTypes" else "name"] != "NOPE"
            for row in listed.json()["data"]["items"]
        ), base


async def test_transport_asset_action_codes_cover_the_vocabulary(client):
    assets = await _narrow_account(
        client,
        "ASSET_CRUD",
        [
            "master.transport_assets.view",
            "master.transport_assets.create",
            "master.transport_assets.update",
            "master.transport_assets.delete",
        ],
    )

    unit = await client.post(
        "/api/v1/capacityUnits", headers=assets, json={"code": "TNX", "name": "Tonnes Extra"}
    )
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["data"]["id"]
    identity = await client.post(
        "/api/v1/transportAssetIdentityTypes", headers=assets, json={"name": "AWB Number"}
    )
    assert identity.status_code == 201, identity.text
    identity_id = identity.json()["data"]["id"]

    renamed = await client.put(
        f"/api/v1/capacityUnits/{unit_id}", headers=assets, json={"name": "Tonnes"}
    )
    assert renamed.status_code == 200, renamed.text
    relabelled = await client.put(
        f"/api/v1/transportAssetIdentityTypes/{identity_id}", headers=assets, json={"identityLabel": "AWB"}
    )
    assert relabelled.status_code == 200, relabelled.text

    # Status toggles accept the screen's update code (same pattern as party roles).
    for base, item_id in (("capacityUnits", unit_id), ("transportAssetIdentityTypes", identity_id)):
        toggled = await client.post(
            f"/api/v1/{base}/{item_id}/status", headers=assets, json={"status": "INACTIVE"}
        )
        assert toggled.status_code == 200, toggled.text
        removed = await client.delete(f"/api/v1/{base}/{item_id}", headers=assets)
        assert removed.status_code == 200, removed.text

    # Active rows are still never deleted directly.
    active_identity = await client.post(
        "/api/v1/transportAssetIdentityTypes", headers=assets, json={"name": "Booking Number"}
    )
    assert active_identity.status_code == 201, active_identity.text
    blocked = await client.delete(
        f"/api/v1/transportAssetIdentityTypes/{active_identity.json()['data']['id']}", headers=assets
    )
    assert blocked.status_code == 409, blocked.text


async def test_party_role_action_codes_and_constraints(client):
    party = await _narrow_account(
        client,
        "PR_CRUD",
        [
            "master.party_roles.view",
            "master.party_roles.create",
            "master.party_roles.update",
            "master.party_roles.delete",
        ],
    )

    created = await client.post(
        "/api/v1/partyRoles", headers=party, json={"code": "TESTROLE", "name": "Test Role"}
    )
    assert created.status_code == 201, created.text
    role_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/v1/partyRoles/{role_id}", headers=party, json={"name": "Renamed Role"}
    )
    assert updated.status_code == 200, updated.text

    toggled = await client.post(
        f"/api/v1/partyRoles/{role_id}/status", headers=party, json={"status": "INACTIVE"}
    )
    assert toggled.status_code == 200, toggled.text

    removed = await client.delete(f"/api/v1/partyRoles/{role_id}", headers=party)
    assert removed.status_code == 200, removed.text

    # Active rows are still never deleted directly.
    active = await client.post(
        "/api/v1/partyRoles", headers=party, json={"code": "ACTIVEROLE", "name": "Active Role"}
    )
    assert active.status_code == 201, active.text
    blocked = await client.delete(
        f"/api/v1/partyRoles/{active.json()['data']['id']}", headers=party
    )
    assert blocked.status_code == 409, blocked.text


async def test_action_codes_do_not_cross_the_page_boundary(client):
    # Party-role codes never write the transport-asset vocabulary.
    party = await _narrow_account(
        client,
        "PR_W_ONLY",
        ["master.party_roles.view", "master.party_roles.create", "master.party_roles.update", "master.party_roles.delete"],
    )
    denied_unit = await client.post(
        "/api/v1/capacityUnits", headers=party, json={"code": "NOPE", "name": "Nope"}
    )
    assert denied_unit.status_code == 403, denied_unit.text
    denied_identity = await client.post(
        "/api/v1/transportAssetIdentityTypes", headers=party, json={"name": "Nope"}
    )
    assert denied_identity.status_code == 403, denied_identity.text