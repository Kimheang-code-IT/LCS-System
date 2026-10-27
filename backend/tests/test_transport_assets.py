"""Transport Assets: the identity vocabulary and the master-data references, and
the uniqueness rules that guard an asset code.

The form (``/master-data/transport-assets``) backs ``transportType``, ``ownerParty``
and ``operatorParty`` with the Transport Types and Business Parties masters, and
offers ``identityType`` from the administrator-managed Asset Identity Types
master. The tests pin the contract that makes those dropdowns safe to use:
every value the configured vocabulary can produce is accepted, applicability and
patterns are reported on the named field, and duplicates never reach a
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


async def test_every_identity_type_the_vocabulary_ships_is_accepted(client):
    """Every seeded identity type fits the transport types it is linked to."""
    headers = await login(client)
    fixtures = [
        ("License Plate", "Truck"),
        ("Chassis Number", "Truck"),
        ("Fleet Number", "Truck"),
        ("IMO Number", "Vessel"),
        ("Vessel Registration", "Vessel"),
        ("Aircraft Registration", "Air"),
        ("Flight Number", "Air"),
        ("Rail Vehicle Number", "Rail"),
        ("Other", "Truck"),  # unlinked vocabulary fits every transport type
    ]
    for index, (identity_type, transport_type) in enumerate(fixtures):
        created = await _create(client, headers, {
            "assetCode": f"TRK-ID-{index}",
            "transportType": transport_type,
            "identity": "2245100" if identity_type == "IMO Number" else f"IDENTITY-{index}",
            "identityType": identity_type,
            "status": "ACTIVE",
        })
        assert created["identityType"] == identity_type


async def test_an_identity_type_outside_its_transport_type_is_refused_on_the_field(client):
    """A road identity type does not describe a vessel, and vice versa.

    The seeded rows link each option to the transport types it applies to, so a
    mismatched pair is reported on ``identityType`` where the operator chooses.
    """
    headers = await login(client)
    body = await _create(client, headers, {
        "assetCode": "TRK-MODE-01",
        "transportType": "Vessel",
        "identity": "3C-0001",
        "identityType": "License Plate",
        "status": "ACTIVE",
    }, expect=422)
    assert "identityType" in body["field_errors"]
    assert "License Plate" in body["field_errors"]["identityType"]

    # The same option is accepted once the transport type agrees.
    await _create(client, headers, {
        "assetCode": "TRK-MODE-02", "transportType": "Truck", "identity": "3C-0002",
        "identityType": "License Plate", "status": "ACTIVE",
    })


async def test_the_identity_pattern_from_the_vocabulary_is_enforced(client):
    """An IMO number is seven digits, which the IMO row's pattern encodes."""
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-PAT-01", "transportType": "Vessel", "identity": "9991234",
        "identityType": "IMO Number", "status": "ACTIVE",
    })
    assert created["identity"] == "9991234"

    body = await _create(client, headers, {
        "assetCode": "TRK-PAT-02", "transportType": "Vessel", "identity": "IMO-9991234",
        "identityType": "IMO Number", "status": "ACTIVE",
    }, expect=422)
    assert "identity" in body["field_errors"]


