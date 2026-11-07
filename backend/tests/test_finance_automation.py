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


async def _charge(client, headers, service_order_id: str, *, fee_type_id: str | None = None, currency: str = "USD") -> dict:
    line = {"description": "Automated freight", "quantity": 2, "unitPrice": 50, "tax": 10}
    if fee_type_id is not None:
        line["feeTypeId"] = fee_type_id
    response = await client.post(
        f"/api/v1/service-orders/{service_order_id}/charges",
        headers=headers,
        json={
            "documentDate": date.today().isoformat(),
            "currency": currency,
            "lines": [line],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_issuing_is_isolated_and_conversion_creates_one_draft(client, session_factory):
    from sqlalchemy import select

    from app.modules.audit.models import AuditEvent
    from app.modules.finance.models import FinancialDocument, JournalEntryLine

    headers = await login(client)
    service_order_id = await _service_order(client, headers)
    charge = await _charge(client, headers, service_order_id)

    # Issue is an operational/billing state change: it creates no finance
    # document, no journal and reports the charge as issued-but-uninvoiced.
    issued = await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})
    assert issued.status_code == 200, issued.text
    issued_data = issued.json()["data"]
    assert issued_data["rawStatus"] == "ISSUED"
    assert "financialDocumentId" not in issued_data

    async with session_factory() as session:
        order_id = int(service_order_id)
        documents = (
            await session.execute(select(FinancialDocument).where(FinancialDocument.service_order_id == order_id))
        ).scalars().all()
        assert documents == [], "issuing must not prepare a finance draft"
        journals = (
            await session.execute(select(JournalEntryLine).where(JournalEntryLine.service_order_id == order_id))
        ).scalars().all()
        assert journals == [], "issuing must not write journal entries"
        events = (
            await session.execute(
                select(AuditEvent.event_type).where(
                    AuditEvent.entity_id == int(charge["id"]),
                    AuditEvent.entity_type == "service_charge",
                )
            )
        ).scalars().all()
        assert events == ["SERVICE_CHARGE_ISSUED"]

    # Explicit, separately-authorized conversion creates exactly one draft.
    converted = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice",
        headers=headers,
        json={},
    )
    assert converted.status_code == 201, converted.text
    document_id = converted.json()["data"]["id"]
    document = await client.get(f"/api/v1/financial-documents/{document_id}", headers=headers)
    assert document.json()["data"]["status"] == "Draft"
    assert document.json()["data"]["total"] == pytest.approx(110)

    # Sequential replay (and re-issue) resolve to the same, single draft.
    replayed = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice",
        headers=headers,
        json={},
    )
    assert replayed.json()["data"]["id"] == document_id
    repeated = await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})
    assert repeated.status_code == 200, repeated.text

    async with session_factory() as session:
        documents = (
            await session.execute(
                select(FinancialDocument).where(FinancialDocument.service_order_id == int(service_order_id))
            )
        ).scalars().all()
        assert len(documents) == 1
        journals = (
            await session.execute(select(JournalEntryLine).where(JournalEntryLine.service_order_id == int(service_order_id)))
        ).scalars().all()
        assert journals == []
        # The replayed issue must not write a second audit event either.
        events = (
            await session.execute(
                select(AuditEvent.event_type).where(
                    AuditEvent.entity_id == int(charge["id"]),
                    AuditEvent.entity_type == "service_charge",
                )
            )
        ).scalars().all()
        assert events == ["SERVICE_CHARGE_ISSUED"]

    report = await client.get("/api/v1/reports/profitability", headers=headers)
    row = next(item for item in report.json()["data"] if item["id"] == service_order_id)
    assert row["quoted"] == pytest.approx(1250)
    assert row["serviceCharges"] == pytest.approx(110)
    assert row["draftRevenue"] == pytest.approx(110)
    assert row["postedRevenue"] == 0
    assert row["uninvoicedCharges"] == 0

    # Posting remains the only journal-producing step.
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


