"""Object storage abstraction for Cloudflare R2.

The S3-compatible client below is the building block the database-configured
storage module (``app.modules.storage``) uses for Cloudflare R2. There is no
local-disk provider, no MinIO, and no environment-configured object store:
file attachment storage lives in Settings → Storage & Backup only.
"""

from __future__ import annotations

import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

logger = logging.getLogger(__name__)


class S3Storage:
    provider = "r2"
    supports_presign = True

    def __init__(
        self,
        *,
        bucket: str = "",
        endpoint_url: str = "",
        public_endpoint_url: str = "",
        access_key: str = "",
        secret_key: str = "",
        region: str = "auto",
        ensure_bucket: bool = True,
    ) -> None:
        """Build an S3-compatible storage client.

        Callers (the storage module's Cloudflare R2 provider) always pass
        explicit database-configured values; there is no env fallback.
        """
        self.bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        endpoint = endpoint_url
        public_endpoint = public_endpoint_url or endpoint
        self._client = self._build_client(endpoint)
        self._presign_client = self._build_client(public_endpoint)
        if ensure_bucket:
            self._ensure_bucket()

    def _build_client(self, endpoint_url: str | None):
        # Trust an explicit scheme in the URL: the internal endpoint may be
        # http:// while the browser-facing one is https://.
        use_ssl = bool(endpoint_url and endpoint_url.lower().startswith("https://"))
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            use_ssl=use_ssl,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except (ClientError, EndpointConnectionError):
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except Exception as exc:  # noqa: BLE001 - storage may not be ready yet
                logger.warning("Object-storage bucket %s could not be created: %s", self.bucket, exc)

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

    def test_connection(self) -> None:
        """Verify bucket access without creating, deleting, or changing objects."""
        self._client.head_bucket(Bucket=self.bucket)
        self._client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)

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

