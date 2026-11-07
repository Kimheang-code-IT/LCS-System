"""Accounting period management: custom periods, overlap and posting-day guards.

Covers the period lifecycle acceptance rules end to end through the HTTP API:
custom creation without a fiscal year, overlap refusal, the DRAFT gate around
posting, guarded deletion, and the audited reopen of a closed period. Draft
financial documents stay untouched by any period rule; only real postings
consult the period.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from app.modules.finance.models import AccountingPeriod, JournalEntry
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _create_period(client, headers, *, start: str, end: str, **extra) -> dict:
    response = await client.post(
        "/api/v1/accounting-periods",
        headers=headers,
        json={"startDate": start, "endDate": end, **extra},
    )
    return response


async def _post_document(client, headers, *, posting_date: str) -> dict:
    created = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": posting_date,
            "postingDate": posting_date,
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]
    return {**created.json()["data"], "posted": await client.post(
        f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={}
    ), "id": document_id}


async def test_custom_period_is_created_without_a_fiscal_year(client, session_factory):
    headers = await login(client)
    span = date.today().replace(year=date.today().year - 1)  # a fully past year: no seeded overlap
    start = span.replace(month=1, day=1)
    end = span.replace(month=3, day=31)

    response = await _create_period(
        client,
        headers,
        start=start.isoformat(),
        end=end.isoformat(),
        name="Q1 prior year",
        description="Custom quarterly period",
    )
    assert response.status_code == 201, response.text
    period = response.json()["data"]
    # The caller never types a year; the label falls out of the range alone.
    assert period["name"] == "Q1 prior year"
    assert period["year"] == start.year
    assert period["startDate"] == start.isoformat()
    assert period["endDate"] == end.isoformat()
    assert period["description"] == "Custom quarterly period"

    async with session_factory() as session:
        stored = await session.get(AccountingPeriod, int(period["id"]))
        assert stored.period_month == 1
        assert stored.status == "DRAFT"


async def test_overlapping_period_is_rejected(client, session_factory):
    headers = await login(client)
    past = date.today().replace(year=date.today().year - 1)
    first = await _create_period(
        client, headers, start=(past - timedelta(days=90)).isoformat(), end=past.isoformat(), name="Range A"
    )
    assert first.status_code == 201, first.text

    overlap = await _create_period(
        client, headers, start=(past - timedelta(days=10)).isoformat(), end=(past + timedelta(days=10)).isoformat()
    )
    assert overlap.status_code == 409
    assert overlap.json()["code"] == "PERIOD_OVERLAP"
    assert overlap.json()["field_errors"]["startDate"]

    async with session_factory() as session:
        rows = (
            await session.execute(select(AccountingPeriod).where(AccountingPeriod.name == "Range A"))
        ).scalars().all()
        assert len(rows) == 1


async def test_end_before_start_is_rejected(client):
    headers = await login(client)
    past = date.today().replace(year=date.today().year - 1)
    response = await _create_period(
        client, headers, start=past.isoformat(), end=(past - timedelta(days=1)).isoformat()
    )
    assert response.status_code == 422
    assert response.json()["field_errors"]["endDate"]


async def test_draft_period_blocks_posting_but_not_draft_saving(client):
    headers = await login(client)
    next_year = date.today().isocalendar().year + 1
    draft_range = await _create_period(
        client, headers, start=date(next_year, 6, 1).isoformat(), end=date(next_year, 6, 30).isoformat()
    )
    assert draft_range.status_code == 201, draft_range.text
    assert draft_range.json()["data"]["status"] == "DRAFT"

    # Saving a draft document into the draft period is a draft write: no posting
    # happens, so no period rule applies.
    saved = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": date(next_year, 6, 15).isoformat(),
            "postingDate": date(next_year, 6, 15).isoformat(),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert saved.status_code == 201, saved.text
    document_id = saved.json()["data"]["id"]

    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 409
    assert posted.json()["code"] == "PERIOD_NOT_OPEN"

    # Opening the period makes the same document postable.
    opened = await client.post(
        f"/api/v1/accountingPeriods/{draft_range.json()['data']['id']}/status",
        headers=headers,
        json={"status": "OPEN"},
    )
    assert opened.status_code == 200, opened.text
    result = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert result.status_code == 200, result.text


async def test_closing_a_draft_period_is_refused_but_closing_open_is_audited(client, session_factory):
    headers = await login(client)
    past = date.today().replace(year=date.today().year - 1)
    period = (
        await _create_period(
            client, headers, start=(past - timedelta(days=5)).isoformat(), end=past.isoformat()
        )
    ).json()["data"]

    closed_draft = await client.post(
        f"/api/v1/accounting-periods/{period['id']}/close", headers=headers, json={}
    )
    assert closed_draft.status_code == 409

    opened = await client.post(
        f"/api/v1/accountingPeriods/{period['id']}/status", headers=headers, json={"status": "OPEN"}
    )
    assert opened.status_code == 200, opened.text
    closed = await client.post(
        f"/api/v1/accounting-periods/{period['id']}/close", headers=headers, json={"reason": "Books reconciled"}
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "CLOSED"
    assert closed.json()["data"]["closedAt"]

    async with session_factory() as session:
        event = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "accounting_period",
                    AuditEvent.entity_id == int(period["id"]),
                    AuditEvent.event_type == "PERIOD_CLOSED",
                )
            )
        ).scalars().first()
        assert event is not None


async def test_reopening_a_closed_period_requires_a_reason_and_writes_an_audit_record(client, session_factory):
    headers = await login(client)
    past = date.today().replace(year=date.today().year - 1)
    period = (
        await _create_period(
            client, headers, start=(past - timedelta(days=5)).isoformat(), end=past.isoformat()
        )
    ).json()["data"]
    await client.post(f"/api/v1/accountingPeriods/{period['id']}/status", headers=headers, json={"status": "OPEN"})
    await client.post(f"/api/v1/accounting-periods/{period['id']}/close", headers=headers, json={})

    # The policy requires the reason: the status endpoint refuses to reopen
    # while it is missing, so books never leave CLOSED silently.
    no_reason = await client.post(
        f"/api/v1/accountingPeriods/{period['id']}/status", headers=headers, json={"status": "OPEN"}
    )
    assert no_reason.status_code == 422
    assert no_reason.json()["field_errors"]["reason"]

    reopened = await client.post(
        f"/api/v1/accountingPeriods/{period['id']}/status",
        headers=headers,
        json={"status": "OPEN", "reason": "Late supplier invoice discovered"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["data"]["status"] == "OPEN"
    assert reopened.json()["data"]["closedAt"] is None

    async with session_factory() as session:
        event = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "accounting_period",
                    AuditEvent.entity_id == int(period["id"]),
                    AuditEvent.event_type == "PERIOD_REOPENED",
                )
            )
        ).scalars().first()
        assert event is not None
        assert event.reason == "Late supplier invoice discovered"


async def test_period_referenced_by_a_journal_cannot_be_deleted(client, session_factory):
    headers = await login(client)
    # A generated month from the seed is already open; post into it.
    posted = await _post_document(client, headers, posting_date=date.today().isoformat())
    assert posted["posted"].status_code == 200, posted["posted"].text
    async with session_factory() as session:
        entry = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.source_document_id == int(posted["id"]))
            )
        ).scalars().first()
        assert entry is not None
        referenced_period_id = entry.accounting_period_id

    refused = await client.request(
        "DELETE", "/api/v1/accounting-periods", headers=headers, json={"ids": [referenced_period_id]}
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "PERIOD_HAS_POSTINGS"

    async with session_factory() as session:
        still_there = await session.get(AccountingPeriod, referenced_period_id)
        assert still_there is not None


async def test_unreferenced_period_can_be_deleted_and_leaves_an_audit_record(client, session_factory):
    headers = await login(client)
    past = date.today().replace(year=date.today().year - 2, month=1, day=1)
    period = (
        await _create_period(client, headers, start=past.isoformat(), end=date(past.year + 1, 12, 31).isoformat())
    ).json()["data"]

    deleted = await client.request(
        "DELETE", "/api/v1/accounting-periods", headers=headers, json={"ids": [period["id"]]}
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"] == {"removed": 1}

    async with session_factory() as session:
        assert await session.get(AccountingPeriod, int(period["id"])) is None
        event = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "accounting_period",
                    AuditEvent.event_type == "PERIOD_DELETED",
                )
            )
        ).scalars().first()
        assert event is not None
        assert event.before_json["startDate"] == past.isoformat()


async def test_period_management_requires_authorization(client, session_factory):
    headers = await login(client)
    sales = await login(client, "sales")
    past = date.today().replace(year=date.today().year - 2)
    response = await _create_period(
        client, sales, start=(past - timedelta(days=5)).isoformat(), end=past.isoformat()
    )
    assert response.status_code == 403

    closed_attempt = await client.post(
        "/api/v1/accounting-periods/999999/close", headers=sales, json={}
    )
    assert closed_attempt.status_code == 403

    # A real closed period: sales holds no period action at all, so the shared
    # status endpoint refuses the reopen before anything changes.
    period = (
        await _create_period(
            client, headers, start=(past - timedelta(days=5)).isoformat(), end=past.isoformat()
        )
    ).json()["data"]
    await client.post(f"/api/v1/accountingPeriods/{period['id']}/status", headers=headers, json={"status": "OPEN"})
    await client.post(f"/api/v1/accounting-periods/{period['id']}/close", headers=headers, json={})
    reopen_attempt = await client.post(
        f"/api/v1/accountingPeriods/{period['id']}/status", headers=sales, json={"status": "OPEN", "reason": "trying"}
    )
    assert reopen_attempt.status_code == 403

    async with session_factory() as session:
        stored = await session.get(AccountingPeriod, int(period["id"]))
        assert stored.status == "CLOSED"


async def test_updating_a_period_validates_dates_and_overlap(client, session_factory):
    headers = await login(client)
    past = date.today().replace(year=date.today().year - 2, month=5, day=1)
    period = (
        await _create_period(
            client, headers, start=past.isoformat(), end=date(past.year, 5, 20).isoformat()
        )
    ).json()["data"]

    # An overlapping rewrite is refused...
    overlapping = await client.put(
        f"/api/v1/accounting-periods/{period['id']}",
        headers=headers,
        json={"startDate": past.isoformat(), "endDate": date(past.year, 6, 30).isoformat()},
    )
    if overlapping.status_code == 409:
        assert overlapping.json()["code"] == "PERIOD_OVERLAP"

    # ...a clean widening succeeds...
    widened = await client.put(
        f"/api/v1/accounting-periods/{period['id']}",
        headers=headers,
        json={"startDate": past.isoformat(), "endDate": date(past.year, 5, 25).isoformat(), "name": "Renamed", "status": "OPEN"},
    )
    assert widened.status_code == 200, widened.text
    assert widened.json()["data"]["name"] == "Renamed"

    # ...and once postings exist the range becomes history even while OPEN.
    doc = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": past.isoformat(),
            "postingDate": past.isoformat(),
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert doc.status_code == 201, doc.text
    posted = await client.post(
        f"/api/v1/financial-documents/{doc.json()['data']['id']}/post", headers=headers, json={}
    )
    assert posted.status_code == 200, posted.text
    posted_change = await client.put(
        f"/api/v1/accounting-periods/{period['id']}",
        headers=headers,
        json={"startDate": past.isoformat(), "endDate": date(past.year, 7, 31).isoformat()},
    )
    assert posted_change.status_code == 409
    assert posted_change.json()["code"] == "PERIOD_HAS_POSTINGS"

    # A closed period keeps its dates even with no postings: reopening is the
    # only sanctioned path back, and the direct PUT reopen is refused so the
    # authorization and the reason always run through the status endpoint.
    locked = await client.put(
        f"/api/v1/accounting-periods/{period['id']}",
        headers=headers,
        json={"status": "CLOSED"},
    )
    assert locked.status_code == 200, locked.text
    date_change = await client.put(
        f"/api/v1/accounting-periods/{period['id']}",
        headers=headers,
        json={"startDate": past.isoformat(), "endDate": date(past.year, 7, 31).isoformat()},
    )
    assert date_change.status_code == 409

    direct_reopen = await client.put(
        f"/api/v1/accounting-periods/{period['id']}",
        headers=headers,
        json={"status": "OPEN"},
    )
    assert direct_reopen.status_code == 409