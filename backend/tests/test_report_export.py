"""Full-result CSV exports for the generated reports.

The export must be the *same* report, not a second one: same filters, same
permission, every matching row (not the visible page) and a footer whose totals
reconcile with ``/generate``.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

TRIAL_BALANCE = "/api/v1/reports/trial-balance/generate"
GENERAL_LEDGER = "/api/v1/reports/general-ledger/generate"
TRIAL_BALANCE_EXPORT = "/api/v1/reports/trial-balance/export"
GENERAL_LEDGER_EXPORT = "/api/v1/reports/general-ledger/export"
JOURNALS = "/api/v1/journal-entries"

OPENING_DATE = date(2025, 1, 15)
PERIOD_START = date(2025, 2, 1)
PERIOD_END = date(2025, 2, 28)


def _line(account: str, *, debit: str = "0", credit: str = "0") -> dict:
    return {"accountCode": account, "debitAmount": debit, "creditAmount": credit}


async def _posted(client, headers, *, posting_date: date, lines: list[dict]) -> dict:
    created = await client.post(
        JOURNALS,
        headers=headers,
        json={
            "entryDate": posting_date.isoformat(),
            "postingDate": posting_date.isoformat(),
            "entryType": "MANUAL",
            "description": f"Export fixture {posting_date.isoformat()}",
            "lines": lines,
        },
    )
    assert created.status_code == 201, created.text
    journal = created.json()["data"]
    posted = await client.post(f"{JOURNALS}/{journal['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    return journal


async def _rows(response) -> list[list[str]]:
    assert response.status_code == 200, response.text
    return list(csv.reader(io.StringIO(response.text)))


async def _generate(client, headers, url: str, **body) -> dict:
    response = await client.post(url, headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _section(rows: list[list[str]], first_cell: str = "Account Code") -> tuple[list[str], list[list[str]], list[str]]:
    """Header, data rows and totals row from an exported report."""
    header_index = next(index for index, row in enumerate(rows) if row and row[0] == first_cell)
    header = rows[header_index]
    data: list[list[str]] = []
    for row in rows[header_index + 1 :]:
        if not row or row[0] == "Totals":
            break
        data.append(row)
    totals = next(row for row in rows if row and row[0] == "Totals")
    return header, data, totals


def _money(cell: str) -> Decimal:
    return Decimal(cell)


async def _standard_month(client, headers) -> None:
    await _posted(
        client, headers, posting_date=OPENING_DATE,
        lines=[_line("1100", debit="1000.0000"), _line("4010", credit="1000.0000")],
    )
    await _posted(
        client, headers, posting_date=date(2025, 2, 5),
        lines=[_line("1100", debit="300.0000"), _line("4010", credit="300.0000")],
    )
    await _posted(
        client, headers, posting_date=date(2025, 2, 10),
        lines=[_line("5010", debit="120.0000"), _line("1020", credit="120.0000")],
    )


async def test_trial_balance_export_contains_every_account_and_the_same_totals(client):
    headers = await login(client)
    await _standard_month(client, headers)
    body = {"fromDate": PERIOD_START.isoformat(), "toDate": PERIOD_END.isoformat()}

    report = await _generate(client, headers, TRIAL_BALANCE, **body)
    response = await client.post(TRIAL_BALANCE_EXPORT, headers=headers, json=body)
    rows = await _rows(response)

    assert response.headers["content-type"].startswith("text/csv")
    assert "trial-balance-" in response.headers["content-disposition"]
    assert rows[0] == ["Trial Balance"]
    assert any(row[0] == "Period" and row[1] == "2025-02-01 to 2025-02-28" for row in rows)
    assert any(row[0] == "Balanced" and row[1] == "yes" for row in rows)

    header, data, totals = _section(rows)
    assert header == [
        "Account Code", "Account Name", "Account Type",
        "Opening Debit", "Opening Credit", "Period Debit", "Period Credit",
        "Closing Debit", "Closing Credit",
    ]
    assert [row[0] for row in data] == [item["accountCode"] for item in report["items"]]
    assert len(data) == len(report["items"]) == 4

    # The footer is the report's own totals, in the same column order.
    assert [_money(cell) for cell in totals[3:]] == [
        _money(report["totals"][key])
        for key in (
            "openingDebit", "openingCredit", "periodDebit", "periodCredit", "closingDebit", "closingCredit"
        )
    ]
    assert _money(totals[3]) == _money(totals[4]) == Decimal("1000.0000")
    assert _money(totals[5]) == _money(totals[6]) == Decimal("420.0000")
    assert _money(totals[7]) == _money(totals[8]) == Decimal("1420.0000")


async def test_trial_balance_export_keeps_exact_four_decimal_amounts(client):
    headers = await login(client)
    await _posted(
        client, headers, posting_date=date(2025, 2, 6),
        lines=[_line("1100", debit="1234.5678"), _line("4010", credit="1234.5678")],
    )
    response = await client.post(
        TRIAL_BALANCE_EXPORT,
        headers=headers,
        json={"fromDate": PERIOD_START.isoformat(), "toDate": PERIOD_END.isoformat()},
    )
    _, data, _ = _section(await _rows(response))
    receivable = next(row for row in data if row[0] == "1100")
    assert receivable[5] == "1234.5678"
    assert receivable[7] == "1234.5678"


async def test_general_ledger_export_streams_every_row_not_one_page(client):
    headers = await login(client)
    # 120 two-line journals: more than one page, exported in a single file.
    for _ in range(120):
        await _posted(
            client, headers, posting_date=date(2025, 2, 1),
            lines=[_line("5010", debit="1.0000"), _line("1020", credit="1.0000")],
        )
    body = {"fromDate": PERIOD_START.isoformat(), "toDate": PERIOD_END.isoformat(), "accountCode": "5010"}
    page = await _generate(client, headers, GENERAL_LEDGER, **body, page=1, pageSize=10)
    assert len(page["items"]) == 10 and page["meta"]["total"] == 120

    rows = await _rows(await client.post(GENERAL_LEDGER_EXPORT, headers=headers, json=body))
    header, data, totals = _section(rows, "Posting Date")
    assert header[0] == "Posting Date" and "Running Balance" in header
    assert len(data) == 120 == page["meta"]["total"]
    # The running balance continues across the whole file: 1..120.
    assert _money(data[-1][header.index("Running Balance")]) == Decimal("120.0000")
    assert _money(totals[header.index("Debit")]) == Decimal("120.0000")
    assert _money(totals[header.index("Running Balance")]) == Decimal("120.0000")


async def test_general_ledger_export_totals_match_the_generated_report(client):
    headers = await login(client)
    await _standard_month(client, headers)
    body = {"fromDate": PERIOD_START.isoformat(), "toDate": PERIOD_END.isoformat(), "accountCode": "1100"}

    report = await _generate(client, headers, GENERAL_LEDGER, **body)
    rows = await _rows(await client.post(GENERAL_LEDGER_EXPORT, headers=headers, json=body))
    header, data, totals = _section(rows, "Posting Date")

    assert len(data) == report["meta"]["total"] == 1
    assert _money(totals[header.index("Debit")]) == _money(report["totals"]["debit"]) == Decimal("300.0000")
    assert _money(totals[header.index("Credit")]) == _money(report["totals"]["credit"]) == Decimal("0.0000")
    assert _money(totals[header.index("Running Balance")]) == _money(report["totals"]["closingBalance"])
    assert any(row[0] == "Opening balance" and _money(row[1]) == Decimal("1000.0000") for row in rows)
    # The row carries the opening balance forward, exactly as the screen does.
    assert _money(data[0][header.index("Running Balance")]) == Decimal("1300.0000")


async def test_export_honours_the_column_selection_and_rejects_unknown_columns(client):
    headers = await login(client)
    await _standard_month(client, headers)
    body = {
        "fromDate": PERIOD_START.isoformat(),
        "toDate": PERIOD_END.isoformat(),
        "fields": ["accountCode", "periodDebit"],
    }
    rows = await _rows(await client.post(TRIAL_BALANCE_EXPORT, headers=headers, json=body))
    header, data, totals = _section(rows)
    assert header == ["Account Code", "Period Debit"]
    # Report order is preserved, not request order.
    bank = next(row for row in data if row[0] == "1020")
    assert bank == ["1020", "0.0000"]
    assert totals == ["Totals", "420.0000"]

    refused = await client.post(
        TRIAL_BALANCE_EXPORT, headers=headers, json={**body, "fields": ["accountCode", "notAColumn"]}
    )
    assert refused.status_code == 422, refused.text
    assert "fields" in refused.json()["field_errors"]


async def test_export_neutralises_formula_injection_in_text_cells(client):
    headers = await login(client)
    # A line description is free text the export writes into a spreadsheet cell.
    await _posted(
        client, headers, posting_date=date(2025, 2, 7),
        lines=[
            _line("5010", debit="10.0000"),
            {"accountCode": "1020", "debitAmount": "0", "creditAmount": "10.0000",
             "description": "=cmd|' /C calc'!A0"},
        ],
    )
    rows = await _rows(
        await client.post(
            GENERAL_LEDGER_EXPORT,
            headers=headers,
            json={
                "fromDate": PERIOD_START.isoformat(),
                "toDate": PERIOD_END.isoformat(),
                "fields": ["description", "debit", "credit"],
            },
        )
    )
    _, data, _ = _section(rows, "Description")
    descriptions = [row[0] for row in data]
    assert "'=cmd|' /C calc'!A0" in descriptions, descriptions
    for row in data:
        for cell in row:
            assert not cell.startswith(("=", "+", "@")), f"a cell would execute in a spreadsheet: {cell!r}"
    # Money cells keep their sign and are never prefixed.
    assert all(_money(cell) >= 0 for row in data for cell in row[1:] if cell)


async def test_csv_writer_neutralises_leading_formula_characters():
    from app.modules.reports import csv_export

    assert csv_export.text("=SUM(A1)") == "'=SUM(A1)"
    assert csv_export.text("+1") == "'+1"
    assert csv_export.text("@import") == "'@import"
    assert csv_export.text("\tcmd") == "'\tcmd"
    assert csv_export.text("Acme Shipping") == "Acme Shipping"
    # A number, including a negative amount, is data, not a formula.
    assert csv_export.text("-125.5000") == "-125.5000"
    assert csv_export.money("-125.5") == "-125.5000"
    assert csv_export.money(Decimal("1234.5678")) == "1234.5678"
    assert csv_export.money(None) == "0.0000"


async def test_export_requires_the_report_permission(client):
    admin = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=admin,
        json={"code": "EXPORT_DENIED", "name": "No Reports", "permissions": []},
    )
    assert role.status_code == 201, role.text
    created = await client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": "noexport",
            "email": "noexport@example.com",
            "displayName": "No Export",
            "password": "Passw0rd!",
            "roleCode": "EXPORT_DENIED",
        },
    )
    assert created.status_code == 201, created.text
    headers = await login(client, "noexport")
    for url in (TRIAL_BALANCE_EXPORT, GENERAL_LEDGER_EXPORT):
        denied = await client.post(url, headers=headers, json={})
        assert denied.status_code == 403, f"{url}: {denied.text}"


async def test_export_works_while_the_system_is_read_only(client):
    headers = await login(client)
    enabled = await client.patch(
        "/api/v1/settings/app-config", headers=headers, json={"system": {"readOnlyMode": True}}
    )
    assert enabled.status_code == 200, enabled.text
    response = await client.post(
        TRIAL_BALANCE_EXPORT, headers=headers, json={"fromDate": PERIOD_START.isoformat()}
    )
    assert response.status_code == 200, response.text
    assert response.text.startswith("Trial Balance")