async def test_a_legacy_identity_type_code_is_normalised_on_write(client):
    """Rows written by an older build keep loading and editing without a migration.

    ``identity_type`` used to default to ``PLATE`` and the column description
    offered ``PLATE``/``IMO``/``TAIL``/``REGISTRATION``. Those are accepted on
    write and stored as the canonical dropdown value, so an existing row is
    normalised the first time it is saved instead of showing an unknown option.
    """
    headers = await login(client)
    legacy = [
        ("PLATE", "License Plate", "Truck"),
        ("IMO", "IMO Number", "Vessel"),
        ("TAIL", "Flight Number", "Air"),
        ("REGISTRATION", "Other", "Truck"),
    ]
    for index, (supplied, canonical, transport_type) in enumerate(legacy):
        created = await _create(client, headers, {
            "assetCode": f"TRK-LEG-{index}",
            "transportType": transport_type,
            "identity": "9234561" if supplied == "IMO" else f"LEGACY-{index}",
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
    # (An explicit type: the Truck default last time; here Vessel's default, IMO
    # Number, comes with a digit-only pattern that plain "3C-5555" may not satisfy.)
    await _create(client, headers, {
        "assetCode": "TRK-IDD-03", "transportType": "Vessel", "identity": "3C-5555",
        "identityType": "Vessel Registration", "status": "ACTIVE",
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
        "assetCode": "TRK-EDIT-03", "transportType": "Vessel", "identity": "7788990",
        "identityType": "IMO", "status": "ACTIVE",
    })
    assert created["identityType"] == "IMO Number"

    updated = await client.put(
        f"/api/v1/transportAssets/{created['id']}",
        json={"identityType": "Vessel Registration", "identity": "KH-VSL-001"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["identityType"] == "Vessel Registration"


async def test_an_asset_without_an_identity_type_falls_back_to_the_default(client):
    """Not required: a caller that omits it gets the default, never a NULL column."""
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-DEF-01", "transportType": "Truck", "identity": "3C-9999", "status": "ACTIVE",
    })
    assert created["identityType"] == "License Plate"


async def test_the_optional_name_and_capacity_round_trip(client):
    """New optional fields persist, edit and answer exactly what was stored."""
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-CAP-01",
        "transportType": "Truck",
        "identity": "3C-5000",
        "assetName": "Phnom Penh Hauler 01",
        "capacityValue": 22.5,
        "capacityUnit": "KG",
        "status": "ACTIVE",
    })
    assert created["assetName"] == "Phnom Penh Hauler 01"
    assert created["capacity"] == "22.5 KG"

    fetched = await client.get(f"/api/v1/transportAssets/{created['id']}", headers=headers)
    data = fetched.json()["data"]
    assert data["assetName"] == "Phnom Penh Hauler 01"
    assert data["capacityUnit"] == "KG"

    renamed = await client.put(
        f"/api/v1/transportAssets/{created['id']}",
        json={"assetCode": "TRK-CAP-01B"},
        headers=headers,
    )
    assert renamed.json()["data"]["assetName"] == "Phnom Penh Hauler 01", "a partial save keeps the name"

    body = await _create(client, headers, {
        "assetCode": "TRK-CAP-02", "transportType": "Truck", "identity": "3C-5001",
        "capacityValue": -1, "status": "ACTIVE",
    }, expect=422)
    assert "capacityValue" in body["field_errors"]


async def test_maintenance_is_a_valid_asset_status(client):
    """The row menu can park an asset for repairs; the field accepts it."""
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-MNT-01", "transportType": "Truck", "identity": "3C-6000",
        "status": "MAINTENANCE",
    })
    assert created["status"] == "MAINTENANCE"

    moved = await client.post(
        f"/api/v1/transportAssets/{created['id']}/status",
        json={"status": "MAINTENANCE"},
        headers=headers,
    )
    assert moved.status_code == 200, moved.text

    # Transitions live on the status-policy endpoint, not on the change payload.
    policy = await client.get("/api/v1/transportAssets/status-policy", headers=headers)
    body = policy.json()["data"]
    statuses = set(body["statuses"])
    assert statuses == {"ACTIVE", "INACTIVE", "MAINTENANCE"}
    targets = {item["to"] for item in body["transitions"]["MAINTENANCE"]}
    assert {"ACTIVE", "INACTIVE"} <= targets


async def test_identity_types_are_master_data_the_assets_form_reads(client):
    """The new collection carries CRUD, the transport-type link and duplicates."""
    headers = await login(client)

    created = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Container Number", "transportType": "Truck", "status": "ACTIVE"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["transportType"] == "Truck"
    assert data["identityLabel"] is None

    listed = await client.get("/api/v1/transportAssetIdentityTypes", headers=headers)
    rows = listed.json()["data"]["items"]
    names = {row["name"] for row in rows}
    assert {"License Plate", "IMO Number", "Other"} <= names
    assert any(row["name"] == "Container Number" and row["transportType"] == "Truck" for row in rows)

    duplicate = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Container Number", "status": "ACTIVE"},
        headers=headers,
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "name" in duplicate.json()["field_errors"]

    updated = await client.put(
        f"/api/v1/transportAssetIdentityTypes/{data['id']}",
        json={"identityLabel": "Container No.", "validationPattern": "^[A-Z]{4}\\d{7}$"},
        headers=headers,
    )
    assert updated.json()["data"]["identityLabel"] == "Container No."

    removed = await client.delete(
        f"/api/v1/transportAssetIdentityTypes/{data['id']}",
        headers=headers,
    )
    assert removed.status_code == 409, removed.text  # active rows are deactivated first

    deactivated = await client.post(
        f"/api/v1/transportAssetIdentityTypes/{data['id']}/status",
        json={"status": "MAINTENANCE"},
        headers=headers,
    )
    assert deactivated.status_code == 422, deactivated.text  # the vocabulary has only two states


