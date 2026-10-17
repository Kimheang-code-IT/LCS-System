"""Quotation version management: comparison, rejection and immutability.

Covers ``compare_revisions`` / ``reject_revision`` and the guarantee that an
issued revision is never rewritten when the quotation is edited again.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def _party_id(client, headers) -> str:
    response = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"][0]["id"]


async def _quotation(client, headers, amount: float = 1000) -> dict:
    party_id = await _party_id(client, headers)
    response = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customerPartyId": party_id,
            "direction": "Import",
            "currency": "USD",
            "amount": amount,
            "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _revisions(client, headers, quotation_id: str) -> list[dict]:
    response = await client.get(f"/api/v1/quotations/{quotation_id}/revisions", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_compare_revisions_reports_header_and_line_differences(client):
    headers = await login(client)
    created = await _quotation(client, headers, 1000)
    first_revision = created["revisionId"]

    assert (await client.post(f"/api/v1/quotation-revisions/{first_revision}/send", headers=headers, json={})).status_code == 200
    # Editing the issued quotation opens a fresh draft revision carrying the new
    # commercial terms, which is what a comparison between the two shows.
    updated = await client.put(
        f"/api/v1/quotations/{created['id']}",
        headers=headers,
        json={"amount": 1200, "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 1200}]},
    )
    assert updated.status_code == 200, updated.text
    second_revision = updated.json()["data"]["revisionId"]
    assert second_revision != first_revision

    compared = await client.get(
        f"/api/v1/quotation-revisions/{first_revision}/compare/{second_revision}", headers=headers
    )
    assert compared.status_code == 200, compared.text
    data = compared.json()["data"]
    assert data["changed"] is True
    assert data["from"]["revisionNo"] == 1
    assert data["to"]["revisionNo"] == 2
    assert data["totals"]["from"] == 1000
    assert data["totals"]["to"] == 1200
    assert data["totals"]["difference"] == 200
    assert any(line["lineNo"] == 1 for line in data["lineChanges"])


async def test_compare_revisions_of_identical_content_reports_no_change(client):
    headers = await login(client)
    created = await _quotation(client, headers, 800)
    first_revision = created["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{first_revision}/send", headers=headers, json={})).status_code == 200

    # A re-quote clones the issued revision unchanged, so the only difference
    # between the two is the status.
    second = await client.post(f"/api/v1/quotations/{created['id']}/revisions", headers=headers, json={})
    assert second.status_code == 201, second.text
    second_revision = second.json()["data"]["revisionId"]

    compared = await client.get(
        f"/api/v1/quotation-revisions/{first_revision}/compare/{second_revision}", headers=headers
    )
    assert compared.status_code == 200, compared.text
    data = compared.json()["data"]
    assert data["lineChanges"] == []
    assert data["totals"]["difference"] == 0
    assert any(change["field"] == "status" for change in data["headerChanges"])


async def test_revisions_of_different_quotations_cannot_be_compared(client):
    headers = await login(client)
    first = await _quotation(client, headers, 100)
    second = await _quotation(client, headers, 200)

    rejected = await client.get(
        f"/api/v1/quotation-revisions/{first['revisionId']}/compare/{second['revisionId']}", headers=headers
    )
    assert rejected.status_code == 422, rejected.text
    assert "revision" in rejected.json()["field_errors"]


async def test_rejecting_a_sent_revision_is_recorded_and_visible_in_history(client):
    headers = await login(client)
    created = await _quotation(client, headers, 500)
    revision_id = created["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200

    rejected = await client.post(
        f"/api/v1/quotation-revisions/{revision_id}/reject", headers=headers, json={"reason": "Price too high"}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["revisionStatus"] == "REJECTED"
    assert rejected.json()["data"]["status"] == "Rejected"

    history = await _revisions(client, headers, created["id"])
    entry = next(row for row in history if row["rawStatus"] == "REJECTED")
    assert entry["revisionNo"] == 1

    # Rejection is idempotent, and a rejected revision can no longer be accepted.
    again = await client.post(f"/api/v1/quotation-revisions/{revision_id}/reject", headers=headers, json={})
    assert again.status_code == 200, again.text

    accepted = await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})
    assert accepted.status_code == 409, accepted.text


async def test_editing_an_issued_revision_opens_a_new_one_and_preserves_the_original(client):
    headers = await login(client)
    created = await _quotation(client, headers, 1000)
    revision_id = created["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200

    updated = await client.put(
        f"/api/v1/quotations/{created['id']}",
        headers=headers,
        json={"amount": 1500, "pricingLines": [{"description": "Freight", "quantity": 1, "unitPrice": 1500}]},
    )
    assert updated.status_code == 200, updated.text

    history = await _revisions(client, headers, created["id"])
    by_no = {row["revisionNo"]: row for row in history}
    assert by_no[1]["rawStatus"] == "SENT", "the issued revision must stay untouched"
    assert by_no[1]["total"] == 1000, "the issued commercial terms must not be rewritten"
    assert max(by_no) >= 2, "editing must open a fresh draft revision"
    assert by_no[max(by_no)]["rawStatus"] == "DRAFT"


async def test_a_converted_revision_cannot_be_converted_twice(client):
    headers = await login(client)
    created = await _quotation(client, headers, 900)
    revision_id = created["revisionId"]
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/send", headers=headers, json={})).status_code == 200
    assert (await client.post(f"/api/v1/quotation-revisions/{revision_id}/accept", headers=headers, json={})).status_code == 200
    first = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert first.status_code == 201, first.text
    assert first.json()["data"]["serviceOrderId"]

    second = await client.post(f"/api/v1/quotation-revisions/{revision_id}/convert", headers=headers, json={})
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "DUPLICATE_CONVERSION"


async def test_concurrent_revision_requests_allocate_distinct_revision_numbers(client):
    """Revision numbering must be serialised, never duplicated."""
    headers = await login(client)
    created = await _quotation(client, headers, 400)

    numbers = []
    for _ in range(3):
        response = await client.post(f"/api/v1/quotations/{created['id']}/revisions", headers=headers, json={})
        assert response.status_code == 201, response.text
        numbers.append(response.json()["data"]["revisionNo"])

    assert sorted(numbers) == sorted(set(numbers)), f"duplicate revision numbers: {numbers}"
    history = await _revisions(client, headers, created["id"])
    stored = [row["revisionNo"] for row in history]
    assert len(stored) == len(set(stored)) == len(numbers) + 1
