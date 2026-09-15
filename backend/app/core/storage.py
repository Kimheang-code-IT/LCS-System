"""Object storage abstraction.

Supports local filesystem storage (development default) and any S3-compatible
object store such as MinIO. The backend talks to the internal endpoint
(``S3_ENDPOINT_URL``) and signs browser-facing URLs with the public endpoint
(``S3_PUBLIC_ENDPOINT_URL``) so uploads/downloads work from outside Docker.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings


class Storage(Protocol):
    provider: str
    supports_presign: bool

    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> tuple[bytes, str]: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def presigned_put(self, key: str, content_type: str, expires: int = 3600) -> str | None: ...
    def presigned_get(self, key: str, expires: int = 3600) -> str | None: ...


class LocalStorage:
    provider = "local"
    supports_presign = False

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        safe = key.lstrip("/").replace("..", "_")
        return self.root / safe

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> tuple[bytes, str]:
        return self._path(key).read_bytes(), "application/octet-stream"

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def presigned_put(self, key: str, content_type: str, expires: int = 3600) -> str | None:
        return None

    def presigned_get(self, key: str, expires: int = 3600) -> str | None:
        return None


class S3Storage:
    provider = "s3"
    supports_presign = True

    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self._client = self._build_client(settings.s3_endpoint_url)
        self._presign_client = self._build_client(settings.s3_public_endpoint_url or settings.s3_endpoint_url)
        self._ensure_bucket()

    @staticmethod
    def _build_client(endpoint_url: str | None):
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except (ClientError, EndpointConnectionError):
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except Exception:  # noqa: BLE001 - storage may not be ready yet
                pass

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type or "application/octet-stream")

    def get(self, key: str) -> tuple[bytes, str]:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read(), response.get("ContentType", "application/octet-stream")

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def presigned_put(self, key: str, content_type: str, expires: int = 3600) -> str | None:
        try:
            return self._presign_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type or "application/octet-stream"},
                ExpiresIn=expires,
            )
        except Exception:  # noqa: BLE001
            return None

    def presigned_get(self, key: str, expires: int = 3600) -> str | None:
        try:
            return self._presign_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )
        except Exception:  # noqa: BLE001
            return None


@lru_cache
def get_storage() -> Storage:
    if settings.storage_provider.lower() in {"s3", "minio"}:
        return S3Storage()
    return LocalStorage(settings.storage_local_path)


def guess_content_type(file_name: str, provided: str | None = None) -> str:
    if provided:
        return provided
    extension = os.path.splitext(file_name)[1].lower().lstrip(".")
    return {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "txt": "text/plain",
        "csv": "text/csv",
        "json": "application/json",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(extension, "application/octet-stream")
