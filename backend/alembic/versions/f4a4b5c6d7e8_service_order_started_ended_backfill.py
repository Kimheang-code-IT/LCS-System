"""Backfill service_orders.started_at/ended_at views over reliable history.

Started reuses ``created_at`` (already set once at creation, never edited) and
Ended reuses ``finished_at`` (written by the Finish action since
``f3a4b5c6d7e8``). Historical FINISHED orders have no stored finish stamp, so
one is backfilled **only** when a reliable SUCCESS ``SERVICE_ORDER_FINISHED``
audit event exists for the order; nothing is invented. Idempotent re-runs.

Revision ID: f4a4b5c6d7e8
Revises: f3a4b5c6d7e8
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f4a4b5c6d7e8"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE service_orders
        SET finished_at = event.occurred_at
        FROM (
            SELECT DISTINCT ON (entity_id) entity_id, occurred_at
            FROM audit_events
            WHERE entity_type = 'service_order'
              AND event_type = 'SERVICE_ORDER_FINISHED'
              AND result = 'SUCCESS'
              AND after_json->>'status' = 'FINISHED'
            ORDER BY entity_id, occurred_at DESC
        ) AS event
        WHERE service_orders.id = event.entity_id
          AND service_orders.status = 'FINISHED'
          AND service_orders.finished_at IS NULL
        """
    )


def downgrade() -> None:
    # The backfilled stamps came from audit history; dropping the columns
    # themselves is owned by f3a4b5c6d7e8's downgrade. Reverting the backfill
    # would only erase derived data, so this is a deliberate no-op.
    pass