"""Shared record-status endpoints: policy, transitions, audit and permissions.

Status changes moved out of the create/edit forms into the row "..." menu, so
they now run through one endpoint per collection:

* ``GET /api/v1/{collection}/status-policy`` — the legal transitions from each
  status, already filtered to the ones the caller may perform.
* ``POST /api/v1/{collection}/{item_id}/status`` — apply one plain transition
  (activate / deactivate / mark / reopen) and audit it.

Workflow transitions (posting, reversal, issuing a charge, closing a period,
sending a quotation) keep their own endpoints and are refused here, which is what
keeps the posting engine as the only writer of an accounting status.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from app.modules.master_data.status_policy import STATUS_POLICIES
from tests.conftest import login

pytestmark = pytest.mark.asyncio

FRONTEND_COMMANDS = (
    Path(__file__).resolve().parents[2] / "frontend" / "app" / "utils" / "freight" / "status-commands.ts"
)


async def _create_role(client, headers, code: str = "ST-1") -> dict:
    response = await client.post(
        "/api/v1/placeRoles",
        headers=headers,
        json={"code": code, "name": f"Status Test {code}", "sortOrder": 10, "status": "ACTIVE"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _change_status(client, headers, collection: str, item_id: str, status: str, reason: str | None = None):
    body: dict[str, object] = {"status": status}
    if reason is not None:
        body["reason"] = reason
    return await client.post(f"/api/v1/{collection}/{item_id}/status", headers=headers, json=body)


async def _policy(client, headers, collection: str) -> dict:
    response = await client.get(f"/api/v1/{collection}/status-policy", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _events(session_factory, entity_type: str, entity_id: int | None = None) -> list[AuditEvent]:
    async with session_factory() as session:
        statement = select(AuditEvent).where(AuditEvent.entity_type == entity_type)
        if entity_id is not None:
            statement = statement.where(AuditEvent.entity_id == entity_id)
        return list((await session.execute(statement)).scalars().all())


def _rows(response) -> list[dict]:
    """List endpoints answer with either ``{data: [...]}`` or a paged envelope."""
    data = response.json()["data"]
    return data if isinstance(data, list) else data["items"]


async def _create_document(client, headers, amount: int = 250) -> dict:
    parties = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = parties.json()["data"]["items"][0]["id"]
    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": "CUSTOMER_INVOICE",
            "documentDate": date.today().isoformat(),
            "party": party_id,
            "currency": "USD",
            "lines": [{"description": "Freight", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_the_policy_lists_the_legal_transitions_of_a_reference_record(client):
    headers = await login(client)
    policy = await _policy(client, headers, "placeRoles")

    assert policy["statuses"] == ["ACTIVE", "INACTIVE"]
    # The policy is keyed by the normalised current status.
    assert policy["transitions"]["ACTIVE"] == [
        {"to": "INACTIVE", "action": "deactivate", "kind": "status", "confirm": False, "reason": False}
    ]
    assert policy["transitions"]["INACTIVE"][0]["to"] == "ACTIVE"


async def test_a_reference_record_is_deactivated_and_reactivated_with_an_audit_row(client, session_factory):
    headers = await login(client)
    role = await _create_role(client, headers, "ST-2")

    deactivated = await _change_status(client, headers, "placeRoles", role["id"], "INACTIVE")
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["status"] == "INACTIVE"

    events = await _events(session_factory, "placeRoles", int(role["id"]))
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "STATUS_CHANGED"
    assert event.action == "deactivate"
    assert event.before_json == {"status": "ACTIVE"}
    assert event.after_json == {"status": "INACTIVE"}
    assert event.actor_user_id is not None
    assert event.occurred_at is not None

    reactivated = await _change_status(client, headers, "placeRoles", role["id"], "ACTIVE")
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["data"]["status"] == "ACTIVE"
    assert len(await _events(session_factory, "placeRoles", int(role["id"]))) == 2


async def test_changing_to_the_current_status_is_a_no_op_without_an_audit_row(client, session_factory):
    headers = await login(client)
    role = await _create_role(client, headers, "ST-3")

    response = await _change_status(client, headers, "placeRoles", role["id"], "active")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "ACTIVE"
    assert await _events(session_factory, "placeRoles", int(role["id"])) == []


async def test_an_unknown_status_is_refused_with_a_field_error(client):
    headers = await login(client)
    role = await _create_role(client, headers, "ST-4")

    response = await _change_status(client, headers, "placeRoles", role["id"], "ARCHIVED")
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "status" in body["field_errors"]


async def test_an_unknown_collection_or_missing_record_is_not_found(client):
    headers = await login(client)

    unknown = await client.get("/api/v1/notACollection/status-policy", headers=headers)
    assert unknown.status_code == 404, unknown.text

    missing = await _change_status(client, headers, "placeRoles", "999999", "INACTIVE")
    assert missing.status_code == 404, missing.text


async def test_a_caller_without_the_manage_permission_is_refused_and_sees_no_action(client, session_factory):
    ops_headers = await login(client, "ops.pp")
    admin_headers = await login(client)
    role = await _create_role(client, admin_headers, "ST-5")

    policy = await _policy(client, ops_headers, "placeRoles")
    assert policy["transitions"] == {}, "an unauthorized caller must not be offered the transition"

    refused = await _change_status(client, ops_headers, "placeRoles", role["id"], "INACTIVE")
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "ACCESS_DENIED"

    current = await client.get(f"/api/v1/placeRoles/{role['id']}", headers=admin_headers)
    assert current.json()["data"]["status"] == "ACTIVE", "a refused change must not touch the record"
    denials = await _events(session_factory, "permission")
    assert any(event.result == "REJECTED" for event in denials), "the refusal is audited"


async def test_a_workflow_transition_must_use_its_own_endpoint(client, session_factory):
    headers = await login(client)
    document = await _create_document(client, headers)

    refused = await _change_status(client, headers, "debitNotes", document["id"], "POSTED")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "TRANSITION_REQUIRES_COMMAND"

    fetched = await client.get(f"/api/v1/financial-documents/{document['id']}", headers=headers)
    assert str(fetched.json()["data"]["status"]).upper() == "DRAFT"
    assert await _events(session_factory, "financial_document", int(document["id"])) == []

    # The dedicated endpoint still posts it, exactly as before.
    posted = await client.post(f"/api/v1/financial-documents/{document['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    assert str(posted.json()["data"]["status"]).upper() == "POSTED"


async def test_the_policy_marks_posting_and_reversal_as_workflow_transitions(client):
    headers = await login(client)
    policy = await _policy(client, headers, "debitNotes")
    assert policy["transitions"]["DRAFT"][0]["kind"] == "command"
    assert policy["transitions"]["POSTED"][0]["kind"] == "command"
    assert policy["transitions"]["POSTED"][0]["reason"] is True


async def test_a_chart_of_account_can_be_deactivated_through_the_status_endpoint(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/chart-of-accounts",
        headers=headers,
        json={
            "accountCode": "7900",
            "accountName": "Status Test Account",
            "accountType": "ASSET",
            "normalBalance": "DEBIT",
            "postable": True,
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["data"]["id"]

    deactivated = await _change_status(client, headers, "chartOfAccounts", account_id, "INACTIVE")
    assert deactivated.status_code == 200, deactivated.text
    assert str(deactivated.json()["data"]["status"]).upper() == "INACTIVE"

    removed = await client.request(
        "DELETE", "/api/v1/chart-of-accounts", headers=headers, json={"ids": [account_id]}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 1


async def test_a_closed_period_blocks_posting_and_reopening_restores_it(client):
    headers = await login(client)
    first = await _create_document(client, headers, 100)
    posted = await client.post(f"/api/v1/financial-documents/{first['id']}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    periods = await client.get("/api/v1/accounting-periods", headers=headers, params={"page_size": 200})
    period = next(
        row for row in _rows(periods)
        if str(row["startDate"]) <= date.today().isoformat() <= str(row["endDate"])
    )
    closed = await client.post(f"/api/v1/accounting-periods/{period['id']}/close", headers=headers, json={})
    assert closed.status_code == 200, closed.text

    blocked = await _create_document(client, headers, 200)
    refused = await client.post(f"/api/v1/financial-documents/{blocked['id']}/post", headers=headers, json={})
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "PERIOD_CLOSED"

    reopened = await _change_status(client, headers, "accountingPeriods", period["id"], "OPEN")
    assert reopened.status_code == 200, reopened.text
    assert str(reopened.json()["data"]["status"]).upper() == "OPEN"
    # Reopening stores OPEN and clears the closure stamp, so the period no
    # longer carries an attribution to the user who closed it.
    assert reopened.json()["data"]["closedAt"] in (None, "")

    accepted = await client.post(f"/api/v1/financial-documents/{blocked['id']}/post", headers=headers, json={})
    assert accepted.status_code == 200, accepted.text
    assert str(accepted.json()["data"]["status"]).upper() == "POSTED"


async def test_a_user_cannot_deactivate_the_protected_administrator(client):
    headers = await login(client)
    users = await client.get("/api/v1/users", headers=headers, params={"page_size": 200})
    admin = next(row for row in _rows(users) if row["username"] == "admin")

    refused = await _change_status(client, headers, "users", admin["id"], "INACTIVE")
    assert refused.status_code == 403, refused.text

    again = await client.get(f"/api/v1/users/{admin['id']}", headers=headers)
    assert str(again.json()["data"]["status"]).upper() == "ACTIVE"


async def test_a_document_sequence_can_be_deactivated(client):
    headers = await login(client)
    sequences = await client.get("/api/v1/document-sequences", headers=headers, params={"page_size": 200})
    sequence = _rows(sequences)[0]

    response = await _change_status(client, headers, "documentSequences", sequence["id"], "INACTIVE")
    assert response.status_code == 200, response.text
    assert str(response.json()["data"]["status"]).upper() == "INACTIVE"


async def test_a_service_order_finish_is_audited(client, session_factory):
    headers = await login(client)
    created = await client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={"customer": "Status Test Customer", "direction": "Import", "currency": "USD"},
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["data"]["id"]

    finished = await client.post(f"/api/v1/service-orders/{order_id}/finish", headers=headers, json={})
    assert finished.status_code == 200, finished.text

    events = await _events(session_factory, "service_order", int(order_id))
    assert [event.event_type for event in events] == ["SERVICE_ORDER_FINISHED"]
    assert events[0].before_json == {"status": "ACTIVE"}
    assert events[0].after_json == {"status": "FINISHED"}


async def test_a_quotation_cancel_runs_its_own_endpoint_and_is_audited(client, session_factory):
    headers = await login(client)
    created = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Status Test Cancel Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": 300,
        },
    )
    assert created.status_code == 201, created.text
    revision_id = created.json()["data"]["revisionId"]

    policy = await _policy(client, headers, "quotations")
    cancel = next(item for item in policy["transitions"]["DRAFT"] if item["action"] == "cancel")
    assert cancel["kind"] == "command", "a quotation status is never a plain status write"

    cancelled = await client.post(
        f"/api/v1/quotation-revisions/{revision_id}/cancel", headers=headers, json={"reason": "withdrawn"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["revisionStatus"] == "CANCELLED"

    events = await _events(session_factory, "quotation_revision", int(revision_id))
    assert [event.event_type for event in events] == ["QUOTATION_CANCELLED"]
    assert events[0].before_json == {"status": "DRAFT"}
    assert events[0].after_json == {"status": "CANCELLED"}
    assert events[0].reason == "withdrawn"

    # The withdrawal is final for that revision: it can no longer be sent.
    refused = await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    assert refused.status_code == 409, refused.text


async def test_a_quotation_send_is_audited(client, session_factory):
    headers = await login(client)
    created = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Status Test Quotation Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": 500,
        },
    )
    assert created.status_code == 201, created.text
    revision_id = created.json()["data"]["revisionId"]

    sent = await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})
    assert sent.status_code == 200, sent.text

    events = await _events(session_factory, "quotation_revision", int(revision_id))
    assert [event.event_type for event in events] == ["QUOTATION_SENT"]
    assert events[0].before_json == {"status": "DRAFT"}
    assert events[0].after_json == {"status": "SENT"}


async def test_the_status_policy_of_a_workflow_collection_never_offers_a_plain_write(client):
    """The accounting statuses are reachable only through their engines."""
    headers = await login(client)
    for collection in ("journals", "jobCharges", "debitNotes", "accountingPeriods", "quotations"):
        policy = await _policy(client, headers, collection)
        for status, transitions in policy["transitions"].items():
            for transition in transitions:
                if transition["kind"] == "status":
                    assert collection == "accountingPeriods" and transition["action"] == "reopen", (
                        f"{collection}:{status} must not be writable by a plain status change"
                    )


async def test_every_command_transition_has_a_frontend_runner():
    """The menu must be able to run every workflow transition the policy declares.

    A ``command`` transition is executed by its own endpoint, so each one needs a
    runner in ``frontend/app/utils/freight/status-commands.ts``; without it the
    row menu would silently hide a legal action.
    """
    source = FRONTEND_COMMANDS.read_text(encoding="utf-8")
    missing = sorted(
        f"{collection}:{transition.action}"
        for collection, policy in STATUS_POLICIES.items()
        for transitions in policy.transitions.values()
        for transition in transitions
        if transition.kind == "command" and f"'{collection}:{transition.action}'" not in source
    )
    assert not missing, "workflow transitions without a frontend runner:\n" + "\n".join(missing)


async def test_every_policy_store_has_a_loader_and_an_applier():
    """A ``status`` transition must have an adapter, or the endpoint would 500."""
    from app.modules.master_data.status_service import _APPLIERS, _LOADERS

    for collection, policy in STATUS_POLICIES.items():
        assert policy.store in _LOADERS, f"{collection} has no current-status loader"
        if any(transition.kind == "status" for items in policy.transitions.values() for transition in items):
            assert policy.store in _APPLIERS, f"{collection} has status transitions but no applier"
