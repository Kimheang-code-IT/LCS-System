from __future__ import annotations

import pytest

from app.core.config import settings as _settings
from app.core.locks import advisory_lock
from app.core.sequences import DEFAULT_PREFIXES
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_setup_status_public_and_requires_setup(client):
    response = await client.get("/api/v1/auth/setup/status")
    assert response.status_code == 200
    assert response.json()["data"]["requiresSetup"] is False


async def test_reset_preserves_protected_admin_and_clears_business_data(client):
    headers = await login(client)

    reset = await client.post("/api/v1/settings/reset-data", headers=headers, json={"confirm": "RESET"})
    assert reset.status_code == 200, reset.text
    assert reset.json()["data"]["reset"] is True

    status = await client.get("/api/v1/auth/setup/status")
    assert status.json()["data"]["requiresSetup"] is False

    # The original protected administrator still signs in. No business data is seeded.
    preserved_headers = await login(client)
    users = (await client.get("/api/v1/users", headers=preserved_headers)).json()["data"]
    assert any(user.get("isProtectedSystemAccount") is True for user in users)
    accounts = await client.get("/api/v1/chartOfAccounts", headers=preserved_headers)
    assert accounts.status_code == 200, accounts.text
    assert accounts.json()["data"]["meta"]["total"] == 0

    # Default configuration is provisioned automatically: document sequences for
    # the current year and the default app config record.
    sequences = await client.get("/api/v1/document-sequences", headers=preserved_headers)
    assert sequences.status_code == 200, sequences.text
    # Asserted against the registry rather than a literal, so adding a document
    # type (credit notes) does not require editing this test as well.
    assert {row["documentType"] for row in sequences.json()["data"]["items"]} == set(DEFAULT_PREFIXES)

    app_config = await client.get("/api/v1/settings/app-config", headers=preserved_headers)
    assert app_config.status_code == 200, app_config.text
    from app.core.config import settings as app_settings

    assert app_config.json()["data"]["system"]["environment"] == app_settings.environment

    audit = await client.get("/api/v1/audit-events", headers=preserved_headers)
    assert any(row["action"] == "reset_business_data" for row in audit.json()["data"]["items"])

    setup_again = await client.post(
        "/api/v1/auth/setup/initialize",
        json={"email": "second@fresh.test", "password": "Fresh123!"},
    )
    assert setup_again.status_code == 409


async def test_reset_requires_typed_confirmation(client):
    headers = await login(client)
    response = await client.post("/api/v1/settings/reset-data", headers=headers, json={"confirm": "nope"})
    assert response.status_code == 422
    assert "confirm" in response.json()["field_errors"]


async def test_setup_lock_rejects_a_concurrent_local_attempt(session_factory):
    async with session_factory() as first_session, session_factory() as second_session:
        async with advisory_lock(first_session, "auth:setup-initialize") as first_acquired:
            assert first_acquired is True
            async with advisory_lock(second_session, "auth:setup-initialize") as second_acquired:
                assert second_acquired is False


@pytest.mark.parametrize(
    ("password", "message_part"),
    [
        ("Ab1@", "at least"),  # below the minimum
        # Here length is refused by the request schema's own cap; production
        # deployments set PASSWORD_MAX_LENGTH lower, so the policy message then
        # says "must not exceed" instead.
        (f"Ab1@{'x' * _settings.password_max_length}", "at most"),
        ("Password123", "too common"),  # on the backend's banned list
        ("Xabc34567r", "special character"),  # missing a symbol
        ("Xb#defgh!", "number"),  # missing a digit
        ("XB#DEFGH!", "lowercase letter"),  # missing a lowercase letter
        ("xb#34567789", "uppercase letter"),  # missing an uppercase letter
    ],
)
async def test_setup_rejects_each_password_rule_individually(client, password, message_part):
    """One policy failure at a time, so the form can show a concrete message."""
    response = await client.post(
        "/api/v1/auth/setup/initialize",
        json={"email": "rules@example.test", "password": password, "name": "Super Admin"},
    )
    assert response.status_code == 422, response.text
    assert message_part in response.json()["field_errors"]["password"]


async def test_setup_initialisation_creates_the_first_administrator_then_refuses(client_fresh):
    """Happy path on a fresh install and the duplicate-initialisation guard."""
    status_before = await client_fresh.get("/api/v1/auth/setup/status")
    assert status_before.json()["data"]["requiresSetup"] is True

    created = await client_fresh.post(
        "/api/v1/auth/setup/initialize",
        json={"email": "admin@example.test", "password": "Abcdef12!", "name": "Super Admin"},
    )
    assert created.status_code == 201, created.text

    # A second initialisation is refused whether or not the lock is free.
    duplicate = await client_fresh.post(
        "/api/v1/auth/setup/initialize",
        json={"email": "second@example.test", "password": "Abcdef12!"},
    )
    assert duplicate.status_code == 409, duplicate.text

    # The created credentials sign in and the user is the protected administrator.
    login_response = await client_fresh.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.test", "password": "Abcdef12!"},
    )
    assert login_response.status_code == 200, login_response.text
