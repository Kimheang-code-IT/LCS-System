"""Client Group (Service Order notifications) and Admin Group Telegram settings.

Pins: dynamic UI-driven configuration persisted in app settings, secrets never
returned, blank token preserves the stored one, independent testing per group,
transactional Service Order notifications that can never block a booking, and
retry/idempotency deduplication.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.modules.telegram import outbox, service
from app.modules.telegram.models import NotificationOutbox
from tests.conftest import login, seed_service_order

pytestmark = pytest.mark.asyncio

TOKEN = "123456:abcdefghijklmnopqrstuvwxyz_123456"
CONFIG = "/api/v1/settings/app-config"
CLIENT_CHAT = -1001234567890


async def _configure(client, headers, session_factory, **telegram_extra) -> None:
    result = await client.patch(CONFIG, headers=headers, json={"telegram": {"enabled": True, "botToken": TOKEN, **telegram_extra}})
    assert result.status_code == 200, result.text
    await client.post(f"{CONFIG}/telegram/test-connection", headers=headers)


async def _claim_and_deliver(session_factory, client=None) -> int:
    """Run one outbox tick: claim rows and deliver through the (mocked) bot."""
    async with session_factory() as session:
        claims = await outbox.claim(session)
    sent = 0
    for row_id, token in claims:
        await outbox.deliver(row_id, token, session_factory=session_factory)
        sent += 1
    return sent


async def _client_rows(session_factory) -> list[NotificationOutbox]:
    async with session_factory() as session:
        return list((await session.execute(
            select(NotificationOutbox).where(NotificationOutbox.destination_type == "CLIENT").order_by(NotificationOutbox.id)
        )).scalars().all())


async def test_client_config_persists_blank_token_preserves_and_redacts(client, session_factory):
    headers = await login(client)
    patch = await client.patch(CONFIG, headers=headers, json={"telegram": {
        "clientEnabled": True,
        "clientGroupId": str(CLIENT_CHAT),
        "clientEvents": {"SERVICE_ORDER_UPDATED": False},
        "clientBotToken": TOKEN,
        "clientConnectionStatus": "forged",
        "clientBotId": 7,
    }})
    assert patch.status_code == 200, patch.text
    value = patch.json()["data"]["telegram"]
    assert value["clientBotToken"] == "" and value["clientBotTokenConfigured"] is True
    assert value["clientConnectionStatus"] != "forged" and not value.get("clientBotId")
    assert value["clientGroupId"] == str(CLIENT_CHAT)

    # Blank token keeps the stored credential; unknown events are refused.
    keep = await client.patch(CONFIG, headers=headers, json={"telegram": {"clientBotToken": ""}})
    assert keep.status_code == 200
    assert keep.json()["data"]["telegram"]["clientBotTokenConfigured"] is True
    async with session_factory() as session:
        stored = await service.config(session)
        assert service.decrypt_secret(stored["clientBotToken"]) == TOKEN
        assert stored["clientEvents"]["SERVICE_ORDER_UPDATED"] is False
        assert stored["clientEvents"]["SERVICE_ORDER_CREATED"] is True
    bad = await client.patch(CONFIG, headers=headers, json={"telegram": {"clientEvents": {"SERVICE_ORDER_BOGUS": True}}})
    assert bad.status_code == 422
    bad_id = await client.patch(CONFIG, headers=headers, json={"telegram": {"clientGroupId": "not-a-chat"}})
    assert bad_id.status_code == 422
    assert "telegram.clientGroupId" in bad_id.json()["field_errors"]


async def test_client_connection_and_test_message_target_the_client_group_only(client, session_factory, telegram_mock):
    headers = await login(client)
    await _configure(client, headers, session_factory, clientEnabled=True, clientGroupId=str(CLIENT_CHAT))
    tested = await client.post(f"{CONFIG}/telegram/client/test-connection", headers=headers)
    assert tested.status_code == 200, tested.text
    assert tested.json()["data"]["status"] == "connected"

    sends = [c for c in telegram_mock if c[0] == "sendMessage"]
    assert not sends
    result = await client.post(f"{CONFIG}/telegram/client/send-test", headers=headers)
    assert result.status_code == 200, result.text
    sends = [c for c in telegram_mock if c[0] == "sendMessage"]
    assert len(sends) == 1 and sends[0][1]["chat_id"] == CLIENT_CHAT


async def test_service_order_created_queues_and_delivers_to_client_group(client, session_factory, telegram_mock):
    headers = await login(client)
    await _configure(client, headers, session_factory, clientEnabled=True, clientGroupId=str(CLIENT_CHAT))
    order = await seed_service_order(client, headers)
    rows = await _client_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].event_type == "SERVICE_ORDER_CREATED"
    assert rows[0].payload["orderNo"] == order["serviceOrderNo"]
    assert "📦 Service Order Created" in rows[0].payload["text"]
    assert "botToken" not in rows[0].payload and "token" not in str(rows[0].payload).lower()

    assert await _claim_and_deliver(session_factory) == 1
    sent = [c for c in telegram_mock if c[0] == "sendMessage"]
    assert sent and sent[0][1]["chat_id"] == CLIENT_CHAT
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, rows[0].id)
        assert row.status == "SENT"


async def test_finish_and_update_events_suppress_retries_and_respect_toggles(client, session_factory, telegram_mock):
    headers = await login(client)
    await _configure(client, headers, session_factory, clientEnabled=True, clientGroupId=str(CLIENT_CHAT))
    order = await seed_service_order(client, headers)
    identifier = order["id"]

    # A retried update within the cooldown window queues at most one notification.
    first = await client.put(f"/api/v1/service-orders/{identifier}", headers=headers, json={"description": "first"})
    assert first.status_code == 200, first.text
    duplicate = await client.put(f"/api/v1/service-orders/{identifier}", headers=headers, json={"description": "second"})
    assert duplicate.status_code == 200, duplicate.text
    rows = await _client_rows(session_factory)
    assert [row.event_type for row in rows].count("SERVICE_ORDER_UPDATED") == 1

    # Disabling the "updated" event stops future updates immediately.
    await client.patch(CONFIG, headers=headers, json={"telegram": {"clientEvents": {"SERVICE_ORDER_UPDATED": False}}})
    await client.put(f"/api/v1/service-orders/{identifier}", headers=headers, json={"description": "third"})
    rows = await _client_rows(session_factory)
    assert [row.event_type for row in rows].count("SERVICE_ORDER_UPDATED") == 1

    finished = await client.post(f"/api/v1/service-orders/{identifier}/finish", headers=headers)
    assert finished.status_code == 200, finished.text
    # Idempotent replay of the same finish: no second notification.
    replay = await client.post(f"/api/v1/service-orders/{identifier}/finish", headers=headers)
    assert replay.status_code == 200
    rows = await _client_rows(session_factory)
    events = [row.event_type for row in rows]
    assert events.count("SERVICE_ORDER_FINISHED") == 1
    assert "Finished" in next(row.payload["text"] for row in rows if row.event_type == "SERVICE_ORDER_FINISHED")


async def test_client_disabled_means_no_rows_and_no_failure(client, session_factory):
    headers = await login(client)
    await _configure(client, headers, session_factory, clientEnabled=False, clientGroupId=str(CLIENT_CHAT))
    order = await seed_service_order(client, headers)
    assert await _client_rows(session_factory) == []
    assert order["id"]

    # Client events with the global bot enabled still enqueue nothing.
    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(NotificationOutbox))
    assert total in (0, None)


async def test_service_order_survives_broken_client_configuration(client, session_factory, monkeypatch):
    headers = await login(client)
    await _configure(client, headers, session_factory, clientEnabled=True, clientGroupId=str(CLIENT_CHAT))

    async def broken_enqueue(*args, **kwargs):
        raise RuntimeError("simulated outbox outage")

    monkeypatch.setattr(outbox, "enqueue_client", broken_enqueue)
    order = await seed_service_order(client, headers)
    assert order["id"]
    monkeypatch.undo()
    await client.patch(CONFIG, headers=headers, json={"telegram": {"clientEvents": {}}})
    rows = await _client_rows(session_factory)
    assert rows == []
