"""Remember Me / refresh-session behavior tests.

These tests exercise the cookie contract (persistent vs browser-session),
server-side session lifetime, refresh rotation, reuse/expiry rejection, and
logout revocation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.auth.models import UserSession
from tests.seed import DEFAULT_PASSWORD

AUTH_COOKIES = (
    settings.access_cookie_name,
    settings.refresh_cookie_name,
    settings.csrf_cookie_name,
)


def _set_cookies(response) -> SimpleCookie:
    jar = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        parsed.load(header)
        jar.update(parsed)
    return jar


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _restarted_client() -> AsyncClient:
    """A client with an empty cookie jar, simulating a browser restart."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, *, remember_me: bool | None = None):
    body: dict[str, object] = {"username": "admin", "password": DEFAULT_PASSWORD}
    if remember_me is not None:
        body["remember_me"] = remember_me
    response = await client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 200, response.text
    return response


async def _only_session(session_factory) -> UserSession:
    async with session_factory() as session:
        return (await session.execute(select(UserSession))).scalars().one()


async def test_login_without_remember_me_sets_browser_session_cookies(client, session_factory):
    response = await _login(client, remember_me=False)
    cookies = _set_cookies(response)

    for name in AUTH_COOKIES:
        morsel = cookies.get(name)
        assert morsel is not None
        assert not morsel["max-age"]
        assert not morsel["expires"]
        assert morsel["path"] == (settings.api_v1_prefix if name == settings.refresh_cookie_name else "/")
        assert morsel["samesite"].lower() == "lax"

    assert cookies[settings.access_cookie_name]["httponly"] is True
    assert cookies[settings.refresh_cookie_name]["httponly"] is True
    assert not cookies[settings.csrf_cookie_name]["httponly"]

    row = await _only_session(session_factory)
    assert not row.remember_me
    expected = datetime.now(UTC) + timedelta(minutes=settings.session_absolute_timeout_minutes)
    assert abs((_as_utc(row.expires_at) - expected).total_seconds()) < 60


async def test_login_with_remember_me_sets_persistent_cookies(client, session_factory):
    response = await _login(client, remember_me=True)
    cookies = _set_cookies(response)

    assert int(cookies[settings.access_cookie_name]["max-age"]) == settings.access_token_expire_minutes * 60
    assert int(cookies[settings.refresh_cookie_name]["max-age"]) <= settings.session_absolute_timeout_minutes * 60
    assert int(cookies[settings.csrf_cookie_name]["max-age"]) <= settings.session_absolute_timeout_minutes * 60

    row = await _only_session(session_factory)
    assert row.remember_me
    expected = datetime.now(UTC) + timedelta(minutes=settings.session_absolute_timeout_minutes)
    assert abs((_as_utc(row.expires_at) - expected).total_seconds()) < 60


async def test_login_omitting_remember_me_defaults_to_session_cookies(client):
    response = await _login(client)
    cookies = _set_cookies(response)
    assert not cookies[settings.refresh_cookie_name]["max-age"]


async def test_browser_restart_with_remember_me_restores_session(client):
    response = await _login(client, remember_me=True)
    refresh_token = _set_cookies(response)[settings.refresh_cookie_name].value
    cookies = _set_cookies(response)
    assert int(cookies[settings.refresh_cookie_name]["max-age"]) <= settings.session_absolute_timeout_minutes * 60

    async with _restarted_client() as fresh_client:
        fresh_client.cookies.set(settings.refresh_cookie_name, refresh_token, path=settings.api_v1_prefix)
        fresh_client.cookies.set(settings.csrf_cookie_name, cookies[settings.csrf_cookie_name].value)
        restored = await fresh_client.post("/api/v1/auth/refresh", json={}, headers={settings.csrf_header_name: cookies[settings.csrf_cookie_name].value})
        assert restored.status_code == 200, restored.text
        restored_cookies = _set_cookies(restored)
        assert 0 < int(restored_cookies[settings.refresh_cookie_name]["max-age"]) <= (
            settings.session_absolute_timeout_minutes * 60
        )


async def test_refresh_rotation_preserves_remember_me_and_absolute_expiry(client, session_factory):
    response = await _login(client, remember_me=True)
    original_refresh = _set_cookies(response)[settings.refresh_cookie_name].value
    csrf_token = client.cookies.get(settings.csrf_cookie_name)
    original_expiry = _as_utc((await _only_session(session_factory)).expires_at)

    rotated = await client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={settings.csrf_header_name: csrf_token or ""},
    )
    assert rotated.status_code == 200, rotated.text
    rotated_cookies = _set_cookies(rotated)
    assert int(rotated_cookies[settings.refresh_cookie_name]["max-age"]) <= settings.session_absolute_timeout_minutes * 60
    assert rotated_cookies[settings.refresh_cookie_name].value != original_refresh

    async with session_factory() as session:
        rows = (await session.execute(select(UserSession).order_by(UserSession.id))).scalars().all()
    assert len(rows) == 1
    new_row = rows[0]
    assert new_row.revoked_at is None
    assert new_row.remember_me
    assert abs((_as_utc(new_row.expires_at) - original_expiry).total_seconds()) < 1


