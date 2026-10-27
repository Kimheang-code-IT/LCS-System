from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_session
from app.main import app
from tests.seed import DEFAULT_PASSWORD, ensure_seed_data, seed_demo_data

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def disable_cache_by_default(monkeypatch):
    """Read-through caching is disabled for every test.

    The in-memory test database is recreated per test while Redis (when running
    locally) is not, so caches keyed only by request parameters could leak data
    across tests. Cache-specific tests re-enable it with an injected fake
    Redis client via the ``fake_redis`` fixture.
    """
    monkeypatch.setattr(settings, "cache_enabled", False)
    # Do not probe a real Redis server from every test: a missing server costs
    # two connect timeouts per write, which dominated the suite runtime.
    monkeypatch.setattr(settings, "redis_enabled", False)
    return None


@pytest.fixture(autouse=True)
def isolate_process_state():
    """Drop process-global state a previous test could have left behind.

    ``app.core.redis`` caches one client in a module global and
    ``app.core.rate_limit`` keeps an in-process fallback window. Either one
    surviving into the next test made query-budget assertions depend on test
    order (the three intermittent failures in the Redis integration file).
    """
    from app.core import rate_limit as rate_limit_module
    from app.core import redis as redis_core

    redis_core._client = None
    rate_limit_module._fallback.clear()
    yield
    redis_core._client = None
    rate_limit_module._fallback.clear()


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded(session_factory):
    async with session_factory() as session:
        await ensure_seed_data(session)
        await seed_demo_data(session)
        await session.commit()
    return True


@pytest_asyncio.fixture
async def client(session_factory, seeded):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def login(client: AsyncClient, username: str = "admin", password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def telegram_mock(monkeypatch):
    from app.modules.telegram import service

    TOKEN = "123456:abcdefghijklmnopqrstuvwxyz_123456"
    calls = []

    class FakeTelegram:
        def __init__(self, token):
            assert token == TOKEN

        async def get_me(self):
            return {"id": 99, "is_bot": True, "username": "lcs_test_bot", "first_name": "LCS"}

        async def call(self, method, payload=None, **kwargs):
            calls.append((method, payload))
            if method == "getChat":
                return {"id": payload["chat_id"], "type": "supergroup", "title": "Private admins"}
            if method == "getChatMember":
                return {"status": "administrator"}
            if method == "getWebhookInfo":
                return {"url": "https://lcs.example/api/v1/integrations/telegram/webhook"}
            return True

        async def send_message(self, chat_id, text):
            calls.append(("sendMessage", {"chat_id": chat_id, "text": text}))
            return {"message_id": 1}

    monkeypatch.setattr(service, "TelegramClient", FakeTelegram)
    return calls

