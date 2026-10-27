"""Run against a disposable migrated database via LCS_AUTH_TEST_DATABASE_URL."""
import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import AuthRequired, Conflict
from app.core.security import hash_token
from app.modules.auth import service
from app.modules.auth.models import UsedRefreshToken, User, UserSession
from tests.seed import ensure_seed_data, seed_demo_data

URL = os.environ.get("LCS_AUTH_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="requires explicitly configured disposable PostgreSQL")


async def test_rotation_concurrency_and_migration_preserve_rows():
    engine = create_async_engine(URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await ensure_seed_data(session)
            await seed_demo_data(session)
            await session.commit()
            user = await session.scalar(select(User).where(User.username == "admin"))
            _, token = await service.create_session(session, user, ip=None, user_agent=None)
            original_count = await session.scalar(select(func.count()).select_from(UserSession))
        barrier = asyncio.Barrier(2)

        async def rotate():
            async with factory() as session:
                await barrier.wait()
                try:
                    return await service.rotate_refresh_token(session, token, ip=None, user_agent=None)
                except Conflict as error:
                    return error

        results = await asyncio.gather(rotate(), rotate())
        assert sum(isinstance(r, tuple) for r in results) == 1
        assert sum(isinstance(r, Conflict) and r.code == "REFRESH_CONFLICT" for r in results) == 1
        winner = next(r for r in results if isinstance(r, tuple))
        async with factory() as session:
            used = await session.get(UsedRefreshToken, hash_token(token))
            used.used_at = datetime.now(UTC) - timedelta(seconds=10)
            await session.commit()
        async with factory() as session:
            with pytest.raises(AuthRequired, match="401") as replay:
                await service.rotate_refresh_token(session, token, ip=None, user_agent=None)
            assert replay.value.code == "SESSION_REVOKED"
        async with factory() as session:
            with pytest.raises(AuthRequired) as denied:
                await service.rotate_refresh_token(session, winner[2], ip=None, user_agent=None)
            assert denied.value.code == "SESSION_REVOKED"
        async with engine.connect() as connection:
            for model in (UserSession, UsedRefreshToken):
                actual = await connection.run_sync(lambda conn, table=model.__tablename__: inspect(conn).get_columns(table))
                expected = {column.name: column for column in model.__table__.columns}
                assert {column["name"] for column in actual} == set(expected)
                for column in actual:
                    declared = expected[column["name"]]
                    assert column["nullable"] == declared.nullable
                    assert str(column["type"].compile(dialect=engine.dialect)).upper() == str(declared.type.compile(dialect=engine.dialect)).upper()
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(UserSession)) == original_count
            assert await session.scalar(select(func.count()).select_from(UsedRefreshToken)) >= 1
            counts = dict((await session.execute(text(
                "SELECT table_name, (xpath('/row/c/text()', query_to_xml("
                "'SELECT count(*) AS c FROM public.' || quote_ident(table_name), false, true, '')))[1]::text::bigint "
                "FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' "
                "AND table_name NOT IN ('used_refresh_tokens', 'alembic_version')"
            ))).all())
        env = {**os.environ, "DATABASE_URL": URL}
        root = Path(__file__).resolve().parents[1]
        for arguments in (("downgrade", "12ab34cd56ef"), ("upgrade", "head")):
            result = await asyncio.to_thread(subprocess.run, [sys.executable, "-m", "alembic", *arguments],
                                             cwd=root, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
        async with factory() as session:
            for table, count in counts.items():
                actual = await session.scalar(text(f'SELECT count(*) FROM "{table}"'))
                assert actual == count, table
            assert await session.scalar(text("SELECT count(*) FROM user_sessions WHERE last_activity_at IS NULL")) == 0
    finally:
        await engine.dispose()
