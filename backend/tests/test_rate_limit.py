"""Rate limiting tests: HTTP limits, window expiry, concurrency, fallback.

Uses the injected FakeRedis client; Redis-down behaviour falls back to the
in-process limiter, which must still return 429 (security controls never fail
open).
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.core import rate_limit as rate_limit_module
from app.core import redis as redis_core
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.modules.reports import router as reports_router
from tests.conftest import login
from tests.fake_redis import FakeRedis


@pytest_asyncio.fixture
async def rate_limited(monkeypatch):
    rate_limit_module._fallback.clear()
    fake = FakeRedis()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "redis_enabled", True)
    monkeypatch.setattr(redis_core, "_client", fake)
    yield fake
    rate_limit_module._fallback.clear()


@pytest.mark.asyncio
async def test_login_account_limit_and_window_expiry(client, rate_limited):
    for _ in range(10):
        attempt = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
        )
        assert attempt.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "900"
    assert blocked.json()["code"] == "RATE_LIMITED"

    rate_limited.now += 901  # window elapsed
    after = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_forgot_password_ip_limit(client, rate_limited):
    # IP limit: 10 per hour. Distinct emails so only the IP counter accumulates
    # (the per-account limit is 5 per hour).
    for index in range(10):
        response = await client.post(
            "/api/v1/auth/forgot-password", json={"email": f"user{index}@example.com"}
        )
        assert response.status_code == 200, response.text
    blocked = await client.post("/api/v1/auth/forgot-password", json={"email": "other@example.com"})
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "3600"


@pytest.mark.asyncio
async def test_concurrent_rate_limit_calls_are_bounded(rate_limited):
    results = await asyncio.gather(
        *[enforce_rate_limit("concurrent-unit", limit=5, window_seconds=60) for _ in range(20)],
        return_exceptions=True,
    )
    denied = [result for result in results if isinstance(result, HTTPException)]
    allowed = [result for result in results if result is None]
    assert len(allowed) == 5
    assert len(denied) == 15
    assert all(error.status_code == 429 for error in denied)


@pytest.mark.asyncio
async def test_redis_down_falls_back_to_in_process(client, rate_limited):
    rate_limited.fail = True
    statuses = []
    for _ in range(6):
        response = await client.post("/api/v1/auth/forgot-password", json={"email": "admin@example.com"})
        statuses.append(response.status_code)
    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


@pytest.mark.asyncio
async def test_reports_rate_limit_and_window_expiry(client, rate_limited, monkeypatch):
    monkeypatch.setattr(reports_router, "REPORT_RATE_LIMIT", 3)
    monkeypatch.setattr(reports_router, "REPORT_RATE_WINDOW_SECONDS", 60)
    headers = await login(client)

    for _ in range(3):
        assert (await client.get("/api/v1/reports/dashboard", headers=headers)).status_code == 200

    blocked = await client.get("/api/v1/reports/dashboard", headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "60"

    rate_limited.now += 61
    assert (await client.get("/api/v1/reports/dashboard", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_does_not_bypass_authentication(client, rate_limited, monkeypatch):
    monkeypatch.setattr(reports_router, "REPORT_RATE_LIMIT", 1)
    unauthenticated = await client.get("/api/v1/reports/dashboard")
    assert unauthenticated.status_code == 401, "authentication must be checked before the limiter"

    headers = await login(client)
    assert (await client.get("/api/v1/reports/dashboard", headers=headers)).status_code == 200
    assert (await client.get("/api/v1/reports/dashboard", headers=headers)).status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_disabled_allows_all(client, monkeypatch):
    monkeypatch.setattr(reports_router, "REPORT_RATE_LIMIT", 1)
    headers = await login(client)
    for _ in range(4):
        assert (await client.get("/api/v1/reports/dashboard", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_fixed_window_counter_uses_atomic_pipeline(rate_limited):
    first = await redis_core.safe_increment("rate:unit-test", 60)
    second = await redis_core.safe_increment("rate:unit-test", 60)
    assert (first, second) == (1, 2)
    # Expiry set only on the first increment (NX).
    assert rate_limited.expires["rate:unit-test"] == 60
    rate_limited.now += 61
    assert await redis_core.safe_increment("rate:unit-test", 60) == 1
