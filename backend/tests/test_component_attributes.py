"""Inline component-attribute create/update/delete contract.

The configuration grid PATCHes one cell at a time, so these tests concentrate on
the boundaries that the UI depends on: trimmed labels, field-level validation,
unknown fields refused by the request schema, duplicate codes, and archiving an
attribute that is still referenced instead of deleting it.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/component-attributes"


async def _create(client, headers, **overrides) -> dict:
    payload = {"label": "Inline Attribute", "dataType": "text", "isRequired": False, **overrides}
    response = await client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _find(client, headers, code: str) -> dict:
    response = await client.get(BASE, headers=headers, params={"page_size": 200, "include_archived": True})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["data"]["items"] if item["code"] == code)


_SUPPORTED_DATA_TYPES = [
    "text",
    "textarea",
    "number",
    "integer",
    "decimal",
    "money",
    "currency",
    "date",
    "datetime",
    "select",
    "multi_select",
    "checkbox",
    "boolean",
    "reference",
]


@pytest.mark.parametrize("data_type", _SUPPORTED_DATA_TYPES)
async def test_every_supported_data_type_can_be_configured(client, data_type):
    headers = await login(client)
    payload = {"label": f"Type {data_type}", "dataType": data_type}
    if data_type in {"select", "multi_select"}:
        payload["options"] = ["A", "B"]
    if data_type == "reference":
        payload["referenceType"] = "business_party"

    created = await _create(client, headers, **payload)
    assert created["dataType"] == data_type


async def test_create_trims_the_label_and_help_text(client):
    headers = await login(client)
    created = await _create(
        client,
        headers,
        label="  Seal Number  ",
        dataType="decimal",
        isRequired=True,
        placeholder="  Enter the seal number  ",
    )

    assert created["label"] == "Seal Number"
    assert created["code"] == "seal-number"
    assert created["dataType"] == "decimal"
    assert created["isRequired"] is True
    assert created["placeholder"] == "Enter the seal number"


async def test_create_rejects_an_empty_label_at_the_field(client):
    headers = await login(client)
    response = await client.post(BASE, headers=headers, json={"label": "   ", "dataType": "text"})

    assert response.status_code == 422, response.text
    assert "label" in response.json()["field_errors"]


async def test_create_rejects_an_unsupported_data_type(client):
    headers = await login(client)
    response = await client.post(BASE, headers=headers, json={"label": "Broken Type", "dataType": "blob"})

    assert response.status_code == 422, response.text
    assert "dataType" in response.json()["field_errors"]


async def test_integer_is_a_supported_data_type(client):
    headers = await login(client)
    created = await _create(client, headers, label="Piece Count", dataType="integer")

    assert created["dataType"] == "integer"


async def test_a_select_needs_static_options_and_options_must_be_unique(client):
    headers = await login(client)

    missing = await client.post(BASE, headers=headers, json={"label": "No Choices", "dataType": "select"})
    assert missing.status_code == 422, missing.text
    assert "options" in missing.json()["field_errors"]

    duplicate = await client.post(
        BASE,
        headers=headers,
        json={"label": "Duplicate Choices", "dataType": "select", "options": ["A", "A"]},
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "options" in duplicate.json()["field_errors"]

    created = await client.post(
        BASE,
        headers=headers,
        json={"label": "With Choices", "dataType": "select", "options": ["Open", "Closed"]},
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["options"] == ["Open", "Closed"]


async def test_a_reference_needs_a_known_master_data_source_and_can_be_cleared(client):
    headers = await login(client)

    missing = await client.post(BASE, headers=headers, json={"label": "No Source", "dataType": "reference"})
    assert missing.status_code == 422, missing.text
    assert "referenceType" in missing.json()["field_errors"]

    created = await _create(
        client, headers, label="Customer Link", dataType="reference", referenceType="business_party"
    )
    cleared_while_reference = await client.patch(
        f"{BASE}/{created['id']}", headers=headers, json={"referenceType": None}
    )
    assert cleared_while_reference.status_code == 422, cleared_while_reference.text

    switched = await client.patch(f"{BASE}/{created['id']}", headers=headers, json={"dataType": "text"})
    assert switched.status_code == 200, switched.text
    cleared = await client.patch(f"{BASE}/{created['id']}", headers=headers, json={"referenceType": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["referenceType"] is None


async def test_validation_rules_are_checked_on_the_server(client):
    headers = await login(client)

    bad_pattern = await client.post(
        BASE,
        headers=headers,
        json={"label": "Bad Pattern", "dataType": "text", "validationRules": {"pattern": "[unclosed"}},
    )
    assert bad_pattern.status_code == 422, bad_pattern.text
    assert "validationRules" in bad_pattern.json()["field_errors"]

    bad_range = await client.post(
        BASE,
        headers=headers,
        json={"label": "Bad Range", "dataType": "number", "validationRules": {"min": 10, "max": 1}},
    )
    assert bad_range.status_code == 422, bad_range.text

    created = await client.post(
        BASE,
        headers=headers,
        json={"label": "Good Range", "dataType": "number", "validationRules": {"min": 0, "max": 10}},
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["validationRules"] == {"min": 0, "max": 10}


async def test_the_explicit_code_is_validated_and_unique(client):
    headers = await login(client)
    created = await _create(client, headers, code="seal-no", label="Seal Number")

    assert created["code"] == "seal-no"
    duplicate = await client.post(BASE, headers=headers, json={"label": "Other", "code": "seal-no"})
    assert duplicate.status_code == 409, duplicate.text
    assert "code" in duplicate.json()["field_errors"]

    malformed = await client.post(BASE, headers=headers, json={"label": "Malformed", "code": "bad code!"})
    assert malformed.status_code == 422, malformed.text
    assert "code" in malformed.json()["field_errors"]


async def test_reordering_attributes_persists_the_catalog_order(client):
    headers = await login(client)
    first = await _create(client, headers, code="order-a", label="Order A")
    second = await _create(client, headers, code="order-b", label="Order B")
    third = await _create(client, headers, code="order-c", label="Order C")

    reordered = await client.post(
        f"{BASE}/reorder",
        headers=headers,
        json={"orderedIds": [third["id"], first["id"], second["id"]]},
    )
    assert reordered.status_code == 200, reordered.text
    assert [item["code"] for item in reordered.json()["data"]] == ["order-c", "order-a", "order-b"]

    listed = await client.get(BASE, headers=headers, params={"page_size": 200})
    codes = [item["code"] for item in listed.json()["data"]["items"]]
    assert codes.index("order-c") < codes.index("order-a") < codes.index("order-b")

    invalid = await client.post(f"{BASE}/reorder", headers=headers, json={"orderedIds": [first["id"], first["id"]]})
    assert invalid.status_code == 422, invalid.text


async def test_a_live_edit_does_not_change_an_already_published_version(client):
    headers = await login(client)
    created = await _create(client, headers, label="Frozen Field", dataType="text")

    groups = await client.get("/api/v1/component-groups", headers=headers, params={"page_size": 200})
    group_id = groups.json()["data"]["items"][0]["id"]
    membership = await client.post(
        f"/api/v1/component-groups/{group_id}/attributes",
        headers=headers,
        json={"attributeId": int(created["id"])},
    )
    assert membership.status_code in (200, 201), membership.text

    published = await client.post(
        "/api/v1/configuration-versions",
        headers=headers,
        json={"changeNote": "frozen field"},
    )
    assert published.status_code == 201, published.text
    version_id = published.json()["data"]["id"]

    changed = await client.patch(
        f"{BASE}/{created['id']}",
        headers=headers,
        json={"dataType": "integer", "label": "Renamed After Publish"},
    )
    assert changed.status_code == 200, changed.text

    version = await client.get(f"/api/v1/configuration-versions/{version_id}", headers=headers)
    assert version.status_code == 200, version.text
    attributes = [
        attribute
        for tab in version.json()["data"]["configSnapshot"]["tabs"]
        for group in tab["groups"]
        for attribute in group["attributes"]
    ]
    frozen = next(attribute for attribute in attributes if attribute["id"] == created["id"])
    assert frozen["dataType"] == "text"
    assert frozen["label"] == "Frozen Field"


async def test_deleting_an_attribute_referenced_by_a_published_version_archives_it(client):
    headers = await login(client)
    created = await _create(client, headers, label="Snapshot Only", dataType="text")

    groups = await client.get("/api/v1/component-groups", headers=headers, params={"page_size": 200})
    group_id = groups.json()["data"]["items"][0]["id"]
    membership = await client.post(
        f"/api/v1/component-groups/{group_id}/attributes",
        headers=headers,
        json={"attributeId": int(created["id"])},
    )
    assert membership.status_code in (200, 201), membership.text

    published = await client.post(
        "/api/v1/configuration-versions",
        headers=headers,
        json={"changeNote": "snapshot delete guard"},
    )
    assert published.status_code == 201, published.text

    removed = await client.delete(
        f"/api/v1/component-group-attributes/{membership.json()['data']['id']}", headers=headers
    )
    assert removed.status_code == 200, removed.text

    deleted = await client.delete(f"{BASE}/{created['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["archived"] is True

    archived = await _find(client, headers, created["code"])
    assert archived["status"] == "INACTIVE"


async def test_create_rejects_unknown_fields_instead_of_ignoring_them(client):
    headers = await login(client)
    response = await client.post(
        BASE,
        headers=headers,
        json={"label": "Unexpected", "dataType": "text", "adminOnly": True},
    )

    assert response.status_code == 422, response.text
    assert "adminOnly" in response.json()["field_errors"]


async def test_duplicate_label_is_a_conflict_on_the_derived_code(client):
    headers = await login(client)
    await _create(client, headers, label="Duplicate Label")

    duplicate = await client.post(
        BASE,
        headers=headers,
        json={"label": "Duplicate Label", "dataType": "text"},
    )

    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_ATTRIBUTE_CODE"
    assert "code" in duplicate.json()["field_errors"]


async def test_patch_updates_one_field_and_leaves_the_others_alone(client):
    headers = await login(client)
    created = await _create(client, headers, label="Per Field Patch", dataType="text")

    required = await client.patch(
        f"{BASE}/{created['id']}", headers=headers, json={"isRequired": True}
    )
    assert required.status_code == 200, required.text
    assert required.json()["data"]["isRequired"] is True
    assert required.json()["data"]["label"] == "Per Field Patch"
    assert required.json()["data"]["dataType"] == "text"

    help_text = await client.patch(
        f"{BASE}/{created['id']}", headers=headers, json={"placeholder": "  Shown below  "}
    )
    assert help_text.status_code == 200, help_text.text
    assert help_text.json()["data"]["placeholder"] == "Shown below"
    assert help_text.json()["data"]["isRequired"] is True

    cleared = await client.patch(
        f"{BASE}/{created['id']}", headers=headers, json={"placeholder": ""}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["placeholder"] is None


async def test_patch_rejects_an_empty_label_and_unknown_fields(client):
    headers = await login(client)
    created = await _create(client, headers, label="Patch Guard", dataType="text")

    empty = await client.patch(f"{BASE}/{created['id']}", headers=headers, json={"label": "  "})
    assert empty.status_code == 422, empty.text
    assert "label" in empty.json()["field_errors"]

    unknown = await client.patch(f"{BASE}/{created['id']}", headers=headers, json={"unexpected": 1})
    assert unknown.status_code == 422, unknown.text
    assert "unexpected" in unknown.json()["field_errors"]


async def test_a_saved_configuration_is_returned_by_a_fresh_list_request(client):
    headers = await login(client)
    created = await _create(
        client,
        headers,
        code="port-of-loading",
        label="Port of Loading",
        dataType="select",
        options=["Sihanoukville", "Phnom Penh"],
        validationRules={"maxLength": 40},
    )

    reloaded = await _find(client, headers, "port-of-loading")
    assert reloaded["id"] == created["id"]
    assert reloaded["label"] == "Port of Loading"
    assert reloaded["options"] == ["Sihanoukville", "Phnom Penh"]
    assert reloaded["validationRules"] == {"maxLength": 40}
    assert isinstance(reloaded["displayOrder"], int)


async def test_deleting_an_unused_attribute_removes_it(client):
    headers = await login(client)
    created = await _create(client, headers, label="Unused Attribute", dataType="text")

    deleted = await client.delete(f"{BASE}/{created['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["archived"] is False

    listed = await client.get(BASE, headers=headers, params={"page_size": 200, "include_archived": True})
    assert created["id"] not in {item["id"] for item in listed.json()["data"]["items"]}


async def test_deleting_a_referenced_attribute_archives_it(client):
    headers = await login(client)
    # Seeded into the Customs group, so it is referenced by a group and a tab.
    referenced = await _find(client, headers, "declaration_no")

    deleted = await client.delete(f"{BASE}/{referenced['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["archived"] is True

    archived = await _find(client, headers, "declaration_no")
    assert archived["status"] == "INACTIVE"


async def test_component_attribute_writes_require_permission(client):
    sales = await login(client, "sales")

    create = await client.post(BASE, headers=sales, json={"label": "Denied", "dataType": "text"})
    assert create.status_code == 403, create.text

    admin = await login(client)
    created = await _create(client, admin, label="Permission Target", dataType="text")

    update = await client.patch(f"{BASE}/{created['id']}", headers=sales, json={"label": "Renamed"})
    assert update.status_code == 403, update.text

    delete = await client.delete(f"{BASE}/{created['id']}", headers=sales)
    assert delete.status_code == 403, delete.text
