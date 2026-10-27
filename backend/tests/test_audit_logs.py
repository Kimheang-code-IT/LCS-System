"""Audit-log listing and the status-policy contract the Audit Logs page relies on.

The page is read-only history: it must list events with the API's sorting,
pagination and filters, stay closed to callers without ``audit_log.read``, and
never be asked for a status policy (the backend has none for it, and the shared
frontend manager must not request one). Other modules keep their policies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from tests.conftest import login
from tests.seed import DEFAULT_PASSWORD

pytestmark = pytest.mark.asyncio

AUDIT = "/api/v1/audit-events"


async def _seed_events(session_factory) -> None:
    base = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    async with session_factory() as session:
        session.add_all([
            AuditEvent(
                event_type="AUDIT_TEST_PASSWORD_CHANGED",
                entity_type="auditLogTest",
                entity_id=7,
                action="change_password",
                result="SUCCESS",
                occurred_at=base,
            ),
            AuditEvent(
                event_type="AUDIT_TEST_MASTER_DATA_CREATED",
                entity_type="auditLogTest",
                entity_id=42,
                action="create",
                result="SUCCESS",
                occurred_at=base + timedelta(minutes=1),
            ),
            AuditEvent(
                event_type="AUDIT_TEST_LOGIN_FAILED",
                entity_type="auditLogTest",
                entity_id=7,
                action="login",
                result="REJECTED",
                occurred_at=base + timedelta(minutes=2),
            ),
            AuditEvent(
                event_type="AUDIT_TEST_OTHER",
                entity_type="auditLogOther",
                entity_id=9,
                action="create",
                result="SUCCESS",
                occurred_at=base + timedelta(minutes=3),
            ),
        ])
        await session.commit()


async def test_events_are_listed_newest_first_with_pagination_meta(client, session_factory):
    await _seed_events(session_factory)
    headers = await login(client)

    params = {"entity_type": "auditLogTest", "page": 1, "page_size": 2}
    first = await client.get(AUDIT, headers=headers, params=params)
    assert first.status_code == 200, first.text
    body = first.json()["data"]
    assert len(body["items"]) == 2
    assert body["meta"] == {"page": 1, "page_size": 2, "total": 3}
    # Newest first: the default order is occurred_at desc, id desc.
    assert [item["result"] for item in body["items"]] == ["REJECTED", "SUCCESS"]

    second = await client.get(AUDIT, headers=headers, params={**params, "page": 2})
    assert [item["eventType"] for item in second.json()["data"]["items"]] == ["AUDIT_TEST_PASSWORD_CHANGED"]


async def test_events_support_sorting_and_entity_filters(client, session_factory):
    await _seed_events(session_factory)
    headers = await login(client)

    sorted_events = await client.get(
        AUDIT,
        headers=headers,
        params={"entity_type": "auditLogTest", "sort_by": "entity_id", "sort_order": "asc", "page_size": 200},
    )
    entity_ids = [item["entityId"] for item in sorted_events.json()["data"]["items"]]
    assert entity_ids == sorted(entity_ids)

    filtered = await client.get(
        AUDIT, headers=headers, params={"entity_type": "auditLogTest", "entity_id": 7}
    )
    assert filtered.status_code == 200
    assert {item["action"] for item in filtered.json()["data"]["items"]} == {"change_password", "login"}

    by_event = await client.get(AUDIT, headers=headers, params={"event_type": "AUDIT_TEST_LOGIN_FAILED"})
    assert [item["entityId"] for item in by_event.json()["data"]["items"]] == [7]

    other = await client.get(AUDIT, headers=headers, params={"entity_type": "auditLogOther"})
    assert [item["eventType"] for item in other.json()["data"]["items"]] == ["AUDIT_TEST_OTHER"]


async def test_a_caller_without_audit_permission_gets_403_and_an_audit_row(client, session_factory):
    await _seed_events(session_factory)
    # SALES_OFFICER does not hold audit_log.read.
    headers = await login(client, "sales", DEFAULT_PASSWORD)

    denied = await client.get(AUDIT, headers=headers)
    assert denied.status_code == 403, denied.text
    assert "message" in denied.json()

    async with session_factory() as session:
        event = (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.event_type == "AUTHORIZATION_DENIED", AuditEvent.action == "audit_log.read")
                .order_by(AuditEvent.id.desc())
            )
        ).scalars().first()
    assert event is not None


async def test_workflow_modules_still_serve_a_status_policy(client):
    headers = await login(client)
    for collection in ("jobs", "quotations", "placeRoles", "users"):
        response = await client.get(f"/api/v1/{collection}/status-policy", headers=headers)
        assert response.status_code == 200, f"{collection}: {response.text}"
        assert response.json()["data"]["collection"] == collection
        assert response.json()["data"]["statuses"]


async def test_audit_logs_has_no_status_policy_so_the_page_must_not_ask(client):
    """No fake policy is created; the read-only page simply has no lifecycle."""
    headers = await login(client)
    response = await client.get("/api/v1/auditLogs/status-policy", headers=headers)
    assert response.status_code == 404
    assert "No status policy" in response.json()["message"]
