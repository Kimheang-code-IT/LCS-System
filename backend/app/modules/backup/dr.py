"""Full disaster-recovery backups: pg_dump + attachments + manifest.

Runs beside the existing logical Sheets/R2 snapshot engine (``service.py``),
which is preserved unchanged. One full backup is a single archive:

    lcs-full-<id>.tar.gz[.fernet]
      db/pg_dump.dump          PostgreSQL custom-format dump (pg_restore ready)
      attachments/<index>-<name> uploaded files (checksum-verified on restore;
                               the raw storage key is only in the manifest)
      manifest.json            id, timestamps, versions, revision, checksums,
                               encryption metadata, file list

* Integrity: SHA-256 per member plus the archive digest recorded in a sidecar
  ``<archive>.manifest.json`` (metadata only, no secrets).
* Encryption: Fernet (AES-128-CBC+HMAC) keyed by ``BACKUP_ENCRYPTION_KEY``;
  the key is never stored inside the archive.
* Destination: the existing R2/S3 configuration when a session is available,
  otherwise ``FULL_BACKUP_S3_*`` environment variables. A local copy always
  remains under ``FULL_BACKUP_DIR`` (default ``<repo>/backups/full``).
* Restore is deliberately a separate CLI/script path (``scripts/full_backup.py``)
  so it stays usable when the application instance or its database is gone.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import Conflict, ValidationFailed

RESTORE_CONFIRM = "RESTORE"
ARCHIVE_PREFIX = "lcs-full-"
MANIFEST_NAME = "manifest.json"


# --- path safety -------------------------------------------------------------
#
# Archive names and attachment storage keys are the only values that reach the
# filesystem from a request or a database row. Each is reduced to a single
# basename before it is joined to a trusted directory, and archive paths are
# confined to the configured backup directory. This is what keeps a crafted
# `../../` name from reading or writing outside the backup root (CodeQL
# py/path-injection).


def _basename(value: str | Path) -> str:
    """One path component, with both separator styles normalised."""
    return os.path.basename(str(value or "").replace("\\", "/"))


def _safe_archive_name(value: str | Path) -> str:
    name = _basename(value)
    if not name.startswith(ARCHIVE_PREFIX) or not (
        name.endswith(".tar.gz") or name.endswith(".tar.gz.fernet")
    ):
        raise ValidationFailed(
            "Unknown backup archive name.", {"file": "Use a name from the backup history."}
        )
    return name


def _safe_archive_path(value: str | Path) -> Path:
    """Resolve an archive name inside the configured backup directory only."""
    path = archive_dir() / _safe_archive_name(value)
    if not path.is_file():
        raise ValidationFailed("That backup archive does not exist.", {"file": "Missing archive"})
    return path


def _confined_child(base: Path, relative: str) -> Path:
    """Join one safe relative name to a trusted directory (defence in depth)."""
    root = base.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationFailed(
            "Invalid archive member path.", {"file": "Invalid path"}
        ) from exc
    if candidate == root:
        raise ValidationFailed("Invalid archive member path.", {"file": "Invalid path"})
    return candidate


def _safe_member_name(value: object) -> str:
    """A single archive member/file name; no directories or traversal."""
    name = _basename(str(value or ""))
    if not name or name in (".", ".."):
        raise ValidationFailed(
            "Invalid attachment storage key.", {"file": "Invalid storage key"}
        )
    return name


# --- paths / environment -----------------------------------------------------


def archive_dir() -> Path:
    configured = os.environ.get("FULL_BACKUP_DIR", "").strip()
    default = Path(__file__).resolve().parents[3] / "backups" / "full"
    path = Path(configured) if configured else default
    path.mkdir(parents=True, exist_ok=True)
    return path


def encryption_key() -> str:
    return os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()


def _fernet(key: str):
    from cryptography.fernet import Fernet

    return Fernet(key.encode("ascii"))


def _binary(name: str) -> str:
    env_name = f"{name.upper()}_BIN"
    configured = os.environ.get(env_name, "").strip()
    if configured:
        return configured
    found = shutil.which(name)
    if not found:
        raise ValidationFailed(
            f"'{name}' was not found. Install the PostgreSQL client tools (postgresql-client) "
            f"or set {env_name}.",
            {"file": f"Missing {name}"},
        )
    return found


def libpq_dsn(url: str | None = None) -> str:
    """SQLAlchemy async URL -> plain libpq DSN accepted by pg_dump/pg_restore."""
    raw = str(url or settings.database_url)
    for driver in ("+asyncpg", "+psycopg2", "+psycopg"):
        raw = raw.replace(driver, "")
    return raw


# --- dump / restore primitives ------------------------------------------------


def dump_database(dsn: str, destination: Path, runner: Callable[..., Any] = subprocess.run) -> None:
    # The caller always passes a temp path; reduce it to its basename anyway so
    # no caller-supplied directory can redirect the dump.
    destination = _confined_child(Path(destination).parent, _basename(destination))
    with open(destination, "wb") as out:
        result = runner(
            [_binary("pg_dump"), "--format=custom", "--no-owner", "--no-privileges", "--dbname", dsn],
            stdout=out,
            stderr=subprocess.PIPE,
            timeout=3600,
        )
    if result.returncode != 0:
        raise ValidationFailed(
            "pg_dump failed; the database backup could not be created.",
            {"file": (result.stderr or b"")[-800:].decode("utf-8", "replace")},
        )
    if destination.stat().st_size == 0:
        raise ValidationFailed("pg_dump produced an empty file.", {"file": "Empty dump"})


def restore_database(dsn: str, dump_path: Path, runner: Callable[..., Any] = subprocess.run) -> None:
    result = runner(
        [
            _binary("pg_restore"),
            "--no-owner",
            "--no-privileges",
            "--single-transaction",
            "--exit-on-error",
            "--dbname",
            dsn,
            str(dump_path),
        ],
        capture_output=True,
        timeout=3600,
    )
    if result.returncode != 0:
        raise ValidationFailed(
            "pg_restore failed; the database was left unchanged (single transaction).",
            {"file": (result.stderr or b"")[-800:].decode("utf-8", "replace")},
        )


# --- archive assembly ---------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    # Keep the digest reader on a single trusted path component even if a caller
    # passes a name assembled elsewhere.
    path = _confined_child(Path(path).parent, _basename(path))
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _attachment_rows(session: AsyncSession) -> list[dict[str, Any]]:
    from app.modules.operations.models import Attachment

    rows = (
        await session.execute(select(Attachment).where(Attachment.is_deleted.is_(False)))
    ).scalars().all()
    return [
        {
            "file_name": row.file_name,
            "storage_key": row.storage_key,
            "mime_type": row.mime_type,
            "file_size_bytes": int(row.file_size_bytes or 0),
            "checksum": row.checksum,
            "storage_provider": row.storage_provider,
        }
        for row in rows
    ]


def _read_attachment(session: AsyncSession, tag: str, key: str) -> tuple[bytes, str]:
    from app.modules.storage import service as storage_service

    if tag not in ("r2", "gdrive"):
        raise ValidationFailed(
            f"Attachment provider '{tag}' cannot be read from this deployment.",
            {"file": "Unsupported provider"},
        )
    provider = storage_service.build_provider(session, tag)
    return provider.get(key)


async def build_archive(
    session: AsyncSession | None,
    *,
    archive_root: Path | None = None,
    dsn: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Create one full backup archive; returns its manifest."""
    now = datetime.now(UTC)
    backup_id = now.strftime("%Y%m%dT%H%M%SZ")
    root = archive_root or archive_dir()
    work = Path(tempfile.mkdtemp(prefix="lcs-full-"))
    manifest: dict[str, Any] = {
        "backupId": backup_id,
        "createdAt": now.isoformat(),
        "application": {"name": "lcs-freight", "version": "0.1.0"},
        "components": ["postgresql", "attachments"],
        "database": {"format": "pg_dump-custom"},
        "files": [],
        "attachmentErrors": [],
    }
    try:
        if session is not None:
            revision = (await session.execute(text("select version_num from alembic_version"))).scalar()
            manifest["database"]["migrationRevision"] = revision
            version = (await session.execute(text("show server_version"))).scalar()
            manifest["database"]["serverVersion"] = version
            attachments = await _attachment_rows(session)
        else:
            attachments = []
        key = encryption_key()
        manifest["encryption"] = {"algorithm": "fernet" if key else "none"}

        # 1) Database dump.
        dump_path = work / "pg_dump.dump"
        dump_database(dsn or libpq_dsn(), dump_path, runner)
        manifest["database"]["sha256"] = _sha256_file(dump_path)
        manifest["database"]["bytes"] = dump_path.stat().st_size

        # 2) Attachments (soft-fail per file; the DB still holds their rows).
        if attachments:
            files_dir = work / "attachments"
            files_dir.mkdir(parents=True, exist_ok=True)
            for index, item in enumerate(attachments):
                try:
                    content, _mime = _read_attachment(session, item["storage_provider"], item["storage_key"])  # type: ignore[arg-type]
                except ValidationFailed as exc:
                    manifest["attachmentErrors"].append(
                        {"storageKey": item["storage_key"], "error": str(getattr(exc, "message", exc))[:200]}
                    )
                    continue
                except Exception as exc:  # noqa: BLE001 - record, don't abort the DB backup
                    manifest["attachmentErrors"].append(
                        {"storageKey": item["storage_key"], "error": str(exc)[:200]}
                    )
                    continue
                # The archive member is a generated index + the key's basename,
                # never the raw storage key (which may contain directories).
                archive_name = f"{index:06d}-{_safe_member_name(item['storage_key'])}"
                target = _confined_child(files_dir, archive_name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                manifest["files"].append(
                    {
                        "storageKey": item["storage_key"],
                        "archivePath": archive_name,
                        "file_name": item["file_name"],
                        "bytes": len(content),
                        "sha256": _sha256_bytes(content),
                    }
                )
        manifest["attachments"] = {"rows": len(attachments), "archived": len(manifest["files"])}

        # 3) Manifest + tar.
        (work / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        archive_path = _confined_child(root, f"{ARCHIVE_PREFIX}{backup_id}.tar.gz")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(dump_path, arcname="db/pg_dump.dump")
            if manifest["files"]:
                tar.add(work / "attachments", arcname="attachments")
            tar.add(work / MANIFEST_NAME, arcname=MANIFEST_NAME)

        # 4) Optional encryption (key stays outside the archive).
        if key:
            encrypted_path = _confined_child(root, f"{archive_path.name}.fernet")
            encrypted_path.write_bytes(_fernet(key).encrypt(archive_path.read_bytes()))
            archive_path.unlink()
            archive_path = encrypted_path
        manifest["archive"] = {"file": archive_path.name, "sha256": _sha256_file(archive_path), "bytes": archive_path.stat().st_size}
        _confined_child(root, f"{archive_path.name}.manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        return manifest
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --- verification --------------------------------------------------------------


def decrypt_if_needed(archive: Path, key: str | None = None) -> tuple[Path, bool]:
    archive = _safe_archive_path(archive)
    key = (key if key is not None else encryption_key()).strip()
    if not archive.name.endswith(".fernet"):
        return archive, False
    if not key:
        raise ValidationFailed(
            "This archive is encrypted. Provide the Fernet key (BACKUP_ENCRYPTION_KEY).",
            {"file": "Missing encryption key"},
        )
    # Fixed prefix: the archive name is user-visible and must not shape a temp path.
    fd, tmp_name = tempfile.mkstemp(prefix="lcs-decrypt-", suffix=".tar.gz")
    os.close(fd)
    tmp = Path(tmp_name)
    tmp.write_bytes(_fernet(key).decrypt(archive.read_bytes()))
    return tmp, True


def read_manifest(archive: Path, key: str | None = None) -> dict[str, Any]:
    plain, cleanup = decrypt_if_needed(_safe_archive_path(archive), key)
    try:
        with tarfile.open(plain, "r:gz") as tar:
            member = tar.extractfile(MANIFEST_NAME)
            if member is None:
                raise ValidationFailed("The archive has no manifest.", {"file": "Missing manifest"})
            return json.loads(member.read().decode("utf-8"))
    finally:
        if cleanup:
            plain.unlink(missing_ok=True)


def verify_archive(archive: Path, key: str | None = None) -> dict[str, Any]:
    """Full integrity check: archive digest, manifest checksum, every member."""
    archive = _safe_archive_path(archive)
    problems: list[str] = []
    sidecar = archive.parent / f"{_basename(archive.name)}.manifest.json"
    expected = None
    if sidecar.exists():
        expected = json.loads(sidecar.read_text(encoding="utf-8")).get("archive", {}).get("sha256")
    actual = _sha256_file(archive)
    if expected and expected != actual:
        problems.append("Archive SHA-256 does not match its sidecar manifest.")

    plain, cleanup = decrypt_if_needed(archive, key)
    try:
        with tarfile.open(plain, "r:gz") as tar:
            try:
                manifest = json.loads(tar.extractfile(MANIFEST_NAME).read().decode("utf-8"))
            except (AttributeError, KeyError, json.JSONDecodeError):
                return {"ok": False, "problems": [*problems, "Manifest is missing or unreadable."]}
            db_sha = manifest.get("database", {}).get("sha256")
            dump_member = tar.extractfile("db/pg_dump.dump")
            if dump_member is None or not db_sha:
                problems.append("Database dump member is missing.")
            else:
                if _sha256_bytes(dump_member.read()) != db_sha:
                    problems.append("Database dump SHA-256 mismatch.")
            for item in manifest.get("files", []):
                # `archivePath` is the generated safe name; older manifests fall
                # back to the storage key's basename.
                member_name = _safe_member_name(item.get("archivePath") or item.get("storageKey"))
                member = tar.extractfile(f"attachments/{member_name}")
                if member is None:
                    problems.append(f"Attachment missing: {item.get('storageKey', member_name)}")
                    continue
                if _sha256_bytes(member.read()) != item["sha256"]:
                    problems.append(f"Attachment SHA-256 mismatch: {item.get('storageKey', member_name)}")
    finally:
        if cleanup:
            plain.unlink(missing_ok=True)
    return {"ok": not problems, "problems": problems, "manifest": manifest}


# --- restore -------------------------------------------------------------------


def guard_restore_target(target_dsn: str) -> None:
    """Refuse to overwrite the live database unless an operator explicitly opts in."""
    if libpq_dsn(target_dsn) == libpq_dsn() and os.environ.get("FULL_BACKUP_ALLOW_LIVE_RESTORE") != "1":
        raise Conflict(
            "LIVE_RESTORE_BLOCKED",
            "Refusing to restore over the running application database. "
            "Point target at an isolated database, or set FULL_BACKUP_ALLOW_LIVE_RESTORE=1 "
            "after taking a safety backup and enabling maintenance mode.",
        )


def restore_archive(
    archive: Path,
    *,
    target_dsn: str,
    confirm: str,
    key: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Verified restore into an isolated target. Never called by the UI alone."""
    if confirm != RESTORE_CONFIRM:
        raise ValidationFailed(f"Type {RESTORE_CONFIRM} to confirm the restore.", {"confirm": "Confirmation required"})
    archive = _safe_archive_path(archive)
    guard_restore_target(target_dsn)
    report = verify_archive(archive, key)
    if not report["ok"]:
        raise ValidationFailed("The archive failed integrity verification.", {"file": "; ".join(report["problems"])[:800]})
    manifest = report["manifest"]
    plain, cleanup = decrypt_if_needed(archive, key)
    work = Path(tempfile.mkdtemp(prefix="lcs-restore-"))
    try:
        with tarfile.open(plain, "r:gz") as tar:
            tar.extractall(work, filter="data")  # noqa: S202 - members are our own archive format
        restore_database(target_dsn, work / "db" / "pg_dump.dump", runner)
        restored = 0
        for item in manifest.get("files", []):
            member_name = _safe_member_name(item.get("archivePath") or item.get("storageKey"))
            path = _confined_child(work / "attachments", member_name)
            if path.exists():
                restored += 1
        return {"restored": manifest.get("database", {}), "attachmentsRestored": restored, "manifest": manifest}
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if cleanup:
            plain.unlink(missing_ok=True)


# --- object storage upload -----------------------------------------------------


async def upload_archive(session: AsyncSession | None, archive: Path) -> str | None:
    """Upload the archive to the configured S3-compatible destination (R2 first)."""
    from app.core.storage import S3Storage

    endpoint = os.environ.get("FULL_BACKUP_S3_ENDPOINT", "").strip()
    bucket = os.environ.get("FULL_BACKUP_S3_BUCKET", "").strip()
    access = os.environ.get("FULL_BACKUP_S3_ACCESS_KEY", "").strip()
    secret = os.environ.get("FULL_BACKUP_S3_SECRET_KEY", "")
    prefix = os.environ.get("FULL_BACKUP_S3_PREFIX", "lcs/full-backups").strip("/")

    if session is not None and (not bucket or not access):
        config = await _r2_config(session)
        endpoint = endpoint or str(config.get("r2Endpoint") or "")
        bucket = bucket or str(config.get("r2BucketName") or "")
        access = access or str(config.get("r2AccessKeyId") or "")
        secret = secret or str(config.get("r2SecretAccessKey") or "")
        prefix = os.environ.get("FULL_BACKUP_S3_PREFIX", "").strip("/") or str(config.get("r2Prefix") or "backups").strip("/")

    if not (endpoint and bucket and access and secret):
        return None
    storage = S3Storage(
        bucket=bucket,
        endpoint_url=endpoint,
        access_key=access,
        secret_key=secret,
        region=os.environ.get("FULL_BACKUP_S3_REGION", "auto"),
        ensure_bucket=False,
    )
    key = f"{prefix}/{archive.name}" if prefix else archive.name
    await asyncio.to_thread(storage.put, key, archive.read_bytes(), "application/octet-stream")
    return key


async def _r2_config(session: AsyncSession) -> dict[str, Any]:
    from app.modules.settings.service import get_app_config

    config = await get_app_config(session)
    r2 = (config.get("storage") or {}).get("providers", {}).get("r2") or {}
    # Backup destination historically lived in the backup group; the canonical
    # R2 block is the single source now.
    backup = config.get("backup") or {}
    return {
        "r2Endpoint": r2.get("endpoint") or backup.get("r2Endpoint") or "",
        "r2BucketName": r2.get("bucketName") or backup.get("r2BucketName") or "",
        "r2AccessKeyId": r2.get("accessKeyId") or backup.get("r2AccessKeyId") or "",
        "r2SecretAccessKey": r2.get("secretAccessKey") or backup.get("r2SecretAccessKey") or "",
        "r2Prefix": r2.get("objectPrefix") or backup.get("r2Prefix") or "backups",
    }


def archive_path_from_name(name: str) -> Path:
    """Resolve a backup file name inside the archive directory (no traversal)."""
    return _safe_archive_path(name)


def list_archives(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or archive_dir()
    items: list[dict[str, Any]] = []
    for archive in sorted(root.glob(f"{ARCHIVE_PREFIX}*.tar.gz*"), reverse=True):
        if archive.name.endswith(".manifest.json"):
            continue
        sidecar = root / f"{archive.name}.manifest.json"
        entry: dict[str, Any] = {"file": archive.name, "bytes": archive.stat().st_size}
        if sidecar.exists():
            try:
                manifest = json.loads(sidecar.read_text(encoding="utf-8"))
                entry.update(
                    {
                        "backupId": manifest.get("backupId"),
                        "createdAt": manifest.get("createdAt"),
                        "encrypted": (manifest.get("encryption") or {}).get("algorithm") == "fernet",
                        "attachments": (manifest.get("attachments") or {}).get("archived", 0),
                    }
                )
            except json.JSONDecodeError:
                entry["manifest"] = "unreadable"
        items.append(entry)
    return items