async def test_capacity_units_are_master_data_and_the_asset_select_reads_them(client):
    """Capacity units are a small administrator-edited list, seeded like the roles.

    The asset capacity select offers only ACTIVE rows; a duplicate code is
    refused on the field so the list can never drift into two KG rows.
    """
    headers = await login(client)

    listed = await client.get("/api/v1/capacityUnits", headers=headers)
    assert listed.status_code == 200, listed.text
    seeded = {row["code"] for row in listed.json()["data"]["items"]}
    assert {"PCS", "KG", "CBM", "CTN", "PAL"} <= seeded

    created = await client.post(
        "/api/v1/capacityUnits",
        json={"code": "PAX", "name": "Passengers", "status": "ACTIVE"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["code"] == "PAX"

    duplicate = await client.post(
        "/api/v1/capacityUnits",
        json={"code": "PAX", "name": "People", "status": "ACTIVE"},
        headers=headers,
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "code" in duplicate.json()["field_errors"]

    renamed = await client.put(
        f"/api/v1/capacityUnits/{created.json()['data']['id']}",
        json={"name": "Carton Boxes"},
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == "Carton Boxes"

    # The list has two states only, even when the status is set directly.
    bad_status = await client.put(
        f"/api/v1/capacityUnits/{created.json()['data']['id']}",
        json={"status": "MAINTENANCE"},
        headers=headers,
    )
    assert bad_status.status_code == 422, bad_status.text


async def test_capacity_value_and_unit_travel_together(client):
    """A capacity value without a unit — or the reverse — is refused.

    Capacity stays optional as a whole (both blank saves fine); the pair rule
    lands on the field that is missing, and a partial update cannot leave the
    record half-filled either.
    """
    headers = await login(client)

    rejected = await _create(client, headers, {
        "assetCode": "TRK-CAP-01",
        "transportType": "Truck",
        "identity": "3C-7070",
        "capacityValue": 24500,
        "status": "ACTIVE",
    }, expect=422)
    assert "capacityUnit" in rejected["field_errors"]

    rejected_unit = await _create(client, headers, {
        "assetCode": "TRK-CAP-02",
        "transportType": "Truck",
        "identity": "3C-8080",
        "capacityUnit": "KG",
        "status": "ACTIVE",
    }, expect=422)
    assert "capacityValue" in rejected_unit["field_errors"]

    created = await _create(client, headers, {
        "assetCode": "TRK-CAP-03",
        "transportType": "Truck",
        "identity": "3C-9090",
        "capacityValue": 24500,
        "capacityUnit": "KG",
        "status": "ACTIVE",
    })
    assert created["capacity"] == "24500 KG"

    blank = await _create(client, headers, {
        "assetCode": "TRK-CAP-04",
        "transportType": "Truck",
        "identity": "3C-1110",
        "status": "ACTIVE",
    })
    assert blank["capacity"] is None

    half = await client.put(
        f"/api/v1/transportAssets/{blank['id']}",
        json={"capacityValue": 9},
        headers=headers,
    )
    assert half.status_code == 422, half.text
    assert "capacityUnit" in half.json()["field_errors"]


async def test_a_dangerous_identity_pattern_is_refused_when_the_vocabulary_is_saved(client):
    """The pattern is checked once, at save time, where the admin can fix it.

    A pattern that does not compile — or one whose nested quantifiers would make
    Python ``re`` backtrack for minutes on a bad identity value — never reaches
    the asset write path, so assets keep saving fast every time.
    """
    headers = await login(client)

    malformed = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Broken Pattern", "validationPattern": "([a-z", "status": "ACTIVE"},
        headers=headers,
    )
    assert malformed.status_code == 422, malformed.text
    assert "validationPattern" in malformed.json()["field_errors"]

    slow = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Slow Pattern", "validationPattern": "(a+)+b", "status": "ACTIVE"},
        headers=headers,
    )
    assert slow.status_code == 422, slow.text
    assert "validationPattern" in slow.json()["field_errors"]

    fine = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Simple Pattern", "validationPattern": r"^\d{3}$", "status": "ACTIVE"},
        headers=headers,
    )
    assert fine.status_code == 201, fine.text

    # Ordinary optional groups are not nested quantifiers.
    optional = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Optional Prefix", "validationPattern": r"^(?:KH-)?\d{6}$", "status": "ACTIVE"},
        headers=headers,
    )
    assert optional.status_code == 201, optional.text


async def test_a_transport_type_change_revalidates_the_identity(client):
    """Moving an asset between transport types keeps its identity — after a check.

    The stored identity value and type are preserved, so the save is refused
    with a message on ``identityType`` when the chosen type does not describe
    the new mode, and nothing is half-written.
    """
    headers = await login(client)
    asset = await _create(client, headers, {
        "assetCode": "TRK-MODE-20",
        "transportType": "Truck",
        "identity": "3C-2020",
        "identityType": "License Plate",
        "status": "ACTIVE",
    })

    refused = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"transportType": "Vessel"},
        headers=headers,
    )
    assert refused.status_code == 422, refused.text
    assert "identityType" in refused.json()["field_errors"]

    unchanged = await client.get(f"/api/v1/transportAssets/{asset['id']}", headers=headers)
    assert unchanged.json()["data"]["transportType"] == "Truck", "a refused save must not move the record"
    assert unchanged.json()["data"]["identity"] == "3C-2020"

    retyped = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"transportType": "Vessel", "identityType": "IMO Number", "identity": "2245109"},
        headers=headers,
    )
    assert retyped.status_code == 200, retyped.text
    assert retyped.json()["data"]["transportType"] == "Vessel"
    assert retyped.json()["data"]["identityType"] == "IMO Number"


