from __future__ import annotations

from app.core.permissions import PAGE_PERMISSION_SOURCE_CODES, PERMISSION_CATALOG
from app.modules.auth import service as auth_service
from tests.conftest import login


def test_permission_catalog_is_unique_and_covers_matrix():
    codes = [code for code, _, _ in PERMISSION_CATALOG]
    assert len(codes) == len(set(codes))
    assert set(PAGE_PERMISSION_SOURCE_CODES).issubset(set(codes))


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
