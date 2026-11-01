"""Temporary diagnostic: what does the SALES role actually hold after the catalog change?"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import authorization
from app.core.config import settings
from app.core.database import Base
from app.core.permissions import ROLE_DEFINITIONS, compile_role_permissions
from app.main import app  # noqa: F401 - registers every model module
from tests.seed import ensure_seed_data, seed_demo_data

settings.cache_enabled = False
settings.redis_enabled = False


async def main() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await ensure_seed_data(session)
        await seed_demo_data(session)
        await session.commit()
        await authorization.refresh(session)

        for code in ("SALES", "VIEWER", "OPERATIONS"):
            stored = sorted(await authorization.role_permission_codes(session, code))
            print(f"\n{code} stored ({len(stored)}):", stored[:40])
            print("  attachment.delete stored:", "attachment.delete" in stored)
        compiled = sorted(compile_role_permissions(ROLE_DEFINITIONS["SALES"]["permissions"]))
        print("\nSALES compiled attachment.*:", [c for c in compiled if c.startswith("attachment")])
        from app.modules.auth.models import User

        user = (await session.execute(__import__("sqlalchemy").select(User).where(User.username == "sales"))).scalar_one()
        codes = authorization.effective_codes(user.id)
        print("sales effective attachment.*:", sorted(c for c in codes if c.startswith("attachment")))
        print("sales can attachment.delete:", authorization.can(user.id, "attachment.delete"))
    await engine.dispose()


asyncio.run(main())
