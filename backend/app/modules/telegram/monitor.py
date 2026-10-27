"""Measured runtime incidents and committed-event producers, sampled once a minute."""

import asyncio
import os
import time
from collections import deque
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
import psutil
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.core.locks import advisory_lock
from app.modules.audit.models import AuditEvent
from app.modules.backup.models import BackupRun
from app.modules.settings import service as settings_service
from app.modules.telegram import outbox, service
from app.modules.telegram.models import NotificationIncident, NotificationOutbox

server_errors: deque[float] = deque(maxlen=1000)
rate_violations: deque[float] = deque(maxlen=1000)
_cached_config: dict = {}
_db_failed_at: float | None = None
_db_notified_at: float | None = None


async def incident(session, key: str, failing: bool, *, summary: str, severity: str = "WARNING", duration: int = 120, recovered: bool = True, category: str = "system", measured: int = 0) -> None:
    now = utcnow()
    value = await service.config(session)
    rule = outbox.policy(value, category)
    row = await session.get(NotificationIncident, key)
    if row is None:
        if not failing:
            return
        row = NotificationIncident(key=key, first_seen_at=now, measured_value=measured)
        session.add(row)
        await session.flush()
    row.measured_value = measured
    if failing:
        if row.state == "RESOLVED":
            row.state, row.first_seen_at = "PENDING", now
        mature = (now - service.aware(row.first_seen_at)).total_seconds() >= duration
        cooldown = row.last_sent_at is None or now - service.aware(row.last_sent_at) >= timedelta(minutes=rule["cooldownMinutes"])
        if mature and cooldown:
            sent = await outbox.enqueue_admin(session, key.upper(), category, severity, reference="Runtime monitor", summary=summary, dedup=f"incident:{key}:{int(service.aware(row.first_seen_at).timestamp())}:{int(now.timestamp()) // (rule['cooldownMinutes'] * 60)}")
            if sent:
                row.last_sent_at, row.state = now, "ACTIVE"
    elif row.state == "PENDING":
        # A sustained-threshold timer must restart after even one nonfailing sample.
        row.state, row.last_sent_at = "RESOLVED", None
    elif recovered:
        if row.state == "ACTIVE" and rule["notifyOnRecovery"]:
            await outbox.enqueue_admin(session, key.upper() + "_RECOVERED", category, severity, reference="Runtime monitor", summary=f"Recovered: {key.replace('_', ' ')}. Runtime checks meet the recovery criteria.", dedup=f"recovery:{key}:{row.first_seen_at.isoformat()}")
        row.state = "RESOLVED"
        row.last_sent_at = None


