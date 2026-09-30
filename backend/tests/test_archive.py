from __future__ import annotations

from sqlalchemy import select

from app.modules.archive.models import ArchiveRecord
from app.modules.audit.models import AuditEvent
from app.modules.master_data.models import FeeType, TradeDirection
from tests.conftest import login


async def _create_reference(client, headers, collection: str, payload: dict) -> dict:
    response = await client.post(f"/api/v1/{collection}", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _archive(client, headers, collection: str, record_id: str):
    response = await client.request(
        "DELETE", f"/api/v1/{collection}", json={"ids": [record_id]}, headers=headers
    )
    assert response.status_code == 200, response.text


async def test_soft_delete_listing_filters_details_and_pagination(client, session_factory):
    headers = await login(client)
    first = await _create_reference(
        client,
        headers,
        "tradeDirections",
        {"code": "ARCHIVE-ONE", "name": "Archive One", "status": "Inactive"},
    )
    second = await _create_reference(
        client,
        headers,
        "feeTypes",
        {"code": "ARCHIVE-TWO", "name": "Archive Two", "status": "Inactive"},
    )
    await _archive(client, headers, "tradeDirections", first["id"])
    await _archive(client, headers, "feeTypes", second["id"])

    active = await client.get("/api/v1/tradeDirections", headers=headers)
    assert all(item["id"] != first["id"] for item in active.json()["data"]["items"])

    response = await client.get("/api/v1/archive", params={"page": 1, "page_size": 1}, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["meta"]["total"] == 2
    assert len(response.json()["data"]["items"]) == 1

    filtered = await client.get(
        "/api/v1/archive",
        params={"entity_type": "tradeDirections", "q": "Archive One"},
        headers=headers,
    )
    items = filtered.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["entityType"] == "tradeDirections"
    assert items[0]["deletedBy"] == "Demo Administrator"

    by_user = await client.get(
        "/api/v1/archive", params={"deleted_by": items[0]["deletedById"]}, headers=headers
    )
    assert by_user.json()["data"]["meta"]["total"] == 2

    details = await client.get(f"/api/v1/archive/tradeDirections/{first['id']}", headers=headers)
    assert details.status_code == 200
    assert details.json()["data"]["data"]["code"] == "ARCHIVE-ONE"

    async with session_factory() as session:
        row = await session.get(TradeDirection, int(first["id"]))
        archive = (
            await session.execute(
                select(ArchiveRecord).where(
                    ArchiveRecord.entity_type == "tradeDirections",
                    ArchiveRecord.entity_id == int(first["id"]),
                )
            )
        ).scalars().one()
        assert row is not None and row.deleted_at is not None
        assert row.deleted_by_user_id == archive.deleted_by_user_id


async def test_restore_success_duplicate_and_audit(client, session_factory):
    headers = await login(client)
    record = await _create_reference(
        client,
        headers,
        "feeTypes",
        {"code": "RESTORE-ONE", "name": "Restore One", "status": "Inactive"},
    )
    await _archive(client, headers, "feeTypes", record["id"])

    restored = await client.post(f"/api/v1/archive/feeTypes/{record['id']}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["data"]["status"] == "RESTORED"

    duplicate = await client.post(f"/api/v1/archive/feeTypes/{record['id']}/restore", headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ARCHIVE_NOT_ACTIVE"

    visible = await client.get(f"/api/v1/feeTypes/{record['id']}", headers=headers)
    assert visible.status_code == 200

    async with session_factory() as session:
        actions = set(
            (
                await session.execute(
                    select(AuditEvent.action).where(
                        AuditEvent.entity_type == "feeTypes",
                        AuditEvent.entity_id == int(record["id"]),
                    )
                )
            ).scalars()
        )
        assert {"DELETE", "RESTORE"} <= actions


async def test_restore_conflict_when_parent_is_archived(client):
    headers = await login(client)
    parent = await _create_reference(
        client,
        headers,
        "places",
        {"code": "ARCH-PARENT", "name": "Archived Parent", "category": "City", "status": "Inactive"},
    )
    child = await _create_reference(
        client,
        headers,
        "places",
        {
            "code": "ARCH-CHILD",
            "name": "Archived Child",
            "category": "Port",
            "parentPlace": parent["id"],
            "status": "Inactive",
        },
    )
    await _archive(client, headers, "places", child["id"])
    await _archive(client, headers, "places", parent["id"])

    response = await client.post(f"/api/v1/archive/places/{child['id']}/restore", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "RESTORE_CONFLICT"
    assert "still archived" in response.json()["message"]


async def test_hard_delete_success_duplicate_and_audit(client, session_factory):
    headers = await login(client)
    record = await _create_reference(
        client,
        headers,
        "feeTypes",
        {"code": "PURGE-ONE", "name": "Purge One", "status": "Inactive"},
    )
    await _archive(client, headers, "feeTypes", record["id"])

    deleted = await client.delete(f"/api/v1/archive/feeTypes/{record['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["status"] == "HARD_DELETED"
    duplicate = await client.delete(f"/api/v1/archive/feeTypes/{record['id']}", headers=headers)
    assert duplicate.status_code == 409

    async with session_factory() as session:
        assert await session.get(FeeType, int(record["id"])) is None
        event = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "feeTypes",
                    AuditEvent.entity_id == int(record["id"]),
                    AuditEvent.action == "HARD_DELETE",
                    AuditEvent.result == "SUCCESS",
                )
            )
        ).scalars().first()
        assert event is not None


async def test_archive_permissions_are_enforced(client):
    admin_headers = await login(client)
    sales_headers = await login(client, "sales")
    record = await _create_reference(
        client,
        admin_headers,
        "feeTypes",
        {"code": "PERM-ONE", "name": "Permission One", "status": "Inactive"},
    )
    await _archive(client, admin_headers, "feeTypes", record["id"])

    assert (await client.get("/api/v1/archive", headers=sales_headers)).status_code == 403
    assert (
        await client.post(f"/api/v1/archive/feeTypes/{record['id']}/restore", headers=sales_headers)
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/archive/feeTypes/{record['id']}", headers=sales_headers)
    ).status_code == 403


async def test_hard_delete_is_blocked_when_related_rows_exist(client):
    headers = await login(client)
    parent = await _create_reference(
        client,
        headers,
        "places",
        {"code": "BLOCK-PARENT", "name": "Blocked Parent", "category": "City", "status": "Inactive"},
    )
    await _create_reference(
        client,
        headers,
        "places",
        {
            "code": "BLOCK-CHILD",
            "name": "Blocking Child",
            "category": "Port",
            "parentPlace": parent["id"],
            "status": "Inactive",
        },
    )
    await _archive(client, headers, "places", parent["id"])

    response = await client.delete(f"/api/v1/archive/places/{parent['id']}", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "HARD_DELETE_BLOCKED"


async def test_generic_archive_masks_sensitive_snapshot_data(client):
    headers = await login(client)
    company = await _create_reference(
        client,
        headers,
        "companies",
        {"code": "MASK-ONE", "name": "Masked Company", "status": "Inactive", "apiToken": "secret-value"},
    )
    await _archive(client, headers, "companies", company["id"])
    details = await client.get(f"/api/v1/archive/companies/{company['id']}", headers=headers)
    assert details.status_code == 200
    assert details.json()["data"]["data"]["data"]["apiToken"] == "********"
