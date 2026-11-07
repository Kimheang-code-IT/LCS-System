"""Backend enforcement of maintenance mode and read-only mode.

Maintenance admission is also enforced on public API routes by the API-router
dependency; this guard restricts the authenticated recovery allowlist using Casbin.

Policy:
- Maintenance blocks ordinary authenticated access with ``503 MAINTENANCE_MODE``.
  Exact authentication/recovery operations remain available; general Settings
  writes and public integrations stay blocked.
- Read-only blocks unsafe HTTP methods with ``409 READ_ONLY_MODE``. Safe reads,
  authentication and the administrator Settings endpoint stay available.
- Health endpoints do not depend on an authenticated context and stay reachable.
"""

from __future__ import annotations

from fastapi import Request

from app.core.context import RequestContext
from app.core.exceptions import DomainError

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_SETTINGS_PATH = "/api/v1/settings/app-config"
# Report generation and export are POSTs only because they carry a filter
# object; they read the ledger and write nothing, so read-only mode must not
# disable them.
_GENERATED_REPORT_PREFIX = "/api/v1/reports/"
_GENERATED_REPORT_SUFFIXES = ("/generate", "/export")


def _is_generated_report(request: Request) -> bool:
    path = request.url.path.rstrip("/")
    return path.startswith(_GENERATED_REPORT_PREFIX) and path.endswith(_GENERATED_REPORT_SUFFIXES)


def _is_recovery_admin(context: RequestContext) -> bool:
    return (
        context.has_permission("settings.app_config.update")
        or context.has_permission("configuration.manage")
    )


def _recovery_allowed(request: Request, context: RequestContext) -> bool:
    path = request.url.path.rstrip("/")
    from app.modules.settings.maintenance import ADMIN_ALLOWED, AUTH_ALLOWED
    if (request.method, path) in AUTH_ALLOWED:
        return True
    if (request.method, path) in ADMIN_ALLOWED:
        return _is_recovery_admin(context)
    return False


async def enforce_access_modes(request: Request, context: RequestContext, session) -> None:
    from app.modules.settings.service import get_access_policy

    policy = await get_access_policy(session)
    from app.core.config import settings
    from app.modules.settings.maintenance import active, load, refusal
    value = await load(session)
    if (settings.force_maintenance or active(value)) and not _recovery_allowed(request, context):
        raise refusal(value)
    if (
        policy["readOnly"]
        and request.method.upper() not in _SAFE_METHODS
        and not _is_generated_report(request)
        and not _recovery_allowed(request, context)
        and not (request.url.path.rstrip("/") == _SETTINGS_PATH and _is_recovery_admin(context))
    ):
        raise DomainError(
            "READ_ONLY_MODE",
            "The application is in read-only mode. Business data cannot be changed right now.",
            status_code=409,
        )
