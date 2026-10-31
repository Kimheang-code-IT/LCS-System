"""Temporary diagnostic: which queries does a cached /auth/me still run?"""

from __future__ import annotations

import asyncio

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import cache
from app.core import authorization
from app.core.config import settings
from app.core.database import Base, get_session
from app.main import app
from tests.seed import ensure_seed_data, seed_demo_data

settings.cache_enabled = False
settings.redis_enabled = False


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])


async def main() -> None:
    fake = FakeRedis()
    cache.install(fake) if hasattr(cache, "install") else None
    settings.cache_enabled = True
    settings.redis_enabled = True
    cache._client = fake  # type: ignore[attr-defined]

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

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        login = await client.post("/api/v1/auth/login", json={"username": "sales", "password": "Passw0rd!"})
        headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
        await client.get("/api/v1/auth/me", headers=headers)  # warm
        statements: list[str] = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            statements.append(" ".join(statement.split())[:150])

        event.listen(engine.sync_engine, "before_cursor_execute", listener)
        response = await client.get("/api/v1/auth/me", headers=headers)
        event.remove(engine.sync_engine, "before_cursor_execute", listener)
        print("status", response.status_code, "queries", len(statements))
        for statement in statements:
            print("  -", statement)

    app.dependency_overrides.clear()
    await engine.dispose()


asyncio.run(main())
