"""Bulk lookup of creator display names for list payloads.

One query per list keeps creator attribution cheap; a missing user row (hard
deleted) yields no name, and the caller renders an em dash instead of inventing
a creator.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


async def user_display_names(session: AsyncSession, user_ids: Iterable[int | None]) -> dict[int, str]:
    ids = {int(value) for value in user_ids if value}
    if not ids:
        return {}
    rows = (
        await session.execute(select(User.id, User.display_name).where(User.id.in_(ids)))
    ).all()
    return {int(user_id): str(name or "") for user_id, name in rows}


async def creator_names_from_audit(
    session: AsyncSession,
    entity_type: str,
    event_type: str,
    entity_ids: Iterable[int],
) -> dict[int, str]:
    """Map entity id -> actor display name from its creation audit event.

    This is the only creator evidence for tables that do not store a creator
    column. Rows created before auditing existed simply stay unmapped (`—`).
    """
    from app.modules.audit.models import AuditEvent

    ids = {int(value) for value in entity_ids if value}
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(AuditEvent.entity_id, User.display_name, AuditEvent.occurred_at)
            .join(User, User.id == AuditEvent.actor_user_id)
            .where(
                AuditEvent.entity_type == entity_type,
                AuditEvent.event_type == event_type,
                AuditEvent.entity_id.in_(ids),
            )
            .order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
        )
    ).all()
    creators: dict[int, str] = {}
    for entity_id, name, _occurred in rows:
        creators.setdefault(int(entity_id), str(name or ""))
    return creators
