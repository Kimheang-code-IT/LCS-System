"""Runtime checks that the endpoints every page calls actually respond.

Complements ``test_frontend_api_contract.py`` (static) by exercising the seeded
test app over the real ASGI transport: every page collection must list and the
journal delete flow must work end to end.
"""

from __future__ import annotations

import pytest

from tests.conftest import login
from tests.test_frontend_api_contract import (
    _page_collection_path,
    _page_collections,
)

pytestmark = pytest.mark.asyncio

PAGE_BASE_PATHS = sorted(
    {
        path
        for collection in _page_collections()
        if (path := _page_collection_path(collection)) is not None
    }
)


async def test_page_collection_list_returns_envelope(client):
    headers = await login(client)
    failures: list[str] = []
    for base in PAGE_BASE_PATHS:
        response = await client.get(base, headers=headers, params={"page_size": 5})
        if response.status_code != 200:
            failures.append(f"{base}: {response.status_code} {response.text}")
        elif "data" not in response.json():
            failures.append(f"{base}: missing envelope {{data: ...}}")
    assert not failures, "Page list endpoints failed:\n" + "\n".join(failures)


async def test_page_collections_deny_without_authentication_or_role(client):
    # Anonymous requests must be rejected outright; a signed-in user with no
    # role holds no protected capability, so every page collection denies too.
    anonymous_failures: list[str] = []
    for base in PAGE_BASE_PATHS:
        response = await client.get(base, params={"page_size": 5})
        if response.status_code != 401:
            anonymous_failures.append(f"{base}: {response.status_code} {response.text[:120]}")
    assert not anonymous_failures, f"Anonymous requests not rejected ({len(anonymous_failures)}/{len(list(PAGE_BASE_PATHS))}):\n" + "\n".join(anonymous_failures[:8])

    holder_headers = await _login_roleless(client)
    denied_failures: list[str] = []
    for base in PAGE_BASE_PATHS:
        response = await client.get(base, headers=holder_headers, params={"page_size": 5})
        if response.status_code != 403:
            denied_failures.append(f"{base}: {response.status_code} {response.text[:120]}")
    assert not denied_failures, f"Roleless requests not denied ({len(denied_failures)}/{len(list(PAGE_BASE_PATHS))}):\n" + "\n".join(denied_failures[:8])


async def _login_roleless(client):
    # A new user needs a role; the assignment is removed right after so the
    # account is truly roleless (same pattern as test_single_role_rbac).
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "PAGE_ROLE", "name": "Page Role", "permissions": []},
    )
    assert role.status_code == 201, role.text
    user = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "page.probe",
            "displayName": "Page Probe",
            "email": "page.probe@example.com",
            "password": "Passw0rd!",
            "roleCode": "PAGE_ROLE",
        },
    )
    assert user.status_code == 201, user.text
    user_id = user.json()["data"]["id"]
    removed = await client.delete(
        f"/api/v1/users/{user_id}/role-assignments/PAGE_ROLE", headers=headers
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["roles"] == []
    return await login(client, "page.probe")


async def test_journal_draft_can_be_deleted(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/journal-entries",
        headers=headers,
        json={
            "entryDate": "2024-01-15",
            "description": "Draft to delete",
            "lines": [
                {"account_code": "1010", "debit_amount": 10, "credit_amount": 0, "currency": "USD"},
                {"account_code": "4010", "debit_amount": 0, "credit_amount": 10, "currency": "USD"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    journal_id = created.json()["data"]["id"]

    deleted = await client.delete(f"/api/v1/journal-entries/{journal_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text

    missing = await client.get(f"/api/v1/journal-entries/{journal_id}", headers=headers)
    assert missing.status_code == 404
