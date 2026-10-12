from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _service_order(client, headers, amount: float = 1250) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Automated Finance Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": amount,
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert quotation.status_code == 201, quotation.text
    revision_id = quotation.json()["data"]["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})).status_code == 200
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    return converted.json()["data"]["serviceOrderId"]


async def _charge(client, headers, service_order_id: str, *, fee_type_id: str | None = None) -> dict:
    line = {"description": "Automated freight", "quantity": 2, "unitPrice": 50, "tax": 10}
    if fee_type_id is not None:
        line["feeTypeId"] = fee_type_id
    response = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": [line],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_issued_charge_automatically_creates_one_draft_invoice_and_report(client):
    headers = await login(client)
    service_order_id = await _service_order(client, headers)
    charge = await _charge(client, headers, service_order_id)

    issued = await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})
    assert issued.status_code == 200, issued.text
    issued_data = issued.json()["data"]
    document_id = issued_data["financialDocumentId"]

    document = await client.get(f"/api/v1/financial-documents/{document_id}", headers=headers)
    assert document.status_code == 200, document.text
    assert document.json()["data"]["status"] == "Draft"
    assert document.json()["data"]["total"] == pytest.approx(110)

    # Both commands are idempotent and resolve to the automatically generated draft.
    repeated = await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})
    converted = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice",
        headers=headers,
        json={},
    )
    assert repeated.json()["data"]["financialDocumentId"] == document_id
    assert converted.json()["data"]["id"] == document_id

    report = await client.get("/api/v1/reports/profitability", headers=headers)
    row = next(item for item in report.json()["data"] if item["id"] == service_order_id)
    assert row["quoted"] == pytest.approx(1250)
    assert row["serviceCharges"] == pytest.approx(110)
    assert row["draftRevenue"] == pytest.approx(110)
    assert row["postedRevenue"] == 0
    assert row["uninvoicedCharges"] == 0

    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    report = await client.get("/api/v1/reports/profitability", headers=headers)
    row = next(item for item in report.json()["data"] if item["id"] == service_order_id)
    assert row["draftRevenue"] == 0
    assert row["postedRevenue"] == pytest.approx(110)
    assert row["grossProfit"] == pytest.approx(110)
    assert row["margin"] == pytest.approx(100)

    ledger = await client.get("/api/v1/reports/ledger-lines", headers=headers)
    assert ledger.status_code == 200, ledger.text
    lines = [line for line in ledger.json()["data"] if line["serviceOrderId"] == int(service_order_id)]
    assert sum(line["debit"] for line in lines) == pytest.approx(110)
    assert sum(line["credit"] for line in lines) == pytest.approx(110)
    assert {line["jobNo"] for line in lines} == {row["jobNo"]}


async def test_service_charge_validation_and_issued_immutability(client):
    headers = await login(client)
    service_order_id = await _service_order(client, headers)
    invalid = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={"lines": [{"description": "Invalid", "quantity": -1, "unitPrice": 10}]},
    )
    assert invalid.status_code == 422

    charge = await _charge(client, headers, service_order_id)
    draft_conversion = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice", headers=headers, json={}
    )
    assert draft_conversion.status_code == 409
    assert (await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})).status_code == 200
    changed = await client.put(
        f"/api/v1/service-charges/{charge['id']}",
        headers=headers,
        json={"lines": [{"description": "Changed", "quantity": 1, "unitPrice": 1}]},
    )
    assert changed.status_code == 409


async def test_fee_specific_posting_rule_drives_automatic_invoice_journal(client):
    headers = await login(client)
    fee_type = await client.post(
        "/api/v1/feeTypes",
        headers=headers,
        json={"code": "AUTO-FEE", "name": "Automated Finance Fee", "status": "Active"},
    )
    assert fee_type.status_code == 201, fee_type.text
    fee_type_id = fee_type.json()["data"]["id"]

    rule = await client.post(
        "/api/v1/posting-rules",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "feeTypeId": fee_type_id,
            "debitAccount": "1100",
            "creditAccount": "4020",
            "status": "ACTIVE",
        },
    )
    assert rule.status_code == 201, rule.text

    service_order_id = await _service_order(client, headers)
    charge = await _charge(client, headers, service_order_id, fee_type_id=fee_type_id)
    issued = await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})
    document_id = issued.json()["data"]["financialDocumentId"]
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    journals = await client.get("/api/v1/journal-entries", headers=headers)
    journal = next(
        item for item in journals.json()["data"]["items"] if item["sourceDocumentId"] == document_id
    )
    credit_codes = {line["account_code"] for line in journal["lines"] if line["credit_amount"] > 0}
    assert "4020" in credit_codes
    assert journal["debitTotal"] == journal["creditTotal"]


async def test_manual_journal_rejects_two_sided_and_negative_lines(client):
    headers = await login(client)
    for line in (
        {"accountCode": "1010", "debitAmount": 10, "creditAmount": 10},
        {"accountCode": "1010", "debitAmount": -10, "creditAmount": 0},
    ):
        response = await client.post(
            "/api/v1/journal-entries",
            headers=headers,
            json={"entryDate": date.today().isoformat(), "lines": [line]},
        )
        assert response.status_code == 422, response.text
