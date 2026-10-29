"""On-demand report generation.

The report engine is only useful if the numbers are right, so these tests pin
the accounting semantics rather than the plumbing:

* the trial balance splits the movement before the period (opening) from the
  movement inside it, and still proves that debit equals credit;
* an unbalanced ledger is reported as unbalanced instead of being presented as
  a control that passed;
* the general ledger continues a running balance from the opening position,
  across page boundaries, and never picks up a draft;
* nothing is generated without the report's own permission.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.finance.models import ChartOfAccount, JournalEntry, JournalEntryLine
from tests.conftest import login

pytestmark = pytest.mark.asyncio

TRIAL_BALANCE = "/api/v1/reports/trial-balance/generate"
GENERAL_LEDGER = "/api/v1/reports/general-ledger/generate"


def _month_start(offset_months: int) -> date:
    today = date.today()
    month = today.month - offset_months
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


OPENING_DATE = _month_start(3)
PERIOD_START = _month_start(1)
PERIOD_END = date.today()
# Inside the period but strictly after its first day, so ordering is checkable.
PERIOD_LATER = min(PERIOD_START + timedelta(days=10), PERIOD_END)


async def _journal(client, headers, *, posting_date: date, lines: list[dict], entry_type: str = "MANUAL") -> dict:
    created = await client.post(
        "/api/v1/journal-entries",
        headers=headers,
        json={
            "entryDate": posting_date.isoformat(),
            "postingDate": posting_date.isoformat(),
            "entryType": entry_type,
            "description": f"Report fixture {posting_date.isoformat()}",
            "lines": lines,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


async def _posted(client, headers, **kwargs) -> dict:
    journal = await _journal(client, headers, **kwargs)
    posted = await client.post(f"/api/v1/journal-entries/{journal['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    return journal


def _line(account: str, debit: str = "0", credit: str = "0") -> dict:
    return {"accountCode": account, "debitAmount": debit, "creditAmount": credit}


async def _generate(client, headers, url: str, **body):
    response = await client.post(url, headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _row(data: dict, code: str) -> dict:
    return next(item for item in data["items"] if item["accountCode"] == code)


async def test_trial_balance_splits_opening_from_period_and_balances(client):
    headers = await login(client)
    await _posted(
        client,
        headers,
        posting_date=OPENING_DATE,
        lines=[_line("1100", debit="400"), _line("4010", credit="400")],
    )
    await _posted(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("1100", debit="100"), _line("4010", credit="100")],
    )

    data = await _generate(
        client,
        headers,
        TRIAL_BALANCE,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
    )

    receivable = _row(data, "1100")
    assert receivable["openingDebit"] == 400.0
    assert receivable["openingCredit"] == 0.0
    assert receivable["periodDebit"] == 100.0
    assert receivable["periodCredit"] == 0.0
    assert receivable["closingDebit"] == 500.0
    assert receivable["closingCredit"] == 0.0

    revenue = _row(data, "4010")
    assert revenue["openingCredit"] == 400.0
    assert revenue["periodCredit"] == 100.0
    assert revenue["closingCredit"] == 500.0

    assert data["balanced"] is True
    assert data["imbalance"] == 0
    assert data["totals"]["periodDebit"] == data["totals"]["periodCredit"] == 100.0
    assert data["meta"]["reportKey"] == "trial-balance"
    assert data["meta"]["filters"]["fromDate"] == PERIOD_START.isoformat()


async def test_trial_balance_ignores_draft_journals(client):
    headers = await login(client)
    draft = await _journal(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("1100", debit="999"), _line("4010", credit="999")],
    )

    data = await _generate(
        client,
        headers,
        TRIAL_BALANCE,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
    )
    assert data["items"] == []
    assert data["balanced"] is True

    posted = await client.post(f"/api/v1/journal-entries/{draft['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    after = await _generate(
        client,
        headers,
        TRIAL_BALANCE,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
    )
    assert _row(after, "1100")["periodDebit"] == 999.0


async def test_trial_balance_reports_an_imbalance_instead_of_hiding_it(client, session_factory):
    """A ledger that does not balance must say so; the control is the point."""
    headers = await login(client)
    async with session_factory() as session:
        receivable = (
            await session.execute(select(ChartOfAccount).where(ChartOfAccount.account_code == "1100"))
        ).scalar_one()
        revenue = (
            await session.execute(select(ChartOfAccount).where(ChartOfAccount.account_code == "4010"))
        ).scalar_one()
        entry = JournalEntry(
            entry_no="JT-UNBALANCED",
            entry_type="MANUAL",
            entry_date=PERIOD_LATER,
            posting_date=PERIOD_LATER,
            status="POSTED",
            debit_total=Decimal("100"),
            credit_total=Decimal("90"),
        )
        session.add(entry)
        await session.flush()
        session.add_all(
            [
                JournalEntryLine(
                    journal_entry_id=entry.id,
                    line_no=1,
                    account_id=receivable.id,
                    debit_amount=Decimal("100"),
                    base_debit_amount=Decimal("100"),
                ),
                JournalEntryLine(
                    journal_entry_id=entry.id,
                    line_no=2,
                    account_id=revenue.id,
                    credit_amount=Decimal("90"),
                    base_credit_amount=Decimal("90"),
                ),
            ]
        )
        await session.commit()

    data = await _generate(
        client,
        headers,
        TRIAL_BALANCE,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
    )
    assert data["balanced"] is False
    assert data["imbalance"] == 10.0
    assert data["meta"]["warnings"], "an unbalanced report must carry a warning"


async def test_general_ledger_carries_opening_and_running_balances(client):
    headers = await login(client)
    await _posted(
        client,
        headers,
        posting_date=OPENING_DATE,
        lines=[_line("1100", debit="200"), _line("4010", credit="200")],
    )
    await _posted(
        client,
        headers,
        posting_date=PERIOD_START,
        lines=[_line("1100", debit="100"), _line("4010", credit="100")],
    )
    await _posted(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("4010", debit="40"), _line("1100", credit="40")],
    )

    data = await _generate(
        client,
        headers,
        GENERAL_LEDGER,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        accountCode="1100",
        pageSize=10,
    )

    assert data["meta"]["total"] == 2
    assert data["openingBalance"] == 200.0
    assert [item["debit"] for item in data["items"]] == [100.0, 0.0]
    assert [item["credit"] for item in data["items"]] == [0.0, 40.0]
    # 200 opening + 100 - 40, carried row by row.
    assert [item["runningBalance"] for item in data["items"]] == [300.0, 260.0]
    assert data["totals"] == {"debit": 100.0, "credit": 40.0, "closingBalance": 260.0}
    assert all(item["voucherType"] == "MANUAL" for item in data["items"])


async def test_general_ledger_pagination_continues_the_running_balance(client):
    headers = await login(client)
    await _posted(
        client,
        headers,
        posting_date=OPENING_DATE,
        lines=[_line("1100", debit="200"), _line("4010", credit="200")],
    )
    await _posted(
        client,
        headers,
        posting_date=PERIOD_START,
        lines=[_line("1100", debit="100"), _line("4010", credit="100")],
    )
    await _posted(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("4010", debit="40"), _line("1100", credit="40")],
    )

    first = await _generate(
        client,
        headers,
        GENERAL_LEDGER,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        accountCode="1100",
        page=1,
        pageSize=1,
    )
    second = await _generate(
        client,
        headers,
        GENERAL_LEDGER,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        accountCode="1100",
        page=2,
        pageSize=1,
    )

    assert first["meta"]["total"] == second["meta"]["total"] == 2
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["runningBalance"] == 300.0
    assert second["items"][0]["runningBalance"] == 260.0
    assert first["items"][0]["id"] != second["items"][0]["id"]
    # The same filters must return the same order, page after page.
    again = await _generate(
        client,
        headers,
        GENERAL_LEDGER,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        accountCode="1100",
        page=1,
        pageSize=1,
    )
    assert again["items"] == first["items"]


async def test_general_ledger_excludes_drafts_and_filters_by_voucher(client):
    headers = await login(client)
    posted = await _posted(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("1100", debit="70"), _line("4010", credit="70")],
    )
    await _journal(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("1100", debit="900"), _line("4010", credit="900")],
    )

    everything = await _generate(
        client,
        headers,
        GENERAL_LEDGER,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        accountCode="1100",
        pageSize=50,
    )
    assert everything["meta"]["total"] == 1, "the draft journal must not appear in the ledger"

    by_voucher = await _generate(
        client,
        headers,
        GENERAL_LEDGER,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        voucherNo=posted["entryNo"],
        pageSize=50,
    )
    assert by_voucher["meta"]["total"] == 2
    assert {item["voucherNo"] for item in by_voucher["items"]} == {posted["entryNo"]}


async def test_general_ledger_returns_an_empty_page_for_an_empty_period(client):
    headers = await login(client)
    data = await _generate(
        client,
        headers,
        GENERAL_LEDGER,
        fromDate="2099-01-01",
        toDate="2099-01-31",
    )
    assert data["items"] == []
    assert data["meta"]["total"] == 0
    assert data["openingBalance"] == 0


async def test_invalid_date_range_is_rejected_with_a_field_error(client):
    headers = await login(client)
    response = await client.post(
        TRIAL_BALANCE,
        headers=headers,
        json={"fromDate": "2026-02-01", "toDate": "2026-01-01"},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "toDate" in body["field_errors"]


async def test_unknown_fiscal_year_is_rejected(client):
    headers = await login(client)
    response = await client.post(GENERAL_LEDGER, headers=headers, json={"fiscalYear": 2199})
    assert response.status_code == 422, response.text
    assert "fiscalYear" in response.json()["field_errors"]


async def test_fiscal_year_resolves_to_the_accounting_periods(client):
    headers = await login(client)
    await _posted(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("1100", debit="10"), _line("4010", credit="10")],
    )
    periods = (
        await client.get("/api/v1/accounting-periods", headers=headers, params={"page_size": 200})
    ).json()["data"]
    in_year = [period for period in periods if period["year"] == PERIOD_LATER.year]
    assert in_year, "posting a journal must create its accounting period"

    data = await _generate(client, headers, TRIAL_BALANCE, fiscalYear=PERIOD_LATER.year)
    # A fiscal year starts where the ledger says it starts, not on 1 January.
    assert data["meta"]["filters"]["fromDate"] == min(period["startDate"] for period in in_year)
    assert data["meta"]["filters"]["toDate"] == max(period["endDate"] for period in in_year)
    assert any(item["accountCode"] == "1100" for item in data["items"])


async def test_unknown_filters_are_refused_rather_than_ignored(client):
    headers = await login(client)
    response = await client.post(TRIAL_BALANCE, headers=headers, json={"fromdate": "2026-01-01"})
    assert response.status_code == 422, response.text


async def test_report_generation_requires_the_report_permission(client):
    admin = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=admin,
        json={"code": "REPORT_DENIED", "name": "No Reports", "permissions": []},
    )
    assert role.status_code == 201, role.text
    created = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "noreports",
            "email": "noreports@example.com",
            "displayName": "No Reports",
            "password": "Passw0rd!",
            "roleCode": "REPORT_DENIED",
        },
    )
    assert created.status_code == 201, created.text

    # A role without any report grant must not reach a financial report.
    headers = await login(client, "noreports")
    for url in (TRIAL_BALANCE, GENERAL_LEDGER):
        denied = await client.post(url, headers=headers, json={})
        assert denied.status_code == 403, f"{url}: {denied.text}"


async def test_generation_is_read_only(client):
    """Generating must not create, post or mutate any journal."""
    headers = await login(client)
    await _posted(
        client,
        headers,
        posting_date=PERIOD_LATER,
        lines=[_line("1100", debit="30"), _line("4010", credit="30")],
    )
    before = (await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})).json()["data"]
    await _generate(client, headers, TRIAL_BALANCE, fromDate=PERIOD_START.isoformat())
    await _generate(client, headers, GENERAL_LEDGER, fromDate=PERIOD_START.isoformat())
    after = (await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})).json()["data"]
    assert after["meta"]["total"] == before["meta"]["total"]
    assert [row["id"] for row in after["items"]] == [row["id"] for row in before["items"]]


async def test_generation_still_works_while_the_system_is_read_only(client):
    """A GET-shaped report must not be refused by the read-only write guard."""
    headers = await login(client)
    enabled = await client.patch(
        "/api/v1/settings/app-config", headers=headers, json={"system": {"readOnlyMode": True}}
    )
    assert enabled.status_code == 200, enabled.text

    data = await _generate(client, headers, TRIAL_BALANCE, fromDate=PERIOD_START.isoformat())
    assert data["meta"]["reportKey"] == "trial-balance"

    blocked = await client.post("/api/v1/feeTypes", headers=headers, json={"code": "RO-X", "name": "Blocked"})
    assert blocked.status_code == 409, blocked.text