async def test_issue_permission_cannot_convert_and_post_permission_is_separate(client):
    """Casbin isolation: a submit-only holder can issue but never convert."""
    from tests.test_master_data_permissions import _narrow_account

    headers = await login(client)
    service_order_id = await _service_order(client, headers)
    charge = await _charge(client, headers, service_order_id)
    issuer = await _narrow_account(client, "SC_ISSUER", ["service_charge.submit", "service_charge.read"])

    # Can issue...
    issued = await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=issuer, json={})
    assert issued.status_code == 200, issued.text

    # ...but conversion stays a separate authorization.
    assert issued.json()["data"].get("financialDocumentId") is None
    denied = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice", headers=issuer, json={}
    )
    assert denied.status_code == 403, denied.text
    converted = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice", headers=headers, json={}
    )
    assert converted.status_code == 201, converted.text
    assert converted.json()["data"]["status"] == "Draft"


async def test_idempotency_key_replay_and_conflict(client):
    """A key returns its document; the same key on another charge is refused."""
    headers = await login(client)
    order_id = await _service_order(client, headers)
    other_order_id = await _service_order(client, headers)
    first = await _charge(client, headers, order_id)
    second = await _charge(client, headers, other_order_id)
    for charge in (first, second):
        assert (await client.post(
            f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={}
        )).status_code == 200

    converted = await client.post(
        f"/api/v1/service-charges/{first['id']}/create-finance-invoice",
        headers={**headers, "Idempotency-Key": "convert-once"},
        json={},
    )
    assert converted.status_code == 201, converted.text
    document_id = converted.json()["data"]["id"]

    # Sequential replay with the same key (same charge) returns the same document.
    replay = await client.post(
        f"/api/v1/service-charges/{first['id']}/create-finance-invoice",
        headers={**headers, "Idempotency-Key": "convert-once"},
        json={},
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["data"]["id"] == document_id

    # The same key against a different charge is a conflict, never a second draft.
    conflict = await client.post(
        f"/api/v1/service-charges/{second['id']}/create-finance-invoice",
        headers={**headers, "Idempotency-Key": "convert-once"},
        json={},
    )
    assert conflict.status_code == 409, conflict.text
    listed = await client.get("/api/v1/financial-documents", headers=headers, params={"page_size": 200})
    assert [item["id"] for item in listed.json()["data"]["items"]].count(document_id) == 1


async def test_a_failed_conversion_leaves_no_source_link_and_retry_succeeds(client, session_factory, monkeypatch):
    """Failure mid-conversion rolls back; no orphan source; the retry works."""
    from sqlalchemy import func, select

    from app.core.context import RequestContext
    from app.modules.auth.models import User
    from app.modules.finance import service as finance_service
    from app.modules.finance.models import FinancialDocumentSource
    from app.modules.operations import service as operations

    headers = await login(client)
    order_id = await _service_order(client, headers)
    charge = await _charge(client, headers, order_id)
    assert (await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})).status_code == 200

    async def explode(*_args, **_kwargs):
        raise RuntimeError("allocation outage")

    async def _context() -> RequestContext:
        async with session_factory() as session:
            user_id = await session.scalar(select(User.id).order_by(User.id))
        return RequestContext(
            user_id=user_id,
            username="admin",
            email="admin@example.test",
            display_name="Retry Check",
            permissions=set(),
            is_platform_admin=True,
            request_id="retry-check",
        )

    monkeypatch.setattr(finance_service, "allocate_number", explode)
    with pytest.raises(RuntimeError):
        async with session_factory() as session:
            await operations.charge_to_invoice(session, await _context(), int(charge["id"]))
    monkeypatch.undo()

    async with session_factory() as session:
        orphans = (
            await session.execute(
                select(func.count()).select_from(FinancialDocumentSource).where(
                    FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE",
                    FinancialDocumentSource.source_id == int(charge["id"]),
                )
            )
        ).scalar()
    assert orphans == 0, "the failed attempt must leave no source link"

    async with session_factory() as session:
        retry = await operations.charge_to_invoice(session, await _context(), int(charge["id"]))
    assert retry["status"] == "Draft"
    async with session_factory() as session:
        links = (
            await session.execute(
                select(func.count()).select_from(FinancialDocumentSource).where(
                    FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE",
                    FinancialDocumentSource.source_id == int(charge["id"]),
                )
            )
        ).scalar()
    assert links == 1, "the retry converts exactly once"


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


async def test_fee_specific_posting_rule_drives_the_explicit_invoice_journal(client):
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
    await client.post(f"/api/v1/service-charges/{charge['id']}/issue", headers=headers, json={})
    converted = await client.post(
        f"/api/v1/service-charges/{charge['id']}/create-finance-invoice", headers=headers, json={}
    )
    document_id = converted.json()["data"]["id"]
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
