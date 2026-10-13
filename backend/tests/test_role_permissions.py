from __future__ import annotations

from app.core.permissions import (
    NAVIGATION_PAGE_ALIASES,
    PAGE_PERMISSION_SOURCE_CODES,
    PERMISSION_CATALOG,
    SOURCE_PERMISSIONS,
)
from app.modules.auth import service as auth_service
from tests.conftest import login


def test_permission_catalog_is_unique_and_covers_matrix():
    codes = [code for code, _, _ in PERMISSION_CATALOG]
    assert len(codes) == len(set(codes))
    assert set(PAGE_PERMISSION_SOURCE_CODES).issubset(set(codes))


def test_every_source_permission_is_reachable_from_a_page_checkbox():
    """No capability may be locked away from roles created in the Roles screen."""
    implied = {code for codes in PAGE_PERMISSION_SOURCE_CODES.values() for code in codes}
    unreachable = sorted(code for code, _, _ in SOURCE_PERMISSIONS if code not in implied)
    assert unreachable == []


def test_every_source_permission_has_a_page_key_for_legacy_roles():
    missing = sorted(
        code for code, _, _ in SOURCE_PERMISSIONS if code not in auth_service.PAGE_KEYS_BY_SOURCE
    )
    assert missing == []


def test_operational_capabilities_come_from_the_page_checkboxes():
    expanded = auth_service.expand_source_permissions(
        {
            "operations.service_orders.view",
            "operations.service_orders.edit",
            "sales.quotations.view",
            "finance.financial_documents.edit",
            "master.reference.edit",
        }
    )
    assert {
        "service_order_config.view",
        "service_order_config.create",
        "service_order_config.update",
        "attachment.read",
        "attachment.upload",
        "attachment.delete",
        "customs_credential.retrieve",
    } <= expanded


def test_service_charge_view_is_separate_from_create():
    view_only = auth_service.expand_source_permissions({"finance.service_charges.view"})
    assert "service_charge.read" in view_only
    assert "service_charge.create" not in view_only
    assert "service_charge.create" in auth_service.expand_source_permissions(
        {"finance.service_charges.create"}
    )


def test_navigation_pages_are_granted_by_their_row():
    """Generic-record and report pages must appear for the rows that serve them."""
    permissions = auth_service.expand_source_permissions({"master.reference.view", "report.read"})
    _, pages = auth_service.resolve_page_keys(permissions, False)
    assert "operations.jobs.view" in pages
    assert "operations.customs.view" in pages
    assert "finance.debit_notes.view" in pages
    assert "reports.view" in pages
    assert "finance.accounts_receivable.view" in pages


def test_every_navigation_page_code_expands_to_something():
    """A page code that grants no API permission would render a page that 403s."""
    catalog = {code for code, _, _ in PERMISSION_CATALOG}
    for code, implied in NAVIGATION_PAGE_ALIASES.items():
        assert code in catalog, f"{code} is missing from the catalog"
        assert PAGE_PERMISSION_SOURCE_CODES[code] == implied
        assert set(implied) <= catalog, f"{code} implies an unknown API permission"


def test_page_permissions_expand_to_source_permissions():
    expanded = auth_service.expand_source_permissions(
        {"sales.quotations.view", "sales.quotations.edit", "admin.users.view"}
    )
    assert "quotation.read" in expanded
    assert "quotation.update_draft" in expanded
    assert "user.read" in expanded


def test_resolve_page_keys_includes_matrix_pages():
    permissions = auth_service.expand_source_permissions(
        {"sales.quotations.view", "finance.accounting.view", "finance.accounting.edit"}
    )
    _, pages = auth_service.resolve_page_keys(permissions, False)
    assert "sales.quotations.view" in pages
    assert "finance.accounting.edit" in pages
    assert "finance.accounting.view" in pages
    assert "dashboard.view" in pages


def test_legacy_source_role_still_maps_to_new_pages():
    permissions = auth_service.expand_source_permissions({"quotation.read", "configuration.manage"})
    _, pages = auth_service.resolve_page_keys(permissions, False)
    assert "sales.quotations.view" in pages
    assert "configuration.view" in pages
    assert "settings.app_config.view" in pages


async def test_role_page_permissions_roundtrip(client):
    headers = await login(client)

    created = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "MATRIX_TEST", "name": "Matrix Test", "permissions": ["finance.accounting.view"]},
    )
    assert created.status_code in (200, 201), created.text
    role = created.json()["data"]
    assert role["permissions"] == ["finance.accounting.view"]

    updated = await client.put(
        f"/api/v1/roles/{role['id']}",
        headers=headers,
        json={"permissions": ["finance.accounting.edit", "admin.users.view"]},
    )
    assert updated.status_code == 200, updated.text

    got = await client.get(f"/api/v1/roles/{role['id']}", headers=headers)
    assert got.status_code == 200
    assert set(got.json()["data"]["permissions"]) == {"finance.accounting.edit", "admin.users.view"}


async def test_role_code_is_derived_when_omitted(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"name": "Warehouse Supervisor", "permissions": ["admin.users.view"]},
    )
    assert created.status_code in (200, 201), created.text
    role = created.json()["data"]
    assert role["code"] == "WAREHOUSE_SUPERVISOR"
    assert role["status"] == "ACTIVE"

    # A second role with the same name gets a distinct code.
    second = await client.post(
        "/api/v1/roles", headers=headers, json={"name": "Warehouse Supervisor"}
    )
    assert second.status_code in (200, 201), second.text
    assert second.json()["data"]["code"] != role["code"]


async def test_unknown_permissions_are_rejected(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "BAD_PERMS", "name": "Bad Perms", "permissions": ["not.a.real.permission"]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_role_search_and_status_filter(client):
    headers = await login(client)
    await client.post(
        "/api/v1/roles", headers=headers, json={"code": "SEARCH_ME", "name": "Searchable Role"}
    )
    found = await client.get("/api/v1/roles", headers=headers, params={"q": "Searchable"})
    assert found.status_code == 200
    assert any(row["code"] == "SEARCH_ME" for row in found.json()["data"])

    filtered = await client.get("/api/v1/roles", headers=headers, params={"status": "INACTIVE"})
    assert filtered.status_code == 200
    assert all(row["status"] == "INACTIVE" for row in filtered.json()["data"])
