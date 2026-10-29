"""Backend enforcement of maintenance mode and read-only mode.

The flags live in App Config, so they are read per authenticated request. The
check sits in ``get_current_context`` rather than the SPA: a disabled button is
not a security control.

Policy:
- Maintenance blocks ordinary authenticated access with ``503 MAINTENANCE_MODE``.
  Authentication endpoints stay open so an administrator can sign in and switch
  it off, and the Settings endpoint stays open for an administrator only.
- Read-only blocks unsafe HTTP methods with ``409 READ_ONLY_MODE``. Safe reads,
  authentication and the administrator Settings endpoint stay available.
- Health endpoints do not depend on an authenticated context and stay reachable.
"""

from __future__ import annotations

from fastapi import Request

from app.core.context import RequestContext
from app.core.exceptions import DomainError

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_AUTH_PREFIX = "/api/v1/auth/"
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
        context.is_platform_admin
        or context.has_permission("settings.app_config.update")
        or context.has_permission("configuration.manage")
    )


def _recovery_allowed(request: Request, context: RequestContext) -> bool:
    path = request.url.path.rstrip("/")
    if path.startswith(_AUTH_PREFIX.rstrip("/")):
        return True
    if path == _SETTINGS_PATH:
        return _is_recovery_admin(context)
    return False


async def enforce_access_modes(request: Request, context: RequestContext, session) -> None:
    from app.modules.settings.service import get_access_policy

    policy = await get_access_policy(session)
    if policy["maintenance"] and not _recovery_allowed(request, context):
        raise DomainError(
            "MAINTENANCE_MODE",
            "The application is in maintenance mode. Only administrators can sign in and change settings.",
            status_code=503,
        )
    if (
        policy["readOnly"]
        and request.method.upper() not in _SAFE_METHODS
        and not _is_generated_report(request)
        and not _recovery_allowed(request, context)
    ):
        raise DomainError(
            "READ_ONLY_MODE",
            "The application is in read-only mode. Business data cannot be changed right now.",
            status_code=409,
        )
