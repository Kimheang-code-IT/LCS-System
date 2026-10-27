"""Account lockout policy is read from the stored configuration.

`app_settings('security')` exposes `maxLoginAttempts` and `accountLockMinutes` in
the administration UI, but the backend ignored them and always used the hardcoded
5 / 15. An administrator could tighten the policy and nothing changed.

The stored values are now honoured, clamped to a safe range so a bad configuration
cannot silently disable the control.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _set_security(client, headers, patch: dict) -> None:
    response = await client.patch(
        "/api/v1/settings/app-config", headers=headers, json={"security": patch}
    )
    assert response.status_code == 200, response.text


async def _fail_login(client, username: str, times: int) -> None:
    for _ in range(times):
        response = await client.post(
            "/api/v1/auth/login", json={"username": username, "password": "definitely-wrong"}
        )
        assert response.status_code in {401, 403, 429}, response.text


async def test_a_tightened_lockout_threshold_is_honoured(client):
    """Three failed attempts, not the default five."""
    headers = await login(client)
    await _set_security(client, headers, {"maxLoginAttempts": 3, "accountLockMinutes": 5})

    # below the threshold: still allowed to try
    await _fail_login(client, "ops.pp", 2)
    assert (
        await client.post(
            "/api/v1/auth/login", json={"username": "ops.pp", "password": "Passw0rd!"}
        )
    ).status_code == 200, "the correct password must still work two failures in"

    # reaching the configured threshold must lock the account
    await _fail_login(client, "ops.pp", 3)
    locked = await client.post(
        "/api/v1/auth/login", json={"username": "ops.pp", "password": "Passw0rd!"}
    )
    assert locked.status_code in {401, 403}, (
        f"the account must be locked after 3 failures, got {locked.status_code}"
    )


async def test_the_default_threshold_applies_when_nothing_is_configured(client):
    """A fresh installation keeps the documented 5-attempt default."""
    headers = await login(client)
    config = await client.get("/api/v1/settings/app-config", headers=headers)
    assert config.status_code == 200, config.text
    security = config.json()["data"]["security"]
    assert security["maxLoginAttempts"] == 5
    assert security["accountLockMinutes"] == 15

    await _fail_login(client, "sales", 4)
    assert (
        await client.post(
            "/api/v1/auth/login", json={"username": "sales", "password": "Passw0rd!"}
        )
    ).status_code == 200, "four failures must not lock when the threshold is five"


async def test_an_unsafe_stored_threshold_is_clamped_rather_than_obeyed(client, session_factory):
    """A legacy stored value that would remove the control must not take effect.

    The settings API now refuses these values, so this writes the row directly to
    simulate data stored before that validation existed.
    """
    from sqlalchemy import select

    from app.modules.settings.models import AppSetting

    async with session_factory() as session:
        row = (
            await session.execute(select(AppSetting).where(AppSetting.setting_key == "security"))
        ).scalars().first()
        if row is None:
            row = AppSetting(setting_key="security", setting_group="security", setting_value={})
            session.add(row)
        row.setting_value = {"maxLoginAttempts": 0, "accountLockMinutes": 0}
        await session.commit()

    assert (
        await client.post(
            "/api/v1/auth/login", json={"username": "finance", "password": "Passw0rd!"}
        )
    ).status_code == 200, "a clamped threshold must not lock an account out immediately"

    # The clamp floor is 3 attempts, so two failures then a success must work.
    await _fail_login(client, "finance", 2)
    assert (
        await client.post(
            "/api/v1/auth/login", json={"username": "finance", "password": "Passw0rd!"}
        )
    ).status_code == 200


async def test_a_successful_login_clears_the_failure_counter(client):
    headers = await login(client)
    await _set_security(client, headers, {"maxLoginAttempts": 3, "accountLockMinutes": 5})

    await _fail_login(client, "ops.pp", 2)
    assert (
        await client.post(
            "/api/v1/auth/login", json={"username": "ops.pp", "password": "Passw0rd!"}
        )
    ).status_code == 200

    # The counter reset, so another two failures must still be tolerated.
    await _fail_login(client, "ops.pp", 2)
    assert (
        await client.post(
            "/api/v1/auth/login", json={"username": "ops.pp", "password": "Passw0rd!"}
        )
    ).status_code == 200, "a successful login must reset the failure count"
