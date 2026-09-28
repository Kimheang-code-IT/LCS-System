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
