"""Attachment lifecycle: upload, list, download and controlled delete.

`attachment.delete` existed in the permission catalog with no endpoint, and
`attachments.is_deleted` was never set, so a file once uploaded stayed readable
indefinitely — even after an operator believed they had removed it.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

# A minimal, valid PNG (1x1). The upload path validates the content signature, so a
# placeholder byte string would be rejected before it reached storage.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


async def _service_order(client, headers) -> str:
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": "Attachment Customer",
            "direction": "Import",
            "currency": "USD",
            "amount": 100,
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


async def _upload(client, headers, name: str = "document.png") -> dict:
    response = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        files={"file": (name, _PNG, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_uploaded_attachment_can_be_deleted_and_stops_being_served(client):
    headers = await login(client)
    attachment = await _upload(client, headers)
    storage_key = attachment["storageKey"]

    served = await client.get(f"/api/v1/attachments/file/{storage_key}", headers=headers)
    assert served.status_code == 200, served.text

    removed = await client.request(
        "DELETE", "/api/v1/attachments", headers=headers, json={"ids": [attachment["id"]]}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["removed"] == 1

    gone = await client.get(f"/api/v1/attachments/file/{storage_key}", headers=headers)
    assert gone.status_code == 404, "a deleted attachment must not be served"


async def test_deleting_an_attachment_twice_is_idempotent(client):
    headers = await login(client)
    attachment = await _upload(client, headers)

    first = await client.request(
        "DELETE", "/api/v1/attachments", headers=headers, json={"ids": [attachment["id"]]}
    )
    assert first.json()["data"]["removed"] == 1

    second = await client.request(
        "DELETE", "/api/v1/attachments", headers=headers, json={"ids": [attachment["id"]]}
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["removed"] == 0, "an already-deleted attachment is not counted again"


async def test_a_deleted_attachment_disappears_from_the_listing(client):
    headers = await login(client)
    order_id = await _service_order(client, headers)
    attachment = await _upload(client, headers)

    listed = await client.get(
        "/api/v1/attachments", headers=headers, params={"module": "jobs", "record_no": order_id}
    )
    assert listed.status_code == 200, listed.text

    removed = await client.request(
        "DELETE", "/api/v1/attachments", headers=headers, json={"ids": [attachment["id"]]}
    )
    assert removed.status_code == 200, removed.text

    after = await client.get(
        "/api/v1/attachments", headers=headers, params={"module": "jobs", "record_no": order_id}
    )
    ids = {row["id"] for row in after.json()["data"]}
    assert attachment["id"] not in ids, "a deleted attachment must not be listed"


async def test_deleting_attachments_requires_a_permission(client):
    """A role without attachment.delete must be refused."""
    headers = await login(client)
    attachment = await _upload(client, headers)

    sales = await login(client, "sales")
    blocked = await client.request(
        "DELETE", "/api/v1/attachments", headers=sales, json={"ids": [attachment["id"]]}
    )
    assert blocked.status_code == 403, blocked.text

    # And it must still be there afterwards.
    still_served = await client.get(
        f"/api/v1/attachments/file/{attachment['storageKey']}", headers=headers
    )
    assert still_served.status_code == 200, still_served.text
