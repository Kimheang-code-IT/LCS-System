from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
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


async def test_pairing_and_chatbot_replies_work_while_admin_alerts_are_disabled(client, session_factory, telegram_mock):
    """Pairing and replies must not depend on the Admin Alerts master switch."""
    headers = await login(client)
    await configure(client, headers, session_factory)
    disabled = await client.patch(CONFIG, headers=headers, json={"telegram": {"enabled": False}})
    assert disabled.status_code == 200
    pair = await client.post("/api/v1/auth/me/telegram/pair", headers=headers, json={"current_password": "Passw0rd!"})
    assert pair.status_code == 200, pair.text
    token = pair.json()["data"]["challenge"]
    assert f"https://t.me/lcs_test_bot?start={token}" == pair.json()["data"]["url"]
    assert (await deliver(client, update(token, update_id=801))).status_code == 200
    me = (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]
    assert me["connected"] is True and me["botUsername"] == "lcs_test_bot"
    assert (await deliver(client, command("/help", 802))).status_code == 200
    assert "/status" in _replies(telegram_mock)[-1]
    assert (await deliver(client, command("/status", 803))).status_code == 200
    assert "Access: enabled" in _replies(telegram_mock)[-1]


async def test_development_polling_works_with_alerts_off_and_skips_replayed_updates(client, session_factory, telegram_mock, monkeypatch):
    from app.modules.telegram import worker

    headers = await login(client)
    await configure(client, headers, session_factory)
    await client.patch(CONFIG, headers=headers, json={"telegram": {"enabled": False}})
    await _link(session_factory, "admin", 123, "Admin Tester")
    replies: list[str] = []

    class PollingBot:
        def __init__(self, _token):
            pass

        async def call(self, method, payload=None):
            if method == "getUpdates":
                return [command("/help", 811)]
            return True

        async def send_message(self, chat_id, text):
            replies.append(text)
            return {"message_id": 1}

    monkeypatch.setattr(service, "TelegramClient", PollingBot)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "telegram_allow_webhook_delete", True)
    worker._poll_bot_id = None
    worker._poll_offset = None
    await worker.poll_updates()
    await worker.poll_updates()  # Telegram re-delivers the same update id
    assert len(replies) == 1 and "/status" in replies[0]


