"""Deletion policy: active records and referenced records must not be deleted.

Covers the reusable policy in ``app/core/deletion.py`` and the finance delete
paths it now guards. Before this, ``chart_of_accounts``, ``financial_accounts`` and
``posting_rules`` could be deleted even while posted journals and documents still
referenced them, which would have left posted history without its account mapping.

The archive module's hard-delete behaviour is covered separately in
``test_archive.py`` and still passes: it now shares the same dependency scan.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _accounts(client, headers) -> list[dict]:
    response = await client.get("/api/v1/chart-of-accounts", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


async def _create_account(client, headers, code: str, *, status: str = "ACTIVE") -> dict:
    response = await client.post(
        "/api/v1/chart-of-accounts",
        headers=headers,
        json={
            "accountCode": code,
            "accountName": f"Test Account {code}",
            "accountType": "ASSET",
            "normalBalance": "DEBIT",
            "postable": True,
            "status": status,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _set_account_status(client, headers, account_id: str, status: str) -> None:
    response = await client.put(
        f"/api/v1/chart-of-accounts/{account_id}", headers=headers, json={"status": status}
    )
    assert response.status_code == 200, response.text


async def _delete_accounts(client, headers, ids: list[str]):
    return await client.request("DELETE", "/api/v1/chart-of-accounts", headers=headers, json={"ids": ids})


def _posted_document(client, headers, party_id: str):
    """A posted customer invoice, so real journal lines reference the accounts."""
    return client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 250}],
        },
    )


async def _first_party_id(client, headers) -> str:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"][0]["id"]


async def test_an_active_chart_of_accounts_row_cannot_be_deleted(client):
    headers = await login(client)
    account = await _create_account(client, headers, "7100")

    blocked = await _delete_accounts(client, headers, [account["id"]])
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "RECORD_ACTIVE"

    still_there = {row["accountCode"] for row in await _accounts(client, headers)}
    assert "7100" in still_there, "the account must survive the refused delete"


async def test_an_inactive_unreferenced_account_can_be_deleted(client):
    headers = await login(client)
    account = await _create_account(client, headers, "7200")
    await _set_account_status(client, headers, account["id"], "INACTIVE")

    removed = await _delete_accounts(client, headers, [account["id"]])
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 1

    remaining = {row["accountCode"] for row in await _accounts(client, headers)}
    assert "7200" not in remaining


async def test_a_referenced_account_cannot_be_deleted_even_when_inactive(client):
    """The seeded 4010 is used by the posting rules the finance baseline creates."""
    headers = await login(client)
    revenue = next(row for row in await _accounts(client, headers) if row["accountCode"] == "4010")
    await _set_account_status(client, headers, revenue["id"], "INACTIVE")

    blocked = await _delete_accounts(client, headers, [revenue["id"]])
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["code"] == "DELETE_BLOCKED_BY_REFERENCES"
    assert "posting_rules" in body["message"], body["message"]


async def test_an_account_used_by_a_posted_journal_cannot_be_deleted(client):
    headers = await login(client)
    party_id = await _first_party_id(client, headers)

    created = await _posted_document(client, headers, party_id)
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    receivable = next(row for row in await _accounts(client, headers) if row["accountCode"] == "1100")
    await _set_account_status(client, headers, receivable["id"], "INACTIVE")

    blocked = await _delete_accounts(client, headers, [receivable["id"]])
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["code"] == "DELETE_BLOCKED_BY_REFERENCES"
    assert "journal_entry_lines" in body["message"], body["message"]


async def test_an_active_posting_rule_cannot_be_deleted(client):
    headers = await login(client)
    rules = await client.get("/api/v1/posting-rules", headers=headers, params={"page_size": 200})
    assert rules.status_code == 200, rules.text
    rule = rules.json()["data"]["items"][0]

    blocked = await client.request(
        "DELETE", "/api/v1/posting-rules", headers=headers, json={"ids": [rule["id"]]}
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "RECORD_ACTIVE"


async def test_an_inactive_unreferenced_posting_rule_can_be_deleted(client):
    headers = await login(client)
    accounts = await _accounts(client, headers)
    debit = next(row for row in accounts if row["accountCode"] == "1100")
    credit = next(row for row in accounts if row["accountCode"] == "4020")

    created = await client.post(
        "/api/v1/posting-rules",
        headers=headers,
        json={
            "documentType": "ADJUSTMENT",
            "debitAccount": debit["accountCode"],
            "creditAccount": credit["accountCode"],
            "status": "INACTIVE",
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    removed = await client.request(
        "DELETE", "/api/v1/posting-rules", headers=headers, json={"ids": [rule_id]}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 1


async def test_a_referenced_financial_account_cannot_be_deleted(client):
    """A receipt records the cash/bank account it settles through."""
    headers = await login(client)
    accounts = await client.get("/api/v1/financial-accounts", headers=headers, params={"page_size": 200})
    assert accounts.status_code == 200, accounts.text
    items = accounts.json()["data"]["items"]
    assert items, "the finance baseline seeds at least one financial account"
    account_id = items[0]["id"]

    active = await client.request(
        "DELETE", "/api/v1/financial-accounts", headers=headers, json={"ids": [account_id]}
    )
    assert active.status_code == 409, active.text
    assert active.json()["code"] == "RECORD_ACTIVE"

    await client.put(
        f"/api/v1/financial-accounts/{account_id}", headers=headers, json={"status": "INACTIVE"}
    )

    party_id = await _first_party_id(client, headers)
    receipt = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_RECEIPT",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "financialAccountId": account_id,
            "lines": [{"description": "Receipt", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert receipt.status_code == 201, receipt.text

    blocked = await client.request(
        "DELETE", "/api/v1/financial-accounts", headers=headers, json={"ids": [account_id]}
    )
    assert blocked.status_code == 409, blocked.text
    body = blocked.json()
    assert body["code"] == "DELETE_BLOCKED_BY_REFERENCES"
    assert "financial_documents" in body["message"], body["message"]


async def test_deletion_that_is_refused_leaves_everything_intact(client):
    """A refused delete must not remove part of a multi-id request."""
    headers = await login(client)
    deletable = await _create_account(client, headers, "7300")
    await _set_account_status(client, headers, deletable["id"], "INACTIVE")
    protected = await _create_account(client, headers, "7400")  # still ACTIVE

    blocked = await _delete_accounts(client, headers, [deletable["id"], protected["id"]])
    assert blocked.status_code == 409, blocked.text

    remaining = {row["accountCode"] for row in await _accounts(client, headers)}
    assert {"7300", "7400"} <= remaining, "a refused request must not partially delete"
