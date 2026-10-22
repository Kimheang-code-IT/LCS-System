"""Container Types must round-trip every field through create, read and update.

The example payload is the one the owner supplied: a 20GP box with a 2.438 m
width and 2.591 m height. Width and height are edited in metres but stored in
millimetres, so the conversion has to be exact in both directions.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

EXAMPLE = {
    "code": "20GP",
    "name": "20ft General Purpose",
    "size": "20FT",
    "kind": "GP",
    "isoCode": "22G1",
    "lengthFeet": 20,
    "widthMeters": 2.438,
    "heightMeters": 2.591,
    "maxGrossWeightKg": 30480,
}


async def _create(client, headers, payload: dict):
    return await client.post("/api/v1/containerTypes", headers=headers, json=payload)


async def test_container_type_all_fields_round_trip(client):
    headers = await login(client)
    created = await _create(client, headers, {**EXAMPLE, "status": "ACTIVE"})
    assert created.status_code == 201, created.text
    body = created.json()["data"]

    assert body["code"] == "20GP"
    assert body["name"] == "20ft General Purpose"
    assert body["size"] == "20FT"
    assert body["kind"] == "GP"
    assert body["isoCode"] == "22G1"
    assert float(body["lengthFeet"]) == 20
    # Metres survive the millimetre round trip exactly.
    assert body["widthMeters"] == 2.438
    assert body["heightMeters"] == 2.591
    assert float(body["maxGrossWeightKg"]) == 30480

    fetched = await client.get(f"/api/v1/containerTypes/{body['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    detail = fetched.json()["data"]
    assert detail["widthMeters"] == 2.438
    assert detail["heightMeters"] == 2.591
    assert detail["isoCode"] == "22G1"
    assert detail["kind"] == "GP"


async def test_container_type_update_persists_every_field(client):
    headers = await login(client)
    created = (await _create(client, headers, {**EXAMPLE, "code": "40HC-EDIT", "status": "ACTIVE"})).json()["data"]

    updated = await client.put(
        f"/api/v1/containerTypes/{created['id']}",
        headers=headers,
        json={
            "code": "40HC-EDIT",
            "name": "40ft High Cube",
            "size": "40FT",
            "kind": "HC",
            "isoCode": "45G1",
            "lengthFeet": 40,
            "widthMeters": 2.438,
            "heightMeters": 2.896,
            "maxGrossWeightKg": 32500,
        },
    )
    assert updated.status_code == 200, updated.text

    fetched = (await client.get(f"/api/v1/containerTypes/{created['id']}", headers=headers)).json()["data"]
    assert fetched["name"] == "40ft High Cube"
    assert fetched["size"] == "40FT"
    assert fetched["kind"] == "HC"
    assert fetched["isoCode"] == "45G1"
    assert float(fetched["lengthFeet"]) == 40
    assert fetched["heightMeters"] == 2.896
    assert float(fetched["maxGrossWeightKg"]) == 32500


async def test_container_type_code_is_required_and_unique(client):
    headers = await login(client)
    blank = await _create(client, headers, {**EXAMPLE, "code": ""})
    assert blank.status_code == 422, blank.text
    assert "code" in blank.json()["field_errors"]

    first = await _create(client, headers, {**EXAMPLE, "code": "DUP-20GP"})
    assert first.status_code == 201, first.text
    duplicate = await _create(client, headers, {**EXAMPLE, "code": "DUP-20GP", "name": "Another 20GP"})
    assert duplicate.status_code == 422, duplicate.text
    assert "code" in duplicate.json()["field_errors"]


async def test_container_type_delete_round_trip(client):
    headers = await login(client)
    created = (await _create(client, headers, {**EXAMPLE, "code": "DEL-20GP", "status": "INACTIVE"})).json()["data"]

    removed = await client.request(
        "DELETE", "/api/v1/containerTypes", headers=headers, json={"ids": [created["id"]]}
    )
    assert removed.status_code == 200, removed.text

    fetched = await client.get(f"/api/v1/containerTypes/{created['id']}", headers=headers)
    assert fetched.status_code == 404, fetched.text