async def security_events(session) -> None:
    now = utcnow()
    cursor = await session.get(NotificationIncident, "audit_cursor")
    if cursor is None:
        cursor = NotificationIncident(key="audit_cursor", first_seen_at=now, measured_value=0, state="ACTIVE")
        session.add(cursor)
        await session.flush()
    events = (await session.execute(select(AuditEvent).where(AuditEvent.id > cursor.measured_value, AuditEvent.occurred_at >= now - timedelta(minutes=15)).order_by(AuditEvent.id).limit(200))).scalars().all()
    value = await service.config(session)
    cooldown = outbox.policy(value, "security")["cooldownMinutes"]
    for event in events:
        cursor.measured_value = event.id
        kind = event.event_type
        category = "security"
        severity = "WARNING"
        summary = None
        if kind in {"LOGIN_FAILED", "AUTHORIZATION_DENIED"}:
            threshold = 8 if kind == "LOGIN_FAILED" else 5
            conditions = [AuditEvent.event_type == kind, AuditEvent.occurred_at >= now - timedelta(minutes=5)]
            if event.actor_user_id is not None:
                conditions.append(AuditEvent.actor_user_id == event.actor_user_id)
            elif event.entity_id:
                conditions.append(AuditEvent.entity_id == event.entity_id)
            count = await session.scalar(select(func.count()).select_from(AuditEvent).where(*conditions))
            if count >= threshold:
                summary = f"Repeated {'failed login' if kind == 'LOGIN_FAILED' else 'authorization denial'} events: {count} in 5 minutes. Review authorized Audit Logs."
            # A denied finance posting is independently actionable evidence, not a claimed attack.
            if kind == "AUTHORIZATION_DENIED" and any(part in event.action for part in ("financial_document.post", "financial_document.submit", "journal_entry.post", "journal_entry.submit")):
                summary = "Unauthorized financial posting was refused. Review authorized Audit Logs."
        elif kind in {"ACCOUNT_LOCKED", "REFRESH_REPLAY"}:
            severity = "CRITICAL"
            summary = "Account temporarily locked after failed logins." if kind == "ACCOUNT_LOCKED" else "A consumed refresh credential was reused; its session was revoked."
        elif event.result == "SUCCESS" and (kind in {"ROLE_ASSIGNED", "ROLE_CREATED", "ROLE_UPDATED", "ROLE_DELETED", "ROLE_DUPLICATED"} or kind.startswith("POSTING_RULE_")):
            summary = "Privileged role or posting-rule configuration changed. Review authorized Audit Logs."
        elif kind == "USER_UPDATED" and any(k in (event.after_json or {}) for k in ("roles", "role", "role_code")):
            summary = "User role configuration changed. Review authorized Audit Logs."
        elif kind == "SETTINGS_UPDATED":
            groups = set((event.metadata_json or {}).get("groups") or [])
            if groups & {"security", "telegram"}:
                summary = "Security or Telegram settings changed. Review authorized Audit Logs."
            elif "backup" in groups:
                category = "backup"
                summary = "Backup configuration changed. Review authorized Audit Logs."
        elif kind == "BACKUP_RESTORE_FAILED":
            category, severity, summary = "backup", "CRITICAL", "Backup restore failed. Review authorized backup logs; no restore success is claimed."
        if summary:
            await outbox.enqueue_admin(session, kind, category, severity, reference=f"Audit event #{event.id}", summary=summary, dedup=f"audit:{kind}:{event.actor_user_id or event.entity_id}:{int(now.timestamp()) // (cooldown * 60)}")


async def backup_events(session) -> None:
    now = utcnow()
    # Run IDs are stable deduplication references; a restart may safely rescan this window.
    runs = (await session.execute(select(BackupRun).where(BackupRun.finished_at >= now - timedelta(days=1), BackupRun.status.in_(["success", "partial", "failed"])).order_by(BackupRun.id.desc()).limit(50))).scalars().all()
    for run in runs:
        success = run.status == "success"
        detail = run.detail or {}
        summary = f"Backup {'completed' if success else 'failed or incomplete'}. Environment: {settings.environment}. Destination: {detail.get('destination_type', 'configured destination')}. Duration: {run.duration_ms or 0} ms."
        if success and "size_bytes" in detail:
            summary += f" Actual snapshot size: {detail['size_bytes']} bytes."
        if not success:
            summary += f" Stage: {detail.get('failure_stage', 'backup execution')}. Review authorized backup logs."
        await outbox.enqueue_admin(session, "BACKUP_SUCCEEDED" if success else "BACKUP_FAILED", "backup", "INFO" if success else "CRITICAL", reference=f"Backup run #{run.id}", summary=summary, dedup=f"backup:{run.id}:{run.status}")
    config, _ = await settings_service._current_app_config(session)
    backup = config.get("backup") or {}
    if backup.get("enabled"):
        last_success = await session.scalar(select(func.max(BackupRun.finished_at)).where(BackupRun.status == "success"))
        # A new installation gets one interval plus a 30-minute grace period.
        state = await session.get(NotificationIncident, "backup_overdue")
        baseline = service.aware(last_success) if last_success else service.aware(state.first_seen_at) if state else now
        overdue = now - baseline > timedelta(hours=int(backup.get("intervalHours") or 24), minutes=30)
        await incident(session, "backup_overdue", overdue or last_success is None, summary="Scheduled backup has no successful completion within its expected interval and grace period.", severity="CRITICAL", duration=0 if last_success else int(backup.get("intervalHours") or 24) * 3600 + 1800, category="backup")


async def api_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3, follow_redirects=False) as client:
            # Connect over loopback while retaining a permitted production Host.
            host = urlsplit(settings.telegram_public_app_url).netloc or settings.allowed_host_list[0]
            response = await client.get(settings.telegram_api_health_url, headers={"Host": host})
            return response.status_code == 200 and response.json().get("status") == "ok"
    except Exception:
        return False


