from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.modules.master_data.models import ModuleRecord
from app.modules.settings.service import APP_CONFIG_COLLECTION, DEFAULT_APP_CONFIG
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_localization_defaults_when_config_record_is_missing(client, session_factory):
    async with session_factory() as session:
        await session.execute(delete(ModuleRecord).where(ModuleRecord.collection == APP_CONFIG_COLLECTION))
        await session.commit()

    response = await client.get("/api/v1/settings/app-config", headers=await login(client))
    assert response.status_code == 200
    assert response.json()["data"]["localization"] == DEFAULT_APP_CONFIG["localization"]


async def test_localization_roundtrip_and_legacy_number_format_normalization(client):
    headers = await login(client)
    response = await client.patch(
        "/api/v1/settings/app-config",
        headers=headers,
        json={
            "localization": {
                "defaultLanguage": "km",
                "timezone": "America/New_York",
                "dateFormat": "D MMM YYYY",
                "timeFormat": "h:mm:ss A",
                "numberFormat": "1.234,56",
                "currency": "EUR",
            }
        },
    )
    assert response.status_code == 200, response.text
    saved = response.json()["data"]["localization"]
    assert saved["defaultLanguage"] == "km"
    assert saved["locale"] == "km-KH"
    assert saved["timezone"] == "America/New_York"
    assert saved["dateFormat"] == "D MMM YYYY"
    assert saved["timeFormat"] == "h:mm:ss A"
    assert saved["numberFormat"] == "#.##0,00"
    assert saved["currency"] == "EUR"

    reloaded = await client.get("/api/v1/settings/app-config", headers=headers)
    assert reloaded.json()["data"]["localization"] == saved


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timezone", "Mars/Olympus_Mons"),
        ("dateFormat", "YY/DD"),
        ("timeFormat", "clock"),
        ("numberFormat", "random"),
        ("currency", "BTC"),
        ("defaultLanguage", "zz"),
    ],
)
async def test_invalid_localization_value_is_rejected(client, field, value):
    response = await client.patch(
        "/api/v1/settings/app-config",
        headers=await login(client),
        json={"localization": {field: value}},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert f"localization.{field}" in response.json()["field_errors"]


async def test_localization_update_requires_configuration_permission(client):
    admin_headers = await login(client)
    created = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": "localization.reader",
            "displayName": "Localization Reader",
            "email": "localization.reader@example.com",
            "role": "AUDITOR",
            "status": "ACTIVE",
            "password": "Passw0rd!",
        },
    )
    assert created.status_code == 201, created.text
    reader_headers = await login(client, "localization.reader")

    readable = await client.get("/api/v1/settings/app-config", headers=reader_headers)
    assert readable.status_code == 200
    denied = await client.patch(
        "/api/v1/settings/app-config",
        headers=reader_headers,
        json={"localization": {"currency": "KHR"}},
    )
    assert denied.status_code == 403


async def test_global_currency_is_only_a_default_for_new_business_records(client):
    headers = await login(client)
    configured = await client.patch(
        "/api/v1/settings/app-config",
        headers=headers,
        json={"localization": {"currency": "KHR"}},
    )
    assert configured.status_code == 200, configured.text

    defaulted = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={"date": "2026-10-01", "customer": "Default Currency Customer", "direction": "Export"},
    )
    assert defaulted.status_code == 201, defaulted.text
    assert defaulted.json()["data"]["currency"] == "KHR"

    explicit = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": "2026-10-01",
            "customer": "Default Currency Customer",
            "direction": "Export",
            "currency": "USD",
        },
    )
    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["data"]["currency"] == "USD"
