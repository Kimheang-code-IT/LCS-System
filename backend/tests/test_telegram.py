from datetime import timedelta

from sqlalchemy import select

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.database import utcnow
from app.modules.settings.models import AppSetting
from app.modules.telegram import service
from app.modules.telegram.models import TelegramLink, TelegramPairing, TelegramUpdate
from tests.conftest import login

TOKEN = "123456:abcdefghijklmnopqrstuvwxyz_123456"
CONFIG = "/api/v1/settings/app-config"
SECRET = "webhook-test-secret"


async def configure(client, headers, session_factory):
    result = await client.patch(CONFIG, headers=headers, json={"telegram": {"enabled": True, "botToken": TOKEN}})
    assert result.status_code == 200, result.text
    tested = await client.post(f"{CONFIG}/telegram/test-connection", headers=headers)
    assert tested.status_code == 200, tested.text
    async with session_factory() as session:
        value = await service.config(session)
        value["webhookSecret"] = encrypt_secret(SECRET)
        await service.save_internal(session, value)
        await session.commit()
    return tested


def update(token, update_id=1, *, group=False, sender_id=123):
    return {"update_id": update_id, "message": {"chat": {"id": -10012 if group else sender_id, "type": "supergroup" if group else "private"}, "from": {"id": sender_id, "username": "tester"}, "text": f"{'/lcs_pair' if group else '/start'} {token}"}}


async def deliver(client, body, secret=SECRET):
    return await client.post("/api/v1/integrations/telegram/webhook", json=body, headers={"X-Telegram-Bot-Api-Secret-Token": secret})


async def test_encrypted_masked_preserved_and_server_owned_config(client, session_factory, telegram_mock):
    headers = await login(client)
    tested = await configure(client, headers, session_factory)
    assert tested.json()["data"]["status"] == "connected"
    result = await client.patch(CONFIG, headers=headers, json={"telegram": {"botToken": "", "adminGroupId": -99, "webhookSecret": "forged", "connectionStatus": "forged"}})
    value = result.json()["data"]["telegram"]
    assert value["botToken"] == "" and value["botTokenConfigured"]
    assert value["connectionStatus"] == "connected"
    assert not value.get("adminGroupId") and "webhookSecret" not in value
    async with session_factory() as session:
        row = (await session.execute(select(AppSetting).where(AppSetting.setting_key == "telegram"))).scalar_one()
        assert row.setting_value["botToken"].startswith("enc:v1:")
        assert decrypt_secret(row.setting_value["botToken"]) == TOKEN


async def test_group_verification_requires_webhook_and_authenticated_confirmation(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    pairing = (await client.post("/api/v1/settings/telegram/group/pair", headers=headers)).json()["data"]
    token = pairing["challenge"]
    denied = await client.post("/api/v1/settings/telegram/group/confirm", headers=headers, json={"challenge": token})
    assert denied.status_code == 422
    assert (await deliver(client, update(token, group=True), "invalid")).status_code == 403
    assert (await deliver(client, update(token, group=True))).status_code == 200
    assert (await deliver(client, update(token, group=True))).status_code == 200
    async with session_factory() as session:
        assert not (await service.config(session)).get("adminGroupId")
        assert len((await session.execute(select(TelegramUpdate))).scalars().all()) == 1
    confirmed = await client.post("/api/v1/settings/telegram/group/confirm", headers=headers, json={"challenge": token})
    assert confirmed.status_code == 200, confirmed.text
    replay = await client.post("/api/v1/settings/telegram/group/confirm", headers=headers, json={"challenge": token})
    assert replay.status_code == 422
    sends = [c for c in telegram_mock if c[0] == "sendMessage"]
    assert len(sends) == 1


async def test_pairing_requires_password_and_private_identity(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    path = "/api/v1/auth/me/telegram/pair"
    assert (await client.post(path, headers=headers, json={"current_password": "wrong"})).status_code == 403
    response = await client.post(path, headers=headers, json={"current_password": "Passw0rd!"})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["challenge"]
    await deliver(client, update(token, group=True))
    assert not (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]["connected"]
    await deliver(client, update(token, update_id=2))
    assert (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]["connected"]
    await deliver(client, update(token, update_id=3, sender_id=124))
    async with session_factory() as session:
        assert (await session.execute(select(TelegramLink))).scalar_one().telegram_user_id == 123
        row = (await session.execute(select(TelegramPairing))).scalar_one()
        assert token not in row.token_hash


async def test_expired_pairing_and_permission_denial(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    token = (await client.post("/api/v1/auth/me/telegram/pair", headers=headers, json={"current_password": "Passw0rd!"})).json()["data"]["challenge"]
    async with session_factory() as session:
        row = await session.get(TelegramPairing, service.digest(token))
        row.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()
    await deliver(client, update(token))
    assert not (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]["connected"]
    assert (await client.post("/api/v1/settings/telegram/group/pair")).status_code in {401, 403}


async def test_backend_refuses_group_recovery_routing(client, telegram_mock):
    headers = await login(client)
    response = await client.patch(CONFIG, headers=headers, json={"telegram": {"rules": {"recovery": {"destination": "ADMIN"}}}})
    assert response.status_code == 422


async def test_delayed_connection_check_cannot_resurrect_removed_credentials(client, session_factory, telegram_mock, monkeypatch):
    headers = await login(client)
    await configure(client, headers, session_factory)
    original = service.TelegramClient

    class DelayedClient(original):
        async def get_me(self):
            from app.modules.settings.service import update_app_config

            async with session_factory() as other:
                await update_app_config(other, None, {"telegram": {"removeBotToken": True}})
            return await super().get_me()

    monkeypatch.setattr(service, "TelegramClient", DelayedClient)
    response = await client.post(f"{CONFIG}/telegram/test-connection", headers=headers)
    assert response.status_code == 422
    async with session_factory() as session:
        value = await service.config(session)
        assert not value["enabled"] and not value["botToken"]


async def test_authenticated_user_without_settings_permissions_is_denied(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    role = await client.post("/api/v1/roles", headers=headers, json={"code": "NO_TELEGRAM", "name": "No Telegram settings", "permissions": ["master.reference.view"]})
    assert role.status_code == 201
    created = await client.post("/api/v1/users", headers=headers, json={"username": "telegramoutsider", "displayName": "Outsider", "email": "telegramoutsider@example.com", "password": "Original-Str0ng!", "role": "NO_TELEGRAM"})
    assert created.status_code == 201
    outsider = await login(client, "telegramoutsider", "Original-Str0ng!")
    for method, path, body in (
        ("post", "/api/v1/settings/telegram/group/pair", {}),
        ("post", "/api/v1/settings/telegram/webhook", {}),
        ("post", f"{CONFIG}/telegram/test-connection", {}),
        ("post", f"{CONFIG}/telegram/send-test", {}),
        ("get", "/api/v1/settings/telegram/history", None),
        ("delete", "/api/v1/settings/telegram/group", None),
        ("patch", CONFIG, {"telegram": {"botToken": TOKEN}}),
    ):
        response = await client.request(method, path, headers=outsider, **({"json": body} if body is not None else {}))
        assert response.status_code == 403, (path, response.text)
    safe = (await client.get(CONFIG, headers=outsider)).json()["data"]["telegram"]
    assert set(safe) == {"enabled"}
    invalid = await client.post("/api/v1/auth/me/telegram/pair", headers=outsider, json={"current_password": "Original-Str0ng!", "user_id": 1})
    assert invalid.status_code == 422
