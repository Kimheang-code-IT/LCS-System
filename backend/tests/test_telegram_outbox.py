from datetime import timedelta

import pytest

from app.core.database import utcnow
from app.modules.telegram import outbox, service
from app.modules.telegram.client import TelegramError
from app.modules.telegram.models import NotificationOutbox
from tests.test_telegram_recovery import recovery_setup, recovery_token


async def request(client):
    assert (await client.post("/api/v1/auth/forgot-password", json={"identifier": "admin"})).status_code == 200


async def test_recovery_delivery_purges_ciphertext_and_history_is_safe(client, session_factory, telegram_mock, monkeypatch):
    headers, _ = await recovery_setup(client, session_factory, monkeypatch)
    await request(client)
    token, row_id = await recovery_token(session_factory)
    async with session_factory() as session:
        claims = await outbox.claim(session)
    assert len(claims) == 1
    await outbox.deliver(*claims[0], session_factory=session_factory)
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        assert row.status == "SENT" and row.sensitive_payload is None and row.sent_at
    sent = [c for c in telegram_mock if c[0] == "sendMessage"]
    assert sent[-1][1]["chat_id"] == 123 and token in sent[-1][1]["text"]
    response = await client.get("/api/v1/settings/telegram/history", headers=headers)
    assert token not in response.text and "sensitive_payload" not in response.text
    assert response.json()["data"]["items"][0]["destination"] == "PRIVATE"
    assert (await client.post(f"/api/v1/settings/telegram/history/{row_id}/retry", headers=headers)).status_code == 422


@pytest.mark.parametrize("code,retryable,expected", [("rate_limited", True, "PENDING"), ("destination_blocked", False, "FAILED"), ("invalid_bot_token", False, "FAILED")])
async def test_delivery_retry_policy(client, session_factory, telegram_mock, monkeypatch, code, retryable, expected):
    await recovery_setup(client, session_factory, monkeypatch)
    await request(client)

    class Unavailable:
        async def send_message(self, *args):
            raise TelegramError(code, retryable=retryable, retry_after=120)

    monkeypatch.setattr(service, "client", lambda _: Unavailable())
    async with session_factory() as session:
        claim = (await outbox.claim(session))[0]
    await outbox.deliver(*claim, session_factory=session_factory)
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, claim[0])
        assert row.status == expected
        assert row.last_error == code
        assert row.attempts == 1
        if retryable:
            assert service.aware(row.next_attempt_at) >= utcnow() + timedelta(seconds=110)
        else:
            assert row.sensitive_payload is None


async def test_restart_claim_recovery_and_expired_payload_purge(client, session_factory, telegram_mock, monkeypatch):
    await recovery_setup(client, session_factory, monkeypatch)
    await request(client)
    _, row_id = await recovery_token(session_factory)
    async with session_factory() as session:
        first = await outbox.claim(session)
        assert len(first) == 1
        assert await outbox.claim(session) == []
        row = await session.get(NotificationOutbox, row_id)
        row.locked_until = utcnow() - timedelta(seconds=1)
        await session.commit()
    async with session_factory() as session:
        reclaimed = await outbox.claim(session)
        assert len(reclaimed) == 1 and reclaimed[0][1] != first[0][1]
    await outbox.deliver(*first[0], session_factory=session_factory)  # Stale claim cannot send.
    assert not telegram_mock
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        row.expires_at = utcnow() - timedelta(seconds=1)
        row.locked_until = utcnow() - timedelta(seconds=1)
        await session.commit()
    async with session_factory() as session:
        assert await outbox.claim(session) == []
        row = await session.get(NotificationOutbox, row_id)
        assert row.status == "CANCELLED" and row.sensitive_payload is None


async def test_terminal_retry_bound(client, session_factory, telegram_mock, monkeypatch):
    await recovery_setup(client, session_factory, monkeypatch)
    await request(client)
    _, row_id = await recovery_token(session_factory)
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        row.attempts = row.max_attempts
        await session.commit()
    async with session_factory() as session:
        assert await outbox.claim(session) == []
        row = await session.get(NotificationOutbox, row_id)
        assert row.status == "FAILED" and row.sensitive_payload is None


def test_transient_delivery_tables_are_excluded_from_external_backup():
    from app.modules.backup.service import _excluded_tables

    assert {"notification_outbox", "telegram_pairings", "telegram_links"} <= _excluded_tables()
