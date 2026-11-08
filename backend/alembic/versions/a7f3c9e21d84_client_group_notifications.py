"""Client-group Telegram notifications: wide destination allow-list.

``notification_outbox.destination_type`` gains ``CLIENT`` so committed Service
Order events can be queued for the client-facing group. Existing PRIVATE and
ADMIN rows stay valid; the widened CHECK accepts every value the old guard
accepted.

Revision ID: a7f3c9e21d84
Revises: b1c2d3e4f5a6
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a7f3c9e21d84"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE notification_outbox DROP CONSTRAINT IF EXISTS notification_destination")
    op.execute(
        "ALTER TABLE notification_outbox ADD CONSTRAINT notification_destination "
        "CHECK (destination_type IN ('PRIVATE', 'ADMIN', 'CLIENT'))"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # CLIENT rows must not block the rollback to the narrower guard.
    op.execute("DELETE FROM notification_outbox WHERE destination_type = 'CLIENT'")
    op.execute("ALTER TABLE notification_outbox DROP CONSTRAINT IF EXISTS notification_destination")
    op.execute(
        "ALTER TABLE notification_outbox ADD CONSTRAINT notification_destination "
        "CHECK (destination_type IN ('PRIVATE', 'ADMIN'))"
    )
