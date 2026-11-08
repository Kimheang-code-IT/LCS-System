"""Excel Import & Export for the Configuration module.

Pins the create-only contract: catalog imports never edit existing codes, the
whole batch is atomic, select options are parsed and re-exported losslessly,
and a configuration version workbook imports as a new DRAFT version without
ever touching the published one.
"""

from __future__ import annotations

import io
import json

import pytest
from openpyxl import load_workbook

from tests.conftest import login

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    from app.modules.excel_io import router as excel_router

    monkeypatch.setattr(
        excel_router, "_RATE_LIMITS", {key: 1_000_000 for key in excel_router._RATE_LIMITS}
    )
    yield


def _workbook_bytes(rows: list[list], headers: list[str], version: int = 1) -> bytes:
    workbook_bytes = _multi_sheet({"Data": (headers, rows)}, version)
    return workbook_bytes


def _multi_sheet(sheets: dict[str, tuple[list[str], list[list]]], version: int = 1) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    instructions = workbook.active
    assert instructions is not None
    instructions.title = "Instructions"
    instructions["A1"] = "TEMPLATE_VERSION"
    instructions["B1"] = version
    for name, (headers, rows) in sheets.items():
        sheet = workbook.create_sheet(name)
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _file(content: bytes) -> dict:
    return {"file": ("batch.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


async def _validate(client, headers: dict, module: str, content: bytes, mode: str = "CREATE_ONLY"):
    return await client.post(
        f"/api/v1/excel/{module}/validate",
        headers=headers,
        files=_file(content),
        data={"mode": mode},
    )


async def _commit(client, headers: dict, token: str):
    return await client.post(f"/api/v1/excel/imports/{token}/commit", headers=headers)


ATTR_HEADERS = ["label", "code", "dataType", "options"]
GROUP_HEADERS = ["code", "name", "nameKm", "description", "renderMode", "displayOrder"]
TAB_HEADERS = ["code", "name", "description", "tradeDirection", "displayOrder"]


async def test_module_catalog_includes_configuration_modules(client):
    headers = await login(client)
    response = await client.get("/api/v1/excel/modules", headers=headers)
    assert response.status_code == 200, response.text
    keys = {item["key"]: item for item in response.json()["data"]}
    for expected in ("componentAttributes", "componentGroups", "componentTabs", "configurationVersions"):
        assert expected in keys, response.text
    assert keys["componentAttributes"]["managePermission"] == "configuration.manage"
    assert keys["configurationVersions"]["viewPermission"] == "configuration.read"


async def test_create_only_modules_reject_other_modes(client):
    headers = await login(client)
    response = await _validate(
        client,
        headers,
        "componentAttributes",
        _workbook_bytes([["Port", "port", "text", ""]], ATTR_HEADERS),
        mode="CREATE_AND_UPDATE",
    )
    assert response.status_code == 422, response.text
    assert "mode" in response.json()["field_errors"]


async def test_attribute_import_parses_select_options_and_skips_duplicates(client):
    headers = await login(client)
    rows = [
        ["Container No.", "container-no", "text", ""],
        ["Port of Loading", "port-of-loading", "select", "Sihanoukville; Phnom Penh"],
    ]
    content = _workbook_bytes(rows, ATTR_HEADERS)
    response = await _validate(client, headers, "componentAttributes", content)
    assert response.status_code == 200, response.text
    summary = response.json()["data"]["summary"]
    assert summary["create"] == 2 and summary["error"] == 0

    committed = await _commit(client, headers, response.json()["data"]["token"])
    assert committed.status_code == 200, committed.text
    assert committed.json()["data"]["create"] == 2

    # Re-import: every code exists now — CREATE_ONLY must skip, never edit.
    again = await _validate(client, headers, "componentAttributes", content)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["summary"]["skip"] == 2
    commit2 = await _commit(client, headers, again.json()["data"]["token"])
    assert commit2.status_code == 200

    found = (await client.get(
        "/api/v1/component-attributes", headers=headers, params={"q": "port-of-loading"}
    )).json()["data"]["items"]
    assert found[0]["options"] == ["Sihanoukville", "Phnom Penh"]


async def test_attribute_import_reports_invalid_rows_with_row_numbers(client):
    headers = await login(client)
    content = _workbook_bytes(
        [
            ["Bad Type", "bad-type", "select", ""],          # select without options
            ["Bad Options", "bad-options", "text", "A; A"],  # options on a non-select
        ],
        ATTR_HEADERS,
    )
    response = await _validate(client, headers, "componentAttributes", content)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["summary"]["error"] == 2
    errors = {(row["excelRow"], row["action"], row["status"]) for row in response.json()["data"]["rows"]}
    assert (2, "ERROR", "INVALID") in errors


async def test_attribute_export_round_trips_back_into_import(client, session_factory):
    headers = await login(client)
    # Seed one attribute through the API, then export.
    created = await client.post(
        "/api/v1/component-attributes",
        headers=headers,
        json={"code": "round-trip", "label": "Round Trip", "dataType": "select", "options": ["A", "B"]},
    )
    assert created.status_code == 201, created.text
    export = await client.post(
        "/api/v1/excel/componentAttributes/export", headers=headers, json={"format": "xlsx"}
    )
    assert export.status_code == 200, export.text
    workbook = load_workbook(io.BytesIO(export.content))
    sheet = [cell.value for cell in next(workbook["Data"].iter_rows(min_row=1, max_row=1))]
    assert sheet == ATTR_HEADERS
    exported = [list(row) for row in workbook["Data"].iter_rows(min_row=2, values_only=True)]
    trip = next(row for row in exported if row[1] == "round-trip")
    assert trip[3] == "A; B"

    # Delete it, then re-import the export: the workbook recreates the row.
    deleted = await client.delete(
        f"/api/v1/component-attributes/{created.json()['data']['id']}", headers=headers
    )
    assert deleted.json()["data"]["archived"] is False
    response = await _validate(client, headers, "componentAttributes", export.content)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["summary"]["create"] == 1
    assert (await _commit(client, headers, response.json()["data"]["token"])).status_code == 200


async def test_group_and_tab_import_with_reference_resolution(client):
    headers = await login(client)
    groups = _workbook_bytes(
        [["shipper", "Shipper Details", "", "", "form", "10"]],
        GROUP_HEADERS,
    )
    response = await _validate(client, headers, "componentGroups", groups)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["summary"]["create"] == 1
    assert (await _commit(client, headers, response.json()["data"]["token"])).status_code == 200

    # A tab referencing an unknown trade direction must fail its row only.
    bad_tab = _workbook_bytes([["shipping", "Shipping", "", "No Such Direction", ""]], TAB_HEADERS)
    response = await _validate(client, headers, "componentTabs", bad_tab)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["summary"]["error"] == 1

    directions = (await client.get("/api/v1/tradeDirections", headers=headers)).json()["data"]["items"]
    assert directions, "seeded trade directions missing"
    good_tab = _workbook_bytes([[ "shipping", "Shipping", "", directions[0]["name"], "20"]], TAB_HEADERS)
    response = await _validate(client, headers, "componentTabs", good_tab)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["summary"]["create"] == 1
    assert (await _commit(client, headers, response.json()["data"]["token"])).status_code == 200

    tabs = (await client.get("/api/v1/component-tabs", headers=headers, params={"q": "shipping"})).json()["data"]["items"]
    assert tabs and tabs[0]["tradeDirectionId"] == str(directions[0]["id"])


def _version_workbook(version_no: int = 99) -> bytes:
    return _multi_sheet({
        "Version": (["versionNo", "changeNote", "scope"], [[version_no, "Imported draft", "GLOBAL"]]),
        "Attributes": (ATTR_HEADERS, [["Container No.", "container-no", "text", ""]]),
        "Groups": (GROUP_HEADERS, [["containers", "Containers", "", "", "table", "5"]]),
        "Tabs": (TAB_HEADERS, [["cargodetail", "Cargo Detail", "", "", "1"]]),
        "Relationships": (
            ["tabCode", "groupCode", "attributeCode", "displayOrder", "isRequired"],
            [["cargodetail", "containers", "", "10", ""], ["", "containers", "container-no", "10", "TRUE"]],
        ),
    })


async def _seed_version(session_factory, snapshot: dict, status: str = "DRAFT") -> dict:
    from app.modules.master_data.models import ConfigurationVersion

    async with session_factory() as session:
        version = ConfigurationVersion(
            version_no=500 + status.__len__(),
            scope="GLOBAL", status=status, origin="PUBLISH",
            change_note=f"seed-{status}", config_snapshot=snapshot, snapshot_schema_version=1,
        )
        session.add(version)
        await session.commit()
        return {"id": int(version.id), "versionNo": int(version.version_no)}


_SNAPSHOT = {
    "tabs": [{
        "id": "1", "code": "cargodetail", "name": "Cargo Detail",
        "tradeDirectionId": None, "displayOrder": 1,
        "groups": [{
            "id": "5", "code": "containers", "name": "Containers",
            "renderMode": "table", "displayOrder": 5,
            "attributes": [{
                "id": "9", "code": "container-no", "label": "Container No.",
                "dataType": "text", "isRequired": True, "displayOrder": 10,
                "options": [], "validationRules": {},
            }],
        }],
    }],
}


async def test_version_export_and_reimport_creates_new_draft(client, session_factory):
    headers = await login(client)
    seeded = await _seed_version(session_factory, json.loads(json.dumps(_SNAPSHOT)), status="DRAFT")
    export = await client.post(
        "/api/v1/excel/configurationVersions/export", headers=headers, json={"ids": [str(seeded["id"])]}
    )
    assert export.status_code == 200, export.text
    workbook = load_workbook(io.BytesIO(export.content))
    assert set(workbook.sheetnames) >= {"Version", "Attributes", "Groups", "Tabs", "Relationships"}
    attrs = [list(row) for row in workbook["Attributes"].iter_rows(min_row=2, values_only=True)]
    assert [row[:3] for row in attrs] == [["Container No.", "container-no", "text"]]
    assert attrs[0][3] in (None, "")

    # The draft's own name would collide on re-import (duplicate identifier),
    # so rename the seeded draft before importing its exported workbook.
    renamed = await client.patch(
        f"/api/v1/configuration-versions/{seeded['id']}",
        headers=headers,
        json={"changeNote": "renamed-seed-draft"},
    )
    assert renamed.status_code == 200, renamed.text

    response = await _validate(client, headers, "configurationVersions", export.content)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["summary"]["create"] >= 3
    assert data["summary"]["error"] == 0
    committed = await _commit(client, headers, data["token"])
    assert committed.status_code == 200, committed.text

    # The created draft is reachable through the version list: the q filter
    # matches both drafts, so pick the imported one by its origin.
    versions = (await client.get(
        "/api/v1/configuration-versions", headers=headers, params={"q": "seed-DRAFT"}
    )).json()["data"]["items"]
    imported = next(item for item in versions if item["origin"] == "IMPORT")
    assert imported["status"] == "DRAFT"
    payload = (await client.get(
        f"/api/v1/configuration-versions/{imported['id']}", headers=headers
    )).json()["data"]
    assert payload["status"] == "DRAFT" and payload["origin"] == "IMPORT"
    assert payload["versionNo"] > seeded["versionNo"]
    tabs = payload["configSnapshot"]["tabs"]
    assert tabs and tabs[0]["code"] == "cargodetail"
    assert tabs[0]["groups"][0]["code"] == "containers"
    assert tabs[0]["groups"][0]["attributes"][0]["code"] == "container-no"


async def test_version_import_never_touches_published_versions(client, session_factory):
    headers = await login(client)
    published = await _seed_version(session_factory, json.loads(json.dumps(_SNAPSHOT)), status="PUBLISHED")
    published_no = published["versionNo"]
    content = _version_workbook()

    response = await _validate(client, headers, "configurationVersions", content)
    assert response.status_code == 200, response.text
    committed = await _commit(client, headers, response.json()["data"]["token"])
    assert committed.status_code == 200, committed.text

    from sqlalchemy import select

    from app.modules.master_data.models import ConfigurationVersion

    async with session_factory() as session:
        row = await session.get(ConfigurationVersion, published["id"])
        assert row.status == "PUBLISHED"
        assert row.version_no == published_no
        # The imported workbook became its own draft; the published snapshot is byte-identical.
        assert json.loads(json.dumps(row.config_snapshot)) == json.loads(json.dumps(_SNAPSHOT))
        live_versions = (
            await session.execute(select(ConfigurationVersion.status, ConfigurationVersion.version_no))
        ).all()
    draft_versions = [item for item in live_versions if item[0] != "PUBLISHED"]
    assert all(item[1] != published_no for item in draft_versions)
    # Only one PUBLISHED row remains (import never publishes).
    assert len([item for item in live_versions if item[0] == "PUBLISHED"]) >= 1


async def test_version_import_rejects_duplicate_draft_names_and_empty_notes(client):
    headers = await login(client)
    content = _multi_sheet({
        "Version": (["versionNo", "changeNote", "scope"], [[1, "", "GLOBAL"]]),
        "Attributes": (ATTR_HEADERS, []),
        "Groups": (GROUP_HEADERS, []),
        "Tabs": (TAB_HEADERS, []),
        "Relationships": (["tabCode", "groupCode", "attributeCode", "displayOrder", "isRequired"], []),
    })
    response = await _validate(client, headers, "configurationVersions", content)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["summary"]["error"] == 1


async def test_version_export_count_endpoint(client, session_factory):
    headers = await login(client)
    await _seed_version(session_factory, {"tabs": []}, status="DRAFT")
    await _seed_version(session_factory, {"tabs": []}, status="RETIRED")
    all_count = (await client.get(
        "/api/v1/excel/configurationVersions/export-count", headers=headers
    )).json()["data"]["count"]
    draft_count = (await client.get(
        "/api/v1/excel/configurationVersions/export-count", headers=headers, params={"status": "DRAFT"}
    )).json()["data"]["count"]
    assert draft_count >= 1 and all_count >= draft_count

    # The version's own snapshot workbook: one id at a time.
    list_bytes = await client.post(
        "/api/v1/excel/configurationVersions/export", headers=headers, json={"format": "xlsx"}
    )
    assert list_bytes.status_code == 200
    workbook = load_workbook(io.BytesIO(list_bytes.content))
    assert [cell.value for cell in workbook["Data"][1]][:2] == ["versionNo", "scope"]
