"""Dashboard reporting correctness.

The dashboard's order KPIs are derived from the service-order status column. The
order lifecycle was simplified to three states (ACTIVE / INACTIVE / FINISHED), but
the dashboard payload kept four pre-simplification key names, and the counters were
looked up by name. Every card therefore reported 0 on every installation, and the
order-by-status chart rendered an empty series even when orders existed.

These tests pin the mapping so the counters cannot silently go dead again.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

# The only statuses a service order can hold; mirrors ORDER_STATUS in
# app/modules/operations/service.py.
LIFECYCLE = ("ACTIVE", "INACTIVE", "FINISHED")


async def _order(client, headers, status: str) -> str:
    """Create a service order through the real workflow and force its status."""
    quotation = await client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "customer": f"Dashboard Customer {status}",
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
    order_id = converted.json()["data"]["serviceOrderId"]
    if status != "ACTIVE":
        updated = await client.put(
            f"/api/v1/service-orders/{order_id}", headers=headers, json={"status": status}
        )
        assert updated.status_code == 200, updated.text
    return order_id


async def _dashboard(client, headers) -> dict:
    response = await client.get("/api/v1/reports/dashboard", headers=headers, params={"granularity": "year"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_dashboard_order_kpis_count_the_real_lifecycle(client):
    headers = await login(client)
    await _order(client, headers, "ACTIVE")
    await _order(client, headers, "ACTIVE")
    await _order(client, headers, "INACTIVE")
    await _order(client, headers, "FINISHED")

    summary = await _dashboard(client, headers)
    kpis = summary["summary"]

    assert kpis["openOrders"] == 2, "active orders must be reported as open"
    assert kpis["inProgressOrders"] == 2, "active orders are the in-progress set"
    assert kpis["onHoldOrders"] == 1, "inactive orders are the parked set"
    assert kpis["awaitingClosure"] == 1, "finished orders await closure"


async def test_dashboard_orders_by_status_chart_uses_real_statuses(client):
    headers = await login(client)
    await _order(client, headers, "ACTIVE")

    summary = await _dashboard(client, headers)
    rows = summary["charts"]["ordersByStatus"]
    statuses = [row["status"] for row in rows]

    assert statuses == list(LIFECYCLE), (
        "the chart must report statuses the application can actually produce; "
        f"got {statuses}"
    )
    assert sum(row["count"] for row in rows) >= 1, "at least the order created above must be counted"
    assert all(row["status"] not in {"OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETED"} for row in rows), (
        "no pre-simplification status may appear in the reporting output"
    )
