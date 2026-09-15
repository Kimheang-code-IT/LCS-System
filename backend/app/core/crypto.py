"""Field-level encryption for credentials that must be retrievable.

Application login passwords use one-way Argon2 hashing (``app.core.security``).
Secrets that an authorised user must be able to read back (for example a
customer customs-portal password) are stored reversibly encrypted with a key
derived from ``JWT_SECRET_KEY``.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PREFIX = "enc:v1:"

# Field names (case-insensitive) that must never be stored in plain text.
SENSITIVE_FIELD_NAMES = {
    "password",
    "credential",
    "credentialreference",
    "customspassword",
    "customsaccountpassword",
    "secret",
    "clientsecret",
    "apikey",
    "api_key",
    "token",
    "privatekey",
}


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_sensitive_field(name: str) -> bool:
    return name.replace("-", "_").lower() in SENSITIVE_FIELD_NAMES


def encrypt_secret(value: str) -> str:
    if value.startswith(_PREFIX):
        return value
    return _PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
