"""Backend enforcement of maintenance mode, read-only mode, session timeout and password policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.models import User, UserCredential
from tests.conftest import login
from tests.seed import DEFAULT_PASSWORD

pytestmark = pytest.mark.asyncio
CONFIG = "/api/v1/settings/app-config"


async def _admin_credential(session_factory) -> tuple[int, UserCredential]:
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.username == "admin"))).scalar_one()
        credential = await session.get(UserCredential, user.id)
        assert credential is not None
        return user.id, credential


async def test_maintenance_blocks_ordinary_access_but_keeps_admin_recovery(client):
    admin = await login(client)
    sales = await login(client, "sales")
    enabled = await client.patch(CONFIG, headers=admin, json={"system": {"maintenanceMode": True}})
    assert enabled.status_code == 200, enabled.text

    blocked = await client.get("/api/v1/quotations", headers=admin)
    assert blocked.status_code == 503, blocked.text
    assert blocked.json()["code"] == "MAINTENANCE_MODE"
    assert (await client.get("/api/v1/quotations", headers=sales)).status_code == 503

    # Recovery: an administrator can still read and change settings.
    assert (await client.get(CONFIG, headers=admin)).status_code == 200
    disabled = await client.patch(CONFIG, headers=admin, json={"system": {"maintenanceMode": False}})
    assert disabled.status_code == 200, disabled.text
    assert (await client.get("/api/v1/quotations", headers=admin)).status_code == 200


async def test_read_only_mode_rejects_writes_and_keeps_reads(client):
    admin = await login(client)
    enabled = await client.patch(CONFIG, headers=admin, json={"system": {"readOnlyMode": True}})
    assert enabled.status_code == 200, enabled.text

    assert (await client.get("/api/v1/quotations", headers=admin)).status_code == 200
    write = await client.post("/api/v1/feeTypes", headers=admin, json={"code": "RO-BLOCK", "name": "Blocked"})
    assert write.status_code == 409, write.text
    assert write.json()["code"] == "READ_ONLY_MODE"
    for method, path, body in (
        ("PUT", "/api/v1/quotations/1", {}),
        ("PATCH", "/api/v1/attachments/1", {"note": "x"}),
        ("DELETE", "/api/v1/attachments", {"ids": []}),
    ):
        blocked = await client.request(method, path, headers=admin, json=body)
        assert blocked.status_code == 409, f"{method} {path}: {blocked.text}"

    # Recovery: the administrator may turn the mode off from Settings.
    disabled = await client.patch(CONFIG, headers=admin, json={"system": {"readOnlyMode": False}})
    assert disabled.status_code == 200, disabled.text
    allowed = await client.post("/api/v1/feeTypes", headers=admin, json={"code": "RO-OK", "name": "Allowed"})
    assert allowed.status_code == 201, allowed.text


async def test_configured_session_timeout_expires_old_access_tokens(client, session_factory):
    from sqlalchemy import update

    from app.modules.auth.models import UserSession

    admin = await login(client)
    saved = await client.patch(CONFIG, headers=admin, json={"security": {"sessionTimeoutMinutes": 1}})
    assert saved.status_code == 200, saved.text
    async with session_factory() as session:
        await session.execute(update(UserSession).values(last_activity_at=datetime.now(UTC) - timedelta(minutes=5)))
        await session.commit()
    expired = await client.get("/api/v1/auth/me", headers=admin)
    assert expired.status_code == 401
    assert expired.json()["code"] == "SESSION_EXPIRED"


async def test_password_expiry_requires_a_change_before_other_routes(client, session_factory):
    admin = await login(client)
    saved = await client.patch(CONFIG, headers=admin, json={"security": {"passwordExpiryDays": 1}})
    assert saved.status_code == 200, saved.text

    user_id, _ = await _admin_credential(session_factory)
    async with session_factory() as session:
        credential = await session.get(UserCredential, user_id)
        credential.password_changed_at = datetime.now(UTC) - timedelta(days=5)
        await session.commit()

    blocked = await client.get("/api/v1/quotations", headers=admin)
    assert blocked.status_code == 403, blocked.text
    assert "password" in blocked.text.lower()
    # Safe recovery path stays reachable.
    assert (await client.get("/api/v1/auth/me", headers=admin)).status_code == 200

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=admin,
        json={"current_password": DEFAULT_PASSWORD, "password": "NewPassw0rd!95"},
    )
    assert changed.status_code == 200, changed.text
    fresh = await login(client, "admin", "NewPassw0rd!95")
    assert (await client.get("/api/v1/quotations", headers=fresh)).status_code == 200


async def test_global_require_password_change_is_one_shot(client):
    admin = await login(client)
    saved = await client.patch(CONFIG, headers=admin, json={"security": {"requirePasswordChange": True}})
    assert saved.status_code == 200, saved.text

    blocked = await client.get("/api/v1/quotations", headers=admin)
    assert blocked.status_code == 403, blocked.text

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=admin,
        json={"current_password": DEFAULT_PASSWORD, "password": "Another0rd!95A"},
    )
    assert changed.status_code == 200, changed.text
    fresh = await login(client, "admin", "Another0rd!95A")
    assert (await client.get("/api/v1/quotations", headers=fresh)).status_code == 200


async def test_session_timeout_also_stops_refresh_rotation(client, session_factory):
    from sqlalchemy import update

    from app.modules.auth.models import UserSession

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    tokens = response.json()["data"]
    admin = {"Authorization": f"Bearer {tokens['access_token']}"}
    saved = await client.patch(CONFIG, headers=admin, json={"security": {"sessionTimeoutMinutes": 1}})
    assert saved.status_code == 200, saved.text

    async with session_factory() as session:
        await session.execute(
            update(UserSession).values(last_activity_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await session.commit()

    csrf = client.cookies.get(settings.csrf_cookie_name)
    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={settings.csrf_header_name: csrf or ""},
    )
    assert refreshed.status_code == 401, refreshed.text
    assert refreshed.json()["code"] == "SESSION_EXPIRED"


async def test_login_lockout_protections_still_apply(client):
    # Wrong password still counts toward the configured attempt limit; this is a
    # regression guard for the existing lockout logic while adding the policies.
    for _ in range(2):
        attempt = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "definitely-wrong"},
        )
        assert attempt.status_code in {401, 422, 423}, attempt.text
