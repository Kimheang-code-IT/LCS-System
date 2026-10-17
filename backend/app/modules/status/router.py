"""Shared record-status endpoints.

``GET /{collection}/status-policy`` tells a screen which status changes are
legal from each status for a collection — already filtered to the ones the
caller may perform — so the row menu can only ever offer valid actions.

``POST /{collection}/{item_id}/status`` applies one plain status transition
(activate, deactivate, mark, reopen). Workflow transitions (posting, reversal,
issuing, closing, sending a quotation) keep their own endpoints; this one
refuses to bypass them.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context
from app.modules.status import service

router = APIRouter()


@router.get("/{collection}/status-policy")
async def read_status_policy(
    collection: str,
    context: RequestContext = Depends(get_current_context),
) -> dict:
    policy = service.policy_for(collection)
    return {"data": service.serialize_policy(collection, policy, context)}


@router.post("/{collection}/{item_id}/status")
async def change_record_status(
    collection: str,
    item_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {
        "data": await service.change_status(
            session,
            context,
            collection,
            item_id,
            str(payload.get("status") or ""),
            payload.get("reason"),
        )
    }