async def test_refresh_without_remember_me_keeps_session_cookies_and_expiry(client, session_factory):
    await _login(client, remember_me=False)
    original_expiry = _as_utc((await _only_session(session_factory)).expires_at)
    csrf_token = client.cookies.get(settings.csrf_cookie_name)

    rotated = await client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={settings.csrf_header_name: csrf_token or ""},
    )
    assert rotated.status_code == 200, rotated.text
    rotated_cookies = _set_cookies(rotated)
    assert not rotated_cookies[settings.refresh_cookie_name]["max-age"]

    async with session_factory() as session:
        rows = (await session.execute(select(UserSession).order_by(UserSession.id))).scalars().all()
    assert len(rows) == 1
    new_row = rows[0]
    assert new_row.revoked_at is None
    assert not new_row.remember_me
    assert abs((_as_utc(new_row.expires_at) - original_expiry).total_seconds()) < 1


async def test_rotated_refresh_token_cannot_be_reused(client, session_factory):
    response = await _login(client, remember_me=True)
    original_refresh = _set_cookies(response)[settings.refresh_cookie_name].value
    csrf_token = client.cookies.get(settings.csrf_cookie_name)

    rotated = await client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={settings.csrf_header_name: csrf_token or ""},
    )
    assert rotated.status_code == 200, rotated.text

    # An overlap is rejected without destroying the winning tab's cookies.
    client.cookies.set(settings.refresh_cookie_name, original_refresh, domain="testserver.local", path=settings.api_v1_prefix)
    client.cookies.set(settings.csrf_cookie_name, csrf_token, domain="testserver.local", path="/")
    reused = await client.post("/api/v1/auth/refresh", json={}, headers={settings.csrf_header_name: csrf_token})
    assert reused.status_code == 409
    assert reused.json()["code"] == "REFRESH_CONFLICT"
    from app.modules.auth.models import UsedRefreshToken
    async with session_factory() as session:
        used = (await session.execute(select(UsedRefreshToken))).scalar_one()
        used.used_at = datetime.now(UTC) - timedelta(seconds=10)
        await session.commit()
    replayed = await client.post("/api/v1/auth/refresh", json={}, headers={settings.csrf_header_name: csrf_token})
    assert replayed.status_code == 401
    assert replayed.json()["code"] == "SESSION_REVOKED"
    assert (await _only_session(session_factory)).revoked_at is not None


async def test_expired_refresh_session_is_rejected(client, session_factory):
    await _login(client, remember_me=True)

    async with session_factory() as session:
        row = (await session.execute(select(UserSession))).scalars().one()
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    csrf = client.cookies.get(settings.csrf_cookie_name)
    expired = await client.post("/api/v1/auth/refresh", json={}, headers={settings.csrf_header_name: csrf})
    assert expired.status_code == 401
    assert "expired" in expired.json()["message"].lower()


async def test_cookie_refresh_still_requires_csrf_token(client):
    await _login(client, remember_me=True)

    rejected = await client.post("/api/v1/auth/refresh", json={})
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "CSRF_VALIDATION_FAILED"


async def test_logout_revokes_refresh_session_and_clears_cookies(client, session_factory):
    response = await _login(client, remember_me=True)
    refresh_token = _set_cookies(response)[settings.refresh_cookie_name].value
    csrf_token = client.cookies.get(settings.csrf_cookie_name)

    logout = await client.post("/api/v1/auth/logout", headers={settings.csrf_header_name: csrf_token or ""})
    assert logout.status_code == 204

    cleared = _set_cookies(logout)
    for name in AUTH_COOKIES:
        assert cleared.get(name) is not None
        assert cleared[name]["max-age"] == "0"

    assert (await _only_session(session_factory)).revoked_at is not None

    client.cookies.clear()
    client.cookies.set(settings.refresh_cookie_name, refresh_token, path=settings.api_v1_prefix)
    from app.core.security import create_csrf_token
    csrf = create_csrf_token(refresh_token)
    client.cookies.set(settings.csrf_cookie_name, csrf)
    rejected = await client.post("/api/v1/auth/refresh", json={}, headers={settings.csrf_header_name: csrf})
    assert rejected.status_code == 401


async def test_logout_still_revokes_when_access_token_expired(client, session_factory):
    await _login(client, remember_me=True)
    csrf_token = client.cookies.get(settings.csrf_cookie_name)

    # Corrupt the access cookie in place (simulating an expired access token)
    # while keeping the valid refresh/CSRF pair.
    for cookie in client.cookies.jar:
        if cookie.name == settings.access_cookie_name:
            cookie.value = "invalid-access-token"

    logout = await client.post("/api/v1/auth/logout", headers={settings.csrf_header_name: csrf_token or ""})
    assert logout.status_code == 204
    assert (await _only_session(session_factory)).revoked_at is not None


async def test_logout_without_credentials_is_rejected(client):
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 401
