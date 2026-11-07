"""Maintenance admission, durable recovery gates and controlled notifications."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import UserSession
from app.modules.settings import maintenance
from app.modules.settings.models import AppSetting
from app.modules.telegram.models import NotificationOutbox
from tests.conftest import login

pytestmark = pytest.mark.asyncio
PATH = "/api/v1/settings/maintenance"


async def enable(client, admin, **overrides):
    result = await client.put(
        PATH,
        headers=admin,
        json={
            "enabled": True,
            "reason": "Isolated maintenance test",
            "revision": 0,
            "confirm": "MAINTENANCE",
            **overrides,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()["data"]


async def test_denial_confirmation_and_stale_save(client, session_factory):
    admin = await login(client)
    sales = await login(client, "sales")
    assert (await client.get(PATH, headers=sales)).status_code == 403
    denied = await client.put(
        PATH, headers=sales, json={"enabled": True, "reason": "Denied", "revision": 0, "confirm": "MAINTENANCE"}
    )
    assert denied.status_code == 403
    assert (
        await client.put(
            PATH,
            headers=admin,
            json={"enabled": True, "reason": "Missing confirmation", "revision": 0, "confirm": "SAVE"},
        )
    ).status_code == 422
    assert (
        await client.patch("/api/v1/settings/app-config", headers=admin, json={"system": {"maintenanceMode": True}})
    ).status_code == 422
    assert (
        await client.put(
            PATH,
            headers=admin,
            json={
                "enabled": True,
                "reason": "Overflow",
                "revision": 0,
                "confirm": "MAINTENANCE",
                "developerGroupId": "-9999999999999999999999999",
            },
        )
    ).status_code == 422
    await enable(client, admin)
    assert (
        await client.put(
            PATH, headers=admin, json={"enabled": False, "reason": "Stale", "revision": 0, "confirm": "REOPEN"}
        )
    ).status_code == 409
    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.entity_type == "maintenance")
            )
            == 1
        )


async def test_admission_sessions_integrations_and_private_status(client, session_factory):
    admin = await login(client)
    sales = await login(client, "sales")
    async with session_factory() as session:
        before = await session.scalar(select(func.count()).select_from(UserSession))
    await enable(client, admin, message="Scheduled service", endsAt=(utcnow() + timedelta(hours=1)).isoformat())
    for method, path, body in [
        ("POST", "/api/v1/feeTypes", {"code": "BLOCKED", "name": "Blocked"}),
        ("POST", "/api/v1/financial-documents/1/post", {}),
        ("POST", "/api/v1/integrations/telegram/webhook", {}),
        ("POST", "/api/v1/auth/setup/initialize", {}),
        ("PATCH", "/api/v1/settings/app-config", {"system": {"maintenanceMode": False}}),
    ]:
        response = await client.request(method, path, headers=admin, json=body)
        assert response.status_code == 503, response.text
        if response.status_code == 503:
            assert response.json()["code"] == "MAINTENANCE_MODE"
            assert int(response.headers["Retry-After"]) >= 60
    assert (await client.get("/api/v1/quotations", headers=sales)).status_code == 503
    assert (await client.get("/api/v1/auth/me", headers=sales)).status_code == 200
    assert (await client.get(PATH, headers=admin)).status_code == 200
    assert (await client.get(PATH, headers=sales)).status_code == 503
    client.cookies.clear()
    public = (await client.get("/api/v1/maintenance/status")).json()["data"]
    assert public["active"] and public["message"] == "Scheduled service"
    assert "reason" not in public and "developerGroupId" not in public
    assert (await client.get("/api/v1/health")).status_code == 200
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(UserSession)) == before
        assert not (await session.scalars(select(UserSession).where(UserSession.revoked_at.is_not(None)))).all()


async def test_schedule_persistence_latch_and_job_pause(client, session_factory, monkeypatch):
    admin = await login(client)
    value = await enable(
        client,
        admin,
        startsAt=(utcnow() + timedelta(hours=1)).isoformat(),
        endsAt=(utcnow() + timedelta(hours=2)).isoformat(),
    )
    assert not (await client.get("/api/v1/maintenance/status")).json()["data"]["active"]
    assert (await client.get("/api/v1/quotations", headers=admin)).status_code == 200
    async with session_factory() as session:
        assert (await maintenance.load(session))["revision"] == value["revision"]
        row = await session.scalar(select(AppSetting).where(AppSetting.setting_key == "maintenance"))
        row.setting_value = {
            **row.setting_value,
            "startsAt": (utcnow() - timedelta(hours=2)).isoformat(),
            "endsAt": (utcnow() - timedelta(hours=1)).isoformat(),
        }
        await session.commit()
    assert (await client.get("/api/v1/quotations", headers=admin)).status_code == 503
    async with session_factory() as session:
        assert await maintenance.jobs_paused(session)
        await maintenance.tick(session)
        await maintenance.tick(session)
        assert (
            await session.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "MAINTENANCE_STARTED")
            )
            == 1
        )
    from app.modules.backup import scheduler

    monkeypatch.setattr(scheduler, "SessionLocal", session_factory)
    run = AsyncMock()
    monkeypatch.setattr(scheduler.service, "run_now", run)
    await scheduler.maybe_run_due()
    run.assert_not_awaited()


async def test_failed_backup_deployment_and_recovery(client):
    admin = await login(client)
    value = await enable(client, admin)
    for failure in ("backup_failed", "failed"):
        result = await client.post(
            PATH + "/deployment",
            headers=admin,
            json={"revision": value["revision"], "status": failure, "reason": "Verification failed"},
        )
        assert result.status_code == 200, result.text
        value = result.json()["data"]
        reopen = await client.put(
            PATH,
            headers=admin,
            json={"enabled": False, "reason": "Unsafe reopen", "revision": value["revision"], "confirm": "REOPEN"},
        )
        assert reopen.status_code == 409
    bypass = await client.put(
        PATH,
        headers=admin,
        json={
            "enabled": True,
            "startsAt": (utcnow() + timedelta(days=1)).isoformat(),
            "reason": "Move active start",
            "revision": value["revision"],
            "confirm": "MAINTENANCE",
        },
    )
    assert bypass.status_code == 409
    incomplete = await client.post(
        PATH + "/deployment",
        headers=admin,
        json={"revision": value["revision"], "status": "verified", "reason": "Missing checks"},
    )
    assert incomplete.status_code == 422
    assert (await client.get("/api/v1/quotations", headers=admin)).status_code == 503


async def test_notifications_separate_groups_transactional_and_retry(client, session_factory, monkeypatch):
    from app.modules.telegram import outbox

    config = {"enabled": True, "botId": 123}
    monkeypatch.setattr(outbox.service, "config", AsyncMock(return_value=config))
    sender = AsyncMock()
    monkeypatch.setattr(outbox.service, "client", lambda _: sender)
    admin = await login(client)
    await enable(
        client, admin, operationsGroupId="-010001", developerGroupId="-10002", reason="Private reason never announced"
    )
    async with session_factory() as session:
        rows = (await session.scalars(select(NotificationOutbox))).all()
        assert len(rows) == 2
        assert {row.destination_reference for row in rows} == {-10001, -10002}
        assert all("Private reason" not in row.payload["text"] for row in rows)
    async with session_factory() as session:
        claims = await outbox.claim(session)
    for claim in claims:
        await outbox.deliver(*claim, session_factory=session_factory)
    assert sender.send_message.await_count == 2


async def test_cookie_activation_requires_csrf(client):
    await login(client)
    body = {"enabled": True, "reason": "CSRF", "revision": 0, "confirm": "MAINTENANCE"}
    assert (await client.put(PATH, json=body)).status_code == 403
    csrf = client.cookies.get(settings.csrf_cookie_name)
    accepted = await client.put(PATH, json=body, headers={settings.csrf_header_name: csrf})
    assert accepted.status_code == 200, accepted.text


async def test_notification_failure_remains_retryable_and_system_optout(client, session_factory, monkeypatch):
    from app.modules.telegram import outbox
    from app.modules.telegram.client import TelegramError

    config = {"enabled": True, "botId": 123, "rules": {"system": {"enabled": True, "minimumSeverity": "INFO"}}}
    monkeypatch.setattr(outbox.service, "config", AsyncMock(return_value=config))
    sender = AsyncMock()
    sender.send_message.side_effect = TelegramError("rate_limited", retryable=True, retry_after=60)
    monkeypatch.setattr(outbox.service, "client", lambda _: sender)
    admin = await login(client)
    await enable(client, admin, operationsGroupId="-10001", developerGroupId="-10002")
    async with session_factory() as session:
        await outbox.enqueue_admin(
            session,
            "API_HEALTH",
            "system",
            "CRITICAL",
            reference="Runtime monitor",
            summary="Health check failed",
            dedup="test-health",
        )
        await session.commit()
        claims = await outbox.claim(session)
    config["rules"]["system"]["enabled"] = False
    for claim in claims:
        await outbox.deliver(*claim, session_factory=session_factory)
    async with session_factory() as session:
        rows = (await session.scalars(select(NotificationOutbox))).all()
        assert all(
            row.status == "PENDING" and row.attempts == 1 for row in rows if row.event_type == "MAINTENANCE_STARTED"
        )
        assert next(row for row in rows if row.event_type == "API_HEALTH").status == "CANCELLED"
        assert (await maintenance.load(session))["enabled"]


async def test_emergency_status_without_database(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(settings, "force_maintenance", True)
    monkeypatch.setattr(maintenance, "load", AsyncMock(side_effect=OperationalError("", {}, Exception())))
    status = await client.get("/api/v1/maintenance/status")
    assert status.status_code == 200 and status.json()["data"]["active"]
    response = await client.post("/api/v1/feeTypes", json={})
    assert response.status_code == 503
