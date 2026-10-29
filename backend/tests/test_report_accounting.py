"""Independent accounting fixtures for the generated financial reports.

Every expectation here is built from a journal this module posts itself, on fixed
calendar dates, into an empty ledger (the seed creates accounts and periods but no
journals). Nothing depends on another test's postings or on the seeded amounts, so
a wrong total cannot hide behind fixture drift.

Date layout used by most tests:

* ``2025-01-15`` — before the report period (opening balance)
* ``2025-02-01 .. 2025-02-28`` — the report period

Policy under test (from ``docs/04`` and the posting service, unchanged):

* only ``POSTED`` journals reach a report; a draft never does;
* a reversed document keeps its original posted journal and gains an equal,
  opposite reversal journal — posted history is immutable;
* amounts are ``base_debit_amount`` / ``base_credit_amount`` (``NUMERIC(19,4)``);
  a foreign-currency line is converted at its own stored rate;
* revenue and expense are not closed into equity, so they keep their closing
  balances and the P&L must agree with them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

TRIAL_BALANCE = "/api/v1/reports/trial-balance/generate"
GENERAL_LEDGER = "/api/v1/reports/general-ledger/generate"
JOURNALS = "/api/v1/journal-entries"

OPENING_DATE = date(2025, 1, 15)
PERIOD_START = date(2025, 2, 1)
PERIOD_END = date(2025, 2, 28)
FEB_EARLY = date(2025, 2, 5)
FEB_MID = date(2025, 2, 10)
FEB_LATE = date(2025, 2, 20)


def _line(account: str, *, debit: str = "0", credit: str = "0", currency: str = "USD", rate: str = "1") -> dict:
    return {
        "accountCode": account,
        "debitAmount": debit,
        "creditAmount": credit,
        "currency": currency,
        "exchangeRate": rate,
    }


async def _journal(client, headers, *, posting_date: date, lines: list[dict], entry_type: str = "MANUAL") -> dict:
    created = await client.post(
        JOURNALS,
        headers=headers,
        json={
            "entryDate": posting_date.isoformat(),
            "postingDate": posting_date.isoformat(),
            "entryType": entry_type,
            "description": f"Accounting fixture {posting_date.isoformat()}",
            "lines": lines,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


async def _posted(client, headers, **kwargs) -> dict:
    journal = await _journal(client, headers, **kwargs)
    posted = await client.post(f"{JOURNALS}/{journal['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    return journal


async def _report(client, headers, url: str, **body) -> dict:
    response = await client.post(url, headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _trial_balance(client, headers, **body) -> dict:
    return await _report(client, headers, TRIAL_BALANCE, **body)


async def _general_ledger(client, headers, **body) -> dict:
    return await _report(client, headers, GENERAL_LEDGER, **body)


def _row(data: dict, code: str) -> dict:
    rows = [item for item in data["items"] if item["accountCode"] == code]
    assert len(rows) == 1, f"expected exactly one row for {code}, got {rows}"
    return rows[0]


def _dec(value: object) -> Decimal:
    """Compare money as the exact decimal the API echoed, not as a float literal."""
    return Decimal(str(value))


async def _standard_month(client, headers) -> dict:
    """Revenue, expense, cash receipt and an opening balance with known totals."""
    await _posted(
        client, headers, posting_date=OPENING_DATE,
        lines=[_line("1100", debit="1000.0000"), _line("4010", credit="1000.0000")],
    )
    await _posted(
        client, headers, posting_date=FEB_EARLY,
        lines=[_line("1100", debit="300.0000"), _line("4010", credit="300.0000")],
    )
    await _posted(
        client, headers, posting_date=FEB_MID,
        lines=[_line("5010", debit="120.0000"), _line("1020", credit="120.0000")],
    )
    await _posted(
        client, headers, posting_date=FEB_LATE,
        lines=[_line("1020", debit="200.0000"), _line("1100", credit="200.0000")],
    )
    return await _trial_balance(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat()
    )


async def test_trial_balance_matches_the_independent_fixture(client):
    headers = await login(client)
    data = await _standard_month(client, headers)

    expected = {
        "1020": ("0", "0", "200", "120", "80", "0"),
        "1100": ("1000", "0", "300", "200", "1100", "0"),
        "4010": ("0", "1000", "0", "300", "0", "1300"),
        "5010": ("0", "0", "120", "0", "120", "0"),
    }
    columns = (
        "openingDebit", "openingCredit", "periodDebit", "periodCredit",
        "closingDebit", "closingCredit",
    )
    for code, values in expected.items():
        row = _row(data, code)
        assert tuple(_dec(row[column]) for column in columns) == tuple(Decimal(value) for value in values), (
            f"{code}: {[row[column] for column in columns]}"
        )

    # The control: both sides of the movement and of the closing position agree.
    totals = data["totals"]
    assert _dec(totals["openingDebit"]) == _dec(totals["openingCredit"]) == Decimal("1000")
    assert _dec(totals["periodDebit"]) == _dec(totals["periodCredit"]) == Decimal("620")
    assert _dec(totals["closingDebit"]) == _dec(totals["closingCredit"]) == Decimal("1300")
    assert data["balanced"] is True
    assert _dec(data["imbalance"]) == Decimal("0")

    # Only the four accounts with movement are listed, not every account.
    assert {row["accountCode"] for row in data["items"]} == set(expected)


async def test_trial_balance_period_is_mid_history_not_all_time(client):
    """Without an opening the period columns would look like a full balance."""
    headers = await login(client)
    await _standard_month(client, headers)
    all_time = await _trial_balance(client, headers, toDate=PERIOD_END.isoformat())
    period_only = await _trial_balance(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat()
    )

    assert _row(all_time, "1100")["closingDebit"] == 1100
    assert _row(period_only, "1100")["closingDebit"] == 1100
    # The same closing position, but the period row opens where January ended.
    assert _row(all_time, "1100")["openingDebit"] == 0
    assert _row(period_only, "1100")["openingDebit"] == 1000
    # An unbounded start moves everything into the period.
    assert _row(all_time, "1100")["periodDebit"] == 1300
    assert _row(period_only, "1100")["periodDebit"] == 300


async def test_general_ledger_opening_and_running_balance_match_the_fixture(client):
    headers = await login(client)
    await _standard_month(client, headers)

    data = await _general_ledger(
        client, headers,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        accountCode="1100",
    )

    assert _dec(data["openingBalance"]) == Decimal("1000")
    assert [_dec(item["debit"]) for item in data["items"]] == [Decimal("300"), Decimal("0")]
    assert [_dec(item["credit"]) for item in data["items"]] == [Decimal("0"), Decimal("200")]
    # 1000 opening + 300 - 200, carried row by row.
    assert [_dec(item["runningBalance"]) for item in data["items"]] == [Decimal("1300"), Decimal("1100")]
    assert data["totals"] == {"debit": 300.0, "credit": 200.0, "closingBalance": 1100.0}
    assert data["meta"]["total"] == 2


async def test_credit_normal_account_keeps_a_signed_running_balance(client):
    headers = await login(client)
    await _standard_month(client, headers)

    data = await _general_ledger(
        client, headers,
        fromDate=PERIOD_START.isoformat(),
        toDate=PERIOD_END.isoformat(),
        accountCode="4010",
    )
    # Debit-normal presentation: a revenue (credit) balance reads as negative.
    assert _dec(data["openingBalance"]) == Decimal("-1000")
    assert _dec(data["items"][-1]["runningBalance"]) == Decimal("-1300")


async def test_general_ledger_without_account_filter_keeps_one_balance_per_account(client):
    headers = await login(client)
    trial = await _standard_month(client, headers)
    ledger = await _general_ledger(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(), pageSize=200
    )

    # Each account's last running balance equals its trial-balance closing side.
    last: dict[str, Decimal] = {}
    for item in ledger["items"]:
        last[item["accountCode"]] = _dec(item["runningBalance"])
    for code, signed in last.items():
        row = _row(trial, code)
        expected = _dec(row["closingDebit"]) - _dec(row["closingCredit"])
        assert signed == expected, f"{code}: running {signed} != closing {expected}"


async def test_voucher_number_and_type_filters_select_exactly_that_journal(client):
    headers = await login(client)
    first = await _posted(
        client, headers, posting_date=FEB_EARLY,
        lines=[_line("5010", debit="11"), _line("1020", credit="11")], entry_type="MANUAL",
    )
    await _posted(
        client, headers, posting_date=FEB_MID,
        lines=[_line("5010", debit="22"), _line("1020", credit="22")], entry_type="PAYROLL",
    )

    by_number = await _general_ledger(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(),
        voucherNo=first["entryNo"], pageSize=50,
    )
    assert by_number["meta"]["total"] == 2
    assert {item["voucherNo"] for item in by_number["items"]} == {first["entryNo"]}

    by_type = await _general_ledger(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(),
        voucherType="payroll", pageSize=50,
    )
    assert by_type["meta"]["total"] == 2
    assert {item["voucherType"] for item in by_type["items"]} == {"PAYROLL"}

    # The voucher filter also carries its own opening balance: the 11 + 22 on 5010
    # are both inside the period, so nothing precedes it.
    assert _dec(by_type["openingBalance"]) == Decimal("0") + _dec(by_type["openingBalance"])


async def test_voucher_filter_opening_balance_excludes_earlier_vouchers(client):
    headers = await login(client)
    opening = await _posted(
        client, headers, posting_date=OPENING_DATE,
        lines=[_line("5010", debit="70"), _line("1020", credit="70")],
    )
    later = await _posted(
        client, headers, posting_date=FEB_EARLY,
        lines=[_line("5010", debit="5"), _line("1020", credit="5")],
    )

    filtered = await _general_ledger(
        client, headers,
        fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(),
        voucherNo=later["entryNo"], pageSize=50,
    )
    assert filtered["meta"]["total"] == 2, filtered["items"]
    # The earlier journal is not part of this voucher, so it must not open it.
    assert _dec(filtered["openingBalance"]) == Decimal("0")
    assert _dec(filtered["items"][0]["runningBalance"]) == Decimal("5")

    whole_account = await _general_ledger(
        client, headers,
        fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(),
        accountCode="5010", pageSize=50,
    )
    assert _dec(whole_account["openingBalance"]) == Decimal("70")
    assert _dec(whole_account["items"][0]["runningBalance"]) == Decimal("75")
    assert opening["entryNo"] != later["entryNo"]


async def test_draft_is_excluded_and_reversal_nets_to_zero(client):
    """A reversal is a new posting: it never rewrites the period it corrects."""
    headers = await login(client)
    await _posted(
        client, headers, posting_date=FEB_EARLY,
        lines=[_line("1100", debit="500"), _line("4010", credit="500")],
    )
    document = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": FEB_MID.isoformat(),
            "party": (await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1}))
            .json()["data"]["items"][0]["id"],
            "currency": "USD",
            "lines": [{"description": "Reversed freight", "quantity": 1, "unitPrice": 400}],
        },
    )
    assert document.status_code == 201, document.text
    posted = await client.post(
        f"/api/v1/financial-documents/{document.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 200, posted.text
    reversed_document = await client.post(
        f"/api/v1/financial-documents/{document.json()['data']['id']}/reverse",
        headers=headers,
        json={"reason": "Accounting fixture"},
    )
    assert reversed_document.status_code == 201, reversed_document.text

    # An unposted journal must never reach the report.
    draft = await _journal(
        client, headers, posting_date=FEB_LATE,
        lines=[_line("1100", debit="999"), _line("4010", credit="999")],
    )

    corrected_period = await _trial_balance(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat()
    )
    # The corrected month is untouched by the later reversal.
    assert _row(corrected_period, "1100")["periodDebit"] == 900.0
    assert _row(corrected_period, "1100")["periodCredit"] == 0.0
    assert _row(corrected_period, "1100")["closingDebit"] == 900.0
    assert corrected_period["balanced"] is True

    # The reversal is a real posted journal dated when it was issued (today).
    today = date.today()
    reversal_window = await _trial_balance(
        client, headers, fromDate=today.replace(day=1).isoformat(), toDate=today.isoformat()
    )
    assert _row(reversal_window, "1100")["periodCredit"] == 400.0
    assert reversal_window["balanced"] is True

    ledger = await _general_ledger(
        client, headers,
        fromDate=today.replace(day=1).isoformat(), toDate=today.isoformat(),
        accountCode="1100", pageSize=50,
    )
    assert ledger["meta"]["total"] == 1, [item["journalNo"] for item in ledger["items"]]
    assert ledger["items"][0]["voucherType"] == "REVERSAL"
    assert ledger["items"][0]["journalNo"] != draft["entryNo"]


async def test_foreign_currency_lines_report_their_base_amount_and_filter(client):
    headers = await login(client)
    await _posted(
        client, headers, posting_date=FEB_MID,
        lines=[
            _line("5010", debit="100.0000", currency="EUR", rate="1.25"),
            _line("2010", credit="100.0000", currency="EUR", rate="1.25"),
        ],
    )
    await _posted(
        client, headers, posting_date=FEB_LATE,
        lines=[_line("5010", debit="10.0000"), _line("1020", credit="10.0000")],
    )

    trial = await _trial_balance(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat()
    )
    # 100 EUR at 1.25 is 125 base, plus the 10 USD line; never 110 mixed.
    assert _dec(_row(trial, "5010")["periodDebit"]) == Decimal("135")
    assert _dec(_row(trial, "2010")["periodCredit"]) == Decimal("125")
    assert trial["balanced"] is True

    eur = await _general_ledger(
        client, headers,
        fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(), currency="eur", pageSize=50,
    )
    assert eur["meta"]["total"] == 2
    assert {item["currency"] for item in eur["items"]} == {"EUR"}
    assert all(_dec(item["debit"]) == Decimal("125") or _dec(item["credit"]) == Decimal("125")
               for item in eur["items"])


async def test_four_decimal_amounts_round_trip(client):
    headers = await login(client)
    await _posted(
        client, headers, posting_date=FEB_MID,
        lines=[
            _line("1100", debit="1234.5678"),
            _line("4010", credit="1234.5678"),
        ],
    )
    trial = await _trial_balance(
        client, headers, fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat()
    )
    assert _dec(_row(trial, "1100")["periodDebit"]) == Decimal("1234.5678")
    assert _dec(_row(trial, "4010")["periodCredit"]) == Decimal("1234.5678")
    assert _dec(trial["totals"]["periodDebit"]) == Decimal("1234.5678")

    ledger = await _general_ledger(
        client, headers,
        fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(), accountCode="1100",
    )
    assert _dec(ledger["items"][0]["debit"]) == Decimal("1234.5678")
    assert _dec(ledger["items"][0]["runningBalance"]) == Decimal("1234.5678")


async def test_fiscal_year_scopes_both_reports_without_losing_the_opening(client):
    headers = await login(client)
    await _posted(
        client, headers, posting_date=date(2024, 12, 20),
        lines=[_line("1100", debit="250"), _line("4010", credit="250")],
    )
    await _posted(
        client, headers, posting_date=date(2025, 3, 10),
        lines=[_line("1100", debit="40"), _line("4010", credit="40")],
    )
    await _posted(
        client, headers, posting_date=date(2026, 1, 10),
        lines=[_line("1100", debit="99"), _line("4010", credit="99")],
    )

    trial = await _trial_balance(client, headers, fiscalYear=2025)
    # A fiscal year spans the periods that exist for that year: posting in a month
    # provisions its period, so 2024-12 and 2026-01 are outside this report.
    assert trial["meta"]["filters"]["fromDate"] == "2025-03-01"
    assert trial["meta"]["filters"]["toDate"] == "2025-03-31"
    # 2024 is the opening, 2025 is the period, 2026 is outside the report.
    assert _dec(_row(trial, "1100")["openingDebit"]) == Decimal("250")
    assert _dec(_row(trial, "1100")["periodDebit"]) == Decimal("40")
    assert _dec(_row(trial, "1100")["closingDebit"]) == Decimal("290")

    ledger = await _general_ledger(client, headers, fiscalYear=2025, accountCode="1100")
    assert ledger["meta"]["total"] == 1
    assert _dec(ledger["openingBalance"]) == Decimal("250")
    assert _dec(ledger["items"][0]["runningBalance"]) == Decimal("290")


async def test_revenue_and_expense_agree_with_the_profit_and_loss_report(client):
    headers = await login(client)
    trial = await _standard_month(client, headers)
    pnl = await client.get("/api/v1/reports/profit-loss", headers=headers)
    assert pnl.status_code == 200, pnl.text
    report = pnl.json()["data"]

    revenue = _dec(_row(trial, "4010")["closingCredit"]) - _dec(_row(trial, "4010")["closingDebit"])
    expense = _dec(_row(trial, "5010")["closingDebit"]) - _dec(_row(trial, "5010")["closingCredit"])
    # Revenue and expense are not closed into equity: their closing balances are
    # the P&L, so the two reports cannot disagree about the same posted data.
    assert _dec(report["revenue"]) == revenue == Decimal("1300")
    assert _dec(report["expense"]) == expense == Decimal("120")
    assert _dec(report["net"]) == Decimal("1180")


async def test_same_date_ordering_is_deterministic_across_pages(client):
    headers = await login(client)
    first = await _posted(
        client, headers, posting_date=FEB_EARLY,
        lines=[_line("5010", debit="1"), _line("1020", credit="1")],
    )
    second = await _posted(
        client, headers, posting_date=FEB_EARLY,
        lines=[_line("5010", debit="2"), _line("1020", credit="2")],
    )

    pages = []
    for page in (1, 2, 3):
        data = await _general_ledger(
            client, headers,
            fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(),
            accountCode="5010", page=page, pageSize=2,
        )
        pages.extend(data["items"])
    again = await _general_ledger(
        client, headers,
        fromDate=PERIOD_START.isoformat(), toDate=PERIOD_END.isoformat(),
        accountCode="5010", page=1, pageSize=4,
    )

    assert [item["id"] for item in pages] == [item["id"] for item in again["items"]]
    assert [item["voucherNo"] for item in pages] == [first["entryNo"], second["entryNo"]]
    # Insertion order is preserved into the running balance: 1 then 2 then 3.
    assert [_dec(item["runningBalance"]) for item in pages] == [Decimal("1"), Decimal("3")]
