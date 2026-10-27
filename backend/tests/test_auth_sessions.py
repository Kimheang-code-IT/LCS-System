"""Stable session security boundaries, using controlled timestamps rather than sleeps."""
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_csrf_token, decode_token, hash_token
from app.modules.auth.models import User, UserSession
from tests.conftest import login


def csrf(client):
    return {settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name) or ""}


async def refresh(client, **kwargs):
    return await client.post("/api/v1/auth/refresh", json={}, headers={**csrf(client), **kwargs})


async def test_access_claims_and_no_refresh_in_json(client, session_factory):
    headers = await login(client)
    claims = decode_token(headers["Authorization"].split()[1])
    assert claims["exp"] - claims["iat"] == 900
    assert claims["iss"] == settings.jwt_issuer
    assert claims["aud"] == settings.jwt_audience
    async with session_factory() as session:
        record = await session.get(UserSession, int(claims["sid"]))
        assert record is not None
        raw = client.cookies.get(settings.refresh_cookie_name)
        assert raw and "." not in raw and record.refresh_token_hash != raw
    result = await refresh(client)
    assert result.status_code == 200
    assert "refresh_token" not in result.json()["data"]


async def test_expired_access_has_specific_code_then_cookie_can_renew(client):
    headers = await login(client)
    claims = decode_token(headers["Authorization"].split()[1])
    claims["iat"] = int((datetime.now(UTC) - timedelta(minutes=20)).timestamp())
    claims["exp"] = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
    expired = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.json()["code"] == "ACCESS_TOKEN_EXPIRED"
    assert (await refresh(client)).status_code == 200


@pytest.mark.parametrize("claim", ["iss", "aud"])
async def test_wrong_issuer_or_audience_is_rejected(client, claim):
    headers = await login(client)
    claims = decode_token(headers["Authorization"].split()[1])
    claims[claim] = "untrusted"
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    result = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 401
    assert result.json()["code"] != "ACCESS_TOKEN_EXPIRED"


async def test_logout_immediately_invalidates_current_access(client):
    headers = await login(client)
    result = await client.post("/api/v1/auth/logout", headers=csrf(client))
    assert result.status_code == 204
    denied = await client.get("/api/v1/auth/me", headers=headers)
    assert denied.status_code == 401
    assert denied.json()["code"] == "SESSION_REVOKED"


async def test_disabled_user_cannot_refresh(client, session_factory):
    headers = await login(client)
    user_id = int(decode_token(headers["Authorization"].split()[1])["sub"])
    async with session_factory() as session:
        user = await session.get(User, user_id)
        user.status = "INACTIVE"
        await session.commit()
    assert (await refresh(client)).status_code == 401


@pytest.mark.parametrize("deadline", ["idle", "absolute"])
async def test_expired_deadline_rejects_refresh_and_access(client, session_factory, deadline):
    headers = await login(client)
    async with session_factory() as session:
        record = (await session.scalars(select(UserSession))).one()
        if deadline == "idle":
            record.last_activity_at = datetime.now(UTC) - timedelta(hours=9)
        else:
            record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    denied = await client.get("/api/v1/auth/me", headers=headers)
    assert denied.json()["code"] == "SESSION_EXPIRED"
    denied = await refresh(client)
    assert denied.status_code == 401
    assert denied.json()["code"] == "SESSION_EXPIRED"
    assert any("Max-Age=0" in c for c in denied.headers.get_list("set-cookie"))


async def test_refresh_and_passive_gets_do_not_extend_idle_but_user_activity_does(client, session_factory):
    headers = await login(client)
    activity = datetime.now(UTC) - timedelta(minutes=5)
    async with session_factory() as session:
        record = (await session.scalars(select(UserSession))).one()
        record.last_activity_at = activity
        absolute = record.expires_at
        record_id = record.id
        await session.commit()
    assert (await refresh(client)).status_code == 200
    assert (await client.get("/api/v1/feeTypes", headers=headers)).status_code == 200
    async with session_factory() as session:
        record = await session.get(UserSession, record_id)
        assert record.last_activity_at.replace(tzinfo=UTC) == activity
        assert record.expires_at == absolute
    assert (await client.get("/api/v1/feeTypes", headers={**headers, "X-User-Activity": "1"})).status_code == 200
    async with session_factory() as session:
        record = await session.get(UserSession, record_id)
        assert record.last_activity_at.replace(tzinfo=UTC) > activity
        assert record.expires_at == absolute


