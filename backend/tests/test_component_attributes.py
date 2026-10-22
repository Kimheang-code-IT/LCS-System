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