async def test_an_archived_identity_type_keeps_its_assets_editable(client):
    """Vocabulary housekeeping must not brick assets that still name it.

    An archived (soft-deleted) row is dropped from the dropdown, yet the assets
    created against it keep loading and keep saving: history is preserved, so an
    unrelated partial edit passes, the form's full payload may resend the same
    stored name, and only a move to a *different* archived name is refused.
    """
    headers = await login(client)
    asset = await _create(client, headers, {
        "assetCode": "TRK-HIST-01",
        "transportType": "Truck",
        "identity": "3C-4001",
        "identityType": "Other",
        "status": "ACTIVE",
    })
    vocab = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Export Permit", "status": "ACTIVE"},
        headers=headers,
    )
    assert vocab.status_code == 201, vocab.text
    moved = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"identityType": "Export Permit", "identity": "EP-2024-01"},
        headers=headers,
    )
    assert moved.status_code == 200, moved.text

    deactivated = await client.post(
        f"/api/v1/transportAssetIdentityTypes/{vocab.json()['data']['id']}/status",
        json={"status": "INACTIVE"},
        headers=headers,
    )
    assert deactivated.status_code == 200, deactivated.text
    archived = await client.delete(
        f"/api/v1/transportAssetIdentityTypes/{vocab.json()['data']['id']}",
        headers=headers,
    )
    assert archived.status_code == 200, archived.text

    renamed = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"assetName": "Older permit truck"},
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["identityType"] == "Export Permit"

    moved_again = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"identityType": "Export Permit"},
        headers=headers,
    )
    # The form resends every field; the stored name is not a move.
    assert moved_again.status_code == 200, moved_again.text

    # A genuine move to another archived name is still refused.
    other = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={"name": "Archived Permit", "status": "ACTIVE"},
        headers=headers,
    )
    assert other.status_code == 201, other.text
    retired = await client.post(
        f"/api/v1/transportAssetIdentityTypes/{other.json()['data']['id']}/status",
        json={"status": "INACTIVE"},
        headers=headers,
    )
    assert retired.status_code == 200, retired.text
    archived_other = await client.delete(
        f"/api/v1/transportAssetIdentityTypes/{other.json()['data']['id']}",
        headers=headers,
    )
    assert archived_other.status_code == 200, archived_other.text
    refused = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"identityType": "Archived Permit"},
        headers=headers,
    )
    assert refused.status_code == 422, refused.text
    assert "identityType" in refused.json()["field_errors"]


async def test_moving_the_identity_type_revalidates_the_stored_identity(client):
    """Choosing a new type must also fit the identity already on the row.

    The form submits the typed identity too, but the endpoint cannot rely on
    that: a partial update that only moves ``identityType`` is refused when the
    stored value contradicts the new type's pattern, on the ``identity`` field.
    """
    headers = await login(client)
    asset = await _create(client, headers, {
        "assetCode": "TRK-MOVE-01",
        "transportType": "Truck",
        "identity": "FREEFORM-1",
        "identityType": "Other",
        "status": "ACTIVE",
    })
    vocab = await client.post(
        "/api/v1/transportAssetIdentityTypes",
        json={
            "name": "Bridge Number",
            "identityLabel": "Bridge Number",
            "validationPattern": r"^\d{6}$",
            "status": "ACTIVE",
        },
        headers=headers,
    )
    assert vocab.status_code == 201, vocab.text

    refused = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"identityType": "Bridge Number"},
        headers=headers,
    )
    assert refused.status_code == 422, refused.text
    assert "identity" in refused.json()["field_errors"]

    accepted = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"identityType": "Bridge Number", "identity": "654321"},
        headers=headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["identity"] == "654321"


