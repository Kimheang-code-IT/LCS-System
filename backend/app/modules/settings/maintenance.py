"""Persistent, uncached maintenance admission policy. End times never reopen access."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session, utcnow
from app.core.exceptions import Conflict, DomainError, ValidationFailed
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import write_audit
from app.modules.settings.models import AppSetting

KEY = "maintenance"
DEFAULT = {
    "enabled": False,
    "startsAt": None,
    "endsAt": None,
    "message": "",
    "estimatedDowntime": "",
    "supportContact": "",
    "reason": "",
    "operationsGroupId": "",
    "developerGroupId": "",
    "revision": 0,
    "deploymentStatus": "pending",
}
_lock = asyncio.Lock()


class MaintenanceChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    message: str = Field(default="", max_length=1000)
    estimatedDowntime: str = Field(default="", max_length=120)
    supportContact: str = Field(default="", max_length=255)
    reason: str = Field(min_length=1, max_length=500)
    operationsGroupId: str = Field(default="", max_length=30, pattern=r"^$|^-[0-9]+$")
    developerGroupId: str = Field(default="", max_length=30, pattern=r"^$|^-[0-9]+$")
    revision: int = Field(ge=0)
    confirm: Literal["MAINTENANCE", "REOPEN", "SAVE"]

    @field_validator("startsAt", "endsAt")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Include a timezone.")
        return value.astimezone(UTC) if value else None

    @field_validator("operationsGroupId", "developerGroupId")
    @classmethod
    def group_id_range(cls, value):
        if value and not -(2**63) <= int(value) < 0:
            raise ValueError("Provide a negative 64-bit Telegram group ID.")
        return str(int(value)) if value else ""

    @model_validator(mode="after")
    def ordered(self):
        if not self.reason.strip():
            raise ValueError("Provide a reason.")
        if self.enabled and self.endsAt and self.startsAt and self.endsAt <= self.startsAt:
            raise ValueError("Estimated end must follow the start.")
        if self.operationsGroupId and self.operationsGroupId == self.developerGroupId:
            raise ValueError("Use separate operations and developer groups.")
        return self


class DeploymentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    status: Literal["verified", "failed", "backup_failed"]
    reason: str = Field(min_length=1, max_length=500)
    # Operator attestations, never presented as automated probes.
    backupReference: str = Field(default="", max_length=200)
    checks: list[
        Literal["drained", "backup", "migrations", "database", "backend", "authentication", "workflows", "jobs"]
    ] = Field(default_factory=list, max_length=8)


def active(value: dict, now: datetime | None = None) -> bool:
    start = value.get("startsAt")
    return bool(value.get("enabled") and (not start or datetime.fromisoformat(start) <= (now or utcnow())))


async def load(session: AsyncSession) -> dict:
    row = await session.scalar(
        select(AppSetting).where(AppSetting.setting_key == KEY).execution_options(populate_existing=True)
    )
    if row:
        return {**DEFAULT, **row.setting_value}
    # Honor the existing flag until the first dedicated maintenance save.
    from app.modules.settings.service import _current_app_config

    config, _ = await _current_app_config(session)
    return {**DEFAULT, "enabled": bool((config.get("system") or {}).get("maintenanceMode"))}


def public(value: dict) -> dict:
    return {
        "active": settings.force_maintenance or active(value),
        "scheduled": bool(value.get("enabled") and not active(value)),
        **{key: value.get(key) for key in ("startsAt", "endsAt", "message", "estimatedDowntime", "supportContact")},
        "forced": settings.force_maintenance,
    }


def refusal(value: dict) -> DomainError:
    exc = DomainError(
        "MAINTENANCE_MODE", value.get("message") or "System under maintenance. Please retry later.", status_code=503
    )
    retry = 60
    if value.get("endsAt"):
        retry = max(60, int((datetime.fromisoformat(value["endsAt"]) - utcnow()).total_seconds()))
    exc.headers = {"Retry-After": str(retry), "Cache-Control": "no-store"}
    return exc


@asynccontextmanager
async def locked(session: AsyncSession):
    # Transaction-scoped PostgreSQL lock is fail-closed and survives row creation races.
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SELECT pg_advisory_xact_lock(4920863140721)"))
        yield
    else:
        async with _lock:
            yield


async def store(session, value, context, event):
    row = await session.scalar(select(AppSetting).where(AppSetting.setting_key == KEY))
    if row is None:
        row = AppSetting(setting_key=KEY, setting_group=KEY)
        session.add(row)
    value = {
        **value,
        "revision": int(value["revision"]) + 1,
        "updatedAt": utcnow().isoformat(),
        "updatedBy": context.user_id if context else None,
    }
    row.setting_value = value
    row.updated_by_user_id = value["updatedBy"]
    await write_audit(
        session,
        context,
        event_type=event,
        entity_type=KEY,
        entity_id=0,
        action=event.lower(),
        reason=value.get("reason"),
        after=value,
    )
    await notify(session, value, event)
    await session.commit()
    return value


async def change(session, context, change: MaintenanceChange):
    async with locked(session):
        old = await load(session)
        if old["revision"] != change.revision:
            raise Conflict("MAINTENANCE_CHANGED", "Maintenance settings changed. Refresh before saving.")
        now_active = active(old)
        if now_active and change.enabled and change.startsAt and change.startsAt > utcnow():
            raise Conflict(
                "MAINTENANCE_ACTIVE",
                "An active maintenance window cannot be moved into the future. Verify and reopen first.",
            )
        if change.enabled and change.confirm != "MAINTENANCE":
            raise ValidationFailed("Confirm maintenance activation.", {"confirm": "Type MAINTENANCE."})
        if now_active and not change.enabled:
            if change.confirm != "REOPEN" or old["deploymentStatus"] != "verified":
                raise Conflict(
                    "MAINTENANCE_NOT_VERIFIED", "Record successful deployment checks and type REOPEN before reopening."
                )
        value = {**old, **change.model_dump(mode="json", exclude={"confirm", "revision"})}
        if not old["enabled"] and change.enabled:
            value["deploymentStatus"] = "pending"
        event = (
            "MAINTENANCE_STARTED"
            if active(value) and not now_active
            else "MAINTENANCE_ENDED"
            if now_active and not value["enabled"]
            else "MAINTENANCE_SCHEDULED"
            if value["enabled"] and not active(value)
            else "MAINTENANCE_UPDATED"
        )
        value["startedNotified"] = active(value)
        return await store(session, value, context, event)


async def record_deployment(session, context, result: DeploymentResult):
    async with locked(session):
        value = await load(session)
        if value["revision"] != result.revision:
            raise Conflict("MAINTENANCE_CHANGED", "Refresh maintenance settings.")
        if not active(value):
            raise Conflict("MAINTENANCE_REQUIRED", "Activate maintenance before recording deployment verification.")
        required = {"drained", "backup", "migrations", "database", "backend", "authentication", "workflows", "jobs"}
        if result.status == "verified" and (set(result.checks) != required or not result.backupReference.strip()):
            raise ValidationFailed("All deployment checks and a verified backup reference are required.")
        value = {
            **value,
            "deploymentStatus": result.status,
            "reason": result.reason,
            "verification": result.model_dump(exclude={"revision"}),
        }
        return await store(
            session, value, context, "DEPLOYMENT_VERIFIED" if result.status == "verified" else "DEPLOYMENT_FAILED"
        )


async def history(session):
    rows = (
        await session.scalars(
            select(AuditEvent).where(AuditEvent.entity_type == KEY).order_by(AuditEvent.id.desc()).limit(30)
        )
    ).all()
    return [
        {
            "id": row.id,
            "event": row.event_type,
            "at": row.occurred_at.isoformat(),
            "by": row.actor_user_id,
            "reason": row.reason,
        }
        for row in rows
    ]


async def notify(session, value, event):
    from datetime import timedelta

    from app.modules.telegram import service
    from app.modules.telegram.models import NotificationOutbox

    config = await service.config(session)
    if not config.get("enabled") or not config.get("botId"):
        return
    developer_only = event.startswith("DEPLOYMENT_")
    for audience in ["developer"] if developer_only else ["operations", "developer"]:
        destination = value.get(f"{audience}GroupId")
        if not destination:
            continue
        session.add(
            NotificationOutbox(
                event_type=event,
                category="system",
                severity="CRITICAL" if event == "DEPLOYMENT_FAILED" else "INFO",
                destination_type="ADMIN",
                destination_reference=int(destination),
                payload={
                    "text": f"LCS: {event.replace('_', ' ').title()}\nScheduled start: {value.get('startsAt') or 'Immediate'}\nEstimated end: {value.get('endsAt') or 'To be confirmed'}",
                    "bot_id": config["botId"],
                    "maintenanceAudience": audience,
                    "maintenanceLifecycle": True,
                },
                expires_at=utcnow() + timedelta(days=1),
                max_attempts=3,
                deduplication_key=f"maintenance:{value['revision']}:{audience}",
            )
        )


async def tick(session):
    async with locked(session):
        value = await load(session)
        if active(value) and not value.get("startedNotified"):
            await store(session, {**value, "startedNotified": True}, None, "MAINTENANCE_STARTED")


# Exact method/path allowlist. Public integrations/setup/password-reset writes are blocked.
AUTH_ALLOWED = {("POST", f"/api/v1/auth/{name}") for name in ("login", "refresh", "logout", "change-password")}
AUTH_ALLOWED |= {("GET", "/api/v1/auth/me"), ("GET", "/api/v1/auth/setup/status")}
ADMIN_ALLOWED = {
    ("GET", "/api/v1/settings/app-config"),
    ("GET", "/api/v1/settings/maintenance"),
    ("PUT", "/api/v1/settings/maintenance"),
    ("POST", "/api/v1/settings/maintenance/deployment"),
}


async def admission(request: Request, session: AsyncSession = Depends(get_session)):
    path = request.url.path.rstrip("/")
    if request.method == "OPTIONS" or (
        request.method == "GET" and path in {"/api/v1/health", "/api/v1/maintenance/status"}
    ):
        return
    try:
        value = await load(session)
    except SQLAlchemyError:
        raise refusal(DEFAULT) from None
    if settings.force_maintenance or active(value):
        pair = (request.method, path)
        if pair not in AUTH_ALLOWED and pair not in ADMIN_ALLOWED:
            request.state.maintenance_blocked = True
            raise refusal(value)
        # ADMIN_ALLOWED endpoints also require the authenticated Casbin recovery guard.


async def jobs_paused(session):
    return settings.force_maintenance or active(await load(session))