async def _database_failure() -> None:
    global _db_failed_at, _db_notified_at
    now = time.monotonic()
    if _db_failed_at is None:
        _db_failed_at = now
    value = _cached_config
    if not value or not value.get("enabled") or not value.get("adminGroupId"):
        return
    rule = outbox.policy(value, "system")
    if not rule["enabled"] or now - _db_failed_at < 60 or _db_notified_at and now - _db_notified_at < rule["cooldownMinutes"] * 60:
        return
    try:
        # The outbox is unavailable with PostgreSQL. This bounded, best-effort exception
        # uses only credentials/destination cached by a previous successful read.
        await service.client(value).send_message(value["adminGroupId"], f"LCS System Alert\nSeverity: CRITICAL\nPostgreSQL connectivity checks failed repeatedly. Durable delivery is unavailable until the database recovers.\nTime: {utcnow().isoformat()}")
        _db_notified_at = now
    except Exception:
        pass


async def monitor_tick() -> None:
    global _cached_config, _db_failed_at, _db_notified_at
    from app.modules.backup import scheduler
    from app.modules.telegram import worker

    try:
        async with asyncio.timeout(5):
            async with SessionLocal() as session:
                await session.execute(text("SELECT 1"))
                _cached_config = await service.config(session)
    except Exception:
        await _database_failure()
        return
    async with SessionLocal() as session:
        async with advisory_lock(session, "telegram:monitor") as acquired:
            if not acquired:
                return
            if _db_failed_at is not None:
                if _db_notified_at and outbox.policy(_cached_config, "system")["notifyOnRecovery"]:
                    await outbox.enqueue_admin(session, "DATABASE_RECOVERED", "system", "CRITICAL", reference="Runtime connectivity probe", summary="PostgreSQL connectivity recovered; durable delivery resumed.", dedup=f"database-recovered:{int(_db_failed_at)}")
                _db_failed_at = _db_notified_at = None
            await security_events(session)
            await backup_events(session)
            disk = psutil.disk_usage(settings.storage_local_path if os.path.exists(settings.storage_local_path) else ".").percent
            memory = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent(interval=None)
            await incident(session, "disk_usage", disk >= 85, recovered=disk < 80, summary=f"Disk utilization: {disk:.0f}%.", severity="CRITICAL" if disk >= 95 else "WARNING", duration=60, measured=int(disk))
            await incident(session, "memory_usage", memory >= 85, recovered=memory < 80, summary=f"Memory utilization: {memory:.0f}% (measured available memory is low).", duration=120, measured=int(memory))
            await incident(session, "cpu_saturation", cpu >= 90, recovered=cpu < 75, summary=f"Sustained CPU utilization: {cpu:.0f}%.", duration=300, measured=int(cpu))
            healthy = await api_healthy()
            await incident(session, "api_health", not healthy, summary="Local FastAPI health probe failed repeatedly.", severity="CRITICAL", duration=120)
            scheduler_bad = settings.backup_scheduler_enabled and (scheduler._task is None or scheduler._task.done())
            await incident(session, "backup_scheduler", scheduler_bad, summary="Configured backup scheduler is not running.", severity="CRITICAL", duration=120)
            oldest = await session.scalar(select(func.min(NotificationOutbox.created_at)).where(NotificationOutbox.status.in_(["PENDING", "PROCESSING"]), NotificationOutbox.expires_at > utcnow()))
            stale = bool(oldest and utcnow() - service.aware(oldest) > timedelta(minutes=10))
            recent_failure = worker.last_failure is not None and time.monotonic() - worker.last_failure < 120
            await incident(session, "notification_worker", stale or recent_failure, summary="Notification worker failed recently or has an overdue delivery backlog.", duration=120)
            cutoff = time.monotonic() - 300
            for bucket in (server_errors, rate_violations):
                while bucket and bucket[0] < cutoff:
                    bucket.popleft()
            await incident(session, "server_errors", len(server_errors) >= 5, summary=f"Observed {len(server_errors)} server errors within five minutes.", duration=0)
            await incident(session, "api_rate_limits", len(rate_violations) >= 10, summary=f"Observed {len(rate_violations)} rate-limit refusals within five minutes.", duration=0, category="security")
            await session.commit()