async def test_origin_and_csrf_cannot_be_bypassed_using_bearer(client):
    headers = await login(client)
    result = await client.post("/api/v1/auth/refresh", json={}, headers=headers)
    assert result.status_code == 403
    result = await refresh(client, Origin="https://evil.example")
    assert result.status_code == 403
    result = await client.post("/api/v1/auth/logout", headers={**headers, **csrf(client), "Origin": "null"})
    assert result.status_code == 403
    assert (await refresh(client)).status_code == 200


async def test_settings_lifetimes_are_validated_and_used(client):
    headers = await login(client)
    path = "/api/v1/settings/app-config"
    # Find the existing endpoint through the same established settings API.
    for config in ({"accessTokenMinutes": 0}, {"accessTokenMinutes": 31}, {"sessionAbsoluteMinutes": 0}):
        result = await client.patch(path, headers=headers, json={"security": config})
        assert result.status_code == 422, result.text
    result = await client.patch(path, headers=headers, json={"security": {"accessTokenMinutes": 3, "sessionAbsoluteMinutes": 60}})
    assert result.status_code == 200, result.text
    result = await refresh(client)
    token = decode_token(result.json()["data"]["access_token"])
    assert token["exp"] - token["iat"] == 180


async def test_short_idle_policy_accepts_activity_before_the_deadline(client, session_factory):
    headers = await login(client)
    result = await client.patch("/api/v1/settings/app-config", headers=headers, json={"security": {"sessionTimeoutMinutes": 1}})
    assert result.status_code == 200
    activity = datetime.now(UTC) - timedelta(seconds=20)
    async with session_factory() as session:
        record = (await session.scalars(select(UserSession))).one()
        record.last_activity_at = activity
        await session.commit()
    assert (await client.get("/api/v1/feeTypes", headers={**headers, "X-User-Activity": "1"})).status_code == 200
    async with session_factory() as session:
        record = (await session.scalars(select(UserSession))).one()
        assert record.last_activity_at.replace(tzinfo=UTC) > activity


async def test_another_accounts_cookie_cannot_submit_the_current_users_draft(client):
    headers = await login(client, "sales")
    claims = decode_token(headers["Authorization"].split()[1])
    # A sibling tab switched the shared cookie to the administrator account.
    await login(client, "admin")
    denied = await client.post("/api/v1/service-orders", json={"customer": "ABC Manufacturing Co., Ltd.", "direction": "Import"},
                               headers={**csrf(client), "X-Expected-User-Id": claims["sub"]})
    assert denied.status_code == 409
    assert denied.json()["code"] == "SESSION_ACCOUNT_CHANGED"


async def test_legacy_production_refresh_cookie_is_exchanged_without_losing_session(client, session_factory, monkeypatch):
    await login(client)
    legacy = jwt.encode({"sub": "1", "type": "refresh", "exp": int(datetime.now(UTC).timestamp()) + 3600},
                        settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    async with session_factory() as session:
        record = (await session.scalars(select(UserSession))).one()
        original_id = record.id
        record.refresh_token_hash = hash_token(legacy)
        await session.commit()
    monkeypatch.setattr(settings, "cookie_secure", True)
    monkeypatch.setattr(settings, "refresh_cookie_name", "__Secure-refresh_token")
    monkeypatch.setattr(settings, "csrf_cookie_name", "__Host-XSRF-TOKEN")
    client.base_url = "https://testserver"
    client.cookies.clear()
    client.cookies.set("__Host-refresh_token", legacy, path="/")
    csrf_value = create_csrf_token(legacy)
    client.cookies.set(settings.csrf_cookie_name, csrf_value, path="/")
    response = await refresh(client)
    assert response.status_code == 200, response.text
    assert any("__Host-refresh_token=" in c and "Max-Age=0" in c for c in response.headers.get_list("set-cookie"))
    assert any("__Secure-refresh_token=" in c and "Path=/api/v1" in c and "Secure" in c and "HttpOnly" in c for c in response.headers.get_list("set-cookie"))
    async with session_factory() as session:
        record = (await session.scalars(select(UserSession))).one()
        assert record.id == original_id
        assert record.refresh_token_hash != hash_token(legacy)
