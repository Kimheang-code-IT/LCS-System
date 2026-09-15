from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.pagination import PageParams, count_query, paged
from app.modules.audit.models import AuditEvent


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
        organization_id=context.organization_id if context else None,
        branch_id=context.branch_id if context else None,
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


def serialize(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "occurredAt": event.occurred_at.isoformat() if event.occurred_at else None,
        "user": event.actor_user_id,
        "userId": event.actor_user_id,
        "action": event.action,
        "eventType": event.event_type,
        "entityType": event.entity_type,
        "entityId": event.entity_id,
        "recordNo": str(event.entity_id),
        "module": event.entity_type,
        "result": event.result,
        "reason": event.reason,
        "remark": event.reason,
        "before": event.before_json,
        "after": event.after_json,
    }


async def list_events(session: AsyncSession, context: RequestContext, page: PageParams, entity_type: str | None = None) -> dict:
    stmt = select(AuditEvent).where(AuditEvent.organization_id == context.organization_id)
    if not context.can_select_all_branches and context.branch_id is not None:
        stmt = stmt.where(or_(AuditEvent.branch_id == context.branch_id, AuditEvent.branch_id.is_(None)))
    if context.branch_id is not None:
        stmt = stmt.where(or_(AuditEvent.branch_id == context.branch_id, AuditEvent.branch_id.is_(None)))
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if page.status:
        stmt = stmt.where(AuditEvent.action == page.status)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(page.page_size).offset(page.offset))
    ).scalars().all()
    return paged([serialize(row) for row in rows], page, total)
