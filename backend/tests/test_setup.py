from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_setup_status_public_and_requires_setup(client):
    response = await client.get("/api/v1/setup/status")
    assert response.status_code == 200
    assert response.json()["data"]["requiresSetup"] is False


async def test_reset_then_setup_initialize_flow(client):
    headers = await login(client)

    reset = await client.post("/api/v1/settings/reset-data", headers=headers, json={"confirm": "RESET"})
    assert reset.status_code == 200, reset.text
    assert reset.json()["data"]["reset"] is True

    status = await client.get("/api/v1/setup/status")
    assert status.json()["data"]["requiresSetup"] is True

    invalid = await client.post("/api/v1/setup/initialize", json={"email": "bad", "password": "123"})
    assert invalid.status_code == 422
    assert "email" in invalid.json()["field_errors"]
    assert "password" in invalid.json()["field_errors"]

    created = await client.post(
        "/api/v1/setup/initialize",
        json={
            "email": "owner@fresh.test",
            "password": "Fresh123!",
            "name": "Fresh Owner",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["email"] == "owner@fresh.test"

    assert (await client.get("/api/v1/setup/status")).json()["data"]["requiresSetup"] is False

    # The freshly created admin can sign in. No business data is seeded.
    new_headers = await login(client, username="owner@fresh.test", password="Fresh123!")
    accounts = await client.get("/api/v1/chartOfAccounts", headers=new_headers)
    assert accounts.status_code == 200, accounts.text
    assert accounts.json()["data"]["meta"]["total"] == 0

    again = await client.post(
        "/api/v1/setup/initialize",
        json={"email": "second@fresh.test", "password": "Fresh123!"},
    )
    assert again.status_code == 409


async def test_reset_requires_typed_confirmation(client):
    headers = await login(client)
    response = await client.post("/api/v1/settings/reset-data", headers=headers, json={"confirm": "nope"})
    assert response.status_code == 422
    assert "confirm" in response.json()["field_errors"]
