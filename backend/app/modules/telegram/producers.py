"""Service Order → client-group notification producers.

Called from the Service Order service right before its commit: the outbox row
commits with the business transaction (transactional outbox), so a Telegram
outage can never fail or delay an order, and a replayed request cannot queue a
duplicate. Every failure here is swallowed and logged — notifications are
best-effort metadata, not business data.
"""

from __future__ import annotations

import logging
from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _date_text(value) -> str:
    stamp = value
    if stamp is None:
        return "—"
    if hasattr(stamp, "astimezone"):
        try:
            stamp = stamp.astimezone(UTC)
        except (TypeError, ValueError):
            pass
    return str(stamp)[:10] if hasattr(stamp, "year") else str(stamp)


async def service_order_notification(
    session: AsyncSession,
    order,
    event: str,
) -> None:
    """Queue one Service Order notification for the client group, if enabled."""
    try:
        from app.modules.telegram import outbox

        await outbox.enqueue_client(
            session,
            event,
            order_no=str(order.service_order_no),
            status=str(order.status or "").title(),
            occurred=_date_text(getattr(order, "date", None)),
        )
    except Exception:  # noqa: BLE001 - Telegram metadata must never break an order.
        logger.warning("Queuing the client-group notification failed; the Service Order itself is unaffected.", exc_info=True)
