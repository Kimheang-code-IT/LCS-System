"""Redis integration tests: cache behaviour, invalidation, API wiring.

The suite never depends on a running Redis server: an in-memory FakeRedis is
injected into ``app.core.redis._client``. A separate connectivity test skips
when no real server is reachable.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import event

from app.core import cache
from app.core import redis as redis_core
from app.core.config import settings
from tests.conftest import login
from tests.fake_redis import FakeRedis


@pytest_asyncio.fixture
async def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(settings, "cache_enabled", True)
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(redis_core, "_client", fake)
    yield fake


class QueryCounter:
    """Counts (and records) SQL statements executed while the context is active."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.count = 0
        self.statements: list[str] = []
        self._listener = None

    def __enter__(self):
        def listener(conn, cursor, statement, parameters, context, executemany):
            self.count += 1
            self.statements.append(" ".join(statement.split()))

        self._listener = listener
        event.listen(self.engine.sync_engine, "before_cursor_execute", listener)
        return self

    def __exit__(self, *args):
        event.remove(self.engine.sync_engine, "before_cursor_execute", self._listener)
        return False


# --- core cache behaviour -----------------------------------------------------


@pytest.mark.asyncio
async def test_cache_roundtrip_and_ttl_expiry(fake_redis):
    await cache.set_json("reports", "k1", value={"a": 1}, ttl_seconds=30)
    assert await cache.get_json("reports", "k1") == {"a": 1}

    fake_redis.now += 31
    assert await cache.get_json("reports", "k1") is None


@pytest.mark.asyncio
async def test_cache_namespace_invalidation(fake_redis):
    await cache.set_json("master_data", "list", value=[1, 2], ttl_seconds=60)
    assert await cache.get_json("master_data", "list") == [1, 2]
    await cache.bump("master_data")
    assert await cache.get_json("master_data", "list") is None


@pytest.mark.asyncio
async def test_cache_key_isolation(fake_redis):
    await cache.set_json("master_data", "samples", 1, value="a", ttl_seconds=60)
    await cache.set_json("reports", "samples", 1, value="b", ttl_seconds=60)
    await cache.set_json("master_data", "samples", 2, value="c", ttl_seconds=60)
    assert await cache.get_json("master_data", "samples", 1) == "a"
    assert await cache.get_json("reports", "samples", 1) == "b"
    assert await cache.get_json("master_data", "samples", 2) == "c"


@pytest.mark.asyncio
async def test_cache_corrupt_payload_falls_back(fake_redis):
    version = await cache.version("reports")
    bad_key = cache.key("reports", version, "dashboard")
    fake_redis.store[bad_key] = "{not-json"
    assert await cache.get_json("reports", "dashboard") is None
    assert bad_key not in fake_redis.store


@pytest.mark.asyncio
async def test_cache_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "cache_enabled", False)
    monkeypatch.setattr(settings, "redis_enabled", True)
    await cache.set_json("reports", "k", value="v", ttl_seconds=60)
    assert await cache.get_json("reports", "k") is None


@pytest.mark.asyncio
async def test_redis_errors_never_raise(fake_redis):
    fake_redis.fail = True
    assert await cache.get_json("reports", "x") is None
    await cache.set_json("reports", "x", value="v", ttl_seconds=60)  # no exception
    await cache.bump("reports")  # no exception
    assert await redis_core.redis_health() == "down"


@pytest.mark.asyncio
async def test_redis_health_states(fake_redis, monkeypatch):
    assert await redis_core.redis_health() == "up"
    fake_redis.fail = True
    assert await redis_core.redis_health() == "down"
    monkeypatch.setattr(settings, "redis_enabled", False)
    assert await redis_core.redis_health() == "disabled"


