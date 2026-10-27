from datetime import timedelta

from sqlalchemy import select

from app.core.database import utcnow
from app.modules.audit.service import write_audit
from app.modules.backup.models import BackupRun
from app.modules.telegram import monitor, service
from app.modules.telegram.models import NotificationIncident, NotificationOutbox
from tests.test_telegram_recovery import recovery_setup


async def enable_alerts(client, session_factory, monkeypatch):
    headers, user_id = await recovery_setup(client, session_factory, monkeypatch)
    async with session_factory() as session:
        value = await service.config(session)
        value["adminGroupId"] = -10012
        value["rules"].update({category: {**service.DEFAULT_RULES[category], "enabled": True, "minimumSeverity": "INFO"} for category in ("security", "backup", "system")})
        await service.save_internal(session, value)
        await session.commit()
    return headers, user_id


async def test_security_alert_threshold_dedup_and_private_minimization(client, session_factory, telegram_mock, monkeypatch):
    await enable_alerts(client, session_factory, monkeypatch)
    async with session_factory() as session:
        for _ in range(7):
            await write_audit(session, None, event_type="LOGIN_FAILED", entity_type="user", entity_id=0, action="login", result="REJECTED", metadata={"untrusted": "do-not-send-this"})
        await monitor.security_events(session)
        await session.flush()
        assert await session.scalar(select(NotificationOutbox.id).where(NotificationOutbox.event_type == "LOGIN_FAILED")) is None
        await write_audit(session, None, event_type="LOGIN_FAILED", entity_type="user", entity_id=0, action="login", result="REJECTED")
        await monitor.security_events(session)
        await session.flush()
        rows = (await session.execute(select(NotificationOutbox).where(NotificationOutbox.event_type == "LOGIN_FAILED"))).scalars().all()
        assert len(rows) == 1 and rows[0].destination_type == "ADMIN"
        assert "do-not-send-this" not in str(rows[0].payload)
        await monitor.security_events(session)
        await session.flush()
        assert len((await session.execute(select(NotificationOutbox).where(NotificationOutbox.event_type == "LOGIN_FAILED"))).scalars().all()) == 1


async def test_actual_login_lockout_produces_alert_evidence(client, session_factory, telegram_mock, monkeypatch):
    await enable_alerts(client, session_factory, monkeypatch)
    for _ in range(5):
        assert (await client.post("/api/v1/auth/login", json={"username": "admin", "password": "incorrect"})).status_code == 401
    async with session_factory() as session:
        await monitor.security_events(session)
        await session.flush()
        assert await session.scalar(select(NotificationOutbox.id).where(NotificationOutbox.event_type == "ACCOUNT_LOCKED"))


async def test_incident_duration_hysteresis_cooldown_and_recovery(client, session_factory, telegram_mock, monkeypatch):
    await enable_alerts(client, session_factory, monkeypatch)
    async with session_factory() as session:
        await monitor.incident(session, "test_cpu", True, summary="Measured CPU saturation", duration=300)
        await session.flush()
        assert await session.scalar(select(NotificationOutbox.id)) is None
        state = await session.get(NotificationIncident, "test_cpu")
        state.first_seen_at = utcnow() - timedelta(seconds=301)
        await monitor.incident(session, "test_cpu", True, summary="Measured CPU saturation", duration=300)
        await session.flush()
        assert state.state == "ACTIVE"
        await monitor.incident(session, "test_cpu", True, summary="Measured CPU saturation", duration=300)
        await monitor.incident(session, "test_cpu", False, recovered=False, summary="Measured CPU saturation")
        await session.flush()
        assert state.state == "ACTIVE"
        assert len((await session.execute(select(NotificationOutbox))).scalars().all()) == 1
        await monitor.incident(session, "test_cpu", False, recovered=True, summary="Measured CPU saturation")
        await session.flush()
        assert state.state == "RESOLVED"
        assert len((await session.execute(select(NotificationOutbox))).scalars().all()) == 2


async def test_backup_results_and_overdue_are_real_and_deduplicated(client, session_factory, telegram_mock, monkeypatch):
    await enable_alerts(client, session_factory, monkeypatch)
    async with session_factory() as session:
        session.add(BackupRun(status="success", trigger="manual", started_at=utcnow() - timedelta(hours=25), finished_at=utcnow() - timedelta(hours=25), duration_ms=1200, detail={"size_bytes": 1234, "destination_type": "R2", "upload_verified": True}))
        session.add(BackupRun(status="failed", trigger="manual", started_at=utcnow() - timedelta(minutes=1), finished_at=utcnow(), detail={"failure_stage": "R2 upload"}, message="secret exception should never be forwarded"))
        # Configuration completeness is deliberately bypassed here to isolate freshness policy.
        from app.modules.settings.service import _upsert_setting

        await _upsert_setting(session, "backup", "backup", {"enabled": True, "intervalHours": 24}, None, "Test schedule")
        await session.flush()
        await monitor.backup_events(session)
        await session.flush()
        rows = (await session.execute(select(NotificationOutbox))).scalars().all()
        assert {row.event_type for row in rows} >= {"BACKUP_FAILED", "BACKUP_OVERDUE"}
        assert all("secret exception" not in str(row.payload) for row in rows)
        count = len(rows)
        await monitor.backup_events(session)
        await session.flush()
        assert len((await session.execute(select(NotificationOutbox))).scalars().all()) == count


async def test_runtime_measurements_drive_alerts(client, session_factory, telegram_mock, monkeypatch):
    await enable_alerts(client, session_factory, monkeypatch)
    monkeypatch.setattr(monitor, "SessionLocal", session_factory)
    from types import SimpleNamespace

    monkeypatch.setattr(monitor.psutil, "disk_usage", lambda _: SimpleNamespace(percent=96))
    monkeypatch.setattr(monitor.psutil, "virtual_memory", lambda: SimpleNamespace(percent=88))
    monkeypatch.setattr(monitor.psutil, "cpu_percent", lambda interval=None: 97)

    async def unhealthy():
        return False

    monkeypatch.setattr(monitor, "api_healthy", unhealthy)
    await monitor.monitor_tick()
    async with session_factory() as session:
        disk = await session.get(NotificationIncident, "disk_usage")
        assert disk.measured_value == 96 and disk.state == "PENDING"
        disk.first_seen_at = utcnow() - timedelta(minutes=3)
        await session.commit()
    await monitor.monitor_tick()
    async with session_factory() as session:
        assert await session.scalar(select(NotificationOutbox.id).where(NotificationOutbox.event_type == "DISK_USAGE"))


async def test_loopback_health_probe_uses_trusted_production_host(monkeypatch):
    import httpx
    from fastapi import FastAPI
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    from app.core.config import settings

    production = FastAPI()
    production.add_middleware(TrustedHostMiddleware, allowed_hosts=["lcs.example"])

    @production.get("/health")
    async def health():
        return {"status": "ok"}

    original = httpx.AsyncClient
    monkeypatch.setattr(settings, "telegram_public_app_url", "https://lcs.example")
    monkeypatch.setattr(settings, "telegram_api_health_url", "http://127.0.0.1:8000/health")
    monkeypatch.setattr(monitor.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.ASGITransport(app=production), **kwargs))
    assert await monitor.api_healthy()
