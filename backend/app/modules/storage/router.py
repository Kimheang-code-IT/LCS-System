"""Administrator HTTP API for the multi-provider storage feature.

All configuration endpoints sit behind the existing settings permissions
(``settings.app_config.update`` to change, ``settings.app_config.view`` or
``backup.read`` to observe). The OAuth callback is the one unauthenticated
route: it is validated by the signed state parameter and never returns
credential material.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_any_permission, require_permission
from app.core.exceptions import AccessDenied, ValidationFailed
from app.core.rate_limit import enforce_rate_limit
from app.modules.audit.service import write_audit
from app.modules.settings.models import AppSetting
from app.modules.storage import service as storage_service
from app.modules.storage.models import StorageJob

router = APIRouter()

_STATE_TTL_SECONDS = 600


def _sign_state(redirect_uri: str) -> str:
    import jwt

    from app.core.config import settings as app_settings

    return jwt.encode(
        {
            "t": "storage-gdrive",
            "redirect": redirect_uri,
            "exp": datetime.now(UTC) + timedelta(seconds=_STATE_TTL_SECONDS),
        },
        app_settings.jwt_secret_key,
        algorithm="HS256",
    )


def _read_state(state: str) -> dict:
    """Decode the signed state or refuse the callback."""
    import jwt
    from jwt import InvalidTokenError

    from app.core.config import settings as app_settings

    try:
        payload = jwt.decode(state, app_settings.jwt_secret_key, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise ValidationFailed(
            "The authorization link expired. Start the connection again.",
            {"state": "Invalid state."},
        ) from exc
    if payload.get("t") != "storage-gdrive" or not payload.get("redirect"):
        raise ValidationFailed("Invalid authorization state.", {"state": "Invalid state."})
    return payload


# --- status -------------------------------------------------------------------

@router.get("/settings/storage/status")
async def storage_status(
    context: RequestContext = Depends(require_any_permission("settings.app_config.view", "backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await storage_service.load_config(session)
    providers = {}
    for tag in ("r2", "gdrive"):
        block = (config.get("providers") or {}).get(tag) or {}
        providers[tag] = {
            "configured": storage_service.is_configured(tag, block),
            "connectionStatus": block.get("connectionStatus", "not_configured"),
            "lastVerifiedAt": block.get("lastVerifiedAt"),
            "lastTestMessage": block.get("lastTestMessage", ""),
            "lastVerifiedLabel": block.get("lastVerifiedAt") or None,
            "connectedEmail": block.get("connectedEmail", ""),
        }
    return {"data": {"config": config, "providers": providers, "overview": await storage_service.backup_overview(session)}}


# --- connection tests ---------------------------------------------------------

@router.post("/settings/storage/test-connection")
async def test_connection(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await enforce_rate_limit(f"storage:test:{context.user_id}", limit=10, window_seconds=300)
    return {"data": await storage_service.test_connection(session, str(payload.get("provider") or "").strip())}


# --- Google Drive OAuth -------------------------------------------------------

@router.post("/settings/storage/google/authorize")
async def google_authorize(
    request: Request,
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = (await storage_service.load_config(session)).get("providers", {}).get("gdrive") or {}
    if str(config.get("authType") or "") not in {"oauth", ""}:
        raise ValidationFailed(
            "Connecting an account requires OAuth authentication mode.",
            {"authType": "Switch the authentication type to OAuth first."},
        )
    client_id = str(config.get("clientId") or "").strip()
    if not client_id:
        raise ValidationFailed("Enter the Google client ID before connecting.", {"clientId": "Required."})
    await enforce_rate_limit(f"storage:oauth:{context.user_id}", limit=5, window_seconds=300)
    from app.core.config import settings as app_settings
    from app.modules.storage.providers import GoogleDriveProvider

    public_base = str(app_settings.telegram_public_app_url or "").strip()
    backend_base = public_base if public_base else f"{request.url.scheme}://{request.url.netloc}"
    redirect_uri = f"{backend_base}/api/v1/storage/google/callback"
    return {"data": {"url": GoogleDriveProvider.build_authorize_url(client_id, redirect_uri, _sign_state(redirect_uri))}}


_CALLBACK_OK = "<!doctype html><title>Google Drive</title><body style='font-family:sans-serif'>Google Drive connected. You can close this window and return to Settings.</body></html>"
_CALLBACK_ERROR = "<!doctype html><title>Google Drive</title><body style='font-family:sans-serif'>Authorization failed. Close this window and start the connection again.</body></html>"


@router.get("/storage/google/callback")
async def google_callback(code: str = Query(default=""), state: str = Query(default="")) -> HTMLResponse:
    """Complete the OAuth exchange server-side; tokens never reach the UI."""
    from app.core.database import SessionLocal
    from app.modules.storage.providers import GoogleDriveProvider

    try:
        payload = _read_state(state)
    except ValidationFailed:
        return HTMLResponse(_CALLBACK_ERROR, status_code=400)
    async with SessionLocal() as session:
        block = storage_service.with_secrets(await storage_service.provider_block(session, "gdrive"))
        # The redirect URI already recorded in the signed state is replayed to
        # Google verbatim, so authorize/callback always agree (redirect-URI
        # validation never depends on caller input).
        client_id, client_secret = block.get("clientId"), block.get("_clientSecret")
        if not code or not client_id or not client_secret:
            return HTMLResponse(_CALLBACK_ERROR, status_code=400)
        try:
            tokens = await GoogleDriveProvider.exchange_code(
                str(code), str(client_id), str(client_secret), str(payload["redirect"])
            )
        except Exception:  # noqa: BLE001 - OAuth failures are user-facing, credential-free
            return HTMLResponse(_CALLBACK_ERROR, status_code=400)
        await _save_oauth_tokens(tokens)
    return HTMLResponse(_CALLBACK_OK)


async def _storage_row(write_session: AsyncSession) -> tuple[AppSetting | None, dict]:
    row = (
        await write_session.execute(select(AppSetting).where(AppSetting.setting_key == "storage").with_for_update())
    ).scalar_one_or_none()
    return row, (dict(row.setting_value or {}) if row else {})


async def _save_oauth_tokens(tokens: dict) -> None:
    """Persist the encrypted refresh token, the connected email and the status."""
    from app.core.crypto import encrypt_secret
    from app.core.database import SessionLocal

    async with SessionLocal() as write_session:
        row, stored = await _storage_row(write_session)
        gdrive = dict((stored.get("providers") or {}).get("gdrive") or {})
        gdrive["connectedEmail"] = tokens.get("connectedEmail") or ""
        gdrive["connectionStatus"] = "connected"
        gdrive["lastVerifiedAt"] = datetime.now(UTC).isoformat()
        gdrive["lastTestMessage"] = f"Connected as {tokens.get('connectedEmail') or 'Google account'}."
        gdrive["refreshTokenEncrypted"] = encrypt_secret(tokens.get("refreshToken") or "")
        stored.setdefault("providers", {})["gdrive"] = gdrive
        if row is None:
            write_session.add(AppSetting(setting_key="storage", setting_group="storage", setting_value=stored))
        else:
            row.setting_value = stored
        await write_session.commit()


@router.post("/settings/storage/google/disconnect")
async def google_disconnect(
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row, stored = await _storage_row(session)
    gdrive = dict((stored.get("providers") or {}).get("gdrive") or {})
    gdrive["connectionStatus"] = "disconnected"
    gdrive["connectedEmail"] = ""
    gdrive["refreshTokenEncrypted"] = ""
    gdrive["lastVerifiedAt"] = datetime.now(UTC).isoformat()
    stored.setdefault("providers", {})["gdrive"] = gdrive
    if row is None:
        session.add(AppSetting(setting_key="storage", setting_group="storage", setting_value=stored))
    else:
        row.setting_value = stored
    await write_audit(
        session,
        context,
        event_type="STORAGE_DISCONNECTED",
        entity_type="storage",
        entity_id=0,
        action="disconnect",
        reason="Google Drive account disconnected by an administrator.",
    )
    await session.commit()
    return {"data": {"status": "disconnected"}}


# --- backup management --------------------------------------------------------

@router.post("/settings/storage/backup-now")
async def backup_now(
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await enforce_rate_limit(f"storage:backup:{context.user_id}", limit=3, window_seconds=300)
    job = await storage_service.backup_now(session, context.user_id)
    await write_audit(session, context, event_type="STORAGE_BACKUP_NOW", entity_type="storage", entity_id=job.id, action="run")
    await session.commit()
    return {"data": storage_service.serialize_job(job)}


@router.get("/settings/storage/backup/jobs")
async def backup_jobs(
    context: RequestContext = Depends(require_any_permission("settings.app_config.view", "backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    jobs = list((await session.execute(select(StorageJob).order_by(StorageJob.id.desc()).limit(50))).scalars().all())
    return {"data": [storage_service.serialize_job(job) for job in jobs]}


@router.post("/settings/storage/backup/retry")
async def backup_retry(
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await storage_service.load_config(session)
    target = str(config.get("backupProvider") or "").strip()
    if not target:
        raise ValidationFailed("No backup provider is configured.", {"backupProvider": "Not configured."})
    job = await storage_service.backup_now(session, context.user_id, target, force_retry=True)
    # The explicit retry also clears the attempt cap on failed replicas.
    await write_audit(session, context, event_type="STORAGE_BACKUP_RETRY", entity_type="storage", entity_id=job.id, action="run")
    await session.commit()
    return {"data": storage_service.serialize_job(job)}


# --- provider switching -------------------------------------------------------

@router.post("/settings/storage/primary")
async def set_primary_provider(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    target = str(payload.get("provider") or "").strip()
    if target not in {"r2", "gdrive"}:
        raise ValidationFailed("The primary provider must be Cloudflare R2 or Google Drive.", {"provider": "Unsupported provider."})
    config = await storage_service.load_config(session)
    block = (config.get("providers") or {}).get(target) or {}
    if not storage_service.is_configured(target, block):
        raise ValidationFailed(
            "Configure and verify the provider before switching uploads to it.",
            {"provider": f"{target} is not connected."},
        )
    backup_provider = str(config.get("backupProvider") or "").strip()
    if bool(config.get("backupEnabled")) and backup_provider == target:
        raise ValidationFailed(
            "The primary and backup providers must be independent destinations.",
            {"provider": "The backup provider uses the same destination."},
        )
    row, stored = await _storage_row(session)
    storage_block = dict(stored or {})
    storage_block["primaryProvider"] = target
    if row is None:
        session.add(AppSetting(setting_key="storage", setting_group="storage", setting_value=storage_block))
    else:
        row.setting_value = storage_block
    await write_audit(
        session,
        context,
        event_type="STORAGE_PRIMARY_CHANGED",
        entity_type="storage",
        entity_id=0,
        action="update",
        reason=f"New uploads now go to {target}. Existing files remain on their original provider.",
        metadata={"primaryProvider": target},
    )
    await session.commit()
    return {"data": {"primaryProvider": target}}


# --- migration ----------------------------------------------------------------

@router.get("/settings/storage/migration/preview")
async def migration_preview(
    target: str = Query(default=""),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await storage_service.migration_preview(session, target.strip())}


@router.post("/settings/storage/migration/start")
async def migration_start(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await enforce_rate_limit(f"storage:migration:{context.user_id}", limit=2, window_seconds=600)
    target = str(payload.get("target") or "").strip()
    dry_run = bool(payload.get("dryRun"))
    job = await storage_service.start_migration(session, target, dry_run, context.user_id)
    await write_audit(
        session,
        context,
        event_type="STORAGE_MIGRATION_STARTED",
        entity_type="storage",
        entity_id=job.id,
        action="run",
        reason="Dry run preview." if dry_run else f"Copies historical files to {target}; originals are preserved.",
        metadata={"target": target, "dryRun": dry_run},
    )
    await session.commit()
    return {"data": storage_service.serialize_job(job)}


@router.get("/settings/storage/progress")
async def migration_progress(
    context: RequestContext = Depends(require_any_permission("settings.app_config.view", "backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = (
        await session.execute(select(StorageJob).where(StorageJob.job_type.in_(["MIGRATION", "RESTORE", "BACKUP"])).order_by(StorageJob.id.desc()))
    ).scalars().first()
    return {"data": storage_service.serialize_job(job) if job else None}


@router.post("/settings/storage/migration/cleanup")
async def migration_cleanup(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("settings.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not context.has_permission("settings.manage") and not context.is_platform_admin:
        raise AccessDenied("Removing legacy files requires the settings.manage permission.")
    await enforce_rate_limit(f"storage:cleanup:{context.user_id}", limit=2, window_seconds=600)
    try:
        result = await storage_service.migration_cleanup(session, str(payload.get("confirm") or ""))
    finally:
        await write_audit(
            session,
            context,
            event_type="STORAGE_LEGACY_CLEANUP",
            entity_type="storage",
            entity_id=0,
            action="delete",
            reason="Explicitly approved legacy source removal after verified migration.",
        )
        await session.commit()
    return {"data": result}


# --- restore ------------------------------------------------------------------

@router.get("/settings/storage/restore/preview")
async def restore_preview(
    context: RequestContext = Depends(require_any_permission("settings.app_config.view", "backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await storage_service.restore_preview(session)}


@router.post("/settings/storage/restore")
async def restore_execute(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not context.has_permission("settings.manage") and not context.is_platform_admin:
        raise AccessDenied("Restoring files requires the settings.manage permission.")
    await enforce_rate_limit(f"storage:restore:{context.user_id}", limit=2, window_seconds=600)
    job = await storage_service.start_restore(session, str(payload.get("confirm") or ""), context.user_id)
    await write_audit(
        session,
        context,
        event_type="STORAGE_RESTORE_STARTED",
        entity_type="storage",
        entity_id=job.id,
        action="restore",
        reason="Copy verified backup replicas back onto the primary provider.",
    )
    await session.commit()
    return {"data": storage_service.serialize_job(job)}
