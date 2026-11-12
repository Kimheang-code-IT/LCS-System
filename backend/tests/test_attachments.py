"""Attachment lifecycle: upload, list, download and controlled delete.

`attachment.delete` existed in the permission catalog with no endpoint, and
`attachments.is_deleted` was never set, so a file once uploaded stayed readable
indefinitely — even after an operator believed they had removed it.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import ValidationFailed
from tests.conftest import login

pytestmark = pytest.mark.asyncio


class _InMemoryProvider:
    """Stands in for the configured cloud provider (no network in tests)."""

    tag = "r2"
    supports_presign = False

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str, file_name: str = "") -> str:
        self._objects[key] = (data, content_type)
        return key

    def get(self, key: str) -> tuple[bytes, str]:
        return self._objects[key]

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._objects

    def size(self, key: str) -> int | None:
        return len(self._objects[key][0]) if key in self._objects else None

    def checksum(self, key: str) -> str | None:
        return None

    def presigned_get(self, key: str, expires: int = 300) -> str | None:
        return None


@pytest.fixture(autouse=True)
def _fake_storage_provider(monkeypatch):
    """Resolve uploads to an in-memory provider: no MinIO, no cloud call."""
    from app.modules.storage import service as storage_service

    provider = _InMemoryProvider()

    async def fake_resolve(session):  # noqa: ANN001, ANN202
        return provider, provider.tag

    async def fake_build(session, tag):  # noqa: ANN001, ARG001
        return provider

    monkeypatch.setattr(storage_service, "resolve_upload_target", fake_resolve)
    monkeypatch.setattr(storage_service, "build_provider", fake_build)
    return provider


async def test_upload_refused_without_configured_provider(client, monkeypatch):
    """No MinIO/env fallback: uploads require an activated provider."""
    from app.modules.storage import service as storage_service

    async def unconfigured(session):  # noqa: ANN001, ANN202
        raise ValidationFailed(
            "File storage is not set up. Configure Cloudflare R2 or Google Drive in Settings → Storage & Backup first.",
            {"storage": "No provider configured."},
        )

    monkeypatch.setattr(storage_service, "resolve_upload_target", unconfigured)
    headers = await login(client)
    response = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        files={"file": ("document.png", _PNG, "image/png")},
    )
    assert response.status_code == 422
    assert "File storage is not set up" in response.json()["message"]


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


async def _upload(client, headers, name: str = "document.png", note: str | None = None) -> dict:
    data = {"note": note} if note is not None else None
    response = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        data=data,
        files={"file": (name, _PNG, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_attachment_module_must_be_a_supported_collection(client):
    headers = await login(client)
    rejected = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        data={"module": "not-a-real-module", "record_no": "1"},
        files={"file": ("document.png", _PNG, "image/png")},
    )
    assert rejected.status_code == 422, rejected.text
    assert "Unsupported entity type" in rejected.text

    linked = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        data={"module": "jobs", "record_no": "1"},
        files={"file": ("document.png", _PNG, "image/png")},
    )
    assert linked.status_code == 201, linked.text
    listed = await client.get("/api/v1/attachments", headers=headers, params={"module": "jobs", "record_no": "1"})
    assert any(item["id"] == linked.json()["data"]["id"] for item in listed.json()["data"])


async def test_an_upload_note_is_saved_listed_and_editable(client):
    headers = await login(client)
    attachment = await _upload(client, headers, note="  Signed copy  ")
    assert attachment["note"] == "Signed copy", "surrounding whitespace is trimmed"

    listed = await client.get(
        "/api/v1/attachments",
        headers=headers,
        params={"module": "jobs", "record_no": "0"},
    )
    assert listed.status_code == 200, listed.text

    edited = await client.patch(
        f"/api/v1/attachments/{attachment['id']}",
        headers=headers,
        json={"note": "Checked against the booking"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["note"] == "Checked against the booking"

    cleared = await client.patch(
        f"/api/v1/attachments/{attachment['id']}", headers=headers, json={"note": "   "}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["note"] is None, "an empty note is stored as NULL"


async def test_an_attachment_note_longer_than_the_limit_is_refused(client):
    headers = await login(client)
    attachment = await _upload(client, headers)
    too_long = await client.patch(
        f"/api/v1/attachments/{attachment['id']}",
        headers=headers,
        json={"note": "x" * 1001},
    )
    assert too_long.status_code == 422, too_long.text


async def test_editing_an_attachment_note_requires_upload_permission(client):
    headers = await login(client)
    attachment = await _upload(client, headers, note="Original")

    created = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "note.auditor",
            "displayName": "Note Auditor",
            "email": "note.auditor@example.com",
            "password": "Passw0rd!",
            "status": "Active",
            "role": "VIEWER",
        },
    )
    assert created.status_code == 201, created.text
    auditor = await login(client, "note.auditor")

    blocked = await client.patch(
        f"/api/v1/attachments/{attachment['id']}", headers=auditor, json={"note": "Not allowed"}
    )
    assert blocked.status_code == 403, blocked.text


async def test_an_upload_can_be_linked_to_its_quotation_and_listed(client):
    headers = await login(client)
    parties = await client.get("/api/v1/businessParties", headers=headers, params={"page_size": 200})
    party_id = parties.json()["data"]["items"][0]["id"]
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customerPartyId": party_id,
            "direction": "Import",
            "currency": "USD",
        },
    )
    assert quotation.status_code == 201, quotation.text
    quotation_id = quotation.json()["data"]["id"]

    uploaded = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        data={"module": "quotations", "record_no": quotation_id},
        files={"file": ("quote.png", _PNG, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text

    listed = await client.get(
        "/api/v1/attachments",
        headers=headers,
        params={"module": "quotations", "record_no": quotation_id},
    )
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()["data"]] == [uploaded.json()["data"]["id"]]


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

    created = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "attachment.viewer",
            "displayName": "Attachment Viewer",
            "email": "attachment.viewer@example.com",
            "password": "Passw0rd!",
            "status": "Active",
            "role": "VIEWER",
        },
    )
    assert created.status_code == 201, created.text
    viewer = await login(client, "attachment.viewer")
    blocked = await client.request(
        "DELETE", "/api/v1/attachments", headers=viewer, json={"ids": [attachment["id"]]}
    )
    assert blocked.status_code == 403, blocked.text

    # And it must still be there afterwards.
    still_served = await client.get(
        f"/api/v1/attachments/file/{attachment['storageKey']}", headers=headers
    )
    assert still_served.status_code == 200, still_served.text