async def test_a_duplicated_code_and_a_mismatched_type_stay_reportable(client):
    """A refusal is a 422 on a field, never a 500 from a hidden flush.

    Two problems at once (a taken code and an inapplicable type) commit in a
    known state: the pending row is not flushed by the read-only lookups inside
    the identity check, so the duplicate reaches the commit guard instead of
    raising an integrity error mid-hook.
    """
    headers = await login(client)
    await _create(client, headers, {
        "assetCode": "TRK-COLLIDE-A",
        "transportType": "Truck",
        "identity": "3C-9101",
        "status": "ACTIVE",
    })
    vessel = await _create(client, headers, {
        "assetCode": "VEH-COLLIDE-B",
        "transportType": "Vessel",
        "identity": "9991234",
        "identityType": "IMO Number",
        "status": "ACTIVE",
    })

    response = await client.put(
        f"/api/v1/transportAssets/{vessel['id']}",
        json={"assetCode": "TRK-COLLIDE-A", "identityType": "License Plate"},
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["field_errors"], response.text


async def test_a_renamed_identity_type_never_blocks_an_asset_edit(client):
    """The asset form resends every field; an unchanged stored name is not a move.

    Renaming (or archiving) a vocabulary row must leave its assets editable: the
    stored name keeps describing them until the caller actually picks a new type,
    and a full-form save that resends the old name must not 500 or 422.
    """
    headers = await login(client)
    asset = await _create(client, headers, {
        "assetCode": "TRK-RENAME-01",
        "transportType": "Truck",
        "identity": "3C-4141",
        "identityType": "License Plate",
        "status": "ACTIVE",
    })
    types = (await client.get("/api/v1/transportAssetIdentityTypes", headers=headers)).json()["data"]["items"]
    plate = next(row for row in types if row["name"] == "License Plate")
    renamed = await client.put(
        f"/api/v1/transportAssetIdentityTypes/{plate['id']}",
        json={"name": "Registration Plate"},
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text

    # The form's full payload still carries the old stored name.
    resaved = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={
            "assetCode": "TRK-RENAME-01",
            "transportType": "Truck",
            "identity": "3C-4141",
            "identityType": "License Plate",
            "status": "ACTIVE",
        },
        headers=headers,
    )
    assert resaved.status_code == 200, resaved.text
    assert resaved.json()["data"]["identityType"] == "License Plate", "the stored value is kept, never rewritten"

    # The status menu's partial save goes through the same branch.
    toggled = await client.put(
        f"/api/v1/transportAssets/{asset['id']}",
        json={"status": "INACTIVE"},
        headers=headers,
    )
    assert toggled.status_code == 200, toggled.text


async def test_a_zero_capacity_still_needs_its_unit(client):
    """The pairing rule is about presence, not truthiness: 0 is a value."""
    headers = await login(client)
    created = await _create(client, headers, {
        "assetCode": "TRK-ZERO-01",
        "transportType": "Truck",
        "identity": "3C-5151",
        "capacityValue": 0,
        "capacityUnit": "PCS",
        "status": "ACTIVE",
    })
    assert created["capacityValue"] == 0

    refused = await client.put(
        f"/api/v1/transportAssets/{created['id']}",
        json={"capacityUnit": None, "capacityValue": 0},
        headers=headers,
    )
    assert refused.status_code == 422, refused.text
    assert "capacityUnit" in refused.json()["field_errors"]


async def test_the_new_master_lists_refuse_writes_without_the_permission(client):
    """Reads keep the legacy master.reference.view fallback; writes need the family."""
    sales = await login(client, "sales")

    for collection, payload in (
        ("capacityUnits", {"code": "NOPE", "name": "Nope", "status": "ACTIVE"}),
        ("transportAssetIdentityTypes", {"name": "Nope", "status": "ACTIVE"}),
    ):
        response = await client.post(f"/api/v1/{collection}", json=payload, headers=sales)
        assert response.status_code == 403, f"{collection}: {response.text}"
