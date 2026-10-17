"""The Financial Documents module: type-driven fields, resolved accounts, live data.

Three product rules are pinned here, all of them driven by the document type:

* a settlement field (payment method, financial account, value date) belongs to a
  receipt or a payment, and a due date belongs to an invoice or a bill. The API
  ignores the rest whatever a client sends, so the field cannot exist on a document
  type that has no such step, no matter what a stale form posts back;
* a line's account code is resolved from the posting rules instead of being typed,
  and the detail payload says which account each line will post to;
* the detail payload carries what the tabs render — the party name, the service
  order number, the outstanding balance, the posted journal and the allocations —
  none of which used to be returned.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.modules.finance.models import FinancialAccount
from app.modules.finance.posting import ALLOCATABLE_TYPES
from app.modules.finance.service import DOCUMENT_TYPE_LABELS, PAYMENT_TYPES
from app.modules.master_data.models import BusinessParty
from tests.conftest import login


async def _party_and_account(session) -> tuple[int, str, int, str]:
    """The seeded customer and bank account the form would pick from Master Data."""
    party = (
        await session.execute(select(BusinessParty).where(BusinessParty.party_code == "CUST-001"))
    ).scalars().first()
    account = (
        await session.execute(select(FinancialAccount).where(FinancialAccount.account_name == "Bank Account"))
    ).scalars().first()
    return int(party.id), party.legal_name, int(account.id), account.account_name


async def _create(client, headers, payload: dict) -> dict:
    response = await client.post("/api/v1/financial-documents", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _detail(client, headers, document_id) -> dict:
    response = await client.get(f"/api/v1/financial-documents/{document_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _post(client, headers, document_id) -> None:
    response = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert response.status_code == 200, response.text


def _invoice_payload(party_id: int, **extra) -> dict:
    return {
        "documentType": "CUSTOMER_INVOICE",
        "date": "2026-03-01",
        "dueDate": "2026-03-31",
        "partyId": party_id,
        "currency": "USD",
        "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        **extra,
    }


async def test_a_receipt_keeps_its_settlement_fields(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, party_name, account_id, account_name = await _party_and_account(session)
    today = date.today().isoformat()

    created = await _create(client, headers, {
        "documentType": "CUSTOMER_RECEIPT",
        "date": today,
        "partyId": party_id,
        "currency": "USD",
        "paymentMethod": "Bank Transfer",
        "financialAccountId": account_id,
        "valueDate": today,
        "remark": "Deposit slip 42",
        "referenceNo": "REF-42",
        "lines": [{"description": "Received", "quantity": 1, "unitPrice": 250}],
    })
    detail = await _detail(client, headers, created["id"])

    assert detail["date"] == today
    assert detail["documentDate"] == today
    assert detail["customer"] == party_name
    assert detail["paymentMethod"] == "Bank Transfer"
    assert detail["financialAccountId"] == str(account_id)
    assert detail["financialAccount"] == account_name
    assert detail["valueDate"] == today
    assert detail["remark"] == "Deposit slip 42"
    assert detail["referenceNo"] == "REF-42"
    assert detail["vat"] == 0
    assert detail["outstanding"] == pytest.approx(250.0)


async def test_an_invoice_ignores_settlement_fields(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, account_id, _ = await _party_and_account(session)

    created = await _create(client, headers, _invoice_payload(
        party_id,
        # A form that switched type may still hold these; none of them may land on
        # a document type that does not settle money.
        paymentMethod="Cash",
        financialAccountId=account_id,
        valueDate="2026-03-02",
    ))
    detail = await _detail(client, headers, created["id"])

    assert detail["dueDate"] == "2026-03-31"
    assert detail["paymentMethod"] is None
    assert detail["financialAccountId"] is None
    assert detail["valueDate"] is None


async def test_a_receipt_ignores_a_due_date(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, _, _ = await _party_and_account(session)

    created = await _create(client, headers, {
        "documentType": "CUSTOMER_RECEIPT",
        "date": "2026-03-01",
        "dueDate": "2026-03-31",
        "partyId": party_id,
        "currency": "USD",
        "lines": [{"description": "Received", "quantity": 1, "unitPrice": 100}],
    })

    assert (await _detail(client, headers, created["id"]))["dueDate"] is None


async def test_an_unknown_document_type_is_rejected(client, session_factory, seeded):
    headers = await login(client)
    response = await client.post("/api/v1/financial-documents", headers=headers, json={
        "documentType": "NOT_A_TYPE",
        "date": date.today().isoformat(),
        "lines": [],
    })

    assert response.status_code == 422, response.text
    assert response.json()["field_errors"]["documentType"]


async def test_a_document_keeps_the_type_it_was_created_with(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, _, _ = await _party_and_account(session)
    created = await _create(client, headers, _invoice_payload(party_id))

    response = await client.put(f"/api/v1/financial-documents/{created['id']}", headers=headers, json={
        "documentType": "CUSTOMER_RECEIPT",
        "date": "2026-03-01",
        "partyId": party_id,
    })

    assert response.status_code == 422, response.text
    assert response.json()["field_errors"]["documentType"]
    assert (await _detail(client, headers, created["id"]))["documentType"] == "CUSTOMER_INVOICE"

    # A caller that sends no type keeps the stored one rather than being refused:
    # the number was allocated from this type's sequence either way.
    harmless = await client.put(f"/api/v1/financial-documents/{created['id']}", headers=headers, json={
        "date": "2026-03-01",
        "partyId": party_id,
        "referenceNo": "REF-KEEP",
    })
    assert harmless.status_code == 200, harmless.text
    assert harmless.json()["data"]["documentType"] == "CUSTOMER_INVOICE"
    assert harmless.json()["data"]["referenceNo"] == "REF-KEEP"


async def test_a_line_account_code_is_resolved_from_the_posting_rules(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, _, _ = await _party_and_account(session)
    created = await _create(client, headers, _invoice_payload(party_id))

    line = (await _detail(client, headers, created["id"]))["lines"][0]

    # Nothing is stored on the line: the rule in force at posting time decides, so a
    # draft never freezes an account the finance team has not confirmed.
    assert line["accountId"] is None
    # The seed's customer-invoice rule credits service revenue.
    assert line["accountCode"] == "4010"


async def test_a_line_may_pin_an_account_from_the_chart_of_accounts(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, _, _ = await _party_and_account(session)
    created = await _create(client, headers, _invoice_payload(
        party_id,
        lines=[{"description": "Other income", "quantity": 1, "unitPrice": 100, "accountCode": "4020"}],
    ))

    assert (await _detail(client, headers, created["id"]))["lines"][0]["accountCode"] == "4020"

    # The pin reaches the journal, which is the point of allowing it.
    await _post(client, headers, created["id"])
    accounts = {entry["account"] for entry in (await _detail(client, headers, created["id"]))["journalEntries"]}
    assert accounts == {"1100", "4020"}


async def test_a_line_cannot_name_an_unknown_account(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, _, _ = await _party_and_account(session)

    response = await client.post("/api/v1/financial-documents", headers=headers, json=_invoice_payload(
        party_id,
        lines=[{"description": "Freight", "quantity": 1, "unitPrice": 100, "accountCode": "9999"}],
    ))

    assert response.status_code == 422, response.text
    assert response.json()["field_errors"]["lines"]


async def test_a_posted_document_exposes_its_journal(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, _, _ = await _party_and_account(session)
    created = await _create(client, headers, _invoice_payload(party_id))

    await _post(client, headers, created["id"])
    detail = await _detail(client, headers, created["id"])

    assert detail["journalId"]
    assert detail["journalNo"]
    entries = detail["journalEntries"]
    assert {entry["account"] for entry in entries} == {"1100", "4010"}
    assert sum(entry["debit"] for entry in entries) == pytest.approx(sum(entry["credit"] for entry in entries))
    assert sum(entry["debit"] for entry in entries) == pytest.approx(100.0)


async def test_allocations_are_visible_from_both_documents(client, session_factory, seeded):
    headers = await login(client)
    async with session_factory() as session:
        party_id, party_name, _, _ = await _party_and_account(session)
    invoice = await _create(client, headers, _invoice_payload(party_id, lines=[
        {"description": "Freight", "quantity": 1, "unitPrice": 400},
    ]))
    receipt = await _create(client, headers, {
        "documentType": "CUSTOMER_RECEIPT",
        "date": "2026-03-05",
        "partyId": party_id,
        "currency": "USD",
        "lines": [{"description": "Received", "quantity": 1, "unitPrice": 400}],
    })
    await _post(client, headers, invoice["id"])
    await _post(client, headers, receipt["id"])

    allocation = await client.post(f"/api/v1/financial-documents/{receipt['id']}/allocate", headers=headers, json={
        "target_document_id": int(invoice["id"]),
        "amount": 150,
        "allocated_currency_code": "USD",
    })
    assert allocation.status_code == 200, allocation.text

    from_receipt = (await _detail(client, headers, receipt["id"]))["allocations"]
    assert len(from_receipt) == 1
    assert from_receipt[0]["targetDocumentNo"] == invoice["documentNo"]
    assert from_receipt[0]["amount"] == pytest.approx(150.0)
    assert from_receipt[0]["originalAmount"] == pytest.approx(400.0)
    assert from_receipt[0]["targetOutstanding"] == pytest.approx(250.0)
    assert from_receipt[0]["party"] == party_name

    # The same link read from the invoice side names the receipt as the counterpart.
    from_invoice = (await _detail(client, headers, invoice["id"]))["allocations"]
    assert [row["targetDocumentNo"] for row in from_invoice] == [receipt["documentNo"]]
    assert from_invoice[0]["targetOutstanding"] == pytest.approx(250.0)


@pytest.mark.parametrize("document_type", sorted(DOCUMENT_TYPE_LABELS))
async def test_every_document_type_round_trips_and_posts(client, session_factory, seeded, document_type):
    """One document of each type: create, read back, post, and balance.

    The module serves all ten types from one form, so each has to survive the
    type-scoped field rules and the posting engine.
    """
    headers = await login(client)
    async with session_factory() as session:
        party_id, _, account_id, _ = await _party_and_account(session)
    settles = document_type in PAYMENT_TYPES

    created = await _create(client, headers, {
        "documentType": document_type,
        "date": "2026-03-01",
        "partyId": party_id,
        "currency": "USD",
        # Every type-scoped field is sent; only the applicable ones may land.
        "paymentMethod": "Cash",
        "financialAccountId": account_id,
        "valueDate": "2026-03-02",
        "dueDate": "2026-03-31",
        "lines": [{"description": f"{document_type} line", "quantity": 1, "unitPrice": 10}],
    })

    detail = await _detail(client, headers, created["id"])
    assert detail["documentType"] == document_type
    assert detail["date"] == "2026-03-01"
    assert detail["total"] == pytest.approx(10.0)
    assert detail["outstanding"] == pytest.approx(10.0)
    assert len(detail["lines"]) == 1
    assert bool(detail["paymentMethod"]) is settles
    assert bool(detail["financialAccountId"]) is settles
    assert bool(detail["valueDate"]) is settles
    assert (detail["dueDate"] is not None) is (document_type in ALLOCATABLE_TYPES)

    await _post(client, headers, created["id"])
    posted = await _detail(client, headers, created["id"])
    assert posted["status"] == "Posted"
    assert posted["journalId"]
    entries = posted["journalEntries"]
    assert sum(entry["debit"] for entry in entries) == pytest.approx(sum(entry["credit"] for entry in entries))
    assert sum(entry["debit"] for entry in entries) == pytest.approx(10.0)
