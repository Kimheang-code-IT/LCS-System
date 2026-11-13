"""Accounting controls for authoritative web financial projections."""
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.finance.models import FinancialDocumentAllocation
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def entry(client, headers, kind, amount, day, **extra):
    parties = (await client.get("/api/v1/businessParties", headers=headers)).json()["data"]["items"]
    response = await client.post("/api/v1/financial-documents", headers=headers, json={
        "documentType": kind, "partyId": parties[0]["id"], "date": day.isoformat(), "currency": "USD",
        "lines": [{"description": "Audit control", "quantity": 1, "unitPrice": amount}], **extra,
    })
    assert response.status_code == 201, response.text
    item = response.json()["data"]
    posted = await client.post(f"/api/v1/financial-documents/{item['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    return item


async def report(client, headers, key, **filters):
    response = await client.post(f"/api/v1/reports/financial/{key}", headers=headers, json=filters)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_invoice_receipt_credit_reconcile_ar_and_do_not_double_revenue(client):
    headers = await login(client)
    today = date.today()
    invoice = await entry(client, headers, "CUSTOMER_INVOICE", 100, today)
    receipt = await entry(client, headers, "CUSTOMER_RECEIPT", 40, today)
    await entry(client, headers, "CREDIT_NOTE", 10, today)
    ar = await report(client, headers, "accounts-receivable")
    assert ar["totals"]["baseOutstanding"] == ar["totals"]["controlBalance"] == 50
    assert ar["totals"]["difference"] == 0
    allocated = await client.post(f"/api/v1/financial-documents/{receipt['id']}/allocate", headers=headers,
        json={"target_document_id": invoice["id"], "amount": 40})
    assert allocated.status_code == 200, allocated.text
    ar = await report(client, headers, "accounts-receivable")
    assert ar["totals"]["difference"] == 0 and ar["totals"]["baseOutstanding"] == 50
    profit = await report(client, headers, "profit-loss")
    assert profit["totals"]["revenue"] == 90
    assert profit["totals"]["net"] == 90


async def test_ar_aging_buckets_follow_the_cutoff_and_due_date(client):
    headers = await login(client)
    today = date.today()
    overdue = await entry(client, headers, "CUSTOMER_INVOICE", 100, today - timedelta(days=60),
        dueDate=(today - timedelta(days=45)).isoformat())
    current = await entry(client, headers, "CUSTOMER_INVOICE", 50, today)
    ar = await report(client, headers, "accounts-receivable")
    rows = {row["id"]: row for row in ar["items"]}
    assert rows[overdue["id"]]["agingBucket"] == "31-60"
    assert rows[current["id"]]["agingBucket"] == "Current"


async def test_supplier_credit_and_partial_payment_reconcile_ap(client):
    headers = await login(client)
    today = date.today()
    bill = await entry(client, headers, "SUPPLIER_BILL", 100, today)
    payment = await entry(client, headers, "SUPPLIER_PAYMENT", 30, today)
    await entry(client, headers, "SUPPLIER_CREDIT_NOTE", 20, today)
    allocated = await client.post(f"/api/v1/financial-documents/{payment['id']}/allocate", headers=headers,
        json={"target_document_id": bill["id"], "amount": 30})
    assert allocated.status_code == 200, allocated.text
    ap = await report(client, headers, "accounts-payable")
    assert ap["totals"]["baseOutstanding"] == ap["totals"]["controlBalance"] == 50
    assert ap["totals"]["difference"] == 0


async def test_cutoff_keeps_pre_reversal_allocation_history(client, session_factory):
    headers = await login(client)
    # Reversal timestamps are UTC; derive dates from the same clock so a
    # midnight local/UTC crossing cannot shift the cutoff.
    today = datetime.now(UTC).date()
    earlier = today-timedelta(days=2)
    cutoff = today-timedelta(days=1)
    invoice = await entry(client, headers, "CUSTOMER_INVOICE", 100, earlier)
    receipt = await entry(client, headers, "CUSTOMER_RECEIPT", 40, earlier)
    allocated = await client.post(f"/api/v1/financial-documents/{receipt['id']}/allocate", headers=headers,
        json={"target_document_id": invoice["id"], "amount": 40})
    assert allocated.status_code == 200, allocated.text
    async with session_factory() as session:
        allocation = (await session.scalars(select(FinancialDocumentAllocation))).one()
        allocation.allocated_at = datetime.combine(earlier, datetime.min.time(), tzinfo=UTC)
        await session.commit()
    reversed_doc = await client.post(f"/api/v1/financial-documents/{receipt['id']}/reverse", headers=headers, json={"reason": "Audit reversal"})
    assert reversed_doc.status_code in (200, 201), reversed_doc.text
    async with session_factory() as session:
        allocation = (await session.scalars(select(FinancialDocumentAllocation))).one()
        assert allocation.reversed_at is not None and allocation.target_amount == 40
    historic = await report(client, headers, "accounts-receivable", toDate=cutoff.isoformat())
    old_invoice = next(row for row in historic["items"] if row["id"] == invoice["id"])
    assert old_invoice["outstanding"] == 60
    assert historic["totals"]["difference"] == 0
    current = await report(client, headers, "accounts-receivable")
    assert current["totals"]["baseOutstanding"] == 100 and current["totals"]["difference"] == 0


async def test_balance_sheet_includes_openings_and_unclosed_earnings(client):
    headers = await login(client)
    today = date.today()
    await entry(client, headers, "CUSTOMER_INVOICE", 100, today-timedelta(days=2))
    balance = await report(client, headers, "balance-sheet", fromDate=today.isoformat(), toDate=today.isoformat())
    assert balance["totals"]["assets"] == balance["totals"]["unclosedEarnings"] == 100
    assert balance["totals"]["difference"] == 0
    assert balance["groups"][2]["total"] == 100


async def test_cash_opening_net_closing_and_internal_transfers(client):
    headers = await login(client)
    today = date.today()
    await entry(client, headers, "CUSTOMER_RECEIPT", 100, today-timedelta(days=1))
    await entry(client, headers, "CUSTOMER_RECEIPT", 50, today)
    await entry(client, headers, "TRANSFER", 20, today)
    cash = await report(client, headers, "cash-flow", fromDate=today.isoformat(), toDate=today.isoformat())
    assert cash["totals"] == {"openingCash": 100, "inflow": 50, "outflow": 0, "net": 50, "closingCash": 150, "difference": 0}
    assert cash["meta"]["classificationSupported"] is False


async def test_foreign_currency_revenue_is_displayed_in_base_currency(client):
    headers = await login(client)
    await entry(client, headers, "CUSTOMER_INVOICE", 100000, date.today(), currency="KHR", exchangeRate="0.00025")
    income = await report(client, headers, "revenue-expense", currencies=["KHR"])
    assert income["totals"]["revenue"] == 25
    assert income["items"][0]["revenue"] == 25
    assert income["items"][0]["currency"] == "USD"
    assert income["items"][0]["documentCurrency"] == "KHR"
