"""Fixed-origin Telegram transport. Never propagate token-bearing request URLs."""

import asyncio
import logging
import re
from typing import Any

import httpx


class _RedactBotURL(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(r"/bot[0-9]+:[A-Za-z0-9_-]+", "/bot[REDACTED]", record.getMessage())
        record.args = ()
        return True


logging.getLogger("httpx").addFilter(_RedactBotURL())
for _name in ("httpcore.connection", "httpcore.http11", "httpcore.http2"):
    logging.getLogger(_name).addFilter(_RedactBotURL())


class TelegramError(Exception):
    def __init__(self, code: str, *, retryable: bool = False, retry_after: int = 0):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.retry_after = min(max(retry_after, 0), 86400)


class TelegramClient:
    def __init__(self, token: str, *, transport: httpx.AsyncBaseTransport | None = None):
        if not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,100}", token):
            raise TelegramError("invalid_bot_token")
        self._token = token
        self._transport = transport

    async def call(self, method: str, payload: dict | None = None, *, retries: int = 0) -> Any:
        if method not in {"getMe", "sendMessage", "setWebhook", "getWebhookInfo", "deleteWebhook", "getChat", "getChatMember"}:
            raise TelegramError("unsupported_method")
        for attempt in range(min(max(retries, 0), 2) + 1):
            try:
                async with httpx.AsyncClient(transport=self._transport, timeout=httpx.Timeout(10, connect=3), follow_redirects=False) as client:
                    response = await client.post(f"https://api.telegram.org/bot{self._token}/{method}", json=payload or {})
                try:
                    body = response.json()
                except ValueError:
                    raise TelegramError("invalid_response", retryable=response.status_code >= 500) from None
                if not isinstance(body, dict):
                    raise TelegramError("invalid_response")
                if response.is_success and body.get("ok") is True:
                    return body.get("result")
                code = body.get("error_code", response.status_code)
                parameters = body.get("parameters") or {}
                retry_after = parameters.get("retry_after", 0)
                retry_after = retry_after if isinstance(retry_after, int) else 0
                errors = {401: "invalid_bot_token", 403: "destination_blocked", 429: "rate_limited", 400: "invalid_destination"}
                raise TelegramError(errors.get(code, "telegram_unavailable"), retryable=code == 429 or isinstance(code, int) and code >= 500, retry_after=retry_after)
            except httpx.HTTPError:
                error = TelegramError("transport_unavailable", retryable=True)
            except TelegramError as exc:
                error = exc
            if not error.retryable or attempt >= retries or error.retry_after > 2:
                raise error from None
            await asyncio.sleep(max(error.retry_after, 0.1 * 2**attempt))
        raise TelegramError("telegram_unavailable")

    async def get_me(self) -> dict:
        result = await self.call("getMe", retries=1)
        if not isinstance(result, dict) or not result.get("is_bot") or not isinstance(result.get("id"), int):
            raise TelegramError("invalid_response")
        return result

    async def send_message(self, chat_id: int, text: str) -> dict:
        # Plain text only: no Telegram HTML/Markdown evaluation or link previews.
        text = "".join(c for c in text if c in "\n\t" or ord(c) >= 32)[:4096]
        result = await self.call("sendMessage", {"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}})
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise TelegramError("invalid_response")
        return result
