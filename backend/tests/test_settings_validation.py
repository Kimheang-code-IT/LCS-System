"""Settings API: server-side validation, secret handling and honest connection status."""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

CONFIG = "/api/v1/settings/app-config"


async def test_out_of_range_settings_are_rejected_on_the_server(client):
    headers = await login(client)
    for payload, field in (
        ({"security": {"sessionTimeoutMinutes": 0}}, "security.sessionTimeoutMinutes"),
        ({"security": {"maxLoginAttempts": 500}}, "security.maxLoginAttempts"),
        ({"notifications": {"deliveryRetries": 99}}, "notifications.deliveryRetries"),
        ({"general": {"maxUploadSizeMb": 0}}, "general.maxUploadSizeMb"),
    ):
        response = await client.patch(CONFIG, headers=headers, json=payload)
        assert response.status_code == 422, response.text
        assert field in response.json()["field_errors"], response.text


async def test_enabling_a_channel_requires_its_configuration(client):
    headers = await login(client)

    email = await client.patch(CONFIG, headers=headers, json={"email": {"enabled": True, "smtpHost": ""}})
    assert email.status_code == 422, email.text
    assert "email.smtpHost" in email.json()["field_errors"]

    telegram = await client.patch(CONFIG, headers=headers, json={"telegram": {"enabled": True, "botToken": ""}})
    assert telegram.status_code == 422, telegram.text
    assert "telegram.botToken" in telegram.json()["field_errors"]


async def test_secrets_are_masked_and_blank_keeps_the_stored_value(client):
    headers = await login(client)
    saved = await client.patch(
        CONFIG,
        headers=headers,
        json={"email": {"enabled": True, "smtpHost": "smtp.example.test", "smtpPort": 587, "password": "top-secret"}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["email"]["password"] == ""
    assert saved.json()["data"]["email"]["passwordConfigured"] is True

    blank = await client.patch(CONFIG, headers=headers, json={"email": {"password": "", "username": "ops"}})
    assert blank.status_code == 200, blank.text
    assert blank.json()["data"]["email"]["passwordConfigured"] is True


async def test_connection_check_does_not_claim_a_fake_success(client):
    headers = await login(client)
    saved = await client.patch(
        CONFIG,
        headers=headers,
        json={"email": {"enabled": True, "smtpHost": "smtp.example.test", "smtpPort": 587}},
    )
    assert saved.status_code == 200, saved.text
    tested = await client.post(f"{CONFIG}/email/test-connection", headers=headers, json={})
    assert tested.status_code == 200, tested.text
    assert tested.json()["data"]["status"] == "not_verified"
    assert "does not run a live" in tested.json()["data"]["message"]


async def test_system_status_is_reported_from_runtime_state(client):
    headers = await login(client)
    config = (await client.get(CONFIG, headers=headers)).json()["data"]
    system = config["system"]
    from app.core.config import settings as app_settings

    assert system["environment"] == app_settings.environment
    assert system["cacheStatus"] in {"enabled", "disabled"}
    assert system["backgroundJobStatus"] in {"running", "scheduled", "idle"}
    assert system["configurationVersion"]


async def test_unauthorized_roles_cannot_change_settings(client):
    admin = await login(client)
    assert (await client.get(CONFIG, headers=admin)).status_code == 200
    sales = await login(client, "sales")
    denied = await client.patch(CONFIG, headers=sales, json={"security": {"maxLoginAttempts": 9}})
    assert denied.status_code == 403, denied.text
