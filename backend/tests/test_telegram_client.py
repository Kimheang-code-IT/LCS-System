import httpx
import pytest

from app.modules.telegram.client import TelegramClient, TelegramError

TOKEN = "123456:abcdefghijklmnopqrstuvwxyz_123456"


async def test_identity_and_plain_message():
    calls = []

    def respond(request):
        import json
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"id": 12, "is_bot": True, "message_id": 1}})

    client = TelegramClient(TOKEN, transport=httpx.MockTransport(respond))
    assert (await client.get_me())["id"] == 12
    await client.send_message(42, "<b>untrusted</b>\x00")
    assert calls[1]["text"] == "<b>untrusted</b>"
    assert "parse_mode" not in calls[1]


@pytest.mark.parametrize("status,code,retry", [(401, "invalid_bot_token", False), (403, "destination_blocked", False), (429, "rate_limited", True), (503, "telegram_unavailable", True)])
async def test_safe_errors(status, code, retry):
    client = TelegramClient(TOKEN, transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"ok": False, "error_code": status, "description": TOKEN, "parameters": {"retry_after": 23}})))
    with pytest.raises(TelegramError) as caught:
        await client.send_message(42, "hello")
    assert caught.value.code == code
    assert caught.value.retryable is retry
    assert caught.value.retry_after == 23
    assert TOKEN not in str(caught.value)


async def test_bounded_transient_retry():
    calls = []

    def respond(_):
        calls.append(1)
        return httpx.Response(503, json={"ok": False, "error_code": 503})

    with pytest.raises(TelegramError):
        await TelegramClient(TOKEN, transport=httpx.MockTransport(respond)).get_me()
    assert len(calls) == 2


def test_token_validation():
    with pytest.raises(TelegramError, match="invalid_bot_token"):
        TelegramClient("https://attacker.example/token")
