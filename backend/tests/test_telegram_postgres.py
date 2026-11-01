"""Concurrency checks against an explicitly supplied disposable migrated PostgreSQL."""

import asyncio
import os
import secrets
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.context import RequestContext
from app.core.database import utcnow
from app.core.exceptions import Conflict
from app.core.security import hash_token
from app.modules.auth import service as auth
from app.modules.auth.models import PasswordResetToken, User
from app.modules.telegram import service as telegram
from app.modules.telegram.models import (
    NotificationIncident,
    NotificationOutbox,
    TelegramLink,
    TelegramPairing,
    TelegramUpdate,
)
from app.modules.telegram.outbox import claim
from tests.seed import ensure_seed_data, seed_demo_data

URL = os.environ.get("LCS_TELEGRAM_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="requires explicitly configured disposable PostgreSQL")


async def test_atomic_reset_and_disjoint_claims_and_schema():
    engine = create_async_engine(URL)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            await ensure_seed_data(session)
            await seed_demo_data(session)
            await session.commit()
            user = await session.scalar(select(User).where(User.username == "admin"))
            await telegram.save_internal(session, {"enabled": True, "botId": 99, "rules": {"recovery": {"enabled": True}}})
            link = await session.get(TelegramLink, user.id)
            if link is None:
                session.add(TelegramLink(user_id=user.id, telegram_user_id=100987, bot_id=99, chat_id=100987, display_name="Disposable PG test"))
            token = secrets.token_urlsafe(32)
            session.add(PasswordResetToken(user_id=user.id, email=user.email, code_hash=hash_token(token), expires_at=utcnow() + timedelta(minutes=15)))
            await session.commit()
        barrier = asyncio.Barrier(2)

        async def reset():
            async with factory() as session:
                await barrier.wait()
                try:
                    await auth.reset_password(session, "", token, "Changed-Str0ng-PG!")
                    return "reset"
                except Conflict:
                    return "rejected"

        results = await asyncio.gather(reset(), reset())
        assert sorted(results) == ["rejected", "reset"]
        async with factory() as session:
            # A successful reset enqueues its own PRIVATE outbox row; clear the
            # queue so the claim phase sees exactly the 8 rows it seeds.
            await session.execute(delete(NotificationOutbox))
            await session.commit()
        async with factory() as session:
            for i in range(8):
                session.add(NotificationOutbox(event_type="PG_TEST", category="system", severity="INFO", destination_type="ADMIN", destination_reference=-1, payload={"text": "Test"}, expires_at=utcnow() + timedelta(hours=1), deduplication_key=f"pg:{secrets.token_hex(16)}:{i}"))
            await session.commit()
        barrier = asyncio.Barrier(2)

        async def claims():
            async with factory() as session:
                await barrier.wait()
                return await claim(session)

        left, right = await asyncio.gather(claims(), claims())
        assert len(left) + len(right) == 8
        assert {row[0] for row in left}.isdisjoint(row[0] for row in right)
        async with factory() as session:
            await telegram.save_internal(session, {"enabled": True, "botId": 99, "botUsername": "lcs_test_bot"})
            await session.commit()
        context = RequestContext(user_id=user.id, username="admin", email=user.email, display_name="Test", permissions=set(), is_platform_admin=True, request_id="pg-test")
        barrier = asyncio.Barrier(2)

        async def pair():
            async with factory() as session:
                await barrier.wait()
                return await telegram.create_pairing(session, context, "GROUP")

        # Supply verified state, as getMe has its own transport tests.
        async with factory() as session:
            value = await telegram.config(session)
            value["connectionStatus"] = "connected"
            await telegram.save_internal(session, value)
            await session.commit()
        pairs = await asyncio.gather(pair(), pair())
        async with factory() as session:
            challenges = (await session.execute(select(TelegramPairing).where(TelegramPairing.user_id == user.id, TelegramPairing.kind == "GROUP"))).scalars().all()
            assert len(challenges) == 1
            assert sum(telegram.digest(pair["challenge"]) == challenges[0].token_hash for pair in pairs) == 1
        async with engine.connect() as conn:
            for model in (TelegramLink, TelegramPairing, TelegramUpdate, NotificationOutbox, NotificationIncident):
                columns = await conn.run_sync(lambda sync, name=model.__tablename__: inspect(sync).get_columns(name))
                declared = {col.name: col for col in model.__table__.columns}
                assert {col["name"] for col in columns} == set(declared)
                for col in columns:
                    assert col["nullable"] == declared[col["name"]].nullable
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(User)) >= 1
    finally:
        await engine.dispose()
