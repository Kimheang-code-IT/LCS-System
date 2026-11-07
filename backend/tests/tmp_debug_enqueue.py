import pytest

pytestmark = pytest.mark.asyncio

from tests.conftest import login, seed_service_order

TOKEN = "123456:abcdefghijklmnopqrstuvwxyz_123456"
CONFIG = "/api/v1/settings/app-config"
CLIENT_CHAT = -1001234567890


async def test_deliver_debug(client, session_factory, telegram_mock):
    headers = await login(client)
    result = await client.patch(CONFIG, headers=headers, json={"telegram": {
        "enabled": True, "botToken": TOKEN, "clientEnabled": True, "clientGroupId": str(CLIENT_CHAT),
    }})
    assert result.status_code == 200, result.text
    tested = await client.post(f"{CONFIG}/telegram/test-connection", headers=headers)
    assert tested.status_code == 200, tested.text
    order = await seed_service_order(client, headers)
    from sqlalchemy import select
    from app.modules.telegram import outbox
    from app.modules.telegram.models import NotificationOutbox
    async with session_factory() as session:
        claims = await outbox.claim(session)
    print("CLAIMS:", claims)
    async with session_factory() as session:
        from app.modules.telegram import service
        value = await service.config(session)
        print("CFG:", {k: value.get(k) for k in ("clientEnabled", "clientGroupId", "clientBotId", "botId", "clientEvents")})
    for row_id, token in claims:
        await outbox.deliver(row_id, token, session_factory=session_factory)
    async with session_factory() as session:
        rows = (await session.execute(select(NotificationOutbox))).scalars().all()
        print("AFTER:", [(r.status, r.last_error) for r in rows])
    print("SENDS:", [c for c in telegram_mock if c[0] == "sendMessage"])
