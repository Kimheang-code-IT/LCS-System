"""Configuration version lifecycle: activation, rollback, compare and audit.

These tests exercise the guarantees the history screen depends on rather than
only the first publish:

* the active pointer changes without mutating the old snapshot;
* rollback copies history into a new version and keeps the source;
* historical Service Orders render their captured snapshot after live edits;
* every lifecycle action is audited and permission-checked.
"""

from __future__ import annotations

import pytest

from tests.conftest import login
from tests.test_config_versions import _create_tab, _publish, _service_order

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/configuration-versions"


async def _active(client, headers) -> dict | None:
    response = await client.get(f"{BASE}/active", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _versions(client, headers) -> list[dict]:
    response = await client.get(BASE, headers=headers, params={"page_size": 200})
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


async def _detail(client, headers, version_id: str) -> dict:
    response = await client.get(f"{BASE}/{version_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_publish_records_hash_actor_and_active_version(client):
    headers = await login(client)
    published = await _publish(client, headers, "first release")
    assert published.status_code == 201, published.text
    version = published.json()["data"]

    assert version["origin"] == "PUBLISH"
    assert version["scope"] == "GLOBAL"
    assert version["snapshotSchemaVersion"] == 2
    assert version["contentHash"]
    assert version["publishedBy"]
    assert version["activatedAt"]
    assert version["sourceVersionId"] is None

    active = await _active(client, headers)
    assert active is not None
    assert active["id"] == version["id"]
    assert active["versionNo"] == version["versionNo"]


async def test_activation_restores_an_earlier_snapshot_without_changing_it(client):
    headers = await login(client)
    first = (await _publish(client, headers, "v1")).json()["data"]
    before = await _detail(client, headers, first["id"])

    await _create_tab(client, headers, "EXTRA", "Extra")
    second = (await _publish(client, headers, "v2")).json()["data"]
    assert second["versionNo"] == 2

    activated = await client.post(f"{BASE}/{first['id']}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    assert activated.json()["data"]["status"] == "PUBLISHED"
    assert activated.json()["data"]["activatedBy"]

    active = await _active(client, headers)
    assert active["id"] == first["id"]

    statuses = {row["versionNo"]: row["status"] for row in await _versions(client, headers)}
    assert statuses == {1: "PUBLISHED", 2: "RETIRED"}

    after = await _detail(client, headers, first["id"])
    assert after["configSnapshot"] == before["configSnapshot"], "activation must not rewrite history"

    # New Service Orders follow the activated version.
    order_id = await _service_order(client, headers)
    pinned = await client.get(f"/api/v1/service-orders/{order_id}/configuration-version", headers=headers)
    assert pinned.json()["data"]["id"] == first["id"]


async def test_rollback_creates_a_new_version_and_keeps_the_source(client):
    headers = await login(client)
    first = (await _publish(client, headers, "baseline")).json()["data"]
    source_snapshot = (await _detail(client, headers, first["id"]))["configSnapshot"]

    await _create_tab(client, headers, "EXTRA", "Extra")
    second = (await _publish(client, headers, "extra tab")).json()["data"]
    assert second["versionNo"] == 2

    rolled = await client.post(
        f"{BASE}/{first['id']}/rollback",
        headers=headers,
        json={"reason": "Restore the baseline layout"},
    )
    assert rolled.status_code == 201, rolled.text
    version = rolled.json()["data"]

    assert version["versionNo"] == 3
    assert version["origin"] == "ROLLBACK"
    assert version["status"] == "PUBLISHED"
    assert version["sourceVersionId"] == first["id"]
    assert version["sourceVersionNo"] == 1
    assert version["changeNote"] == "Restore the baseline layout"
    assert version["configSnapshot"] == source_snapshot

    # v1 and v2 remain in history, only v3 is active.
    statuses = {row["versionNo"]: row["status"] for row in await _versions(client, headers)}
    assert statuses == {1: "RETIRED", 2: "RETIRED", 3: "PUBLISHED"}


async def test_rollback_requires_a_reason(client):
    headers = await login(client)
    first = (await _publish(client, headers)).json()["data"]
    await _create_tab(client, headers, "EXTRA", "Extra")
    await _publish(client, headers, "second")

    rejected = await client.post(f"{BASE}/{first['id']}/rollback", headers=headers, json={"reason": "   "})
    assert rejected.status_code == 422, rejected.text
    assert "reason" in rejected.json()["field_errors"]


async def test_compare_uses_stable_ids_to_report_changes(client):
    headers = await login(client)
    first = (await _publish(client, headers, "v1")).json()["data"]
    await _create_tab(client, headers, "EXTRA", "Extra")
    second = (await _publish(client, headers, "v2")).json()["data"]

    compared = await client.get(f"{BASE}/{first['id']}/compare/{second['id']}", headers=headers)
    assert compared.status_code == 200, compared.text
    data = compared.json()["data"]
    assert data["changes"]["summary"]["addedTabs"] == 1
    assert [tab["code"] for tab in data["changes"]["tabs"]["added"]] == ["extra"]

    same = await client.get(f"{BASE}/{second['id']}/compare/{second['id']}", headers=headers)
    assert same.status_code == 200, same.text
    assert same.json()["data"]["changes"]["unchanged"] is True


async def test_lifecycle_actions_are_audited(client):
    headers = await login(client)
    first = (await _publish(client, headers, "audit v1")).json()["data"]
    await _create_tab(client, headers, "EXTRA", "Extra")
    second = (await _publish(client, headers, "audit v2")).json()["data"]

    activated = await client.post(f"{BASE}/{first['id']}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    rolled = await client.post(
        f"{BASE}/{second['id']}/rollback", headers=headers, json={"reason": "Audit rollback"}
    )
    assert rolled.status_code == 201, rolled.text
    rolled_id = rolled.json()["data"]["id"]

    history = await client.get(f"{BASE}/activation-history", headers=headers, params={"page_size": 50})
    assert history.status_code == 200, history.text
    actions = [event["action"] for event in history.json()["data"]["items"]]
    assert "PUBLISH" in actions
    assert "ACTIVATE" in actions
    assert "ROLLBACK" in actions

    version_history = await client.get(f"{BASE}/{rolled_id}/activate-history", headers=headers)
    assert version_history.status_code == 200, version_history.text
    assert [event["action"] for event in version_history.json()["data"]["items"]] == ["ROLLBACK"]


async def test_historical_service_order_renders_its_captured_snapshot(client):
    headers = await login(client)
    first = (await _publish(client, headers, "captured layout")).json()["data"]
    order_id = await _service_order(client, headers)

    before = await client.get(f"/api/v1/service-orders/{order_id}/component-tabs", headers=headers)
    assert before.status_code == 200, before.text
    captured = before.json()["data"]
    assert captured["configVersionId"] == first["id"]
    assert any(tab["code"] == "CUSTOMS" for tab in captured["tabs"])

    tabs = await client.get("/api/v1/component-tabs", headers=headers, params={"page_size": 200})
    customs = next(tab for tab in tabs.json()["data"]["items"] if tab["code"] == "CUSTOMS")
    renamed = await client.patch(
        f"/api/v1/component-tabs/{customs['id']}", headers=headers, json={"name": "Customs Renamed"}
    )
    assert renamed.status_code == 200, renamed.text
    assert (await _publish(client, headers, "rename tab")).status_code == 201

    after = await client.get(f"/api/v1/service-orders/{order_id}/component-tabs", headers=headers)
    assert after.status_code == 200, after.text
    historical = after.json()["data"]
    assert historical["configVersionId"] == first["id"]
    # The order keeps the name frozen in its version, not the live one.
    assert next(tab for tab in historical["tabs"] if tab["code"] == "CUSTOMS")["name"] == "Customs"

    new_order_id = await _service_order(client, headers)
    current = await client.get(f"/api/v1/service-orders/{new_order_id}/component-tabs", headers=headers)
    assert current.status_code == 200, current.text
    assert next(tab for tab in current.json()["data"]["tabs"] if tab["code"] == "CUSTOMS")["name"] == "Customs Renamed"


async def test_lifecycle_endpoints_require_permission_and_reject_invalid_ids(client):
    sales = await login(client, "sales")
    headers = await login(client)
    first = (await _publish(client, headers)).json()["data"]

    for method, url, body in (
        ("post", BASE, {"changeNote": "denied"}),
        ("post", f"{BASE}/{first['id']}/activate", None),
        ("post", f"{BASE}/{first['id']}/rollback", {"reason": "denied"}),
        ("get", f"{BASE}/{first['id']}/compare/{first['id']}", None),
    ):
        response = await getattr(client, method)(url, headers=sales, json=body) if body is not None else await getattr(client, method)(url, headers=sales)
        assert response.status_code == 403, response.text

    assert (await client.get(f"{BASE}/999999", headers=headers)).status_code == 404
    assert (await client.post(f"{BASE}/999999/activate", headers=headers)).status_code == 404
    assert (
        await client.post(f"{BASE}/999999/rollback", headers=headers, json={"reason": "missing"})
    ).status_code == 404
    assert (await client.get(f"{BASE}/999999/compare/{first['id']}", headers=headers)).status_code == 404


async def test_duplicate_version_number_race_is_rejected_without_losing_the_active_version(client, monkeypatch):
    """A forced duplicate allocation must roll back, never leave two versions.

    The real race is prevented by the advisory/row lock plus the unique
    constraint. SQLite's shared in-memory connection cannot run two
    transactions concurrently, so this test forces the duplicate allocation
    deterministically and proves the constraint path repairs the transaction.
    """
    from app.modules.master_data import config_versions

    headers = await login(client)
    first = await _publish(client, headers, "first")
    assert first.status_code == 201, first.text

    await _create_tab(client, headers, "EXTRA", "Extra")

    async def duplicate_version_no(_session):
        return 1

    monkeypatch.setattr(config_versions, "_next_version_no", duplicate_version_no)
    rejected = await _publish(client, headers, "race")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "CONFIGURATION_PUBLISH_CONFLICT"

    versions = await _versions(client, headers)
    assert len(versions) == 1
    assert versions[0]["versionNo"] == 1
    assert versions[0]["status"] == "PUBLISHED", "the failed publish must restore the previous active row"
    assert len({version["versionNo"] for version in versions}) == len(versions)
