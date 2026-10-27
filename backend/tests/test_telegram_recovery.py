import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.core.database import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import PasswordResetToken, UserCredential, UserSession
from app.modules.telegram import service
from app.modules.telegram.models import NotificationOutbox, TelegramLink
from tests.conftest import login
from tests.test_telegram import configure


async def recovery_setup(client, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "telegram_public_app_url", "https://lcs.example")
    headers = await login(client)
    await configure(client, headers, session_factory)
    user_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["data"]["id"]
    async with session_factory() as session:
        value = await service.config(session)
        value["rules"] = {"recovery": {**service.DEFAULT_RULES["recovery"], "enabled": True}}
        await service.save_internal(session, value)
        session.add(TelegramLink(user_id=user_id, telegram_user_id=123, bot_id=99, chat_id=123, display_name="Tester"))
        await session.commit()
    return headers, user_id


async def recovery_token(session_factory):
    async with session_factory() as session:
        row = (await session.execute(select(NotificationOutbox).where(NotificationOutbox.event_type == "PASSWORD_RESET_REQUESTED"))).scalar_one()
        text = json.loads(decrypt_secret(row.sensitive_payload))["text"]
        return parse_qs(urlsplit(text.splitlines()[-1]).fragment)["token"][0], row.id


async def test_generic_response_and_private_encrypted_delivery(client, session_factory, telegram_mock, monkeypatch):
    await recovery_setup(client, session_factory, monkeypatch)
    existing = await client.post("/api/v1/auth/forgot-password", json={"username": "admin"})
    absent = await client.post("/api/v1/auth/forgot-password", json={"username": "missing"})
    assert existing.status_code == absent.status_code == 200
    assert existing.json() == absent.json() == {"data": {"sent": True}}
    token, row_id = await recovery_token(session_factory)
    assert len(token) >= 40
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        reset = (await session.execute(select(PasswordResetToken))).scalar_one()
        assert row.destination_type == "PRIVATE" and row.destination_reference == 123
        assert token not in json.dumps(row.payload) and token not in row.sensitive_payload
        assert reset.code_hash != token and len(reset.code_hash) >= 64
        assert service.aware(row.expires_at) < service.aware(reset.expires_at)


async def test_unlinked_accounts_do_not_issue_recovery(client, session_factory, telegram_mock, monkeypatch):
    headers = await login(client)
    await configure(client, headers, session_factory)
    response = await client.post("/api/v1/auth/forgot-password", json={"identifier": "admin"})
    assert response.json() == {"data": {"sent": True}}
    async with session_factory() as session:
        assert await session.scalar(select(PasswordResetToken.id)) is None


async def test_reset_is_single_use_revokes_sessions_and_hides_token(client, session_factory, telegram_mock, monkeypatch):
    headers, user_id = await recovery_setup(client, session_factory, monkeypatch)
    await client.post("/api/v1/auth/forgot-password", json={"identifier": "admin"})
    token, _ = await recovery_token(session_factory)
    assert (await client.post("/api/v1/auth/forgot-password/verify", json={"token": token})).status_code == 200
    payload = {"token": token, "password": "New-Str0ng-Password!", "password_confirmation": "New-Str0ng-Password!"}
    reset = await client.post("/api/v1/auth/forgot-password/reset", json=payload)
    assert reset.status_code == 200, reset.text
    assert (await client.post("/api/v1/auth/forgot-password/reset", json=payload)).status_code == 409
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"username": "admin", "password": payload["password"]})).status_code == 200
    async with session_factory() as session:
        assert (await session.get(UserCredential, user_id)).must_change_password is False
        events = (await session.execute(select(AuditEvent))).scalars().all()
        assert token not in str([e.metadata_json for e in events])
        sessions = (await session.execute(select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.id))).scalars().all()
        assert all(s.revoked_at for s in sessions[:-1])


async def test_expired_and_invalid_tokens_fail(client, session_factory, telegram_mock, monkeypatch):
    await recovery_setup(client, session_factory, monkeypatch)
    await client.post("/api/v1/auth/forgot-password", json={"email": "admin"})
    token, _ = await recovery_token(session_factory)
    async with session_factory() as session:
        record = (await session.execute(select(PasswordResetToken))).scalar_one()
        record.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()
    for value in (token, "x" * 43):
        assert (await client.post("/api/v1/auth/forgot-password/verify", json={"token": value})).status_code == 422
        assert (await client.post("/api/v1/auth/forgot-password/reset", json={"token": value, "password": "New-Str0ng-Password!"})).status_code == 409


async def test_disconnect_invalidates_already_issued_recovery(client, session_factory, telegram_mock, monkeypatch):
    headers, _ = await recovery_setup(client, session_factory, monkeypatch)
    await client.post("/api/v1/auth/forgot-password", json={"identifier": "admin"})
    token, row_id = await recovery_token(session_factory)
    result = await client.post("/api/v1/auth/me/telegram/disconnect", headers=headers, json={"current_password": "Passw0rd!"})
    assert result.status_code == 200
    assert (await client.post("/api/v1/auth/forgot-password/reset", json={"token": token, "password": "New-Str0ng-Password!"})).status_code == 409
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        assert row.status == "CANCELLED" and row.sensitive_payload is None
