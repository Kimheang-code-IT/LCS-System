"""Regression cases for the Finance audit's accounting and authorization boundaries."""
from datetime import date

import pytest
from sqlalchemy import delete

from app.modules.finance.models import PostingRule
from tests.conftest import login
from tests.test_job_finance_entries import _create_entry, _receipt, _service_order

pytestmark = pytest.mark.asyncio


async def test_allocation_replay_is_bound_to_payment_target_and_amount(client):
    headers = await login(client)
    order, party = await _service_order(client, headers)
    invoice = await _create_entry(client, headers, order, party, 100)
    await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    receipt = await _receipt(client, headers, order, party, 100)
    keyed = {**headers, "Idempotency-Key": "audit-allocation"}
    path = f"/api/v1/financial-documents/{receipt['id']}/allocate"
    payload = {"target_document_id": invoice["id"], "amount": 25}
    first = await client.post(path, headers=keyed, json=payload)
    assert first.status_code == 200, first.text
    replay = await client.post(path, headers=keyed, json=payload)
    assert replay.status_code == 200 and replay.json()["data"]["idempotentReplay"]
    changed = await client.post(path, headers=keyed, json={**payload, "amount": 20})
    assert changed.status_code == 409, changed.text
    different = await client.post(f"/api/v1/financial-documents/{invoice['id']}/allocate", headers=keyed, json=payload)
    assert different.status_code == 409, different.text


async def test_receipt_cannot_settle_supplier_bill(client):
    headers = await login(client)
    order, party = await _service_order(client, headers)
    bill = await _create_entry(client, headers, order, party, 100, "SUPPLIER_BILL")
    await client.post(f"/api/v1/financial-documents/{bill['id']}/post", headers=headers, json={})
    receipt = await _receipt(client, headers, order, party, 100)
    refused = await client.post(f"/api/v1/financial-documents/{receipt['id']}/allocate", headers=headers,
        json={"target_document_id": bill["id"], "amount": 10})
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "ALLOCATION_TYPE_MISMATCH"


async def test_selected_cash_account_owns_the_posted_receipt_ledger_line(client):
    headers = await login(client)
    order, party = await _service_order(client, headers)
    accounts = (await client.get("/api/v1/financial-accounts", headers=headers)).json()["data"]["items"]
    cash = next(row for row in accounts if row["ledgerCode"] == "1010")
    receipt = await client.post("/api/v1/financial-documents", headers=headers, json={
        "documentType": "CUSTOMER_RECEIPT", "partyId": party, "serviceOrderId": order,
        "date": date.today().isoformat(), "currency": "USD", "financialAccountId": cash["id"],
        "lines": [{"description": "Cash receipt", "quantity": 1, "unitPrice": 50}],
    })
    assert receipt.status_code == 201, receipt.text
    doc_id = receipt.json()["data"]["id"]
    posted = await client.post(f"/api/v1/financial-documents/{doc_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    detail = (await client.get(f"/api/v1/financial-documents/{doc_id}", headers=headers)).json()["data"]
    debit = [row for row in detail["journalEntries"] if row["debit"]]
    assert [(row["account"], row["debit"]) for row in debit] == [("1010", 50)]


async def test_missing_posting_rule_is_a_refusal_even_if_legacy_accounts_exist(client, session_factory):
    headers = await login(client)
    order, party = await _service_order(client, headers)
    invoice = await _create_entry(client, headers, order, party, 100)
    async with session_factory() as session:
        await session.execute(delete(PostingRule).where(PostingRule.document_type == "CUSTOMER_INVOICE"))
        await session.commit()
    refused = await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    assert refused.status_code == 422, refused.text
    detail = (await client.get(f"/api/v1/financial-documents/{invoice['id']}", headers=headers)).json()["data"]
    assert detail["status"] == "Draft" and not detail.get("journalId")


async def test_parent_selection_persists_and_cycle_is_refused(client):
    headers = await login(client)
    parent = await client.post("/api/v1/chart-of-accounts", headers=headers, json={
        "accountCode": "AUDIT-P", "accountName": "Parent", "accountType": "ASSET", "postable": False,
    })
    child = await client.post("/api/v1/chart-of-accounts", headers=headers, json={
        "accountCode": "AUDIT-C", "accountName": "Child", "accountType": "ASSET", "parentCode": "AUDIT-P",
    })
    assert child.status_code == 201, child.text
    assert str(child.json()["data"]["parentAccountId"]) == parent.json()["data"]["id"]
    refused = await client.put(f"/api/v1/chart-of-accounts/{parent.json()['data']['id']}", headers=headers,
        json={"parentCode": "AUDIT-C"})
    assert refused.status_code == 422, refused.text
