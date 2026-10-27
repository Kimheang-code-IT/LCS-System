"""Strong password policy: one rule for every new-password path.

The policy is code-defined in ``app.core.security.validate_password_strength``
(there is no configurable complexity setting), and every endpoint that accepts a
new password calls it before hashing: first-run setup, self-service reset,
self-service change, administrator reset and user creation. These tests pin the
rule itself, prove each endpoint refuses a password it does not meet, prove a
refusal leaves the stored credential untouched, and prove a legacy weak password
can still sign in (the policy applies to new passwords only).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password, validate_password_strength, verify_password
from app.modules.auth.models import User, UserCredential
from tests.conftest import login

pytestmark = pytest.mark.asyncio

USERS = "/api/v1/users"
FRONTEND_RULES = (
    Path(__file__).resolve().parents[2] / "frontend" / "app" / "utils" / "validation" / "field-rules.ts"
)

VALID_PASSWORDS = ("Abc@1234", "Freight#2026", "Admin@12345", "Freight-Forwarding-2026!x")

# (password, the message the user must see)
INVALID_PASSWORDS = (
    ("abc@1234", "uppercase"),
    ("ABC@1234", "lowercase"),
    ("Abcd@efg", "number"),
    ("Abcd1234", "special"),
    ("Ab@123", "at least 8 characters"),
)


@pytest.mark.parametrize("password", VALID_PASSWORDS)
def test_compliant_passwords_are_accepted(password: str):
    assert validate_password_strength(password) == []


@pytest.mark.parametrize(("password", "expected"), INVALID_PASSWORDS)
def test_each_missing_category_is_reported(password: str, expected: str):
    errors = validate_password_strength(password)
    assert any(expected in error for error in errors), errors


def test_each_category_is_reported_separately():
    # "short" is long enough to be lowercase but missing everything else.
    errors = validate_password_strength("short")
    assert any("at least 8 characters" in error for error in errors)
    assert any("uppercase" in error for error in errors)
    assert any("number" in error for error in errors)
    assert any("special" in error for error in errors)


def test_common_passwords_stay_refused():
    errors = validate_password_strength("Password123")
    assert any("too common" in error for error in errors), errors
    assert any("special" in error for error in errors), errors


def test_effective_policy_matches_the_frontend_mirror():
    """The Vite form refuses locally what the API would refuse after a round trip."""
    source = FRONTEND_RULES.read_text(encoding="utf-8")
    minimum = int(re.search(r"PASSWORD_MIN_LENGTH = (\d+)", source).group(1))
    maximum = int(re.search(r"PASSWORD_MAX_LENGTH = (\d+)", source).group(1))
    assert minimum == settings.password_min_length
    assert maximum == settings.password_max_length
    assert minimum >= 8
    for rule in (r"[A-Z]", r"[a-z]", r"[0-9]", r"[^A-Za-z0-9]"):
        assert rule in source, f"field-rules.ts no longer enforces {rule}"


async def _credential(session_factory, user_id: int) -> UserCredential:
    async with session_factory() as session:
        return (
            await session.execute(select(UserCredential).where(UserCredential.user_id == user_id))
        ).scalars().one()


async def _create_user(client, headers, username: str, password: str = "Original-Str0ng!") -> dict:
    response = await client.post(
        USERS,
        headers=headers,
        json={
            "username": username,
            "displayName": username,
            "email": f"{username}@example.com",
            "password": password,
            "status": "Active",
            "role": "AUDITOR",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_user_creation_rejects_each_weak_password(client, session_factory):
    headers = await login(client)
    for index, (password, expected) in enumerate(INVALID_PASSWORDS):
        username = f"weak.create.{index}"
        response = await client.post(
            USERS,
            headers=headers,
            json={
                "username": username,
                "displayName": "Weak",
                "email": f"{username}@example.com",
                "password": password,
                "role": "AUDITOR",
            },
        )
        assert response.status_code == 422, response.text
        assert expected in response.json()["field_errors"]["password"], response.text
    async with session_factory() as session:
        assert (await session.execute(select(User).where(User.username.like("weak.create.%")))).scalars().all() == []


async def test_administrator_reset_rejects_a_weak_password_without_touching_the_hash(client, session_factory):
    headers = await login(client)
    user = await _create_user(client, headers, "policy.reset")
    before = (await _credential(session_factory, user["id"])).password_hash

    response = await client.post(
        f"{USERS}/{user['id']}/password",
        headers=headers,
        json={"password": "Abcd1234"},
    )
    assert response.status_code == 422, response.text
    assert "special" in response.json()["field_errors"]["password"]
    assert (await _credential(session_factory, user["id"])).password_hash == before

    # The original password still signs in: nothing was half-applied.
    client.cookies.clear()
    await login(client, "policy.reset", "Original-Str0ng!")
    client.cookies.clear()


async def test_self_change_rejects_a_weak_password_and_keeps_the_old_one(client, session_factory):
    headers = await login(client)
    user = await _create_user(client, headers, "policy.change")
    before = (await _credential(session_factory, user["id"])).password_hash

    client.cookies.clear()
    user_headers = await login(client, "policy.change", "Original-Str0ng!")
    for password, expected in INVALID_PASSWORDS:
        response = await client.post(
            "/api/v1/auth/change-password",
            headers=user_headers,
            json={"current_password": "Original-Str0ng!", "password": password},
        )
        assert response.status_code == 422, response.text
        assert expected in response.json()["field_errors"]["password"]
    assert (await _credential(session_factory, user["id"])).password_hash == before
    client.cookies.clear()


async def test_self_change_accepts_a_compliant_password(client, session_factory):
    headers = await login(client)
    user = await _create_user(client, headers, "policy.accept")

    client.cookies.clear()
    user_headers = await login(client, "policy.accept", "Original-Str0ng!")
    response = await client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={"current_password": "Original-Str0ng!", "password": "Freight#2026"},
    )
    assert response.status_code == 200, response.text
    credential = await _credential(session_factory, user["id"])
    assert verify_password("Freight#2026", credential.password_hash)
    assert not verify_password("Original-Str0ng!", credential.password_hash)
    client.cookies.clear()


async def test_password_reset_rejects_a_weak_password_before_consuming_the_link(client):
    # Strength is checked before the token lookup, so a weak password is refused
    # identically whether or not the link is still valid.
    response = await client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"code": "x" * 40, "password": "Abcd1234"},
    )
    assert response.status_code == 422, response.text
    assert "special" in response.json()["field_errors"]["password"]


async def test_first_run_setup_rejects_a_weak_password(client):
    # The seeded test database already has users, so the strength check must fire
    # before the setup-completed conflict; either way a weak password is refused.
    response = await client.post(
        "/api/v1/auth/setup/initialize",
        json={"email": "fresh@example.test", "password": "Abcd1234"},
    )
    assert response.status_code == 422, response.text
    assert "special" in response.json()["field_errors"]["password"]


async def test_confirm_password_mismatch_is_refused_by_the_api(client):
    headers = await login(client)
    user = await _create_user(client, headers, "policy.confirm")
    response = await client.post(
        f"{USERS}/{user['id']}/password",
        headers=headers,
        json={"password": "Freight#2026", "password_confirmation": "Freight#2027"},
    )
    assert response.status_code == 422, response.text
    assert "do not match" in response.json()["field_errors"]["passwordConfirmation"]


async def test_a_legacy_weak_password_can_still_sign_in(client, session_factory):
    """The new policy must never lock out an account that predates it."""
    async with session_factory() as session:
        user = User(
            user_code="LEGACY.WEAK",
            username="legacy.weak",
            email="legacy.weak@example.com",
            display_name="Legacy Weak",
            status="ACTIVE",
        )
        session.add(user)
        await session.flush()
        session.add(UserCredential(user_id=user.id, password_hash=hash_password("weak")))
        await session.commit()

    response = await client.post("/api/v1/auth/login", json={"username": "legacy.weak", "password": "weak"})
    assert response.status_code == 200, response.text
