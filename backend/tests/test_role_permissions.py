"""Permission catalog, page→capability compile and Casbin role administration.

This replaces the old suite that asserted a `role_permissions` join table and a
runtime permission implication graph. The vocabulary and the compile step still
deserve regression coverage: they decide what a checkbox in the Roles &
Permissions screen actually grants.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core import authorization
from app.core.authorization.models import CasbinRule
from app.core.permissions import (
    ALL_PERMISSION_CODES,
    PAGE_PERMISSION_CODES,
    PERMISSION_CATALOG,
    ROLE_DEFINITIONS,
    SOURCE_PERMISSION_CODES,
    compile_role_permissions,
    resolve_role_codes,
)
from tests.conftest import login


# --- Catalog ------------------------------------------------------------------
def test_permission_catalog_is_unique_and_fully_classified():
    codes = [code for code, _resource, _action in PERMISSION_CATALOG]
    assert len(codes) == len(set(codes))
    # Every code is either a capability a guard checks or a matrix/menu code.
    assert set(codes) == SOURCE_PERMISSION_CODES | PAGE_PERMISSION_CODES


#: Capabilities that no matrix page grants on purpose: they are coarse fallbacks
#: accepted by a guard, or belong to a feature without an API yet.
COARSE_ONLY_CAPABILITIES = {
    "configuration.manage",  # whole-configuration fallback; the page grants precise codes
    "master.reference.manage",  # whole-master-data fallback for roles saved before the matrix
    "customs_credential.retrieve",  # no endpoint or UI yet (docs/10 §7)
}


def test_every_capability_has_a_page_or_is_a_deliberate_coarse_fallback():
    """No capability may be unreachable from the Roles & Permissions matrix."""
    granted_by_pages = {
        code
        for page_code in PAGE_PERMISSION_CODES
        for code in compile_role_permissions([page_code])
    }
    unreachable = sorted(SOURCE_PERMISSION_CODES - granted_by_pages - COARSE_ONLY_CAPABILITIES)
    assert unreachable == []


def test_a_page_grants_only_the_capabilities_it_declares():
    # A read-only page must never hand out the write capabilities of another page.
    read_only = resolve_role_codes(["configuration.view"])
    assert "configuration.read" in read_only
    assert "configuration.compare" in read_only
    assert "service_order_config.view" in read_only
    assert "configuration.manage" not in read_only
    assert "service_order_config.create" not in read_only
    assert "service_order_config.update" not in read_only
    assert "service_order_config.delete" not in read_only

    create_only = resolve_role_codes(["configuration.create"])
    assert create_only == {"configuration.create", "service_order_config.create"}


def test_settings_view_does_not_escalate_to_settings_write_or_backup():
    view = resolve_role_codes(["settings.app_config.view"])
    assert view == {"settings.app_config.view"}
    assert "settings.app_config.update" not in view
    assert "backup.manage" not in view

    backup = resolve_role_codes(["settings.backup.create"])
    assert "backup.manage" in backup
    assert "settings.app_config.update" not in backup


def test_unticking_a_page_removes_the_capabilities_it_added():
    stored = resolve_role_codes(["sales.quotations.view"])
    assert "quotation.read" in stored
    # The matrix sends only the ticked pages, so a save without that page drops
    # both the page and the capability it carried.
    assert resolve_role_codes(["admin.users.view"]) == {"admin.users.view", "user.read"}
    # A capability with no page behind it stays a deliberate grant.
    assert resolve_role_codes(["backup.read"]) >= {"backup.read"}


def test_compiling_is_idempotent_for_every_catalog_code():
    """Saving the same selection twice must never widen the policy set."""
    not_idempotent = sorted(
        code
        for code in ALL_PERMISSION_CODES
        if resolve_role_codes([code]) != resolve_role_codes(resolve_role_codes([code]))
    )
    assert not_idempotent == []


def test_one_capability_never_grants_an_independent_capability():
    """`quotation.read` must not hand out `attachment.read` (a sibling on the page)."""
    for code in (
        "quotation.read",
        "quotation.update",
        "attachment.read",
        "attachment.upload",
        "user.read",
        "role.read",
        "financial_document.post",
        "backup.read",
    ):
        granted = resolve_role_codes([code])
        extra = sorted(item for item in granted - {code} if item in SOURCE_PERMISSION_CODES)
        assert extra == [], f"{code} also granted {extra}"


def test_seeded_roles_are_defined_with_explicit_grants():
    assert set(ROLE_DEFINITIONS) == {
        "SUPER_ADMIN",
        "ADMIN",
        "MANAGER",
        "SALES",
        "OPERATIONS",
        "ACCOUNTANT",
        "VIEWER",
    }
    for code, definition in ROLE_DEFINITIONS.items():
        if code == "SUPER_ADMIN":
            continue  # wildcard, seeded as a direct policy row
        compiled = compile_role_permissions(definition["permissions"])
        assert compiled, code
        assert "*" not in compiled, code


def test_read_only_roles_never_receive_write_capabilities():
    for code in ("VIEWER",):
        compiled = compile_role_permissions(ROLE_DEFINITIONS[code]["permissions"])
        writes = {
            item
            for item in compiled
            if item.rsplit(".", 1)[-1]
            in {"create", "update", "delete", "manage", "post", "reverse", "publish", "close"}
        }
        assert writes == set()


# --- Casbin administration ----------------------------------------------------
async def test_creating_a_role_stores_policy_rows(client, session_factory):
    headers = await login(client)
    created = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "POLICY_PROBE", "name": "Policy Probe", "permissions": ["sales.quotations.view"]},
    )
    assert created.status_code == 201, created.text
    role_id = created.json()["data"]["id"]

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(CasbinRule).where(
                    CasbinRule.ptype == "p",
                    CasbinRule.v0 == "role:POLICY_PROBE",
                )
            )
        ).scalars().all()
    granted = {f"{row.v1}.{row.v2}" for row in rows}
    assert {"quotation.read", "sales.quotations.view"} <= granted

    # Grant and revoke endpoints write the same store.
    granted_more = await client.post(
        f"/api/v1/roles/{role_id}/permissions",
        headers=headers,
        json={"permissions": ["admin.users.view"]},
    )
    assert granted_more.status_code == 200, granted_more.text
    assert "user.read" in granted_more.json()["data"]["permissions"]

    revoked = await client.request(
        "DELETE",
        f"/api/v1/roles/{role_id}/permissions",
        headers=headers,
        json={"permissions": ["admin.users.view"]},
    )
    assert revoked.status_code == 200, revoked.text
    assert "user.read" not in revoked.json()["data"]["permissions"]


async def test_role_permissions_are_direct_and_inheritance_is_gone(client):
    headers = await login(client)
    parent = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "INH_PARENT", "name": "Inheritance Parent", "permissions": ["admin.users.view"]},
    )
    assert parent.status_code == 201, parent.text
    child = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "code": "INH_CHILD",
            "name": "Inheritance Child",
            "permissions": ["sales.quotations.view"],
            "parentRoles": ["INH_PARENT"],
        },
    )
    # The inheritance field no longer exists in the API.
    assert child.status_code == 422, child.text
    detail = (await client.get(f"/api/v1/roles/{parent.json()['data']['id']}", headers=headers)).json()["data"]
    assert "parentRoles" not in detail
    assert "inheritedPermissions" not in detail
    assert "effectivePermissions" not in detail
    assert "childRoles" not in detail
    # The inheritance endpoints are gone.
    gone = await client.put(
        f"/api/v1/roles/{parent.json()['data']['id']}/inheritance",
        headers=headers,
        json={"parentRoles": ["INH_PARENT"]},
    )
    assert gone.status_code in (404, 405), gone.text

    # A user holding the parent gains nothing from a child role or vice versa:
    # the role's own grants are the whole story.
    user = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "inh.user",
            "displayName": "Direct User",
            "email": "inh.user@example.com",
            "password": "Passw0rd!",
            "roleCode": "INH_PARENT",
        },
    )
    assert user.status_code == 201, user.text
    effective = await client.get(
        f"/api/v1/users/{user.json()['data']['id']}/effective-permissions", headers=headers
    )
    assert effective.status_code == 200, effective.text
    codes = set(effective.json()["data"]["permissions"])
    assert "user.read" in codes
    assert "quotation.read" not in codes  # nothing inherited


async def test_unknown_permission_codes_are_rejected(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "BAD_CODES", "name": "Bad Codes", "permissions": ["quotation.fly"]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_inactive_role_grants_nothing(client):
    """A deactivated role is skipped when the enforcer loads."""
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "OFF_ROLE", "name": "Off Role", "permissions": ["admin.users.view"]},
    )
    assert role.status_code == 201, role.text
    user = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "off.user",
            "displayName": "Off User",
            "email": "off.user@example.com",
            "password": "Passw0rd!",
            "roleCode": "OFF_ROLE",
        },
    )
    assert user.status_code == 201, user.text
    user_headers = await login(client, "off.user")
    assert (await client.get("/api/v1/users", headers=user_headers)).status_code == 200

    # Deactivating is refused while an active user holds the role; the guard is
    # the point, because a disabled role must never keep granting access.
    blocked = await client.put(
        f"/api/v1/roles/{role.json()['data']['id']}",
        headers=headers,
        json={"status": "INACTIVE"},
    )
    assert blocked.status_code == 409, blocked.text


async def test_every_catalog_code_is_known_to_the_casbin_enforcer(client):
    """The matrix, the guards and the policy store must agree on the vocabulary."""
    headers = await login(client)
    catalog = await client.get("/api/v1/permissions/catalog", headers=headers)
    assert catalog.status_code == 200, catalog.text
    data = catalog.json()["data"]
    listed = {entry["code"] for module in data["modules"] for entry in module["permissions"]}
    assert listed == set(ALL_PERMISSION_CODES)
    page_codes = {
        code for page in data["pages"] for code in page["permissions"]
    }
    assert page_codes <= set(ALL_PERMISSION_CODES)
    # Default deny: an unknown subject holds nothing, and a code nobody granted
    # is refused. (The seeded ``admin`` is the protected wildcard holder, so it is
    # the wrong subject for this check.)
    assert authorization.can(987654, "quotation.read") is False
    assert authorization.effective_codes(987654) == frozenset()
    assert authorization.is_super_admin(1) is True
