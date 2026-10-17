"""Published configuration versions for the dynamic Service Order form.

Covers migration d5e6f7a8b9c0 and ``app/modules/master_data/config_versions.py``.
The point of the feature is that a configuration change cannot silently change
how an existing Service Order reads, so the tests focus on historical pinning
rather than on the snapshot contents alone.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _publish(client, headers, note: str = "test publish") -> dict:
    response = await client.post(
        "/api/v1/configuration-versions", headers=headers, json={"changeNote": note}
    )
    return response


async def _create_tab(client, headers, code: str, name: str, direction: str | None = None) -> dict:
    response = await client.post(
        "/api/v1/component-tabs",
        headers=headers,
        json={"code": code, "name": name, "displayOrder": 10, "tradeDirectionId": direction},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _service_order(client, headers) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Config Version Customer",
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
    return converted.json()["data"]["serviceOrderId"]


async def test_preview_describes_the_live_configuration_without_publishing(client):
    headers = await login(client)
    preview = await client.get("/api/v1/configuration-versions/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    assert data["tabCount"] >= 1, "the seeded Customs tab should be visible"
    assert data["currentVersionNo"] is None, "nothing is published on a fresh installation"
    assert data["unchanged"] is False
    codes = [tab["code"] for tab in data["preview"]["tabs"]]
    assert "CUSTOMS" in codes


async def test_publish_creates_one_published_version_and_stamps_the_tabs(client):
    headers = await login(client)

    published = await _publish(client, headers)
    assert published.status_code == 201, published.text
    version = published.json()["data"]
    assert version["versionNo"] == 1
    assert version["status"] == "PUBLISHED"
    assert version["changeNote"] == "test publish"
    assert version["configSnapshot"]["tabs"], "the snapshot must capture the live tabs"

    listed = await client.get("/api/v1/configuration-versions", headers=headers)
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    assert [row["versionNo"] for row in items] == [1]
    assert items[0]["status"] == "PUBLISHED"


async def test_publishing_an_unchanged_configuration_is_rejected(client):
    headers = await login(client)
    assert (await _publish(client, headers)).status_code == 201

    again = await _publish(client, headers, "no-op")
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "CONFIGURATION_UNCHANGED"

    listed = await client.get("/api/v1/configuration-versions", headers=headers)
    assert [row["versionNo"] for row in listed.json()["data"]["items"]] == [1]


async def test_a_new_publish_retires_the_previous_version(client):
    headers = await login(client)
    assert (await _publish(client, headers)).status_code == 201

    await _create_tab(client, headers, "EXTRA", "Extra")

    second = await _publish(client, headers, "added a tab")
    assert second.status_code == 201, second.text
    assert second.json()["data"]["versionNo"] == 2
    assert second.json()["data"]["status"] == "PUBLISHED"

    listed = await client.get("/api/v1/configuration-versions", headers=headers)
    by_version = {row["versionNo"]: row["status"] for row in listed.json()["data"]["items"]}
    assert by_version == {1: "RETIRED", 2: "PUBLISHED"}, "exactly one version may stay live"


async def test_existing_service_orders_keep_the_configuration_they_were_captured_under(client):
    headers = await login(client)
    first = await _publish(client, headers)
    assert first.status_code == 201
    version_one = first.json()["data"]["id"]

    order_id = await _service_order(client, headers)
    pinned = await client.get(f"/api/v1/service-orders/{order_id}/configuration-version", headers=headers)
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["data"]["id"] == version_one

    # Changing the live configuration must not repoint the existing order.
    await _create_tab(client, headers, "LATER", "Later")
    assert (await _publish(client, headers, "second configuration")).status_code == 201

    still_pinned = await client.get(f"/api/v1/service-orders/{order_id}/configuration-version", headers=headers)
    assert still_pinned.status_code == 200, still_pinned.text
    assert still_pinned.json()["data"]["id"] == version_one
    assert still_pinned.json()["data"]["status"] == "RETIRED"


async def test_publishing_without_any_active_tab_is_rejected(client):
    headers = await login(client)
    tabs = await client.get("/api/v1/component-tabs", headers=headers, params={"page_size": 200})
    assert tabs.status_code == 200, tabs.text
    for tab in tabs.json()["data"]["items"]:
        removed = await client.delete(f"/api/v1/component-tabs/{tab['id']}", headers=headers)
        assert removed.status_code in {200, 204}, removed.text

    rejected = await _publish(client, headers)
    assert rejected.status_code == 422, rejected.text
    assert "changeNote" in rejected.json()["field_errors"]


async def test_publishing_requires_configuration_permission(client):
    sales = await login(client, "sales")
    blocked = await _publish(client, sales)
    assert blocked.status_code == 403, blocked.text


async def test_attribute_code_cannot_change_once_values_are_saved(client):
    headers = await login(client)
    tabs = await client.get("/api/v1/component-tabs", headers=headers, params={"page_size": 200})
    assert tabs.status_code == 200, tabs.text
    tab = next(row for row in tabs.json()["data"]["items"] if row["code"] == "CUSTOMS")

    detail = await client.get(f"/api/v1/component-tabs/{tab['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    group = detail.json()["data"]["groups"][0]

    memberships = await client.get(
        f"/api/v1/component-groups/{group['id']}/attributes", headers=headers
    )
    assert memberships.status_code == 200, memberships.text
    attribute = memberships.json()["data"][0]

    # Save a value keyed by that attribute's code on a real service order.
    order_id = await _service_order(client, headers)
    saved = await client.post(
        f"/api/v1/service-orders/{order_id}/component-tabs/groups/{group['id']}/rows/bulk",
        headers=headers,
        json={"rows": [{"values": {attribute["code"]: "REF-1"}}]},
    )
    assert saved.status_code == 200, saved.text

    rename = await client.patch(
        f"/api/v1/component-attributes/{attribute['id']}",
        headers=headers,
        json={"code": f"{attribute['code']}_renamed"},
    )
    assert rename.status_code == 409, rename.text
    assert rename.json()["code"] == "ATTRIBUTE_CODE_IN_USE"

    # Only the label may change while values reference the code.
    relabel = await client.patch(
        f"/api/v1/component-attributes/{attribute['id']}", headers=headers, json={"label": "Renamed label"}
    )
    assert relabel.status_code == 200, relabel.text
    assert relabel.json()["data"]["label"] == "Renamed label"
    assert relabel.json()["data"]["code"] == attribute["code"]
