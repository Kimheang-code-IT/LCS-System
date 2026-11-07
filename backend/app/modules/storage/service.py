"""Multi-provider storage service.

Reads the ``storage`` group of the application config (see
``app.modules.settings.service.DEFAULT_APP_CONFIG["storage"]``), builds the
matching providers, performs connection tests, and drives the three management
workflows:

* backup     — replicate attachments to the configured backup provider
* migration  — controlled copy of historical files to a new provider
* restore    — put verified replicas back onto the primary provider

Provider network calls are synchronous (boto3 / googleapiclient) and wrapped in
``asyncio.to_thread``. Long-running jobs run as background tasks on their own
DB sessions (the existing backup-module pattern), never inside request
transactions, so backup provider outages cannot block uploads.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, ValidationFailed
from app.modules.storage import providers as provider_mod
from app.modules.storage.models import StorageJob, StorageReplica

logger = logging.getLogger(__name__)

JOB_BACKUP = "BACKUP"
JOB_MIGRATION = "MIGRATION"
JOB_RESTORE = "RESTORE"

_CONFIGURED_TAGS = {"r2", "gdrive"}
# Legacy provider tags whose objects are gone: MinIO ('s3'/'minio') and the
# local-disk store ('local'). Both fail with a clear "no longer available"
# error; the b1c2 migration soft-deleted their attachment rows.
_REMOVED_TAGS = {"s3", "minio", "local"}


def _md5_hex(data: bytes) -> str:
    # Non-security digest: it must match the R2/S3 ETag and Drive md5Checksum,
    # so replica verification can compare against what the provider stored.
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


# --- configuration access -----------------------------------------------------

async def load_config(session: AsyncSession) -> dict[str, Any]:
    from app.modules.settings.service import get_app_config

    config = await get_app_config(session, None)
    return config.get("storage") or {}


async def provider_block(session: AsyncSession, tag: str) -> dict[str, Any]:
    """The stored (un-redacted) provider block, secrets included."""
    from app.modules.settings.models import AppSetting
    from app.modules.settings.service import DEFAULT_APP_CONFIG

    row = (
        await session.execute(select(AppSetting).where(AppSetting.setting_key == "storage"))
    ).scalar_one_or_none()
    stored: dict[str, Any] = dict(row.setting_value or {}) if row else {}
    default = DEFAULT_APP_CONFIG["storage"]["providers"][tag]
    return {**default, **(stored.get("providers", {}).get(tag) or {})}


_SECRET_KEY_MAP = {
    "_secretAccessKey": "secretAccessKey",
    "_clientSecret": "clientSecret",
    "_serviceAccountJson": "serviceAccountJson",
}


def with_secrets(block: dict[str, Any]) -> dict[str, Any]:
    """Expose stored secret values under the ``_``-keys the providers read."""
    mapped = dict(block)
    for internal, stored_name in _SECRET_KEY_MAP.items():
        value = str(block.get(stored_name) or "")
        if value:
            mapped[internal] = value
    mapped.setdefault("_refreshToken", str(block.get("refreshTokenEncrypted") or ""))
    return mapped


def is_configured(tag: str, block: dict[str, Any]) -> bool:
    if tag == "r2":
        return all(str(block.get(key) or "").strip() for key in ("accountId", "bucket", "accessKeyId", "secretAccessKey"))
    if tag == "gdrive":
        if str(block.get("authType") or "").strip() == "service_account":
            return bool(str(block.get("serviceAccountJson") or "").strip())
        return (
            bool(str(block.get("connectedEmail") or "").strip())
            and str(block.get("connectionStatus") or "") == "connected"
        )
    return False


async def build_provider(session: AsyncSession, tag: str) -> provider_mod.FileProvider:
    """Build one usable provider; raise a field-addressable error when unconfigured."""
    if tag not in _CONFIGURED_TAGS:
        raise ValidationFailed(f"Unknown storage provider '{tag}'.", {"provider": "Unsupported provider."})
    block = with_secrets(await provider_block(session, tag))
    if not is_configured(tag, block):
        raise ValidationFailed(
            f"Storage provider '{tag}' is not fully configured.",
            {f"storage.{tag}": "Complete the configuration first."},
        )
    try:
        return provider_mod.build_provider(tag, block)
    except json.JSONDecodeError as exc:
        raise ValidationFailed(
            "The service account JSON is not valid.",
            {f"storage.{tag}": "Upload a valid service account key file."},
        ) from exc
    except Exception as exc:  # noqa: BLE001 - provider construction detail
        raise ValidationFailed(
            f"Storage provider '{tag}' could not be initialized.",
            {f"storage.{tag}": str(exc)[:300]},
        ) from exc


# --- connection tests ---------------------------------------------------------

async def test_connection(session: AsyncSession, tag: str) -> dict[str, Any]:
    """Run a provider connection test and persist status/lastVerifiedAt."""
    if tag not in _CONFIGURED_TAGS:
        raise ValidationFailed("Connection tests apply to Cloudflare R2 and Google Drive.", {"provider": "Unsupported provider."})
    block = with_secrets(await provider_block(session, tag))
    try:
        provider = provider_mod.build_provider(tag, block)
        message = await asyncio.to_thread(provider.test_connection)
        status = "connected"
    except Exception as exc:  # noqa: BLE001 - never expose credential context
        logger.warning("Storage connection test failed for %s: %s", tag, exc)
        status = "connection_failed"
        message = await asyncio.to_thread(_failure_message, tag)
    await _persist_status(session, tag, status, message)
    return {"status": status, "message": message}


def _failure_message(tag: str) -> str:
    if tag == "r2":
        return "Cloudflare R2 connection failed. Verify the account ID, bucket, access keys and endpoint."
    return "Google Drive connection failed. Verify the account type, credentials and destination folder."


async def _persist_status(session: AsyncSession, tag: str, status: str, message: str) -> None:
    """Write only status fields back — secret values are merged, never replaced."""
    from app.core.database import SessionLocal
    from app.modules.settings.models import AppSetting
    from app.modules.settings.service import DEFAULT_APP_CONFIG

    async with SessionLocal() as write_session:
        row = (
            await write_session.execute(
                select(AppSetting).where(AppSetting.setting_key == "storage").with_for_update()
            )
        ).scalar_one_or_none()
        stored: dict[str, Any] = dict(row.setting_value or {}) if row else {}
        default = DEFAULT_APP_CONFIG["storage"]
        block = {**default["providers"][tag], **(stored.get("providers", {}).get(tag) or {})}
        block["connectionStatus"] = status
        block["lastVerifiedAt"] = datetime.now(UTC).isoformat()
        block["lastTestMessage"] = message[:500]
        stored.setdefault("providers", {})[tag] = block
        if row is None:
            write_session.add(AppSetting(setting_key="storage", setting_group="storage", setting_value=stored))
        else:
            row.setting_value = stored
        await write_session.commit()


# --- upload / download dispatch ----------------------------------------------

async def resolve_upload_target(session: AsyncSession) -> tuple[provider_mod.FileProvider, str]:
    """The provider new uploads go to (the configured primary).

    The application has no environment fallback storage: when no provider is
    activated, file operations fail with a clear message instead.
    """
    config = await load_config(session)
    tag = str(config.get("primaryProvider") or "").strip()
    if not tag:
        raise ValidationFailed(
            "File storage is not set up. Configure Cloudflare R2 or Google Drive in Settings → Storage & Backup first.",
            {"storage": "No provider configured."},
        )
    provider = await build_provider(session, tag)
    return provider, tag


async def read_file(storage_key: str, provider_tag: str | None = None, session: AsyncSession | None = None) -> tuple[bytes, str]:
    """Read one attachment's bytes from the provider it actually lives on.

    MinIO-era rows (``storage_provider`` 's3'/'minio') fail with a clear
    message: the MinIO objects were removed, so they are no longer readable.
    """
    from app.core.database import SessionLocal
    from app.core.exceptions import NotFound
    from app.modules.operations.models import Attachment

    if not provider_tag:
        active = session or SessionLocal()  # out-of-band callers (backup jobs)
        try:
            row = (
                await active.execute(select(Attachment).where(Attachment.storage_key == storage_key))
            ).scalar_one_or_none()
            provider_tag = row.storage_provider if row else None
        finally:
            if session is None:
                await active.close()

    # Metadata with no tag (should not exist) is treated as the removed local
    # store: the disk files are gone with the storage volume.
    tag = provider_tag or "local"
    if tag in _REMOVED_TAGS:
        raise NotFound(
            "This file was stored on local disk or the removed MinIO service and is no longer available."
        )

    provider = None if session is None else await build_provider(session, tag)
    if provider is None:
        async with SessionLocal() as own:
            provider = await build_provider(own, tag)
    try:
        return await asyncio.to_thread(provider.get, storage_key)
    except LookupError as exc:
        raise NotFound("File not found.") from exc


def presigned_url_for(attachment: Any, provider: provider_mod.FileProvider) -> str | None:
    return provider.presigned_get(attachment.storage_key, 300) if provider.supports_presign else None


# --- backup engine ------------------------------------------------------------

async def schedule_replication(
    session: AsyncSession, attachment_id: int, target: str | None = None, *, by_migration: bool = False
) -> None:
    """Idempotently create a durable PENDING replica row; the scheduler runs it."""
    config = await load_config(session)
    target = target or (str(config.get("backupProvider") or "").strip() or None)
    backup_enabled = bool(config.get("backupEnabled"))
    if not target or (not backup_enabled and not by_migration):
        return
    if target == config.get("primaryProvider"):
        return
    if not is_configured(target, (config.get("providers") or {}).get(target) or {}):
        return
    existing = (
        await session.execute(
            select(StorageReplica).where(
                StorageReplica.attachment_id == attachment_id,
                StorageReplica.backup_provider == target,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    session.add(StorageReplica(attachment_id=attachment_id, backup_provider=target, backup_key="-", status="PENDING", created_by_migration=by_migration))
    await session.commit()


async def replicate_attachment(attachment_id: int, replica_id: int, provider: provider_mod.FileProvider) -> str:
    """Copy one attachment to its replica's provider and verify it in place.

    Uses a fresh row instance so it is safe to call from job tasks while the
    caller's session might hold an older version. Returns the final status.
    """
    from app.core.database import SessionLocal
    from app.modules.operations.models import Attachment

    async with SessionLocal() as session:
        current = await session.get(StorageReplica, replica_id)
        attachment = (await session.get(Attachment, attachment_id)) if current else None
        if current is None:
            return "MISSING"
        if attachment is None or attachment.is_deleted:
            await session.delete(current)
            await session.commit()
            return "MISSING"
        try:
            content, content_type = await read_file(attachment.storage_key, attachment.storage_provider)
            checksum = _md5_hex(content)
            key = current.backup_key if current.backup_key != "-" else (
                f"migrated/{attachment.storage_key}" if not provider.supports_presign else provider_mod.new_object_key(attachment.file_name)
            )
            backup_key = await asyncio.to_thread(provider.put, key, content, content_type, attachment.file_name)
            stored_size = await asyncio.to_thread(provider.size, backup_key) or len(content)
            stored_checksum = await asyncio.to_thread(provider.checksum, backup_key)
            if stored_size != len(content) or (stored_checksum and stored_checksum != checksum):
                raise ValueError("Replica verification failed: size or checksum mismatch.")
            current.backup_key = backup_key
            current.file_size_bytes = stored_size
            current.checksum = checksum or stored_checksum
            current.status = "ACTIVE"
            current.last_synced_at = datetime.now(UTC)
            current.last_error = None
            current.attempts += 1
        except Exception as exc:  # noqa: BLE001 - failures persist for retry
            current.attempts += 1
            current.status = "FAILED"
            current.last_error = str(exc)[:500]
            logger.warning("Replication of attachment %s failed: %s", attachment_id, exc)
        await session.commit()
        return current.status


async def retryable_replicas(session: AsyncSession, target: str, max_attempts: int) -> list[StorageReplica]:
    return list(
        (
            await session.execute(
                select(StorageReplica)
                .where(
                    StorageReplica.backup_provider == target,
                    StorageReplica.status.in_(["PENDING", "FAILED"]),
                    StorageReplica.attempts < max(1, max_attempts),
                )
                .order_by(StorageReplica.id)
            )
        ).scalars().all()
    )


async def _process_replicas(job: StorageJob, target: str) -> None:
    """The backup sweep body: process every retryable replica to ``target``."""
    from app.core.config import settings as app_settings
    from app.core.database import SessionLocal

    async with SessionLocal() as session:
        current = await session.get(StorageJob, job.id)
        if current is None or current.status in {"RUNNING", "COMPLETED"}:
            return
        current.status = "RUNNING"
        current.started_at = current.started_at or datetime.now(UTC)
        await session.commit()
        provider = await build_provider(session, target)
        replicas = await retryable_replicas(session, target, max(1, int(app_settings.storage_backup_max_retries)))
        current.total = max(current.total, len(replicas))
        for replica in replicas:
            await replicate_attachment(replica.attachment_id, replica.id, provider)
            current.processed += 1
            current.progress = int(current.processed * 100 / max(1, current.total))
        remaining = (
            await retryable_replicas(session, target, 1_000)  # any attempts left
        )
        current.status = "COMPLETED" if not remaining else "PENDING"
        current.message = (
            f"{current.processed}/{current.total} processed."
            if current.status == "COMPLETED"
            else f"{current.processed}/{current.total} processed; retrying failures next tick."
        )
        current.finished_at = datetime.now(UTC) if current.status == "COMPLETED" else None
        await session.commit()


async def backup_now(session: AsyncSession, user_id: int | None, target: str | None = None, *, force_retry: bool = False) -> StorageJob:
    """Sweep every attachment lacking a replica on ``target`` into PENDING rows."""
    from app.modules.operations.models import Attachment

    config = await load_config(session)
    target = target or str(config.get("backupProvider") or "").strip()
    if not target:
        raise ValidationFailed("Configure a backup provider before running a backup.", {"backupProvider": "Not configured."})
    if target == config.get("primaryProvider"):
        raise ValidationFailed("The backup provider must differ from the primary provider.", {"backupProvider": "Same destination."})
    await build_provider(session, target)  # Validation only.
    if force_retry:
        # The explicit retry clears the attempt cap so failed files re-run now.
        failed = await session.execute(
            update(StorageReplica)
            .where(StorageReplica.backup_provider == target, StorageReplica.status == "FAILED")
            .values(attempts=0, status="PENDING")
        )
        _ = failed
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(Attachment).where(Attachment.is_deleted.is_(False))
            )
        ).scalar_one()
    )
    job = StorageJob(job_type=JOB_BACKUP, target_provider=target, status="PENDING", total=total, started_by_user_id=user_id)
    session.add(job)
    await session.commit()
    asyncio.get_running_loop().create_task(_process_replicas(job, target))
    return job


# --- managed job execution ----------------------------------------------------

async def reconcile(session: AsyncSession) -> None:
    """Scheduler tick: process new/failed replicas and resume interrupted jobs."""
    config = await load_config(session)
    if bool(config.get("backupEnabled")):
        target = str(config.get("backupProvider") or "").strip()
        if target and is_configured(target, (config.get("providers") or {}).get(target) or {}):
            pending = await retryable_replicas(session, target, 1)
            if pending:
                job = StorageJob(job_type=JOB_BACKUP, target_provider=target, status="PENDING", total=len(pending))
                session.add(job)
                await session.commit()
                asyncio.get_running_loop().create_task(_process_replicas(job, target))
    # Resume unstarted jobs and reset jobs whose heartbeat stalled.
    running = list((await session.execute(select(StorageJob).where(StorageJob.status == "RUNNING"))).scalars().all())
    for job in running:
        if job.updated_at and (datetime.now(UTC) - job.updated_at).total_seconds() > 600:
            job.status = "PENDING"
            await session.commit()
    resumable = list((await session.execute(select(StorageJob).where(StorageJob.status == "PENDING"))).scalars().all())
    for job in resumable:
        try:
            provider = await build_provider(session, job.target_provider)
        except ValidationFailed:
            continue
        if job.job_type == JOB_BACKUP:
            asyncio.get_running_loop().create_task(_process_replicas(job, job.target_provider))
        elif job.job_type == JOB_MIGRATION and not job.dry_run:
            asyncio.get_running_loop().create_task(_run_migration_job(job.id, provider))
        elif job.job_type == JOB_RESTORE:
            asyncio.get_running_loop().create_task(_run_restore_job(job.id, provider))


# --- migration ----------------------------------------------------------------

async def migration_preview(session: AsyncSession, target: str) -> dict[str, Any]:
    from app.modules.operations.models import Attachment

    if target not in _CONFIGURED_TAGS:
        raise ValidationFailed("Choose Cloudflare R2 or Google Drive as the migration target.", {"target": "Unsupported target."})
    await build_provider(session, target)  # Only configured, verified targets.
    rows = list(
        (
            await session.execute(
                select(Attachment.storage_provider, Attachment.file_size_bytes).where(Attachment.is_deleted.is_(False))
            )
        ).all()
    )
    by_provider: dict[str, int] = {}
    total_bytes = 0
    for provider_name, size in rows:
        by_provider[str(provider_name)] = by_provider.get(str(provider_name), 0) + 1
        total_bytes += int(size or 0)
    migrated = len(
        set(
            (
                await session.execute(select(StorageReplica.attachment_id).where(StorageReplica.backup_provider == target))
            ).scalars().all()
        )
    )
    return {
        "target": target,
        "byProvider": by_provider,
        "files": len(rows),
        "bytes": total_bytes,
        "alreadyOnTarget": migrated,
        "toMigrate": max(0, len(rows) - migrated),
    }


async def start_migration(session: AsyncSession, target: str, dry_run: bool, user_id: int | None) -> StorageJob:
    from app.modules.operations.models import Attachment

    existing = list(
        
            await session.execute(
                select(StorageJob).where(StorageJob.job_type == JOB_MIGRATION, StorageJob.status.in_(["PENDING", "RUNNING"]))
            )
        
    ).scalars().all()
    if existing:
        raise Conflict("MIGRATION_RUNNING", "A migration is already in progress.")
    if target == (await load_config(session)).get("primaryProvider"):
        raise ValidationFailed("Migrating onto the primary provider changes nothing.", {"target": "Target equals primary."})
    provider = await build_provider(session, target)
    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Attachment)
                .outerjoin(StorageReplica, (StorageReplica.attachment_id == Attachment.id) & (StorageReplica.backup_provider == target))
                .where(Attachment.is_deleted.is_(False), StorageReplica.id.is_(None), Attachment.storage_provider != target)
            )
        ).scalar_one()
    )
    job = StorageJob(
        job_type=JOB_MIGRATION, target_provider=target, status="PENDING", dry_run=dry_run, total=total, started_by_user_id=user_id
    )
    session.add(job)
    await session.commit()
    if not dry_run:
        asyncio.get_running_loop().create_task(_run_migration_job(job.id, provider))
    return job


async def _run_migration_job(job_id: int, provider: provider_mod.FileProvider) -> None:
    from app.core.database import SessionLocal
    from app.modules.operations.models import Attachment

    async with SessionLocal() as session:
        job = await session.get(StorageJob, job_id)
        if job is None or job.status == "RUNNING":
            return
        job.status = "RUNNING"
        job.started_at = datetime.now(UTC)
        await session.commit()
        target = job.target_provider
        attachments = list(
            (
                await session.execute(
                    select(Attachment).where(
                        Attachment.is_deleted.is_(False),
                        Attachment.storage_provider != target,
                    ).order_by(Attachment.id)
                )
            ).scalars().all()
        )
        job.total = len(attachments)
        for attachment in attachments:
            replica = (
                await session.execute(
                    select(StorageReplica).where(
                        StorageReplica.attachment_id == attachment.id,
                        StorageReplica.backup_provider == target,
                    )
                )
            ).scalar_one_or_none()
            if replica is not None and replica.status == "ACTIVE":
                job.processed += 1  # Idempotent: a verified copy already exists.
                continue
            try:
                if replica is None:
                    replica = StorageReplica(
                        attachment_id=attachment.id,
                        backup_provider=target,
                        backup_key="-",
                        status="PENDING",
                        created_by_migration=True,
                    )
                    session.add(replica)
                    await session.flush()
                replica_id = replica.id
                await session.commit()
                final_status = await replicate_attachment(attachment.id, replica_id, provider)
                if final_status != "ACTIVE":
                    fresh = await session.get(StorageReplica, replica_id)
                    raise ValueError((fresh.last_error if fresh else None) or "Replication failed.")
                job.processed += 1
            except IntegrityError:
                # A concurrent upload scheduled the same replica; the unique
                # constraint is the arbiter. Roll back and count it as copied.
                await session.rollback()
                job.processed += 1
            except Exception as exc:  # noqa: BLE001 - keep migrating the rest
                await session.rollback()
                job.failed += 1
                logger.warning("Migration of attachment %s failed: %s", attachment.id, exc)
            job.progress = int(job.processed * 100 / max(1, job.total))
            try:
                await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()
        job.status = "COMPLETED" if job.failed == 0 else "FAILED"
        job.finished_at = datetime.now(UTC)
        job.message = f"Copied {job.processed}/{job.total} file(s); {job.failed} failed." if job.failed else f"Copied {job.processed} file(s)."
        await session.commit()


async def migration_cleanup(session: AsyncSession, confirm: str) -> dict[str, Any]:
    """Explicitly approved removal of the originals left on the *old* provider.

    Only rows the migration itself replicated are considered, the source
    provider must differ from the current primary, and a checksum-verified
    replica must exist. Never automatic and never applied to unrelated rows.
    """
    from app.modules.operations.models import Attachment
    from app.core.database import SessionLocal

    if confirm.strip().upper() != "DELETE":
        raise ValidationFailed("Type DELETE to confirm removing migration source files.", {"confirm": "Confirmation required."})
    config = await load_config(session)
    primary = str(config.get("primaryProvider") or "").strip()
    async with SessionLocal() as own:
        attachments = list(
            (await own.execute(select(Attachment).where(Attachment.is_deleted.is_(False)))).scalars().all()
        )
        removed = 0
        for attachment in attachments:
            if attachment.storage_provider not in _CONFIGURED_TAGS or attachment.storage_provider == primary:
                continue
            replica = (
                await own.execute(
                    select(StorageReplica).where(
                        StorageReplica.attachment_id == attachment.id,
                        StorageReplica.status == "ACTIVE",
                        StorageReplica.created_by_migration.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if replica is None:
                continue
            try:
                # Rebuild the source provider from its own stored config; the
                # source tag may differ from the current primary.
                source = await build_provider(own, attachment.storage_provider)
                if not await asyncio.to_thread(source.exists, attachment.storage_key):
                    continue
                if replica.checksum and replica.checksum != await asyncio.to_thread(source.checksum, attachment.storage_key):
                    continue  # Verify before touching anything.
                await asyncio.to_thread(source.delete, attachment.storage_key)
                removed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Migration cleanup for attachment %s failed: %s", attachment.id, exc)
        await own.commit()
    return {"removed": removed}


# --- restore ------------------------------------------------------------------

async def restore_preview(session: AsyncSession) -> dict[str, Any]:
    from app.modules.operations.models import Attachment

    primary, primary_tag = await resolve_upload_target(session)
    replicas = list(
        (
            await session.execute(select(StorageReplica).where(StorageReplica.status == "ACTIVE"))
        ).scalars().all()
    )
    restorable = 0
    for replica in replicas:
        if replica.backup_provider == primary_tag:
            continue  # Restore must come from an independent destination.
        attachment = await session.get(Attachment, replica.attachment_id)
        if attachment is None or attachment.is_deleted:
            continue
        if not await asyncio.to_thread(primary.exists, attachment.storage_key):
            restorable += 1
    return {"restorable": restorable, "replicas": len(replicas), "primary": primary_tag}


async def start_restore(session: AsyncSession, confirm: str, user_id: int | None) -> StorageJob:
    if confirm.strip().upper() != "RESTORE":
        raise ValidationFailed("Type RESTORE to confirm restoring files.", {"confirm": "Confirmation required."})
    provider, tag = await resolve_upload_target(session)
    job = StorageJob(job_type=JOB_RESTORE, target_provider=tag, status="PENDING", started_by_user_id=user_id)
    session.add(job)
    await session.commit()
    asyncio.get_running_loop().create_task(_run_restore_job(job.id, provider))
    return job


async def _run_restore_job(job_id: int, primary: provider_mod.FileProvider) -> None:
    from app.core.database import SessionLocal
    from app.modules.operations.models import Attachment

    async with SessionLocal() as session:
        job = await session.get(StorageJob, job_id)
        if job is None:
            return
        job.status = "RUNNING"
        job.started_at = datetime.now(UTC)
        await session.commit()
        replicas = [
            replica
            for replica in list(
                (
                    await session.execute(
                        select(StorageReplica).where(StorageReplica.status == "ACTIVE").order_by(StorageReplica.id)
                    )
                ).scalars().all()
            )
            if replica.backup_provider != primary.tag
        ]
        job.total = len(replicas)
        for replica in replicas:
            attachment = await session.get(Attachment, replica.attachment_id)
            if attachment is None or attachment.is_deleted or await asyncio.to_thread(primary.exists, attachment.storage_key):
                job.processed += 1
                continue
            try:
                provider = await build_provider(session, replica.backup_provider)
                content, content_type = await asyncio.to_thread(provider.get, replica.backup_key)
                restored_key = await asyncio.to_thread(
                    primary.put, attachment.storage_key, content, content_type, attachment.file_name
                )
                if restored_key != attachment.storage_key:
                    attachment.storage_key = restored_key
                    attachment.storage_provider = primary.tag
                job.processed += 1
            except Exception as exc:  # noqa: BLE001
                job.failed += 1
                logger.warning("Restore of attachment %s failed: %s", replica.attachment_id, exc)
            job.progress = int(job.processed * 100 / max(1, job.total))
            try:
                await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()
        job.status = "COMPLETED" if job.failed == 0 else "FAILED"
        job.finished_at = datetime.now(UTC)
        job.message = f"Restored {job.processed}/{job.total} file(s)." if not job.failed else f"{job.processed}/{job.total} restored; {job.failed} failed."
        await session.commit()


# --- dashboard ----------------------------------------------------------------

def serialize_job(job: StorageJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "jobType": job.job_type,
        "target": job.target_provider,
        "status": job.status,
        "dryRun": job.dry_run,
        "total": job.total,
        "processed": job.processed,
        "failed": job.failed,
        "progress": job.progress,
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
        "message": job.message,
    }


async def backup_overview(session: AsyncSession) -> dict[str, Any]:
    config = await load_config(session)
    target = str(config.get("backupProvider") or "").strip()
    pending = 0
    last_success: str | None = None
    last_failure: str | None = None
    if target:
        rows = list(
            (
                await session.execute(
                    select(StorageReplica).where(StorageReplica.backup_provider == target).order_by(StorageReplica.id.desc()).limit(200)
                )
            ).scalars().all()
        )
        pending = sum(1 for replica in rows if replica.status in {"PENDING", "FAILED"})
        for replica in rows:
            if replica.status == "ACTIVE" and replica.last_synced_at:
                stamp = replica.last_synced_at.isoformat()
                last_success = max(last_success or "", stamp)
            elif replica.status == "FAILED" and replica.updated_at:
                stamp = replica.updated_at.isoformat()
                last_failure = max(last_failure or "", stamp)
    jobs = list((await session.execute(select(StorageJob).order_by(StorageJob.id.desc()).limit(5))).scalars().all())
    return {
        "backupEnabled": bool(config.get("backupEnabled")),
        "primaryProvider": config.get("primaryProvider") or "",
        "backupProvider": target,
        "pending": pending,
        "lastSuccessfulBackup": last_success,
        "lastFailedBackup": last_failure,
        "recentJobs": [serialize_job(job) for job in jobs],
    }
