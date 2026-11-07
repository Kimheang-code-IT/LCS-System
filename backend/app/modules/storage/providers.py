"""Storage providers for file attachments.

Two database-configured providers, cloud-only:

* :class:`CloudflareR2Provider` — S3-compatible, built on the existing
  ``S3Storage`` (``region="auto"``, path addressing).
* :class:`GoogleDriveProvider`  — native Drive API (google-api-python-client),
  authenticated backend downloads, no presigned URLs.

All network calls are synchronous (boto3 / googleapiclient); callers wrap them
in ``asyncio.to_thread`` exactly like the backup module does.

There is no local-disk provider and no MinIO: file attachment storage is
Cloudflare R2 or Google Drive, configured in Settings → Storage & Backup.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Protocol

from app.core.config import settings
from app.core.storage import S3Storage

logger = logging.getLogger(__name__)

# Scope notes: ``drive.file`` lets the app see and manage only files it created
# or was granted — the least-privilege scope for both OAuth users on My Drive
# and cloud-identity service accounts added to a Shared Drive as members.
# ``userinfo.email`` only records which account connected.
_GOOGLE_SCOPE_DRIVE = "https://www.googleapis.com/auth/drive.file"
_GOOGLE_SCOPE_EMAIL = "https://www.googleapis.com/auth/userinfo.email"

PROVIDER_TAGS = {"r2", "gdrive"}


class FileProvider(Protocol):
    """Upload/download abstraction for one configured destination.

    ``put`` returns the authoritative provider file id: object keys for
    S3-compatible stores, the Drive ``fileId`` for Google Drive (a caller
    cannot choose Drive ids up front).
    """

    tag: str
    supports_presign: bool

    def put(self, key: str, data: bytes, content_type: str, file_name: str = "") -> str: ...
    def get(self, key: str) -> tuple[bytes, str]: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def copy(self, key: str) -> str: ...
    def size(self, key: str) -> int | None: ...
    def checksum(self, key: str) -> str | None: ...
    def presigned_get(self, key: str, expires: int = 300) -> str | None: ...


class CloudflareR2Provider:
    """R2 via the S3-compatible SDK. Region is always ``auto``."""

    tag = "r2"
    supports_presign = True

    def __init__(self, config: dict[str, Any]) -> None:

        account_id = str(config.get("accountId") or "").strip()
        self._storage = S3Storage(
            bucket=str(config.get("bucket") or "").strip(),
            # Endpoint auto-generates from the account id; the override field
            # still wins for non-default (jurisdiction) endpoints.
            endpoint_url=str(config.get("endpoint") or "").strip()
            or f"https://{account_id}.r2.cloudflarestorage.com",
            access_key=str(config.get("accessKeyId") or "").strip(),
            secret_key=str(config.get("secretAccessKey") or ""),
            region="auto",
            ensure_bucket=False,
        )

    def put(self, key: str, data: bytes, content_type: str, file_name: str = "") -> str:
        self._storage.put(key, data, content_type)
        return key

    def get(self, key: str) -> tuple[bytes, str]:
        return self._storage.get(key)

    def delete(self, key: str) -> None:
        self._storage.delete(key)

    def exists(self, key: str) -> bool:
        return self._storage.exists(key)

    def copy(self, key: str) -> str:
        # Same-bucket copies keep the key; cross-provider copies go through the
        # storage service (download + upload), not provider.copy.
        return key

    def size(self, key: str) -> int | None:
        try:
            head = self._storage._client.head_object(Bucket=self._storage.bucket, Key=key)  # noqa: SLF001
            return int(head.get("ContentLength") or 0)
        except Exception:  # noqa: BLE001
            return None

    def checksum(self, key: str) -> str | None:
        data, _ = self.get(key)
        return self._md5(data)

    def presigned_get(self, key: str, expires: int = 300) -> str | None:
        return self._storage.presigned_get(key, expires)

    def test_connection(self) -> str:
        self._storage.test_connection()
        return f"Connected to bucket {self._storage.bucket}."

    @staticmethod
    def _md5(data: bytes) -> str:
        import hashlib

        # Non-security digest: it must match the R2/S3 ETag and Drive md5Checksum.
        return hashlib.md5(data, usedforsecurity=False).hexdigest()


class GoogleDriveProvider:
    """Native Google Drive API provider.

    Two credential modes from the stored, encrypted config:

    * ``oauth``          — a personal Google account connected through the
      server-side OAuth code exchange (refresh token, auto-refreshed here).
    * ``service_account``— a Google Workspace service account added as a
      member of a Shared Drive. It never owns My Drive storage: root files
      must live in the configured Shared Drive / root folder.
    """

    tag = "gdrive"
    supports_presign = False

    def __init__(self, config: dict[str, Any]) -> None:
        self._client = self._build_client(config)
        self._root_folder = str(config.get("rootFolderId") or "").strip()
        self._shared_drive_id = str(config.get("sharedDriveId") or "").strip()

    def _build_client(self, config: dict[str, Any]):  # noqa: ANN202
        from google.oauth2 import credentials as oauth_credentials
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        auth_type = str(config.get("authType") or "").strip() or "oauth"
        scopes = [_GOOGLE_SCOPE_DRIVE, _GOOGLE_SCOPE_EMAIL]
        if auth_type == "service_account":
            raw = str(config.get("serviceAccountJson") or "").strip()
            if not raw:
                raise ValueError("Google Drive service account JSON is not configured.")
            info = json.loads(raw)
            info.setdefault("scopes", scopes)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=scopes
            )
        else:
            from app.core.crypto import decrypt_secret

            refresh_token = str(config.get("_refreshToken") or "")
            if refresh_token:
                refresh_token = decrypt_secret(refresh_token)
            if not refresh_token:
                raise ValueError("Google Drive is not connected: no OAuth grant found.")
            credentials = oauth_credentials.Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=str(config.get("clientId") or "").strip(),
                client_secret=str(config.get("_clientSecret") or "").strip(),
                scopes=scopes,
            )
            # googleapiclient refreshes automatically on the first authorized call.
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    # --- file operations -----------------------------------------------------

    def put(self, key: str, data: bytes, content_type: str, file_name: str = "") -> str:
        import io

        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=content_type or "application/octet-stream", resumable=False)
        body: dict[str, Any] = {"name": key}
        parents = [self._root_folder or self._shared_drive_id] if (self._root_folder or self._shared_drive_id) else []
        if parents:
            body["parents"] = parents
        file_id = (
            self._client.files()
            .create(body=body, media_body=media, fields="id", supportsAllDrives=True)
            .execute()
        )
        return str(file_id)

    def get(self, key: str) -> tuple[bytes, str]:
        import io

        from googleapiclient.http import MediaIoBaseDownload

        meta = self._metadata(key)
        mime = str(meta.get("mimeType") or "application/octet-stream")
        request = self._client.files().get_media(fileId=key, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue(), mime

    def delete(self, key: str) -> None:
        self._client.files().delete(fileId=key, supportsAllDrives=True).execute()

    def exists(self, key: str) -> bool:
        try:
            self._metadata(key)
            return True
        except Exception:  # noqa: BLE001 - any Drive error means "not readable"
            return False

    def copy(self, key: str) -> str:
        body: dict[str, Any] = {"name": f"copy-{key}"}
        parents = [self._root_folder or self._shared_drive_id] if (self._root_folder or self._shared_drive_id) else []
        if parents:
            body["parents"] = parents
        copied = (
            self._client.files()
            .copy(fileId=key, body=body, fields="id", supportsAllDrives=True)
            .execute()
        )
        return str(copied)

    def _metadata(self, key: str) -> dict[str, Any]:
        return (
            self._client.files()
            .get(fileId=key, fields="id,size,md5Checksum,mimeType,name", supportsAllDrives=True)
            .execute()
        )

    def size(self, key: str) -> int | None:
        try:
            return int(self._metadata(key).get("size") or 0)
        except Exception:  # noqa: BLE001
            return None

    def checksum(self, key: str) -> str | None:
        try:
            md5 = self._metadata(key).get("md5Checksum")
            return str(md5) if md5 else None
        except Exception:  # noqa: BLE001
            return None

    def presigned_get(self, key: str, expires: int = 300) -> str | None:
        return None  # Drive files are always downloaded through the backend.

    # --- connection test -----------------------------------------------------

    def test_connection(self) -> str:
        """Verify the destination is reachable *and writable*.

        OAuth mode checks that the chosen root folder accepts children; service
        account mode additionally requires explicit Shared Drive membership
        (``drives.get`` fails when the account is not a member).
        """
        from googleapiclient.errors import HttpError

        try:
            info = self._client.about().get(fields="user").execute()
            who = str((info.get("user") or {}).get("emailAddress") or "unknown account")
            if self._root_folder:
                meta = self._client.files().get(fileId=self._root_folder, fields="capabilities", supportsAllDrives=True).execute()
                if not (meta.get("capabilities") or {}).get("canAddChildren"):
                    raise ValueError("The root folder is not writable by this account.")
            if self._shared_drive_id:  # Workspace mode: prove membership.
                self._client.drives().get(driveId=self._shared_drive_id).execute()
                meta = self._client.drives().get(driveId=self._shared_drive_id).execute()
                if not meta:
                    raise ValueError("Shared Drive is not accessible.")
            return f"Connected to Google Drive as {who}."
        except HttpError as exc:
            detail = getattr(exc, "error_details", None) or exc.reason  # no credential material
            raise ValueError(f"Google Drive connection failed: {detail}") from exc

    # --- OAuth helpers (server-side only) ------------------------------------

    @staticmethod
    def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
        from urllib.parse import urlencode

        params = urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": f"{_GOOGLE_SCOPE_DRIVE} {_GOOGLE_SCOPE_EMAIL}",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        })
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    @staticmethod
    async def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                # Error text is a standard OAuth error code, never credentials.
                raise ValueError(f"Google authorization failed ({token_response.json().get('error', 'unknown')}).")
            tokens = token_response.json()
            profile = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            email = profile.json().get("email") if profile.status_code == 200 else ""
        return {
            "refreshToken": tokens.get("refresh_token", ""),
            "accessToken": tokens.get("access_token", ""),
            "connectedEmail": email or "",
        }


# --- resolution ---------------------------------------------------------------

def build_provider(tag: str, config: dict[str, Any]) -> FileProvider:
    """Instantiate one provider. Secrets must already be merged into ``config``."""
    if tag == "r2":
        return CloudflareR2Provider(config)
    if tag == "gdrive":
        return GoogleDriveProvider(config)
    raise ValueError(f"Unknown storage provider: {tag}")


def new_object_key(file_name: str) -> str:
    """S3-compatible object key (unchanged legacy format)."""
    return f"{uuid.uuid4().hex}-{file_name}"


def presigned_url(provider: FileProvider, key: str) -> str | None:
    if not provider.supports_presign or not settings.presigned_url_expire_seconds:
        return None
    return provider.presigned_get(key, settings.presigned_url_expire_seconds)
