"""Reporting values that must reflect real posted data.

Two defects are pinned here:

1. ``cashBankBalance`` was a hardcoded ``0.0``, so the dashboard's cash card read
   zero even after a receipt or payment had been posted. It is now derived from
   the posted ledger lines of the accounts the administrator mapped in
   ``financial_accounts``.

2. ``GET /service-orders/{id}/invoice`` looked only for a ``SERVICE_ORDER`` source
   record, but issuing a charge creates the invoice with a ``SERVICE_ORDER_CHARGE``
   source. The lookup therefore reported "no invoice" for a document that existed,
   and the create path raised a misleading "already invoiced" error.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _service_order(client, headers, amount: float = 300) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Reporting Correctness Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": amount,
        },
    )
    assert quotation.status_code == 201, quotation.text
    revision_id = quotation.json()["data"]["revisionId"]
    assert (
        await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    ).status_code == 200
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    return converted.json()["data"]["serviceOrderId"]


async def _dashboard_summary(client, headers) -> dict:
    response = await client.get(
        "/api/v1/reports/dashboard", headers=headers, params={"granularity": "year"}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["summary"]


async def test_cash_and_bank_balance_reflects_posted_receipts(client):
    headers = await login(client)
    before = (await _dashboard_summary(client, headers))["cashBankBalance"]

    financial_accounts = await client.get(
        "/api/v1/financial-accounts", headers=headers, params={"page_size": 200}
    )
    assert financial_accounts.status_code == 200, financial_accounts.text
    bank = next(
        row for row in financial_accounts.json()["data"]["items"] if row["currency"] == "USD"
    )

    party = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = party.json()["data"]["items"][0]["id"]

    # A posted customer receipt debits the bank account, so cash goes up.
    receipt = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_RECEIPT",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "financialAccountId": bank["id"],
            "lines": [{"description": "Deposit", "quantity": 1, "unitPrice": 500}],
        },
    )
    assert receipt.status_code == 201, receipt.text
    posted = await client.post(
        f"/api/v1/financial-documents/{receipt.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 200, posted.text

    after = (await _dashboard_summary(client, headers))["cashBankBalance"]
    assert after == before + 500, f"expected the posted receipt to raise cash by 500, got {after - before}"


async def test_cash_and_bank_balance_ignores_draft_documents(client):
    """A draft is not posted, so it must not move the balance."""
    headers = await login(client)
    before = (await _dashboard_summary(client, headers))["cashBankBalance"]

    financial_accounts = await client.get(
        "/api/v1/financial-accounts", headers=headers, params={"page_size": 200}
    )
    bank = financial_accounts.json()["data"]["items"][0]
    party = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = party.json()["data"]["items"][0]["id"]

    draft = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_RECEIPT",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "financialAccountId": bank["id"],
            "lines": [{"description": "Draft deposit", "quantity": 1, "unitPrice": 400}],
        },
    )
    assert draft.status_code == 201, draft.text

    after = (await _dashboard_summary(client, headers))["cashBankBalance"]
    assert after == before, "an unposted document must not affect the cash balance"


async def test_service_order_invoice_is_found_after_issuing_a_charge(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)

    charge = await client.post(
        f"/api/v1/service-orders/{order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 250}],
        },
    )
    assert charge.status_code == 201, charge.text

    issued = await client.post(
        f"/api/v1/service-charges/{charge.json()['data']['id']}/issue", headers=headers, json={}
    )
    assert issued.status_code == 200, issued.text
    invoice_id = issued.json()["data"]["financialDocumentId"]

    # The order-level lookup must see the invoice the charge produced.
    found = await client.get(f"/api/v1/service-orders/{order_id}/invoice", headers=headers)
    assert found.status_code == 200, found.text
    assert found.json()["data"] is not None, "the invoice created by the charge must be reachable"
    assert found.json()["data"]["id"] == invoice_id


async def test_trial_balance_reconciles_against_posted_data(client):
    """The control that proves the ledger balances: debit equals credit, net zero."""
    headers = await login(client)
    party = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = party.json()["data"]["items"][0]["id"]

    before = await client.get("/api/v1/reports/trial-balance", headers=headers)
    assert before.status_code == 200, before.text
    before_data = before.json()["data"]
    assert before_data["totals"]["difference"] == 0
    assert before_data["balanced"] is True

    # Post a real invoice: debit receivables, credit revenue, plus tax.
    invoice = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 2, "unitPrice": 125, "taxRate": 10}],
        },
    )
    assert invoice.status_code == 201, invoice.text
    posted = await client.post(
        f"/api/v1/financial-documents/{invoice.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 200, posted.text

    after = await client.get("/api/v1/reports/trial-balance", headers=headers)
    assert after.status_code == 200, after.text
    data = after.json()["data"]

    assert data["balanced"] is True, "the ledger must still balance after a posting"
    assert data["totals"]["difference"] == 0
    assert data["totals"]["debit"] == data["totals"]["credit"]

    # The posting must appear, and the increase must be symmetric on both sides.
    delta_debit = round(data["totals"]["debit"] - before_data["totals"]["debit"], 4)
    delta_credit = round(data["totals"]["credit"] - before_data["totals"]["credit"], 4)
    assert delta_debit == delta_credit == 275.0, (
        f"2 x 125 plus 10% tax is 275 on each side, got debit {delta_debit} credit {delta_credit}"
    )

    receivable = next(row for row in data["items"] if row["accountCode"] == "1100")
    assert receivable["debit"] >= 275.0, "the invoice must debit receivables"


async def test_trial_balance_ignores_draft_and_double_counts_no_reversal(client):
    headers = await login(client)
    party = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = party.json()["data"]["items"][0]["id"]

    draft = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "lines": [{"description": "Draft freight", "quantity": 1, "unitPrice": 900}],
        },
    )
    assert draft.status_code == 201, draft.text

    baseline = (await client.get("/api/v1/reports/trial-balance", headers=headers)).json()["data"]
    assert baseline["balanced"] is True

    posted = await client.post(
        f"/api/v1/financial-documents/{draft.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 200, posted.text
    after_post = (await client.get("/api/v1/reports/trial-balance", headers=headers)).json()["data"]

    reversed_document = await client.post(
        f"/api/v1/financial-documents/{draft.json()['data']['id']}/reverse",
        headers=headers,
        json={"reason": "Trial balance control"},
    )
    assert reversed_document.status_code == 201, reversed_document.text
    after_reversal = (await client.get("/api/v1/reports/trial-balance", headers=headers)).json()["data"]

    # Posting moved both sides by 900; the reversal adds an equal and opposite
    # journal, so both sides grow again by 900 and the net returns to the baseline.
    assert round(after_post["totals"]["debit"] - baseline["totals"]["debit"], 4) == 900.0
    assert round(after_reversal["totals"]["debit"] - after_post["totals"]["debit"], 4) == 900.0
    assert after_reversal["balanced"] is True
    assert after_reversal["totals"]["difference"] == 0

    # Net balances cancel: every account's signed balance is back where it started.
    baseline_net = round(sum(row["balance"] for row in baseline["items"]), 4)
    reversal_net = round(sum(row["balance"] for row in after_reversal["items"]), 4)
    assert reversal_net == baseline_net, "a full reversal must return each account to its prior balance"


async def test_profit_loss_reports_posted_revenue_and_expense(client):
    headers = await login(client)
    party = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = party.json()["data"]["items"][0]["id"]

    before = (await client.get("/api/v1/reports/profit-loss", headers=headers)).json()["data"]

    invoice = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 400}],
        },
    )
    assert invoice.status_code == 201, invoice.text
    posted = await client.post(
        f"/api/v1/financial-documents/{invoice.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 200, posted.text

    after = (await client.get("/api/v1/reports/profit-loss", headers=headers)).json()["data"]

    assert round(after["revenue"] - before["revenue"], 4) == 400.0, "the invoice must add 400 revenue"
    # Revenue is credit-normal, so it must read as a positive number.
    assert after["revenue"] > 0
    assert after["net"] == round(after["revenue"] - after["expense"], 4)
    assert any(row["amount"] > 0 for row in after["revenueAccounts"])


async def test_balance_sheet_satisfies_the_accounting_identity(client):
    """Assets must equal liabilities + equity + the current net result."""
    headers = await login(client)
    party = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = party.json()["data"]["items"][0]["id"]

    draft = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 600, "taxRate": 10}],
        },
    )
    assert draft.status_code == 201, draft.text
    assert (
        await client.post(
            f"/api/v1/financial-documents/{draft.json()['data']['id']}/post", headers=headers, json={}
        )
    ).status_code == 200

    sheet = (await client.get("/api/v1/reports/balance-sheet", headers=headers)).json()["data"]

    assert sheet["balanced"] is True, (
        f"assets {sheet['assets']} must equal liabilities+equity+net {sheet['liabilitiesAndEquity']} "
        f"(difference {sheet['difference']})"
    )
    assert sheet["difference"] == 0
    # The document debits receivables, so assets must have grown.
    assert sheet["assets"] >= 660.0, sheet


async def test_cash_flow_matches_the_dashboard_cash_balance(client):
    """Both read the same account mapping, so they cannot disagree."""
    headers = await login(client)
    party = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = party.json()["data"]["items"][0]["id"]

    financial_accounts = await client.get(
        "/api/v1/financial-accounts", headers=headers, params={"page_size": 200}
    )
    bank = financial_accounts.json()["data"]["items"][0]

    receipt = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_RECEIPT",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "financialAccountId": bank["id"],
            "lines": [{"description": "Deposit", "quantity": 1, "unitPrice": 750}],
        },
    )
    assert receipt.status_code == 201, receipt.text
    assert (
        await client.post(
            f"/api/v1/financial-documents/{receipt.json()['data']['id']}/post", headers=headers, json={}
        )
    ).status_code == 200

    flow = (await client.get("/api/v1/reports/cash-flow", headers=headers)).json()["data"]
    summary = (
        await client.get("/api/v1/reports/dashboard", headers=headers, params={"granularity": "year"})
    ).json()["data"]["summary"]

    assert round(flow["closingBalance"], 4) == round(summary["cashBankBalance"], 4), (
        "the cash-flow closing balance and the dashboard cash card must agree"
    )
    assert flow["inflow"] >= 750.0
    # The identity the report is built on.
    assert round(flow["inflow"] - flow["outflow"], 4) == round(flow["net"], 4) == round(flow["closingBalance"], 4)


async def test_container_register_lists_containers_with_their_order_and_status(client):
    """Required operational report; containers must appear with their order."""
    headers = await login(client)
    order_id = await _service_order(client, headers)

    added = await client.post(
        f"/api/v1/service-orders/{order_id}/containers",
        headers=headers,
        json={"containerNumber": "REGU1234567", "containerType": "40HC", "status": "EXPECTED"},
    )
    assert added.status_code == 201, added.text

    report = await client.get("/api/v1/reports/container-register", headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()["data"]

    row = next(
        (item for item in data["items"] if item["containerNumber"] == "REGU1234567"), None
    )
    assert row is not None, f"the new container must appear in the register: {data['items']}"
    assert row["serviceOrderId"] == order_id
    assert row["serviceOrderNo"], "the register must carry the order number"
    assert row["status"] == "EXPECTED"
    assert row["containerType"], "the register must resolve the container type name"

    assert data["total"] == len(data["items"])
    statuses = {entry["status"]: entry["count"] for entry in data["byStatus"]}
    assert statuses.get("EXPECTED", 0) >= 1, statuses


async def test_order_invoice_endpoint_is_idempotent_after_charges_are_issued(client):
    """A satisfied order returns its invoice instead of a misleading error."""
    headers = await login(client)
    order_id = await _service_order(client, headers)

    charge = await client.post(
        f"/api/v1/service-orders/{order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 250}],
        },
    )
    assert charge.status_code == 201, charge.text
    issued = await client.post(
        f"/api/v1/service-charges/{charge.json()['data']['id']}/issue", headers=headers, json={}
    )
    assert issued.status_code == 200, issued.text
    invoice_id = issued.json()["data"]["financialDocumentId"]

    again = await client.post(f"/api/v1/service-orders/{order_id}/invoice", headers=headers, json={})
    assert again.status_code == 201, again.text
    assert again.json()["data"]["id"] == invoice_id, "the existing invoice must be returned, not duplicated"