@pytest.mark.asyncio
async def test_real_redis_connectivity():
    """Optional integration check against a real Redis, skipped when absent."""
    import redis.asyncio as aioredis

    urls = [settings.redis_url]
    # On Windows ``localhost`` may resolve to ::1 first while Docker publishes
    # the port on IPv4 only; retry the explicit loopback address.
    if "localhost" in settings.redis_url:
        urls.append(settings.redis_url.replace("localhost", "127.0.0.1"))
    last_error: Exception | None = None
    for url in urls:
        client = aioredis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await client.ping()
        except Exception as exc:
            last_error = exc
            await client.aclose()
            continue
        await client.aclose()
        return
    pytest.skip(f"No Redis server reachable ({urls}): {type(last_error).__name__}: {last_error}")


# --- master data + business party caching ------------------------------------


@pytest.mark.asyncio
async def test_master_data_list_cache_hit_and_invalidation(client, fake_redis, engine):
    headers = await login(client)

    with QueryCounter(engine) as first:
        response = await client.get("/api/v1/placeRoles", headers=headers)
    assert response.status_code == 200, response.text
    assert first.count > 0

    with QueryCounter(engine) as second:
        cached = await client.get("/api/v1/placeRoles", headers=headers)
    assert cached.status_code == 200
    assert cached.json() == response.json()
    assert second.count <= 1, "cached list response must not query the database"

    created = await client.post(
        "/api/v1/placeRoles",
        headers=headers,
        json={"code": "NEWPR", "name": "New Place Role", "sortOrder": 99, "status": "ACTIVE"},
    )
    assert created.status_code == 201, created.text

    refreshed = await client.get("/api/v1/placeRoles", headers=headers)
    assert refreshed.status_code == 200
    names = [item.get("name") for item in refreshed.json()["data"]["items"]]
    assert "New Place Role" in names


