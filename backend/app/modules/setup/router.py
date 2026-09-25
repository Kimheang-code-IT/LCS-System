from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.setup import service

router = APIRouter()


@router.get("/setup/status")
async def setup_status(session: AsyncSession = Depends(get_session)) -> dict:
    return {"data": await service.status(session)}


@router.post("/setup/initialize", status_code=status.HTTP_201_CREATED)
async def setup_initialize(
    payload: dict = Body(default={}),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.initialize(session, payload)}
