"""Service-order finance tab: manual financial entries, no automatic charge import."""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _party_id(client, headers) -> str:
    parties = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 1})
    return parties.json()["data"]["items"][0]["id"]


async def _service_order(client, headers) -> tuple[str, str]:
    party_id = await _party_id(client, headers)
    created = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customerPartyId": party_id,
            "direction": "Import",
            "currency": "USD",
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert created.status_code == 201, created.text
    revision_id = created.json()["data"]["revisionId"]
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    converted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert converted.status_code == 201, converted.text
    return converted.json()["data"]["serviceOrderId"], party_id


async def _create_entry(client, headers, order_id: str, party_id: str, amount: float, doc_type: str = "CUSTOMER_INVOICE") -> dict:
    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": doc_type,
            "date": date.today().isoformat(),
            "documentDate": date.today().isoformat(),
            "description": "Manual finance entry",
            "partyId": party_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "lines": [{"description": "Manual finance entry", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_finance_tab_does_not_create_or_import_records(client):
    headers = await login(client)
    order_id, _party = await _service_order(client, headers)
    before = await client.get("/api/v1/financial-documents", headers=headers, params={"page_size": 200})
    count = len(before.json()["data"]["items"])
    after = await client.get("/api/v1/financial-documents", headers=headers, params={"page_size": 200})
    assert len(after.json()["data"]["items"]) == count
    assert order_id
    assert all(
        row.get("documentType") != "CUSTOMER_INVOICE" or row.get("serviceOrderId") != order_id
        for row in after.json()["data"]["items"]
    ), "conversion must not create an invoice for the order"


async def test_manual_entry_is_linked_to_the_order_and_stays_a_draft(client):
    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    entry = await _create_entry(client, headers, order_id, party_id, 250)
    assert entry["status"] == "Draft"
    assert entry["serviceOrderId"] == order_id
    assert entry["paidAmount"] == 0

    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    assert all(row.get("sourceDocumentId") != entry["id"] for row in journals.json()["data"]["items"]), (
        "saving a draft must not post a journal"
    )


async def test_manual_entry_validates_order_party_and_amount(client):
    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)

    missing_order = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "serviceOrderId": "999999",
            "currency": "USD",
            "lines": [{"description": "x", "quantity": 1, "unitPrice": 10}],
        },
    )
    assert missing_order.status_code == 422, missing_order.text

    zero = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_INVOICE",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "lines": [{"description": "x", "quantity": 1, "unitPrice": 0}],
        },
    )
    assert zero.status_code == 422, zero.text


async def test_customer_receipt_allocates_partially(client):
    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    invoice = await _create_entry(client, headers, order_id, party_id, 1000)
    posted = await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    accounts = await client.get("/api/v1/financial-accounts", headers=headers, params={"page_size": 1})
    account_id = accounts.json()["data"]["items"][0]["id"]
    receipt = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_RECEIPT",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "financialAccountId": account_id,
            "lines": [{"description": "Partial receipt", "quantity": 1, "unitPrice": 600}],
        },
    )
    assert receipt.status_code == 201, receipt.text
    receipt_id = receipt.json()["data"]["id"]
    receipt_posted = await client.post(
        f"/api/v1/financial-documents/{receipt_id}/post", headers=headers, json={}
    )
    assert receipt_posted.status_code == 200, receipt_posted.text

    allocated = await client.post(
        f"/api/v1/financial-documents/{receipt_id}/allocate",
        headers=headers,
        json={"target_document_id": invoice["id"], "amount": 600},
    )
    assert allocated.status_code == 200, allocated.text

    refreshed = await client.get(f"/api/v1/financial-documents/{invoice['id']}", headers=headers)
    data = refreshed.json()["data"]
    assert data["total"] == 1000
    assert data["paidAmount"] == 600
    assert data["outstanding"] == 400


