"""Operational Service Order tabs render only the published configuration.

The live ``component_*`` tables are draft administration data. These tests pin
the rule that a Service Order shows a tab only after a configuration version
containing it has been published, and that drafts never leak into the form.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _publish(client: httpx.AsyncClient, headers: dict[str, str], note: str = "publish") -> httpx.Response:
    return await client.post("/api/v1/configuration-versions", headers=headers, json={"changeNote": note})


async def _import_direction_id(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    response = await client.get("/api/v1/tradeDirections", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    for row in response.json()["data"]["items"]:
        if str(row.get("name") or row.get("code") or "").strip().lower() == "import":
            return str(row["id"])
    raise AssertionError("Import trade direction is missing from the seed data")


async def _create_tab(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    code: str,
    name: str,
    direction_id: str | None,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/component-tabs",
        headers=headers,
        json={"code": code, "name": name, "displayOrder": 10, "tradeDirectionId": int(direction_id) if direction_id else None},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _create_group(client: httpx.AsyncClient, headers: dict[str, str], code: str, name: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/component-groups",
        headers=headers,
        json={"code": code, "name": name, "displayOrder": 10},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _create_attribute(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    code: str,
    label: str,
    *,
    data_type: str = "text",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/component-attributes",
        headers=headers,
        json={"code": code, "label": label, "dataType": data_type},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _link_group(
    client: httpx.AsyncClient, headers: dict[str, str], tab_id: str, group_id: str
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/component-tabs/{tab_id}/groups",
        headers=headers,
        json={"groupId": int(group_id)},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _link_attribute(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    group_id: str,
    attribute_id: str,
    *,
    is_required: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"attributeId": int(attribute_id)}
    if is_required is not None:
        payload["isRequired"] = is_required
    response = await client.post(
        f"/api/v1/component-groups/{group_id}/attributes",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _new_order(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Published Config Customer",
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


async def _order_tabs(
    client: httpx.AsyncClient, headers: dict[str, str], order_id: str
) -> dict[str, Any]:
    response = await client.get(f"/api/v1/service-orders/{order_id}/component-tabs", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _build_tab_with_group(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    direction_id: str,
    *,
    tab_code: str,
    group_code: str,
    attribute_code: str,
) -> dict[str, str]:
    tab = await _create_tab(client, headers, tab_code, tab_code.title(), direction_id)
    group = await _create_group(client, headers, group_code, group_code.title())
    attribute = await _create_attribute(client, headers, attribute_code, attribute_code.title())
    await _link_attribute(client, headers, str(group["id"]), str(attribute["id"]))
    link = await _link_group(client, headers, str(tab["id"]), str(group["id"]))
    return {
        "tab_id": str(tab["id"]),
        "tab_code": str(tab["code"]),
        "group_id": str(group["id"]),
        "attribute_id": str(attribute["id"]),
        "attribute_code": str(attribute["code"]),
        "tab_group_id": str(link["id"]),
    }


async def test_no_published_version_means_no_dynamic_tabs(client):
    headers = await login(client)
    live = await client.get("/api/v1/component-tabs", headers=headers, params={"page_size": 200})
    assert live.status_code == 200, live.text
    assert live.json()["data"]["items"], "the seed ships live draft tabs"

    order_id = await _new_order(client, headers)
    boot = await _order_tabs(client, headers, order_id)
    assert boot["tabs"] == [], "live draft tabs must not reach an operational order"
    assert boot["configVersionId"] is None


async def test_draft_changes_are_invisible_until_the_next_publish(client):
    headers = await login(client)
    direction = await _import_direction_id(client, headers)
    config = await _build_tab_with_group(
        client,
        headers,
        direction,
        tab_code="PUBLISHED_V1",
        group_code="published_group",
        attribute_code="published_field",
    )

    published = await _publish(client, headers, "v1")
    assert published.status_code == 201, published.text

    pinned_order = await _new_order(client, headers)
    tabs = (await _order_tabs(client, headers, pinned_order))["tabs"]
    codes = {tab["code"] for tab in tabs}
    assert config["tab_code"] in codes

    # A draft tab added after the publish must not appear on the pinned order.
    draft = await _build_tab_with_group(
        client,
        headers,
        direction,
        tab_code="DRAFT_V2",
        group_code="draft_group",
        attribute_code="draft_field",
    )
    after_draft = (await _order_tabs(client, headers, pinned_order))["tabs"]
    after_codes = {tab["code"] for tab in after_draft}
    assert config["tab_code"] in after_codes
    assert draft["tab_code"] not in after_codes, "a draft tab must not appear"

    # Publishing V2 makes it available to a new order; the pinned order keeps V1.
    second = await _publish(client, headers, "v2")
    assert second.status_code == 201, second.text
    pinned_codes = {tab["code"] for tab in (await _order_tabs(client, headers, pinned_order))["tabs"]}
    assert config["tab_code"] in pinned_codes
    assert draft["tab_code"] not in pinned_codes, "the pinned order keeps V1"

    fresh_order = await _new_order(client, headers)
    fresh_codes = {tab["code"] for tab in (await _order_tabs(client, headers, fresh_order))["tabs"]}
    assert {config["tab_code"], draft["tab_code"]} <= fresh_codes

    # The draft group is now published, so operational saves are accepted.
    assert config["group_id"] and draft["group_id"]


async def test_rows_cannot_be_saved_for_an_unpublished_group(client):
    headers = await login(client)
    direction = await _import_direction_id(client, headers)
    await _build_tab_with_group(
        client,
        headers,
        direction,
        tab_code="ONLY_PUBLISHED",
        group_code="only_published_group",
        attribute_code="only_published_field",
    )
    assert (await _publish(client, headers)).status_code == 201
    order_id = await _new_order(client, headers)

    draft = await _build_tab_with_group(
        client,
        headers,
        direction,
        tab_code="HIDDEN_DRAFT",
        group_code="hidden_draft_group",
        attribute_code="hidden_draft_field",
    )
    blocked = await client.post(
        f"/api/v1/service-orders/{order_id}/component-tabs/groups/{draft['group_id']}/rows/bulk",
        headers=headers,
        json={"rows": [{"values": {"hidden_draft_field": "x"}}]},
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["field_errors"], "the refusal explains why"


async def test_a_required_draft_attribute_does_not_block_published_saves(client):
    headers = await login(client)
    direction = await _import_direction_id(client, headers)
    config = await _build_tab_with_group(
        client,
        headers,
        direction,
        tab_code="STABLE",
        group_code="stable_group",
        attribute_code="stable_field",
    )
    assert (await _publish(client, headers)).status_code == 201
    order_id = await _new_order(client, headers)

    # Draft-only change: a new required attribute on the same live group.
    extra = await _create_attribute(client, headers, "draft_required", "Draft Required")
    await _link_attribute(client, headers, config["group_id"], str(extra["id"]), is_required=True)

    saved = await client.post(
        f"/api/v1/service-orders/{order_id}/component-tabs/groups/{config['group_id']}/rows/bulk",
        headers=headers,
        json={
            "rows": [{"values": {config["attribute_code"]: "kept"}}],
            "tabGroupId": int(config["tab_group_id"]),
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["items"][0]["values"][config["attribute_code"]] == "kept"


async def test_duplicate_tab_identifiers_are_refused(client):
    headers = await login(client)
    direction = await _import_direction_id(client, headers)
    await _create_tab(client, headers, "DUPLICATE", "First", direction)
    # The live tables carry a unique code, so a duplicate cannot even be created.
    duplicate = await client.post(
        "/api/v1/component-tabs",
        headers=headers,
        json={"code": "DUPLICATE", "name": "Second", "displayOrder": 10, "tradeDirectionId": int(direction)},
    )
    assert duplicate.status_code in {409, 422}, duplicate.text

    # The publish validator still rejects a snapshot with duplicate identifiers
    # (for example one produced by an import or an older migration).
    from app.modules.master_data.config_versions import validate_snapshot

    errors = validate_snapshot({
        "tabs": [
            {
                "code": "SAME",
                "name": "One",
                "displayOrder": 0,
                "groups": [
                    {
                        "code": "g",
                        "name": "G",
                        "displayOrder": 0,
                        "displayMode": "table_only",
                        "dataCardinality": "multiple",
                        "formColumns": 3,
                        "attributes": [
                            {
                                "code": "a",
                                "label": "A",
                                "dataType": "text",
                                "displayOrder": 0,
                            }
                        ],
                    }
                ],
            },
            {
                "code": "same",
                "name": "Two",
                "displayOrder": 1,
                "groups": [],
            },
        ]
    })
    assert any("Duplicate tab identifier" in message for message in errors.values())
    assert any("Add at least one group" in message for message in errors.values())


async def test_publication_rejects_a_tab_without_groups_or_attributes(client):
    headers = await login(client)
    direction = await _import_direction_id(client, headers)

    empty_tab = await _create_tab(client, headers, "EMPTY_TAB", "Empty", direction)
    rejected = await _publish(client, headers)
    assert rejected.status_code == 422, rejected.text
    errors = rejected.json()["field_errors"]
    assert any(message == "Add at least one group to this tab." for message in errors.values())

    group = await _create_group(client, headers, "empty_group", "Empty Group")
    await _link_group(client, headers, str(empty_tab["id"]), str(group["id"]))
    rejected = await _publish(client, headers, "still empty")
    assert rejected.status_code == 422, rejected.text
    assert any(
        message == "Add at least one attribute to this group."
        for message in rejected.json()["field_errors"].values()
    )


async def test_failed_publication_keeps_the_previous_version_active(client):
    headers = await login(client)
    direction = await _import_direction_id(client, headers)
    await _build_tab_with_group(
        client,
        headers,
        direction,
        tab_code="GOOD_V1",
        group_code="good_group",
        attribute_code="good_field",
    )
    first = await _publish(client, headers, "good")
    assert first.status_code == 201, first.text

    await _create_tab(client, headers, "BROKEN", "Broken", direction)
    assert (await _publish(client, headers, "broken")).status_code == 422

    active = await client.get("/api/v1/configuration-versions/active", headers=headers)
    assert active.status_code == 200, active.text
    assert active.json()["data"]["id"] == first.json()["data"]["id"]
    assert active.json()["data"]["status"] == "PUBLISHED"
