from __future__ import annotations

from tests.conftest import login


async def _items(client, url: str, params: dict, headers: dict) -> list[dict]:
    response = await client.get(url, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


async def test_service_order_sort_key_maps_camel_case_to_column(client):
    """sortKey/sortDir order by the mapped column (serviceOrderNo -> service_order_no)."""
    headers = await login(client)
    for _ in range(2):
        created = await client.post("/api/v1/service-orders", json={}, headers=headers)
        assert created.status_code == 201, created.text

    ascending = await _items(
        client, "/api/v1/service-orders", {"sortKey": "serviceOrderNo", "sortDir": "asc"}, headers
    )
    descending = await _items(
        client, "/api/v1/service-orders", {"sortKey": "serviceOrderNo", "sortDir": "desc"}, headers
    )
    assert len(ascending) >= 2
    numbers = [row["serviceOrderNo"] for row in ascending]
    assert numbers == sorted(numbers)
    assert [row["serviceOrderNo"] for row in descending] == list(reversed(numbers))


async def test_document_sequences_sort_and_unknown_key_fallback(client):
    headers = await login(client)
    ascending = await _items(
        client, "/api/v1/document-sequences", {"sortKey": "documentType", "sortDir": "asc"}, headers
    )
    descending = await _items(
        client, "/api/v1/document-sequences", {"sortKey": "documentType", "sortDir": "desc"}, headers
    )
    assert len(ascending) >= 2
    types = [row["documentType"] for row in ascending]
    assert types == sorted(types)
    assert [row["documentType"] for row in descending] == list(reversed(types))

    # Keys that do not map to a column fall back to the endpoint default order.
    default = await _items(client, "/api/v1/document-sequences", {}, headers)
    fallback = await _items(
        client, "/api/v1/document-sequences", {"sortKey": "notAColumn", "sortDir": "desc"}, headers
    )
    assert [row["id"] for row in fallback] == [row["id"] for row in default]


async def test_chart_of_accounts_sort_desc(client):
    headers = await login(client)
    descending = await _items(
        client, "/api/v1/chart-of-accounts", {"sortKey": "accountCode", "sortDir": "desc"}, headers
    )
    codes = [row["accountCode"] for row in descending]
    assert len(codes) >= 2
    assert codes == sorted(codes, reverse=True)


async def test_reference_sort_accepts_camel_case_key(client):
    headers = await login(client)
    descending = await _items(
        client, "/api/v1/businessParties", {"sortKey": "partyCode", "sortDir": "desc"}, headers
    )
    codes = [row["partyCode"] for row in descending]
    assert len(codes) >= 2
    assert codes == sorted(codes, reverse=True)


async def test_archive_sort_uses_api_field_aliases(client):
    headers = await login(client)
    first = await client.post(
        "/api/v1/tradeDirections",
        json={"code": "SORT-ONE", "name": "Sort One", "status": "Inactive"},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/api/v1/feeTypes",
        json={"code": "SORT-TWO", "name": "Sort Two", "status": "Inactive"},
        headers=headers,
    )
    assert second.status_code == 201, second.text
    for collection, record_id in (
        ("tradeDirections", first.json()["data"]["id"]),
        ("feeTypes", second.json()["data"]["id"]),
    ):
        deleted = await client.request(
            "DELETE", f"/api/v1/{collection}", json={"ids": [record_id]}, headers=headers
        )
        assert deleted.status_code == 200, deleted.text

    ascending = await _items(client, "/api/v1/archive", {"sortKey": "module", "sortDir": "asc"}, headers)
    descending = await _items(client, "/api/v1/archive", {"sortKey": "module", "sortDir": "desc"}, headers)
    modules = [row["module"] for row in ascending]
    assert len(modules) >= 2
    assert modules == sorted(modules)
    assert [row["module"] for row in descending] == list(reversed(modules))


async def _bare_list(client, url: str, params: dict, headers: dict) -> list[dict]:
    response = await client.get(url, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_users_sort_by_display_name(client):
    """The users list accepts sortKey/sortDir even though it is not paginated."""
    headers = await login(client)
    ascending = await _bare_list(client, "/api/v1/users", {"sortKey": "displayName", "sortDir": "asc"}, headers)
    descending = await _bare_list(client, "/api/v1/users", {"sortKey": "displayName", "sortDir": "desc"}, headers)
    names = [row["displayName"] for row in ascending]
    assert len(names) >= 2
    assert names == sorted(names)
    assert [row["displayName"] for row in descending] == list(reversed(names))

    # An unknown key must not break the endpoint; it falls back to the default order.
    fallback = await _bare_list(client, "/api/v1/users", {"sortKey": "notAColumn", "sortDir": "asc"}, headers)
    default = await _bare_list(client, "/api/v1/users", {}, headers)
    assert [row["id"] for row in fallback] == [row["id"] for row in default]


async def test_roles_sort_by_code(client):
    headers = await login(client)
    ascending = await _bare_list(client, "/api/v1/roles", {"sortKey": "code", "sortDir": "asc"}, headers)
    codes = [row["code"] for row in ascending]
    assert len(codes) >= 2
    assert codes == sorted(codes)


async def test_accounting_periods_sort_by_start_date(client):
    headers = await login(client)
    ascending = await _bare_list(
        client, "/api/v1/accounting-periods", {"sortKey": "startDate", "sortDir": "asc"}, headers
    )
    starts = [row["startDate"] for row in ascending]
    assert len(starts) >= 2
    assert starts == sorted(starts)

    default = await _bare_list(client, "/api/v1/accounting-periods", {}, headers)
    fallback = await _bare_list(
        client, "/api/v1/accounting-periods", {"sortKey": "notAColumn", "sortDir": "asc"}, headers
    )
    assert [row["id"] for row in fallback] == [row["id"] for row in default]
