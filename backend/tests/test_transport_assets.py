"""Transport Assets: the identity dropdown, the master-data references, and the
uniqueness rules that guard an asset code.

The form (``/master-data/transport-assets``) backs ``transportType``, ``ownerParty``
and ``operatorParty`` with the Transport Types and Business Parties masters, and
offers ``identityType`` as a closed dropdown. These tests pin the contract that
makes those dropdowns safe to use: every value they can produce is accepted, and
anything they cannot produce is refused on the named field rather than as a
constraint error the operator cannot act on.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _create(client, headers, payload: dict, *, expect: int = 201):
    response = await client.post("/api/v1/transportAssets", json=payload, headers=headers)
    assert response.status_code == expect, response.text
    return response.json()["data"] if expect < 400 else response.json()


async def _create_party(client, headers, name: str, roles: list[str]) -> dict:
    response = await client.post(
        "/api/v1/businessParties",
        json={"partyCode": f"TP-{name[:8].upper().replace(' ', '-')}", "legalName": name, "roles": roles, "status": "ACTIVE"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_create_reads_back_every_field_the_form_sends(client):
    """A record written through the dropdowns comes back ready to edit.

    ``transportType`` and the two party fields are stored as foreign keys but read
    back out by name, which is exactly what the select shows, so a reopened form
    shows the chosen records instead of blank dropdowns.
    """
    headers = await login(client)
    owner = await _create_party(client, headers, "Plate Owner Ltd.", ["Supplier"])
    operator = await _create_party(client, headers, "Plate Operator Ltd.", ["Supplier"])

    created = await _create(client, headers, {
        "assetCode": "TRK-9001",
        "transportType": "Truck",
        "identity": "3C-9088",
        "identityType": "License Plate",
        "ownerParty": owner["legalName"],
        "operatorParty": operator["legalName"],
        "description": "40T tractor head",
        "status": "ACTIVE",
    })

    assert created["assetCode"] == "TRK-9001"
    assert created["identity"] == "3C-9088"
    assert created["identityType"] == "License Plate"
    assert created["transportType"] == "Truck"
    assert created["ownerParty"] == "Plate Owner Ltd."
    assert created["operatorParty"] == "Plate Operator Ltd."

    fetched = await client.get(f"/api/v1/transportAssets/{created['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    for key, expected in [
        ("assetCode", "TRK-9001"),
        ("identity", "3C-9088"),
        ("identityType", "License Plate"),
        ("transportType", "Truck"),
        ("ownerParty", "Plate Owner Ltd."),
        ("operatorParty", "Plate Operator Ltd."),
    ]:
        assert data[key] == expected, f"{key} must survive a create/read round trip"


async def test_every_identity_type_the_dropdown_offers_is_accepted(client):
    """The dropdown is the whole vocabulary; nothing it offers may be refused."""
    headers = await login(client)
    for index, identity_type in enumerate(["License Plate", "IMO Number", "Flight Number", "Other"]):
        created = await _create(client, headers, {
            "assetCode": f"TRK-ID-{index}",
            "transportType": "Vessel" if index == 1 else "Truck",
            "identity": f"IDENTITY-{index}",
            "identityType": identity_type,
            "status": "ACTIVE",
        })
        assert created["identityType"] == identity_type


async def test_a_legacy_identity_type_code_is_normalised_on_write(client):
    """Rows written by an older build keep loading and editing without a migration.

    ``identity_type`` used to default to ``PLATE`` and the column description
    offered ``PLATE``/``IMO``/``TAIL``/``REGISTRATION``. Those are accepted on
    write and stored as the canonical dropdown value, so an existing row is
    normalised the first time it is saved instead of showing an unknown option.
    """
    headers = await login(client)
    legacy = [
        ("PLATE", "License Plate"),
        ("IMO", "IMO Number"),
        ("TAIL", "Flight Number"),
        ("REGISTRATION", "Other"),
    ]
    for index, (supplied, canonical) in enumerate(legacy):
        created = await _create(client, headers, {
            "assetCode": f"TRK-LEG-{index}",
            "transportType": "Truck",
            "identity": f"LEGACY-{index}",
            "identityType": supplied,
            "status": "ACTIVE",
        })
        assert created["identityType"] == canonical


async def test_an_unknown_identity_type_is_refused_on_the_field(client):
    headers = await login(client)
    body = await _create(client, headers, {
        "assetCode": "TRK-BAD-01",
        "transportType": "Truck",
        "identity": "3C-0000",
        "identityType": "Fingerprint",
        "status": "ACTIVE",
    }, expect=422)
    assert "identityType" in body["field_errors"]


async def test_missing_required_fields_are_named_instead_of_failing_a_constraint(client):
    """A blank required field must reach the form as a field error.

    ``asset_code``, ``transport_type_id`` and ``identity`` are ``NOT NULL``. Left
    to the database the rejection arrives as an integrity error with no field
    attached, which the form cannot place under an input.
    """
    headers = await login(client)
    body = await _create(client, headers, {"status": "ACTIVE"}, expect=422)
    assert set(body["field_errors"]) == {"assetCode", "transportType", "identity"}

    blank = await _create(client, headers, {
        "assetCode": "   ",
        "transportType": "",
        "identity": "  ",
        "status": "ACTIVE",
    }, expect=422)
    assert set(blank["field_errors"]) == {"assetCode", "transportType", "identity"}


async def test_duplicate_asset_code_is_refused_on_the_asset_code_field(client):
    headers = await login(client)
    payload = {"assetCode": "TRK-DUP-01", "transportType": "Truck", "identity": "3C-1111", "status": "ACTIVE"}
    await _create(client, headers, payload)

    clash = await _create(client, headers, {**payload, "identity": "3C-2222"}, expect=422)
    assert "assetCode" in clash["field_errors"]


async def test_a_whitespace_padded_asset_code_still_collides(client):
    """The unique index compares the stored column, so the code is trimmed first.

    Without trimming ``"TRK-TRIM-01"`` and ``" TRK-TRIM-01 "`` are two distinct
    rows that read as the same code in the list.
    """
    headers = await login(client)
    await _create(client, headers, {
        "assetCode": "TRK-TRIM-01", "transportType": "Truck", "identity": "3C-3333", "status": "ACTIVE",
    })
    clash = await _create(client, headers, {
        "assetCode": "  TRK-TRIM-01  ", "transportType": "Truck", "identity": "3C-4444", "status": "ACTIVE",
    }, expect=422)
    assert "assetCode" in clash["field_errors"]


async def test_duplicate_identity_within_a_transport_type_is_refused(client):
    """``uq_transport_assets_type_identity_active`` guards (transport type, identity)."""
    headers = await login(client)
    await _create(client, headers, {
        "assetCode": "TRK-IDD-01", "transportType": "Truck", "identity": "3C-5555", "status": "ACTIVE",
    })
    clash = await _create(client, headers, {
        "assetCode": "TRK-IDD-02", "transportType": "Truck", "identity": "3C-5555", "status": "ACTIVE",
    }, expect=422)
    assert "identity" in clash["field_errors"]

    # The same identity under a different transport type is a different asset.
    await _create(client, headers, {
        "assetCode": "TRK-IDD-03", "transportType": "Vessel", "identity": "3C-5555", "status": "ACTIVE",
    })


async def test_editing_an_asset_is_a_partial_save_and_still_guards_the_code(client):
    """Edit keeps the fields it does not touch, and refuses a taken code.

    The form submits the whole record, but the endpoint must not depend on that:
    a partial update that omits a required field falls back to the stored value,
    and one that sets a code another row already owns is refused on the field.
    """
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-EDIT-01",
        "transportType": "Truck",
        "identity": "3C-6666",
        "identityType": "License Plate",
        "status": "ACTIVE",
    })
    await _create(client, headers, {
        "assetCode": "TRK-EDIT-02", "transportType": "Truck", "identity": "3C-7777", "status": "ACTIVE",
    })

    renamed = await client.put(
        f"/api/v1/transportAssets/{created['id']}",
        json={"assetCode": "TRK-EDIT-01B"},
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text
    data = renamed.json()["data"]
    assert data["assetCode"] == "TRK-EDIT-01B"
    assert data["identity"] == "3C-6666", "an omitted field must keep its stored value"
    assert data["identityType"] == "License Plate"
    assert data["transportType"] == "Truck"

    clash = await client.put(
        f"/api/v1/transportAssets/{created['id']}",
        json={"assetCode": "TRK-EDIT-02"},
        headers=headers,
    )
    assert clash.status_code == 422, clash.text
    assert "assetCode" in clash.json()["field_errors"]


async def test_editing_normalises_a_legacy_identity_type(client):
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-EDIT-03", "transportType": "Truck", "identity": "3C-8888",
        "identityType": "IMO", "status": "ACTIVE",
    })
    assert created["identityType"] == "IMO Number"

    updated = await client.put(
        f"/api/v1/transportAssets/{created['id']}",
        json={"identityType": "Flight Number"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["identityType"] == "Flight Number"


async def test_an_asset_without_an_identity_type_falls_back_to_the_default(client):
    """Not required: a caller that omits it gets the default, never a NULL column."""
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-DEF-01", "transportType": "Truck", "identity": "3C-9999", "status": "ACTIVE",
    })
    assert created["identityType"] == "License Plate"