"""RBAC assignment integrity and safe legacy mapping.

Revision ID: a2b3c4d5e6f7
Revises: a7b8c9d0e1f2
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Normalize every current assignment to the non-expiring form covered by
    # the partial unique index. This closes the legacy loophole where several
    # future-dated expiry rows could all be considered active by the service.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id
                           ORDER BY (expires_at IS NULL) DESC, id
                       ) AS rn
                FROM user_role_assignments
                WHERE expires_at IS NULL OR expires_at > now()
            )
            UPDATE user_role_assignments AS ura
            SET expires_at = CASE WHEN ranked.rn = 1 THEN NULL ELSE now() END
            FROM ranked
            WHERE ura.id = ranked.id
            """
        )
    )

    # Existing active users with no assignment are mapped explicitly to an
    # active zero-permission role. This preserves accounts without silently
    # granting administrator access.
    op.execute(
        sa.text(
            """
            INSERT INTO roles (code, name, description, is_system_role, status)
            SELECT 'MIGRATED_NO_ACCESS', 'Migrated - No Access',
                   'Safe migration role for legacy users that had no active role.',
                   false, 'ACTIVE'
            WHERE EXISTS (
                SELECT 1
                FROM users AS u
                WHERE upper(u.status) = 'ACTIVE'
                  AND NOT EXISTS (
                      SELECT 1 FROM user_role_assignments AS ura
                      WHERE ura.user_id = u.id AND ura.expires_at IS NULL
                  )
            )
              AND NOT EXISTS (SELECT 1 FROM roles WHERE code = 'MIGRATED_NO_ACCESS')
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO user_role_assignments (user_id, role_id, assigned_by_user_id, starts_at, expires_at)
            SELECT u.id, r.id, NULL, now(), NULL
            FROM users AS u
            CROSS JOIN roles AS r
            WHERE r.code = 'MIGRATED_NO_ACCESS'
              AND upper(u.status) = 'ACTIVE'
              AND NOT EXISTS (
                  SELECT 1 FROM user_role_assignments AS ura
                  WHERE ura.user_id = u.id AND ura.expires_at IS NULL
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM user_role_assignments
            WHERE role_id = (SELECT id FROM roles WHERE code = 'MIGRATED_NO_ACCESS')
            """
        )
    )
    op.execute(sa.text("DELETE FROM roles WHERE code = 'MIGRATED_NO_ACCESS'"))