async def _receipt(client, headers, order_id: str, party_id: str, amount: float) -> dict:
    """A posted customer receipt; the bank account comes from Master Data."""
    accounts = await client.get("/api/v1/financial-accounts", headers=headers, params={"page_size": 1})
    account_id = accounts.json()["data"]["items"][0]["id"]
    receipt = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "CUSTOMER_RECEIPT",
            "date": date.today().isoformat(),
            "partyId": party_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "financialAccountId": account_id,
            "lines": [{"description": "Receipt", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert receipt.status_code == 201, receipt.text
    receipt_id = receipt.json()["data"]["id"]
    posted = await client.post(f"/api/v1/financial-documents/{receipt_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    return receipt.json()["data"]


async def test_partial_then_full_allocation_reconciles_without_second_revenue(client, session_factory):
    """Test B/C/D/H/M/N: two receipts settle 500 exactly once, in one journal each."""
    from sqlalchemy import func, select

    from app.modules.audit.models import AuditEvent
    from app.modules.finance.models import JournalEntry

    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    invoice = await _create_entry(client, headers, order_id, party_id, 500)
    posted = await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    first = await _receipt(client, headers, order_id, party_id, 200)
    allocated = await client.post(
        f"/api/v1/financial-documents/{first['id']}/allocate",
        headers={**headers, "Idempotency-Key": "partial-allocation"},
        json={"target_document_id": invoice["id"], "amount": 200},
    )
    assert allocated.status_code == 200, allocated.text
    assert allocated.json()["data"]["targetOutstanding"] == 300
    assert allocated.json()["data"]["paymentBalance"] == 0

    replay = await client.post(
        f"/api/v1/financial-documents/{first['id']}/allocate",
        headers={**headers, "Idempotency-Key": "partial-allocation"},
        json={"target_document_id": invoice["id"], "amount": 200},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["idempotentReplay"] is True

    second = await _receipt(client, headers, order_id, party_id, 300)
    settled = await client.post(
        f"/api/v1/financial-documents/{second['id']}/allocate",
        headers=headers,
        json={"target_document_id": invoice["id"], "amount": 300},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["data"]["targetOutstanding"] == 0

    refreshed = (await client.get(f"/api/v1/financial-documents/{invoice['id']}", headers=headers)).json()["data"]
    # The document keeps its posting status; settlement is expressed by the balances.
    assert refreshed["outstanding"] == 0 and float(refreshed["paidAmount"]) == 500

    async with session_factory() as session:
        # Revenue is recognized once: the invoice keeps exactly one journal, its
        # 500/500 shape untouched by the settlements.
        entry = (await session.execute(select(JournalEntry).where(JournalEntry.source_document_id == int(invoice["id"])))).scalars().one()
        assert entry.debit_total == entry.credit_total == 500
        # Exactly one audit event per settlement decision (the replay wrote none).
        events = (
            await session.execute(
                select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.entity_type == "financial_document",
                    AuditEvent.event_type == "PAYMENT_ALLOCATED",
                )
            )
        ).scalar()
        assert events == 2, events

    # AR/GL reconciliation: the control account nets to the report outstanding.
    ledger = await client.get("/api/v1/reports/ledger-lines", headers=headers)
    lines = ledger.json()["data"]
    ar = [line for line in lines if line["accountCode"] == "1100"]
    assert sum(line["debit"] for line in ar) - sum(line["credit"] for line in ar) == 0, "AR control nets to the settled invoices"
    receivables = (await client.get("/api/v1/reports/receivables", headers=headers)).json()["data"]
    assert sum(row["balance"] for row in receivables) == 0


async def test_a_receipt_cannot_allocate_another_partys_invoice(client):
    """Test G: settlement stays inside one party's documents."""
    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    others = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_ids = [row["id"] for row in others.json()["data"]["items"]]
    other_party = next((pid for pid in party_ids if pid != party_id), None)
    if other_party is None:  # the seed is a single-party fixture in some profiles
        other_party = (await client.post(
            "/api/v1/businessParties",
            headers=headers,
            json={"partyCode": "ALLOC-OTHER", "legalName": "Other Party", "status": "ACTIVE"},
        )).json()["data"]["id"]
    invoice = await _create_entry(client, headers, order_id, other_party, 100)
    posted = await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    receipt = await _receipt(client, headers, order_id, party_id, 100)
    refused = await client.post(
        f"/api/v1/financial-documents/{receipt['id']}/allocate",
        headers=headers,
        json={"target_document_id": invoice["id"], "amount": 100},
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "PARTY_MISMATCH", refused.text

    # Nothing moved: the receipt stays fully unapplied and the invoice unpaid.
    detail = (await client.get(f"/api/v1/financial-documents/{invoice['id']}", headers=headers)).json()["data"]
    assert detail["outstanding"] == 100 and detail["paidAmount"] == 0


async def _supplier_posting_test_parties(client, headers, supplier_name: str = "Supplier Co") -> str:
    others = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    supplier = next(
        (row["id"] for row in others.json()["data"]["items"] if "SUP" in str(row.get("partyCode", "")).upper()),
        None,
    )
    if supplier:
        return supplier
    created = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "AP-SUPPLIER", "legalName": supplier_name, "status": "ACTIVE"},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


async def _bill(client, headers, order_id: str, supplier_id: str, amount: float) -> dict:
    bill = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "SUPPLIER_BILL",
            "date": date.today().isoformat(),
            "partyId": supplier_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "lines": [{"description": "Freight cost", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert bill.status_code == 201, bill.text
    return bill.json()["data"]


async def _supplier_payment(client, headers, order_id: str, supplier_id: str, amount: float) -> dict:
    accounts = await client.get("/api/v1/financial-accounts", headers=headers, params={"page_size": 1})
    account_id = accounts.json()["data"]["items"][0]["id"]
    payment = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "documentType": "SUPPLIER_PAYMENT",
            "date": date.today().isoformat(),
            "partyId": supplier_id,
            "serviceOrderId": order_id,
            "currency": "USD",
            "paymentMethod": "Bank Transfer",
            "financialAccountId": account_id,
            "lines": [{"description": "Payment", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert payment.status_code == 201, payment.text
    payment_id = payment.json()["data"]["id"]
    posted = await client.post(f"/api/v1/financial-documents/{payment_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    return payment.json()["data"]


async def test_supplier_bill_partial_then_full_payment_reconciles_ap(client, session_factory):
    """08.3 journey: 300 bill; 100 partial, 200 full; AP/GL net zero; expense once."""
    from sqlalchemy import select

    from app.modules.finance.models import JournalEntry

    headers = await login(client)
    order_id, _party = await _service_order(client, headers)
    supplier_id = await _supplier_posting_test_parties(client, headers)
    bill = await _bill(client, headers, order_id, supplier_id, 300)
    assert bill["status"] == "Draft"
    posted = await client.post(f"/api/v1/financial-documents/{bill['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    partial = await _supplier_payment(client, headers, order_id, supplier_id, 100)
    allocated = await client.post(
        f"/api/v1/financial-documents/{partial['id']}/allocate",
        headers={**headers, "Idempotency-Key": "ap-partial"},
        json={"target_document_id": bill["id"], "amount": 100},
    )
    assert allocated.status_code == 200, allocated.text
    assert allocated.json()["data"]["targetOutstanding"] == 200
    payable_detail = (await client.get(f"/api/v1/financial-documents/{bill['id']}", headers=headers)).json()["data"]
    assert payable_detail["outstanding"] == 200 and float(payable_detail["paidAmount"]) == 100

    final = await _supplier_payment(client, headers, order_id, supplier_id, 200)
    settled = await client.post(
        f"/api/v1/financial-documents/{final['id']}/allocate",
        headers=headers,
        json={"target_document_id": bill["id"], "amount": 200},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["data"]["targetOutstanding"] == 0
    payable_detail = (await client.get(f"/api/v1/financial-documents/{bill['id']}", headers=headers)).json()["data"]
    assert payable_detail["outstanding"] == 0 and float(payable_detail["paidAmount"]) == 300

    async with session_factory() as session:
        # The expense is recognized once: the bill's journal is untouched.
        entry = (await session.execute(select(JournalEntry).where(JournalEntry.source_document_id == int(bill["id"])))).scalars().one()
        assert entry.debit_total == entry.credit_total == 300

    # AP/GL reconciliation: control account 2010 nets to the payable report total.
    ledger = (await client.get("/api/v1/reports/ledger-lines", headers=headers)).json()["data"]
    ap = [line for line in ledger if line["accountCode"] == "2010"]
    assert sum(line["credit"] for line in ap) - sum(line["debit"] for line in ap) == 0, "AP control nets to the settled bills"
    payables = (await client.get("/api/v1/reports/payables", headers=headers)).json()["data"]
    assert sum(row["balance"] for row in payables) == 0
    expense = [line for line in ledger if line["accountCode"] == "5010"]
    assert sum(line["debit"] for line in expense) == 300, "the supplier expense is booked once"


async def test_a_supplier_payment_cannot_settle_another_suppliers_bill(client):
    headers = await login(client)
    order_id, _party = await _service_order(client, headers)
    supplier_id = await _supplier_posting_test_parties(client, headers)
    others = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    other = next((row["id"] for row in others.json()["data"]["items"] if str(row["id"]) != str(supplier_id)), None)
    if other is None:
        other = (await client.post(
            "/api/v1/businessParties",
            headers=headers,
            json={"partyCode": "AP-OTHER", "legalName": "Other Supplier", "status": "ACTIVE"},
        )).json()["data"]["id"]
    bill = await _bill(client, headers, order_id, other, 100)
    posted = await client.post(f"/api/v1/financial-documents/{bill['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    payment = await _supplier_payment(client, headers, order_id, supplier_id, 100)
    refused = await client.post(
        f"/api/v1/financial-documents/{payment['id']}/allocate",
        headers=headers,
        json={"target_document_id": bill["id"], "amount": 100},
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "PARTY_MISMATCH", refused.text
    # The payment stays unapplied and the bill unpaid.
    detail = (await client.get(f"/api/v1/financial-documents/{bill['id']}", headers=headers)).json()["data"]
    assert detail["outstanding"] == 100
    payment_detail = (await client.get(f"/api/v1/financial-documents/{payment['id']}", headers=headers)).json()["data"]
    assert float(payment_detail["paidAmount"]) == 0


async def test_reversing_an_allocated_invoice_unsettles_and_money_stays_received(client, session_factory):
    """08.4: reversal after allocation; the receipt becomes unapplied, never refunded."""
    from sqlalchemy import select

    from app.modules.audit.models import AuditEvent
    from app.modules.finance.models import FinancialDocument, FinancialDocumentAllocation, JournalEntry

    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    invoice = await _create_entry(client, headers, order_id, party_id, 500)
    posted = await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    receipt = await _receipt(client, headers, order_id, party_id, 200)
    allocated = await client.post(
        f"/api/v1/financial-documents/{receipt['id']}/allocate",
        headers=headers,
        json={"target_document_id": invoice["id"], "amount": 200},
    )
    assert allocated.status_code == 200, allocated.text

    reversal = await client.post(
        f"/api/v1/financial-documents/{invoice['id']}/reverse",
        headers=headers,
        json={"reason": "Customer dispute"},
    )
    assert reversal.status_code == 201, reversal.text
    assert reversal.json()["data"]["status"] == "Reversed"

    async with session_factory() as session:
        # The settlement is undone on both sides; the allocation row is retained
        # as history (retired by reversed_at) and nothing was refunded.
        rows = (
            await session.execute(
                select(FinancialDocumentAllocation).where(
                    FinancialDocumentAllocation.target_document_id == int(invoice["id"])
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].reversed_at is not None
        assert rows[0].reversed_by_document_id == int(invoice["id"])
        receipt_left = await session.get(FinancialDocument, int(receipt["id"]))
        assert receipt_left.paid_amount == 0, "the receipt is unapplied again, not refunded"
        # The original entry survives and the reversal mirrors it: two entries, each balanced.
        originals = (
            await session.execute(select(JournalEntry).where(JournalEntry.source_document_id == int(invoice["id"])))
        ).scalars().all()
        assert len(originals) == 2, "the reversal journal was created without touching the original"
        assert all(entry.debit_total == entry.credit_total for entry in originals)
        assert all(entry.status == "POSTED" for entry in originals)
        events = (
            await session.execute(
                select(AuditEvent.event_type).where(
                    AuditEvent.entity_id == int(invoice["id"]),
                    AuditEvent.entity_type == "financial_document",
                )
            )
        ).scalars().all()
    assert events.count("FINANCIAL_REVERSED") == 1

    again = await client.post(
        f"/api/v1/financial-documents/{invoice['id']}/reverse",
        headers=headers,
        json={"reason": "double click"},
    )
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "DOCUMENT_ALREADY_REVERSED"

    async with session_factory() as session:
        events_after = (
            await session.execute(
                select(AuditEvent.event_type).where(
                    AuditEvent.entity_id == int(invoice["id"]),
                    AuditEvent.entity_type == "financial_document",
                )
            )
        ).scalars().all()
    assert events_after.count("FINANCIAL_REVERSED") == 1, "the replay must not audit again"

    # Ledger reconciliation: the invoice pair nets zero; the AR control keeps the
    # (valid) customer credit the receipt left behind — money received, not owed.
    ledger = (await client.get("/api/v1/reports/ledger-lines", headers=headers)).json()["data"]
    ar = [line for line in ledger if line["accountCode"] == "1100"]
    assert sum(line["debit"] for line in ar) - sum(line["credit"] for line in ar) == -200
    receivables = (await client.get("/api/v1/reports/receivables", headers=headers)).json()["data"]
    assert sum(row["balance"] for row in receivables) == 0
    unapplied = (await client.get(f"/api/v1/financial-documents/{receipt['id']}", headers=headers)).json()["data"]
    assert float(unapplied["total"]) - float(unapplied["paidAmount"]) == 200


async def test_financial_permissions_stay_separate(client):
    """16: a read-only finance account cannot post, allocate or reverse."""
    from tests.test_master_data_permissions import _narrow_account

    headers = await login(client)
    order_id, party_id = await _service_order(client, headers)
    invoice = await _create_entry(client, headers, order_id, party_id, 100)
    reader = await _narrow_account(client, "FIN_ONLY_READ", ["financial_document.read"])

    assert (await client.post(f"/api/v1/financial-documents/{invoice['id']}/post", headers=reader, json={})).status_code == 403
    assert (await client.post(
        f"/api/v1/financial-documents/{invoice['id']}/allocate", headers=reader, json={"target_document_id": invoice["id"], "amount": 10}
    )).status_code == 403
    assert (await client.post(
        f"/api/v1/financial-documents/{invoice['id']}/reverse", headers=reader, json={"reason": "no"}
    )).status_code == 403
    # The reads stay allowed; nothing changed.
    assert (await client.get(f"/api/v1/financial-documents/{invoice['id']}", headers=reader)).status_code == 200
    detail = (await client.get(f"/api/v1/financial-documents/{invoice['id']}", headers=headers)).json()["data"]
    assert detail["status"] == "Draft"
