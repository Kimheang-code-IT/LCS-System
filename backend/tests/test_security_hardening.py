from __future__ import annotations

import pytest

from app.core.config import Settings, settings
from app.core.exceptions import ValidationFailed
from app.modules.operations import service as operations_service
from tests.conftest import login


async def test_cookie_session_requires_valid_csrf_token(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Passw0rd!"},
    )
    assert response.status_code == 200

    rejected = await client.post("/api/v1/auth/profile/avatar", json={"avatar": None})
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "CSRF_VALIDATION_FAILED"

    csrf_token = client.cookies.get(settings.csrf_cookie_name)
    assert csrf_token
    accepted = await client.post(
        "/api/v1/auth/profile/avatar",
        json={"avatar": None},
        headers={settings.csrf_header_name: csrf_token},
    )
    assert accepted.status_code == 200


async def test_bearer_auth_does_not_require_csrf_header(client):
    headers = await login(client)
    response = await client.post("/api/v1/auth/profile/avatar", headers=headers, json={"avatar": None})
    assert response.status_code == 200


async def test_disallowed_upload_extension_is_rejected(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/attachments/presign",
        headers=headers,
        json={"fileName": "payload.svg", "mimeType": "image/svg+xml"},
    )
    assert response.status_code == 422


def test_upload_content_must_match_extension():
    with pytest.raises(ValidationFailed):
        operations_service._validate_upload_content("pdf", b"not a PDF")


def _production_settings(**overrides) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "JWT_SECRET_KEY": "j" * 32,
        "CSRF_SECRET_KEY": "c" * 32,
        "FIELD_ENCRYPTION_KEY": "f" * 32,
        "SETUP_TOKEN": "s" * 32,
        "COOKIE_SECURE": True,
        "AUTH_RETURN_TOKENS": False,
        "ACCESS_TOKEN_EXPIRE_MINUTES": 15,
        "PASSWORD_MIN_LENGTH": 12,
        "RATE_LIMIT_ENABLED": True,
        "CORS_ORIGINS": "https://app.example.com",
        "ALLOWED_HOSTS": "app.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_requires_https_origin():
    with pytest.raises(ValueError, match="production HTTPS origins"):
        _production_settings(CORS_ORIGINS="http://app.example.com")


def test_production_configuration_rejects_reused_secrets():
    with pytest.raises(ValueError, match="must all be different"):
        _production_settings(CSRF_SECRET_KEY="j" * 32)

