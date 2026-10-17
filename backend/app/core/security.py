from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()
_dummy_password_hash = _hasher.hash(secrets.token_urlsafe(32))

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def verify_password_or_dummy(password: str, password_hash: str | None) -> bool:
    """Perform an Argon2 verification even when an account does not exist.

    Keeping the expensive code path similar makes username enumeration through
    response timing substantially harder.
    """
    return verify_password(password, password_hash or _dummy_password_hash)


def validate_password_strength(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < settings.password_min_length:
        errors.append(f"Password must be at least {settings.password_min_length} characters.")
    if len(password) > settings.password_max_length:
        errors.append(f"Password must not exceed {settings.password_max_length} characters.")
    if password.casefold() in {
        "password",
        "password123",
        "changeme",
        "changeme123",
        "admin123",
        "letmein",
        "qwerty123",
    }:
        errors.append("Password is too common.")
    return errors


def _encode(payload: dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(UTC)
    to_encode = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "type": token_type,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str | int, token_version: int = 0, *, must_change_password: bool = False) -> str:
    """Encode an access token.

    ``pwd`` marks a credential an administrator set, so the API can refuse every
    route except changing it. Carrying the flag in the token rather than reading
    the credential row means the check costs no query.
    """
    payload: dict[str, Any] = {"sub": str(subject), "tv": int(token_version)}
    if must_change_password:
        payload["pwd"] = 1
    return _encode(payload, timedelta(minutes=settings.access_token_expire_minutes), ACCESS_TOKEN_TYPE)


def create_refresh_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    payload = {"sub": str(subject)}
    lifetime = expires_delta or timedelta(days=settings.refresh_token_expire_days)
    return _encode(payload, lifetime, REFRESH_TOKEN_TYPE)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_reset_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def create_csrf_token(refresh_token: str) -> str:
    random_value = secrets.token_urlsafe(32)
    key = (settings.csrf_secret_key or settings.jwt_secret_key).encode("utf-8")
    message = f"{hash_token(refresh_token)}.{random_value}".encode()
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"{signature}.{random_value}"


def verify_csrf_token(token: str, refresh_token: str) -> bool:
    try:
        signature, random_value = token.split(".", 1)
    except ValueError:
        return False
    if len(signature) != 64 or not random_value:
        return False
    key = (settings.csrf_secret_key or settings.jwt_secret_key).encode("utf-8")
    message = f"{hash_token(refresh_token)}.{random_value}".encode()
    expected = hmac.new(key, message, hashlib.sha256).hexdigest()
    return constant_time_compare(signature, expected)
