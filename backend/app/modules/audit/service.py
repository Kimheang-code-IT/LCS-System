from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.pagination import PageParams, count_query, paged
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import User


async def write_audit(
    session: AsyncSession,
    context: RequestContext | None,
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    action: str,
    result: str = "SUCCESS",
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=context.user_id if context else None,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        result=result,
        reason=reason,
        request_id=context.request_id if context else None,
        ip_address=context.ip_address if context else None,
        user_agent=context.user_agent if context else None,
        before_json=before,
        after_json=after,
        metadata_json=metadata,
    )
    session.add(event)
    await session.flush()
    return event


def serialize(event: AuditEvent, user_name: str | None = None) -> dict[str, Any]:
    return {
        "id": event.id,
        "occurredAt": event.occurred_at.isoformat() if event.occurred_at else None,
        "action": event.action,
        "result": event.result,
        "user": user_name or (str(event.actor_user_id) if event.actor_user_id is not None else ""),
        "ipAddress": event.ip_address,
        "entityId": event.entity_id,
    }


async def list_events(session: AsyncSession, context: RequestContext, page: PageParams, entity_type: str | None = None) -> dict:
    stmt = (
        select(AuditEvent, User.display_name)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
    )
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if page.status:
        stmt = stmt.where(AuditEvent.action == page.status)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).all()
    return paged([serialize(event, user_name) for event, user_name in rows], page, total)
