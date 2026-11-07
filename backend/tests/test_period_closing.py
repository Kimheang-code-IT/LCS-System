"""Period Closing: the review contract and the lock-time gate (P10 task 10.1/10.3)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


def _range(offset_months: int = 3) -> tuple[str, str]:
    """A bounded range entirely before the seed's three auto-generated periods."""
    month = date.today().replace(day=1)
    for _ in range(offset_months):
        month = (month - timedelta(days=1)).replace(day=1)
    return month.isoformat(), (month + timedelta(days=27)).isoformat()


async def _open_period(client, headers, name: str = "Close Test", offset_months: int = 3) -> str:
    start, end = _range(offset_months)
    created = await client.post(
        "/api/v1/accountingPeriods",
        headers=headers,
        json={"name": name, "startDate": start, "endDate": end, "status": "OPEN"},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


async def _posted_invoice(client, headers, party_id: str, document_date: str, amount: float = 400) -> str:
    document = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "documentDate": document_date,
            "partyId": party_id,
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert document.status_code == 201, document.text
    document_id = document.json()["data"]["id"]
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    return document_id


async def _validation(client, headers, period_id: str) -> dict:
    response = await client.post(f"/api/v1/accounting-periods/{period_id}/closing-validation", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_the_clean_period_validates_and_closes(client, session_factory):
    """Checks 1/2/4/5/7/8 on a period whose only activity is one posted invoice."""
    headers = await login(client)
    party = (await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})).json()["data"]["items"][0]
    period_id = await _open_period(client, headers)
    start, _end = _range()
    document_id = await _posted_invoice(client, headers, party["id"], start)

    report = await _validation(client, headers, period_id)
    assert report["blockingCount"] == 0
    codes = {check["code"]: check["status"] for check in report["checks"]}
    assert codes["PERIOD_STATE"] == "PASS"
    assert codes["JOURNAL_BALANCE"] == "PASS"
    assert codes["JOURNAL_LINES"] == "PASS"
    assert codes["POSTING_LINKS"] == "PASS"
    assert codes["TRIAL_BALANCE"] == "PASS"
    assert codes["BANK_RECONCILIATION"] == "NOT_AVAILABLE", "an unexecuted check is never a PASS"
    assert codes["ACCOUNTS_RECEIVABLE"] == "PASS"
    assert report["summary"]["revenue"] == 400 and report["summary"]["profit"] == 400
    assert report["summary"]["arOutstanding"] == 400
    assert report["baseCurrency"] == "USD"

    closed = await client.post(
        f"/api/v1/accounting-periods/{period_id}/close", headers=headers, json={"reason": "month end"}
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"].upper() == "CLOSED"
    assert closed.json()["data"]["closedAt"]

    # A backdated posting into the closed period is refused...
    backdated = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "SUPPLIER_BILL",
            "documentDate": start,
            "partyId": party["id"],
            "currency": "USD",
            "lines": [{"description": "Backdated", "quantity": 1, "unitPrice": 10}],
        },
    )
    assert backdated.status_code == 201, backdated.text
    document_id = backdated.json()["data"]["id"]
    refused = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert refused.status_code == 409
    assert refused.json()["code"] in ("PERIOD_CLOSED", "PERIOD_NOT_OPEN"), refused.text

    # ...and closing again is refused (already closed).
    again = await client.post(
        f"/api/v1/accounting-periods/{period_id}/close", headers=headers, json={"reason": "x"}
    )
    assert again.status_code in (409, 422), again.text


async def test_the_validation_reports_drafts_as_warnings_not_blockers(client):
    headers = await login(client)
    party = (await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})).json()["data"]["items"][0]
    period_id = await _open_period(client, headers, "Draft Review", offset_months=4)
    created = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "documentDate": _range(4)[0],
            "partyId": party["id"],
            "currency": "USD",
            "lines": [{"description": "Draft", "quantity": 1, "unitPrice": 50}],
        },
    )
    assert created.status_code == 201, created.text

    report = await _validation(client, headers, period_id)
    drafts = next(check for check in report["checks"] if check["code"] == "DRAFT_DOCUMENTS")
    assert drafts["status"] == "WARNING" and drafts["affectedCount"] == 1
    # The draft still closes (drafts never block per the P10 policy).
    closed = await client.post(
        f"/api/v1/accounting-periods/{period_id}/close", headers=headers, json={"reason": "ok"}
    )
    assert closed.status_code == 200, closed.text
