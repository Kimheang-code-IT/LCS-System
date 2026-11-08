"""Mark MinIO-era and local-disk file attachments as removed.

File/object storage is cloud-only (Cloudflare R2 / Google Drive) and the MinIO
objects plus the Docker upload volume were deleted (authorized, verified
MinIO-only / local-object-store data). Attachment rows whose objects lived on
those stores — ``storage_provider`` 'minio', the env-S3 value 's3' (which in
this project had always pointed at the MinIO endpoint), or 'local' (the Docker
upload volume) — can no longer be read.

* ``attachments.is_deleted = true`` for those rows (soft delete keeps the
  historical row and its audit trail).
* ``attachment_links`` rows for those attachments are removed, so link tables
  only reference files that still exist somewhere.
* Rows on r2/gdrive are untouched, and so are all business records.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a0b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REMOVED_STORAGE_PROVIDERS = "IN ('minio', 's3', 'local')"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM attachment_links WHERE attachment_id IN "
            f"(SELECT id FROM attachments WHERE storage_provider {_REMOVED_STORAGE_PROVIDERS})"
        )
    )
    result = conn.execute(
        sa.text(
            "UPDATE attachments SET is_deleted = TRUE "
            f"WHERE storage_provider {_REMOVED_STORAGE_PROVIDERS} AND is_deleted = FALSE"
        )
    )
    removed = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else 0
    print(f"Soft-deleted {removed} MinIO-era attachment(s) and removed their links.")


def downgrade() -> None:
    # Not reversible: the MinIO objects were deleted, so re-activating the flag
    # would advertise files that no longer exist anywhere.
    pass
