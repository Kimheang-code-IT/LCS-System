from __future__ import annotations

import pytest

from app.core.locks import advisory_lock
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
    assert {row["documentType"] for row in sequences.json()["data"]["items"]} == {
        "QUOTATION",
        "SERVICE_ORDER",
        "SERVICE_CHARGE",
        "CUSTOMER_INVOICE",
        "SUPPLIER_BILL",
        "CUSTOMER_RECEIPT",
        "SUPPLIER_PAYMENT",
        "JOURNAL",
    }

    app_config = await client.get("/api/v1/settings/app-config", headers=preserved_headers)
    assert app_config.status_code == 200, app_config.text
    assert app_config.json()["data"]["system"]["environment"] == "production"

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