async def test_verification_code_links_telegram_identity_and_ui_fields(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    generated = await client.post("/api/v1/auth/me/telegram/verification-code", headers=headers)
    assert generated.status_code == 200, generated.text
    data = generated.json()["data"]
    assert len(data["code"]) == 6 and data["code"].isdigit()
    assert data["botUsername"] == "lcs_test_bot"
    assert (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]["connected"] is False

    assert (await deliver(client, command(f"/verify {data['code']}", 901))).status_code == 200
    assert "Verification successful" in _replies(telegram_mock)[-1]
    me = (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]
    assert me["connected"] is True
    assert me["telegramUserId"] == 123
    assert me["username"] == "tester"


async def test_verification_code_is_single_use_and_regeneration_invalidates(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    first = (await client.post("/api/v1/auth/me/telegram/verification-code", headers=headers)).json()["data"]["code"]
    second = (await client.post("/api/v1/auth/me/telegram/verification-code", headers=headers)).json()["data"]["code"]
    await deliver(client, command(f"/verify {first}", 911))
    assert "Invalid or expired" in _replies(telegram_mock)[-1]
    await deliver(client, command(f"/verify {second}", 912))
    assert "Verification successful" in _replies(telegram_mock)[-1]
    # The consumed code cannot be replayed.
    await deliver(client, command(f"/verify {second}", 913))
    assert "Invalid or expired" in _replies(telegram_mock)[-1]


async def test_expired_and_brute_forced_codes_are_rejected(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    code = (await client.post("/api/v1/auth/me/telegram/verification-code", headers=headers)).json()["data"]["code"]
    async with session_factory() as session:
        row = await session.get(TelegramPairing, service.digest(code))
        row.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()
    await deliver(client, command(f"/verify {code}", 921))
    assert "Invalid or expired" in _replies(telegram_mock)[-1]
    # Five failed guesses exhaust the per-Telegram-account budget.
    for offset, guess in enumerate(("000001", "000002", "000003", "000004", "000005")):
        await deliver(client, command(f"/verify {guess}", 930 + offset, sender_id=321))
    await deliver(client, command("/verify 000006", 940, sender_id=321))
    assert "Too many attempts" in _replies(telegram_mock)[-1]


async def test_verify_requires_current_permission_and_active_user(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    role = await client.post("/api/v1/roles", headers=headers, json={"code": "VERIFY_BOT", "name": "Verify", "permissions": ["telegram.chatbot.use"]})
    assert role.status_code == 201, role.text
    role_id = role.json()["data"]["id"]
    created = await client.post("/api/v1/users", headers=headers, json={"username": "verifyuser", "displayName": "Verify User", "email": "verifyuser@example.com", "password": "Original-Str0ng!", "role": "VERIFY_BOT"})
    assert created.status_code == 201, created.text
    user_headers = await login(client, "verifyuser", "Original-Str0ng!")
    code = (await client.post("/api/v1/auth/me/telegram/verification-code", headers=user_headers)).json()["data"]["code"]

    # Permission revoked after the code was issued.
    assert (await client.request("DELETE", f"/api/v1/roles/{role_id}/permissions", headers=headers, json={"permissions": ["telegram.chatbot.use"]})).status_code == 200
    await deliver(client, command(f"/verify {code}", 951, sender_id=777))
    assert "not enabled" in _replies(telegram_mock)[-1]
    async with session_factory() as session:
        from sqlalchemy import select as _select

        assert await session.scalar(_select(TelegramLink).where(TelegramLink.user_id == created.json()["data"]["id"])) is None

    # Regrant, then an inactive account cannot verify either.
    assert (await client.post(f"/api/v1/roles/{role_id}/permissions", headers=headers, json={"permissions": ["telegram.chatbot.use"]})).status_code == 200
    fresh = (await client.post("/api/v1/auth/me/telegram/verification-code", headers=user_headers)).json()["data"]["code"]
    async with session_factory() as session:
        from app.modules.auth.models import User

        user = await session.get(User, created.json()["data"]["id"])
        user.status = "SUSPENDED"
        await session.commit()
    await deliver(client, command(f"/verify {fresh}", 952, sender_id=777))
    assert "not active" in _replies(telegram_mock)[-1]


async def test_verification_rejects_telegram_identity_linked_elsewhere(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    await _link(session_factory, "admin", 123, "tester")
    role = await client.post("/api/v1/roles", headers=headers, json={"code": "VERIFY_OTHER", "name": "Verify Other", "permissions": ["telegram.chatbot.use"]})
    assert role.status_code == 201, role.text
    created = await client.post("/api/v1/users", headers=headers, json={"username": "verifyother", "displayName": "Other", "email": "verifyother@example.com", "password": "Original-Str0ng!", "role": "VERIFY_OTHER"})
    assert created.status_code == 201, created.text
    other_headers = await login(client, "verifyother", "Original-Str0ng!")
    code = (await client.post("/api/v1/auth/me/telegram/verification-code", headers=other_headers)).json()["data"]["code"]
    await deliver(client, command(f"/verify {code}", 961, sender_id=123))
    assert "already linked to another LCS account" in _replies(telegram_mock)[-1]


async def test_verify_works_through_polling_with_admin_alerts_disabled(client, session_factory, telegram_mock, monkeypatch):
    from app.modules.telegram import worker

    headers = await login(client)
    await configure(client, headers, session_factory)
    await client.patch(CONFIG, headers=headers, json={"telegram": {"enabled": False}})
    code = (await client.post("/api/v1/auth/me/telegram/verification-code", headers=headers)).json()["data"]["code"]
    replies: list[str] = []

    class PollingBot:
        def __init__(self, _token):
            pass

        async def call(self, method, payload=None):
            if method == "getUpdates":
                return [command(f"/verify {code}", 971)]
            return True

        async def send_message(self, chat_id, text):
            replies.append(text)
            return {"message_id": 1}

    monkeypatch.setattr(service, "TelegramClient", PollingBot)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "telegram_allow_webhook_delete", True)
    worker._poll_bot_id = None
    worker._poll_offset = None
    await worker.poll_updates()
    assert any("Verification successful" in text for text in replies)
    assert (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]["telegramUserId"] == 123


async def test_polling_does_not_steal_a_registered_webhook(client, session_factory, telegram_mock, monkeypatch):
    from app.modules.telegram import worker

    headers = await login(client)
    await configure(client, headers, session_factory)
    calls: list[str] = []

    class GuardBot:
        def __init__(self, _token):
            pass

        async def call(self, method, payload=None):
            calls.append(method)
            if method == "getWebhookInfo":
                return {"url": "https://prod.example/api/v1/integrations/telegram/webhook"}
            return True

    monkeypatch.setattr(service, "TelegramClient", GuardBot)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "telegram_allow_webhook_delete", False)
    worker._poll_bot_id = None
    worker._poll_offset = None
    worker._warned.clear()
    await worker.poll_updates()
    assert "getUpdates" not in calls and "deleteWebhook" not in calls
    state = worker.health()
    assert state["status"] == "misconfigured"
    assert state["lastError"] == "webhook_registered_elsewhere"


async def test_polling_removes_webhook_only_when_explicitly_allowed(client, session_factory, telegram_mock, monkeypatch):
    from app.modules.telegram import worker

    headers = await login(client)
    await configure(client, headers, session_factory)
    calls: list[str] = []

    class WebhookBot:
        def __init__(self, _token):
            pass

        async def call(self, method, payload=None):
            calls.append(method)
            if method == "getWebhookInfo":
                return {"url": "https://dev.example/api/v1/integrations/telegram/webhook"}
            if method == "getUpdates":
                return []
            return True

    monkeypatch.setattr(service, "TelegramClient", WebhookBot)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "telegram_allow_webhook_delete", True)
    worker._poll_bot_id = None
    worker._poll_offset = None
    await worker.poll_updates()
    assert calls == ["getWebhookInfo", "deleteWebhook", "getUpdates"]
    assert worker.health()["status"] == "polling"


async def test_development_polling_is_one_consumer_and_processes_pairing(client, session_factory, telegram_mock, monkeypatch):
    from app.modules.telegram import worker

    headers = await login(client)
    await configure(client, headers, session_factory)
    pair = await client.post("/api/v1/auth/me/telegram/pair", headers=headers, json={"current_password": "Passw0rd!"})
    assert pair.status_code == 200, pair.text
    token = pair.json()["data"]["challenge"]

    calls: list[str] = []

    class PollingBot:
        def __init__(self, _token):
            pass

        async def call(self, method, payload=None):
            calls.append(method)
            if method == "getUpdates":
                return [{"update_id": 501, "message": {"chat": {"id": 123, "type": "private"}, "from": {"id": 123, "username": "admin"}, "text": f"/start {token}"}}]
            return True

    monkeypatch.setattr(service, "TelegramClient", PollingBot)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "telegram_allow_webhook_delete", True)
    worker._poll_bot_id = None
    worker._poll_offset = None
    await worker.poll_updates()
    assert calls[:2] == ["getWebhookInfo", "getUpdates"]
    link = (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]
    assert link["connected"] is True


async def test_admin_alert_test_targets_only_authorized_verified_recipients(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    # Linked admins are eligible; a linked user without telegram.alerts.receive is not.
    role = await client.post("/api/v1/roles", headers=headers, json={"code": "NO_ALERTS", "name": "No alerts", "permissions": ["master.reference.view"]})
    assert role.status_code == 201, role.text
    created = await client.post("/api/v1/users", headers=headers, json={"username": "alertoutsider", "displayName": "Outsider", "email": "alertoutsider@example.com", "password": "Original-Str0ng!", "role": "NO_ALERTS"})
    assert created.status_code == 201, created.text
    async with session_factory() as session:
        from sqlalchemy import select as _select

        from app.modules.auth.models import User

        admin = (await session.execute(_select(User).where(User.username == "admin"))).scalar_one()
        outsider = (await session.execute(_select(User).where(User.username == "alertoutsider"))).scalar_one()
        session.add_all([
            TelegramLink(user_id=admin.id, telegram_user_id=123, bot_id=99, chat_id=123, display_name="Admin Tester"),
            TelegramLink(user_id=outsider.id, telegram_user_id=456, bot_id=99, chat_id=456, display_name="Outsider"),
        ])
        await session.commit()
    result = await client.post(f"{CONFIG}/telegram/send-test", headers=headers)
    assert result.status_code == 200, result.text
    assert "1 recipient" in result.json()["data"]["message"]
    sends = [c for c in telegram_mock if c[0] == "sendMessage"]
    assert len(sends) == 1 and sends[0][1]["chat_id"] == 123
    # The Settings card shows the same verified-recipient count.
    config_value = (await client.get(CONFIG, headers=headers)).json()["data"]["telegram"]
    assert config_value["adminRecipientCount"] == 1
    assert config_value["updateMode"] in {"webhook", "polling"}
    assert config_value["workerEnabled"] is True
    # The count survives a save response, so the Test Alert button stays gated.
    saved = await client.patch(CONFIG, headers=headers, json={"telegram": {"enabled": True}})
    assert saved.json()["data"]["telegram"]["adminRecipientCount"] == 1


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
        ("get", "/api/v1/auth/me/telegram", None),
        ("post", "/api/v1/auth/me/telegram/pair", {"current_password": "Original-Str0ng!"}),
        ("post", "/api/v1/auth/me/telegram/disconnect", {"current_password": "Original-Str0ng!"}),
    ):
        response = await client.request(method, path, headers=outsider, **({"json": body} if body is not None else {}))
        assert response.status_code == 403, (path, response.text)
    safe = (await client.get(CONFIG, headers=outsider)).json()["data"]["telegram"]
    assert set(safe) == {"enabled"}
    invalid = await client.post("/api/v1/auth/me/telegram/pair", headers=outsider, json={"current_password": "Original-Str0ng!", "user_id": 1})
    assert invalid.status_code == 403


def command(text, update_id, sender_id=123):
    return {"update_id": update_id, "message": {"chat": {"id": sender_id, "type": "private"}, "from": {"id": sender_id, "username": "tester"}, "text": text}}


async def _link(session_factory, username, telegram_id, display_name):
    from sqlalchemy import select as _select

    from app.modules.auth.models import User

    async with session_factory() as session:
        user = (await session.execute(_select(User).where(User.username == username))).scalar_one()
        session.add(TelegramLink(user_id=user.id, telegram_user_id=telegram_id, bot_id=99, chat_id=telegram_id, display_name=display_name))
        await session.commit()
        return user.id


def _replies(telegram_mock):
    return [call[1]["text"] for call in telegram_mock if call[0] == "sendMessage"]


async def test_chatbot_commands_for_linked_permitted_active_user(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    await _link(session_factory, "admin", 123, "Admin Tester")

    # Unlinked senders only see the public pairing instructions.
    await deliver(client, command("/start", 700, sender_id=999))
    assert "LCS profile" in _replies(telegram_mock)[-1]
    assert (await deliver(client, command("/help", 701))).status_code == 200
    assert "/status" in _replies(telegram_mock)[-1]
    await deliver(client, command("/status", 702))
    assert "Access: enabled" in _replies(telegram_mock)[-1]
    # Unknown commands are ignored, never reflected.
    before = len(_replies(telegram_mock))
    await deliver(client, command("/drop_tables", 703))
    assert len(_replies(telegram_mock)) == before
    # /disconnect revokes the link from the verified private chat.
    await deliver(client, command("/disconnect", 704))
    assert (await client.get("/api/v1/auth/me/telegram", headers=headers)).json()["data"]["connected"] is False


async def test_chatbot_denies_unpermitted_and_inactive_users_and_revocation(client, session_factory, telegram_mock):
    headers = await login(client)
    await configure(client, headers, session_factory)
    role = await client.post("/api/v1/roles", headers=headers, json={"code": "CHATBOT", "name": "Chatbot", "permissions": ["telegram.chatbot.use"]})
    assert role.status_code == 201, role.text
    role_id = role.json()["data"]["id"]
    created = await client.post("/api/v1/users", headers=headers, json={"username": "chatbotuser", "displayName": "Chatbot User", "email": "chatbotuser@example.com", "password": "Original-Str0ng!", "role": "CHATBOT"})
    assert created.status_code == 201, created.text
    user_id = await _link(session_factory, "chatbotuser", 456, "Chatbot User")

    await deliver(client, command("/status", 711, sender_id=456))
    assert "Access: enabled" in _replies(telegram_mock)[-1]

    # Permission removal takes effect on the next message.
    revoked = await client.request("DELETE", f"/api/v1/roles/{role_id}/permissions", headers=headers, json={"permissions": ["telegram.chatbot.use"]})
    assert revoked.status_code == 200, revoked.text
    await deliver(client, command("/status", 712, sender_id=456))
    assert "not enabled" in _replies(telegram_mock)[-1]
    # The profile controls disappear for that user as well.
    headers_user = await login(client, "chatbotuser", "Original-Str0ng!")
    assert (await client.get("/api/v1/auth/me/telegram", headers=headers_user)).status_code == 403

    # Regrant, then an inactive account is denied even with a valid link.
    assert (await client.post(f"/api/v1/roles/{role_id}/permissions", headers=headers, json={"permissions": ["telegram.chatbot.use"]})).status_code == 200
    async with session_factory() as session:
        from app.modules.auth.models import User

        user = await session.get(User, user_id)
        user.status = "SUSPENDED"
        await session.commit()
    await deliver(client, command("/status", 713, sender_id=456))
    assert "not enabled" in _replies(telegram_mock)[-1]
