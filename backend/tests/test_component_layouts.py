"""Independent display layouts for component groups inside one tab.

A tab is no longer restricted to a single render mode: each group assignment
carries its own display mode, cardinality, form columns and behaviour flags.
These tests cover the runtime payload, layout validation, save enforcement and
configuration-version history.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _direction_id(client, headers, code: str = "IMPORT") -> str:
    response = await client.get("/api/v1/tradeDirections", headers=headers, params={"page_size": 100})
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    return next(str(row["id"]) for row in items if row["code"] == code)


async def _attribute(client, headers, label: str) -> dict:
    created = await client.post(
        "/api/v1/component-attributes",
        headers=headers,
        json={"label": label, "dataType": "text"},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


async def _group(client, headers, name: str, attributes: list[dict]) -> dict:
    created = await client.post(
        "/api/v1/component-groups",
        headers=headers,
        json={"name": name, "renderMode": "table"},
    )
    assert created.status_code == 201, created.text
    group = created.json()["data"]
    for attribute in attributes:
        added = await client.post(
            f"/api/v1/component-groups/{group['id']}/attributes",
            headers=headers,
            json={"attributeId": attribute["id"], "displayOrder": 10},
        )
        assert added.status_code == 201, added.text
    return group


async def _tab(client, headers, code: str, direction: str) -> dict:
    created = await client.post(
        "/api/v1/component-tabs",
        headers=headers,
        json={"code": code, "name": code.title(), "tradeDirectionId": direction, "displayOrder": 10},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


async def _attach(client, headers, tab_id: str, group_id: str, **layout) -> dict:
    response = await client.post(
        f"/api/v1/component-tabs/{tab_id}/groups",
        headers=headers,
        json={"groupId": group_id, **layout},
    )
    assert response.status_code == 201, response.text
    return next(row for row in response.json()["data"]["groups"] if row["id"] == group_id)


async def _service_order(client, headers) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Layout Test Customer",
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


async def _bootstrap(client, headers, order_id: str) -> dict:
    response = await client.get(f"/api/v1/service-orders/{order_id}/component-tabs", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _save(client, headers, order_id: str, group_id: str, rows: list[dict], tab_group_id: str | None = None):
    return await client.post(
        f"/api/v1/service-orders/{order_id}/component-tabs/groups/{group_id}/rows/bulk",
        headers=headers,
        json={"rows": rows, "tabGroupId": tab_group_id},
    )


async def _shipment_tab(client, headers) -> tuple[dict, list[dict]]:
    """A tab with three groups, each using a different display mode."""
    direction = await _direction_id(client, headers)
    general_attr = await _attribute(client, headers, "General Reference")
    container_attr = await _attribute(client, headers, "Container Number")
    seal_attr = await _attribute(client, headers, "Seal Number")
    cargo_attr = await _attribute(client, headers, "Cargo Description")

    general = await _group(client, headers, "General Information", [general_attr])
    containers = await _group(client, headers, "Container Details", [container_attr, seal_attr])
    cargo = await _group(client, headers, "Cargo Details", [cargo_attr])

    tab = await _tab(client, headers, "SHIPMENT-LAYOUT", direction)
    first = await _attach(
        client, headers, tab["id"], general["id"],
        displayMode="form_only", dataCardinality="single", formColumns=2,
        showGroupTitle=True, editable=True, collapsible=False, defaultExpanded=True,
        displayOrder=10,
    )
    second = await _attach(
        client, headers, tab["id"], containers["id"],
        displayMode="table_only", dataCardinality="multiple", displayOrder=20,
    )
    third = await _attach(
        client, headers, tab["id"], cargo["id"],
        displayMode="form_and_table", dataCardinality="multiple", formColumns=1,
        collapsible=True, defaultExpanded=True, displayOrder=30,
    )
    return tab, [first, second, third]


async def test_one_tab_renders_independent_layouts_in_configured_order(client):
    headers = await login(client)
    tab, links = await _shipment_tab(client, headers)
    order_id = await _service_order(client, headers)

    payload = await _bootstrap(client, headers, order_id)
    shipment = next(item for item in payload["tabs"] if item["code"] == tab["code"])
    assert [group["name"] for group in shipment["groups"]] == [
        "General Information",
        "Container Details",
        "Cargo Details",
    ]
    assert [group["displayMode"] for group in shipment["groups"]] == [
        "form_only",
        "table_only",
        "form_and_table",
    ]
    assert [group["dataCardinality"] for group in shipment["groups"]] == ["single", "multiple", "multiple"]
    assert shipment["groups"][0]["formColumns"] == 2
    assert shipment["groups"][2]["formColumns"] == 1
    assert shipment["groups"][2]["collapsible"] is True
    assert shipment["groups"][2]["defaultExpanded"] is True
    assert shipment["groups"][0]["showGroupTitle"] is True
    assert shipment["groups"][0]["editable"] is True
    assert shipment["groups"][0]["tabGroupId"] == links[0]["tabGroupId"]


async def test_legacy_assignment_without_layout_keeps_its_render_mode(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)
    payload = await _bootstrap(client, headers, order_id)
    customs = next(tab for tab in payload["tabs"] if tab["code"] == "CUSTOMS")
    group = customs["groups"][0]
    # The seeded group has render_mode='table' and no per-assignment layout.
    assert group["displayMode"] == "table_only"
    assert group["dataCardinality"] == "multiple"
    assert group["tabGroupId"]


async def test_layout_schema_validation_rejects_unsupported_values(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)
    url = f"/api/v1/component-tab-groups/{links[0]['tabGroupId']}"

    bad_mode = await client.patch(url, headers=headers, json={"displayMode": "grid_only"})
    assert bad_mode.status_code == 422, bad_mode.text
    assert "displayMode" in bad_mode.json()["field_errors"]

    bad_columns = await client.patch(url, headers=headers, json={"formColumns": 5})
    assert bad_columns.status_code == 422, bad_columns.text
    assert "formColumns" in bad_columns.json()["field_errors"]

    bad_cardinality = await client.patch(url, headers=headers, json={"dataCardinality": "many"})
    assert bad_cardinality.status_code == 422, bad_cardinality.text
    assert "dataCardinality" in bad_cardinality.json()["field_errors"]

    unknown = await client.patch(url, headers=headers, json={"gridTemplate": "x"})
    assert unknown.status_code == 422, unknown.text
    assert "gridTemplate" in unknown.json()["field_errors"]


async def test_form_only_cannot_keep_multiple_records(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)

    response = await client.patch(
        f"/api/v1/component-tab-groups/{links[1]['tabGroupId']}",
        headers=headers,
        json={"displayMode": "form_only", "dataCardinality": "multiple"},
    )
    assert response.status_code == 422, response.text
    assert "dataCardinality" in response.json()["field_errors"]


async def test_changing_to_single_record_is_refused_when_rows_would_be_hidden(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)
    order_id = await _service_order(client, headers)
    table_group = links[1]
    assert table_group["displayMode"] == "table_only"

    saved = await _save(
        client, headers, order_id, table_group["id"],
        [{"values": {"container-number": "CONT-1"}}, {"values": {"container-number": "CONT-2"}}],
        table_group["tabGroupId"],
    )
    assert saved.status_code == 200, saved.text

    blocked = await client.patch(
        f"/api/v1/component-tab-groups/{table_group['tabGroupId']}",
        headers=headers,
        json={"dataCardinality": "single"},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "LAYOUT_CHANGE_WOULD_HIDE_ROWS"
    assert "dataCardinality" in blocked.json()["field_errors"]


async def test_save_enforces_the_assignment_cardinality(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)
    order_id = await _service_order(client, headers)
    general = links[0]

    rejected = await _save(
        client, headers, order_id, general["id"],
        [{"values": {"general-reference": "A"}}, {"values": {"general-reference": "B"}}],
        general["tabGroupId"],
    )
    assert rejected.status_code == 422, rejected.text
    assert "rows" in rejected.json()["field_errors"]

    accepted = await _save(
        client, headers, order_id, general["id"],
        [{"values": {"general-reference": "A"}}],
        general["tabGroupId"],
    )
    assert accepted.status_code == 200, accepted.text


async def test_form_and_table_rows_save_and_reload(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)
    order_id = await _service_order(client, headers)
    cargo = links[2]

    saved = await _save(
        client, headers, order_id, cargo["id"],
        [
            {"values": {"cargo-description": "Rice"}},
            {"values": {"cargo-description": "Garments"}},
        ],
        cargo["tabGroupId"],
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["data"]["items"]) == 2

    payload = await _bootstrap(client, headers, order_id)
    shipment = next(tab for tab in payload["tabs"] if tab["code"] == "shipment-layout")
    reloaded = next(group for group in shipment["groups"] if group["id"] == cargo["id"])
    assert [row["cargo-description"] for row in reloaded["rows"]] == ["Rice", "Garments"]


async def test_read_only_layout_refuses_writes_and_requires_configuration_permission(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)
    order_id = await _service_order(client, headers)
    cargo = links[2]

    read_only = await client.patch(
        f"/api/v1/component-tab-groups/{cargo['tabGroupId']}",
        headers=headers,
        json={"editable": False},
    )
    assert read_only.status_code == 200, read_only.text
    assert read_only.json()["data"]["editable"] is False

    refused = await _save(
        client, headers, order_id, cargo["id"],
        [{"values": {"cargo-description": "Blocked"}}],
        cargo["tabGroupId"],
    )
    assert refused.status_code == 422, refused.text

    sales = await login(client, "sales")
    denied_layout = await client.patch(
        f"/api/v1/component-tab-groups/{cargo['tabGroupId']}",
        headers=sales,
        json={"editable": True},
    )
    assert denied_layout.status_code == 403, denied_layout.text

    denied_save = await _save(
        client, sales, order_id, cargo["id"],
        [{"values": {"cargo-description": "Blocked"}}],
        cargo["tabGroupId"],
    )
    assert denied_save.status_code == 403, denied_save.text


async def test_published_snapshots_keep_the_layout_of_each_version(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)

    first = await client.post("/api/v1/configuration-versions", headers=headers, json={"changeNote": "layouts v1"})
    assert first.status_code == 201, first.text
    first_id = first.json()["data"]["id"]
    snapshot = first.json()["data"]["configSnapshot"]
    shipment = next(tab for tab in snapshot["tabs"] if tab["code"] == "shipment-layout")
    modes = {group["code"]: group["displayMode"] for group in shipment["groups"]}
    assert modes
    assert set(modes.values()) == {"form_only", "table_only", "form_and_table"}

    updated = await client.patch(
        f"/api/v1/component-tab-groups/{links[1]['tabGroupId']}",
        headers=headers,
        json={"displayMode": "form_and_table", "formColumns": 4},
    )
    assert updated.status_code == 200, updated.text

    second = await client.post("/api/v1/configuration-versions", headers=headers, json={"changeNote": "layouts v2"})
    assert second.status_code == 201, second.text

    # The retired version still describes the layout the order was captured
    # under; publishing never rewrites an existing snapshot.
    historical = await client.get(f"/api/v1/configuration-versions/{first_id}", headers=headers)
    assert historical.status_code == 200, historical.text
    historical_group = next(
        group
        for tab in historical.json()["data"]["configSnapshot"]["tabs"]
        if tab["code"] == "shipment-layout"
        for group in tab["groups"]
        if group["code"] == links[1]["code"]
    )
    assert historical_group["displayMode"] == "table_only"
    assert historical_group["formColumns"] == 3


async def test_column_order_and_visibility_come_from_the_group_membership(client):
    headers = await login(client)
    direction = await _direction_id(client, headers)
    first_attr = await _attribute(client, headers, "Column One")
    second_attr = await _attribute(client, headers, "Column Two")
    third_attr = await _attribute(client, headers, "Column Three")
    group = await _group(client, headers, "Ordered Columns", [first_attr, second_attr, third_attr])
    tab = await _tab(client, headers, "ORDERED-COLUMNS", direction)
    await _attach(client, headers, tab["id"], group["id"], displayMode="table_only")

    memberships = await client.get(
        f"/api/v1/component-groups/{group['id']}/attributes", headers=headers
    )
    assert memberships.status_code == 200, memberships.text
    rows = memberships.json()["data"]
    by_code = {row["code"]: row for row in rows}

    hidden = await client.patch(
        f"/api/v1/component-group-attributes/{by_code['column-two']['id']}",
        headers=headers,
        json={"isVisible": False},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["data"]["isVisible"] is False

    reordered = await client.post(
        f"/api/v1/component-groups/{group['id']}/attributes/reorder",
        headers=headers,
        json={"orderedIds": [by_code["column-three"]["id"], by_code["column-one"]["id"]]},
    )
    assert reordered.status_code == 200, reordered.text

    order_id = await _service_order(client, headers)
    payload = await _bootstrap(client, headers, order_id)
    runtime = next(
        item
        for tab_item in payload["tabs"]
        for item in tab_item["groups"]
        if item["id"] == group["id"]
    )
    assert [attribute["code"] for attribute in runtime["attributes"]] == ["column-three", "column-one"]


async def test_duplicate_row_ids_are_refused(client):
    headers = await login(client)
    _, links = await _shipment_tab(client, headers)
    order_id = await _service_order(client, headers)
    cargo = links[2]

    saved = await _save(
        client, headers, order_id, cargo["id"],
        [{"values": {"cargo-description": "Original"}}],
        cargo["tabGroupId"],
    )
    row_id = saved.json()["data"]["items"][0]["id"]

    duplicate = await _save(
        client, headers, order_id, cargo["id"],
        [
            {"id": row_id, "values": {"cargo-description": "First"}},
            {"id": row_id, "values": {"cargo-description": "Second"}},
        ],
        cargo["tabGroupId"],
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "2.id" in duplicate.json()["field_errors"]