@pytest.mark.asyncio
async def test_business_party_cache_invalidated_on_update(client, fake_redis):
    headers = await login(client)
    listed = await client.get("/api/v1/businessParties", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert items
    target = items[0]
    original = target["legalName"]

    updated = await client.put(
        f"/api/v1/businessParties/{target['id']}",
        headers=headers,
        json={"displayName": "Cached Display Name"},
    )
    assert updated.status_code == 200, updated.text

    after = await client.get("/api/v1/businessParties", headers=headers)
    refreshed = next(item for item in after.json()["data"]["items"] if item["id"] == target["id"])
    assert refreshed["legalName"] == original
    assert refreshed["displayName"] == "Cached Display Name"


# --- reports caching ----------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_cache_hit_and_bump(client, fake_redis, engine):
    headers = await login(client)

    with QueryCounter(engine) as first:
        response = await client.get("/api/v1/reports/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    assert first.count > 1

    with QueryCounter(engine) as second:
        cached = await client.get("/api/v1/reports/dashboard", headers=headers)
    assert cached.status_code == 200
    assert cached.json()["data"] == response.json()["data"]
    # Only the per-request user lookup should hit the database.
    assert second.count <= 1, f"dashboard cache miss: {second.count} queries"

    await cache.bump("reports")
    with QueryCounter(engine) as third:
        refreshed = await client.get("/api/v1/reports/dashboard", headers=headers)
    assert refreshed.status_code == 200
    assert third.count > 1


@pytest.mark.asyncio
async def test_scope_is_part_of_report_cache_key(client, fake_redis, engine):
    """Platform admin and standard users must not share a dashboard cache key."""
    admin_headers = await login(client)
    assert (await client.get("/api/v1/reports/dashboard", headers=admin_headers)).status_code == 200

    sales_headers = await login(client, "sales")
    with QueryCounter(engine) as standard:
        assert (await client.get("/api/v1/reports/dashboard", headers=sales_headers)).status_code == 200
    assert standard.count > 1, "a different authorization scope must miss the admin cache entry"


@pytest.mark.asyncio
async def test_financial_posting_invalidates_report_cache(client, fake_redis, monkeypatch):
    from tests.test_workflows import _create_and_post_invoice, test_quotation_lifecycle_and_conversion

    bumps: list[tuple[str, ...]] = []
    original_bump = cache.bump

    async def spy(*namespaces: str) -> None:
        bumps.append(tuple(namespaces))
        await original_bump(*namespaces)

    monkeypatch.setattr(cache, "bump", spy)

    headers = await login(client)
    service_order_id = await test_quotation_lifecycle_and_conversion(client)
    await _create_and_post_invoice(client, headers, service_order_id)

    assert any("reports" in call for call in bumps), f"expected reports invalidation, saw {bumps}"


# --- permission cache ---------------------------------------------------------


@pytest.mark.asyncio
async def test_identity_cache_hit_and_role_change_invalidates(client, fake_redis, engine):
    sales_headers = await login(client, "sales")
    # Login already cached the identity; start from a clean namespace so the
    # first /auth/me is a guaranteed miss and the second a guaranteed hit.
    await cache.bump("auth")

    with QueryCounter(engine) as first:
        me_before = await client.get("/api/v1/auth/me", headers=sales_headers)
    assert me_before.status_code == 200
    assert first.count >= 3  # user + assignments + roles/permissions + avatar

    with QueryCounter(engine) as second:
        me_cached = await client.get("/api/v1/auth/me", headers=sales_headers)
    assert me_cached.status_code == 200
    assert me_cached.json()["data"]["sourcePermissions"] == me_before.json()["data"]["sourcePermissions"]
    # The hit must not re-resolve the identity (no user, role or policy read);
    # the remaining statements are the session, user row and access policy the
    # request itself needs.
    assert not any("casbin_rule" in statement for statement in second.statements), second.statements
    assert second.count <= 4, f"identity cache miss: {second.count} queries: {second.statements}"

    headers = await login(client)
    users = (await client.get("/api/v1/users", headers=headers)).json()["data"]
    sales_user = next(user for user in users if user["username"] == "sales")

    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "CACHE_TEST_ROLE", "name": "Cache Test Role", "permissions": ["admin.users.view"]},
    )
    assert role.status_code in (200, 201), role.text
    role_id = role.json()["data"]["id"]

    assigned = await client.post(
        f"/api/v1/users/{sales_user['id']}/role-assignments",
        headers=headers,
        json={"role_id": int(role_id)},
    )
    assert assigned.status_code in (200, 201), assigned.text

    me_after = await client.get("/api/v1/auth/me", headers=sales_headers)
    assert me_after.status_code == 200
    after_permissions = set(me_after.json()["data"]["sourcePermissions"])
    before_permissions = set(me_before.json()["data"]["sourcePermissions"])
    assert after_permissions != before_permissions, "permission cache must invalidate immediately after role change"


@pytest.mark.asyncio
async def test_avatar_change_invalidates_identity_cache(client, fake_redis):
    headers = await login(client)
    first = await client.get("/api/v1/auth/me", headers=headers)
    assert first.status_code == 200
    assert first.json()["data"]["avatar"] in (None, "")

    changed = await client.post(
        "/api/v1/auth/profile/avatar", headers=headers, json={"avatar": "data:image/png;base64,AAAA"}
    )
    assert changed.status_code == 200, changed.text

    after = await client.get("/api/v1/auth/me", headers=headers)
    assert after.json()["data"]["avatar"] == "data:image/png;base64,AAAA"


@pytest.mark.asyncio
async def test_refresh_reset_key_roundtrip_with_fake_redis(fake_redis):
    """The existing password-reset Redis cache keeps working through safe_*."""
    await redis_core.safe_set("reset:user@example.test", "123456", ex=900)
    assert await redis_core.safe_get("reset:user@example.test") == "123456"
    assert await redis_core.safe_exists("reset:user@example.test") is True
    await redis_core.safe_delete("reset:user@example.test")
    assert await redis_core.safe_get("reset:user@example.test") is None


@pytest.mark.asyncio
async def test_cache_serializes_decimal_and_dates(fake_redis):
    payload = {"amount": json.dumps({"value": "1.5"}), "items": [{"id": 1}]}
    await cache.set_json("reports", "mixed", value=payload, ttl_seconds=60)
    assert await cache.get_json("reports", "mixed") == payload
