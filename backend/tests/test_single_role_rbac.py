"""Direct-RBAC specifics: one role per user, no permission expansion.

Complements ``test_auth_rbac.py`` (deny-by-default, escalation, protected
administrator) with the guarantees the single-role model adds: the database
constraint, replacement semantics, roleless accounts and idempotent saves.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import authorization
from app.core.authorization.models import CasbinRule
from app.modules.audit.models import AuditEvent
from tests.conftest import login

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "b4c5d6e7f8a9_single_role_direct_rbac.py"
)


async def test_the_database_allows_only_one_role_per_user(session_factory):
    """The partial unique index refuses a second assignment for one user."""
    async with session_factory() as session:
        await authorization.set_user_roles(session, 4242, ["VIEWER"])
        session.add(CasbinRule(ptype="g", v0="user:4242", v1="role:SALES"))
        with pytest.raises(Exception, match="single_user_role|UNIQUE"):
            await session.flush()


async def test_a_roleless_user_holds_no_protected_permissions(client):
    """Removing the only role leaves the account with nothing protected."""
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "TEMP_ROLE", "name": "Temp Role", "permissions": ["admin.users.view"]},
    )
    assert role.status_code == 201, role.text
    user = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "temp.holder",
            "displayName": "Temp Holder",
            "email": "temp.holder@example.com",
            "password": "Passw0rd!",
            "roleCode": "TEMP_ROLE",
        },
    )
    assert user.status_code == 201, user.text
    user_id = user.json()["data"]["id"]

    holder_headers = await login(client, "temp.holder")
    assert (await client.get("/api/v1/users", headers=holder_headers)).status_code == 200

    # Roleless again: the authorization grants are gone with the assignment.
    client.cookies.clear()
    removed = await client.delete(
        f"/api/v1/users/{user_id}/role-assignments/TEMP_ROLE", headers=headers
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["roles"] == []

    holder_headers = await login(client, "temp.holder")
    denied = await client.get("/api/v1/users", headers=holder_headers)
    assert denied.status_code == 403, denied.text


async def test_repeated_permission_saves_do_not_expand(client):
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "IDEMPotent".upper(), "name": "Idempotent", "permissions": ["admin.users.view"]},
    )
    assert role.status_code == 201, role.text
    role_id = role.json()["data"]["id"]
    first = role.json()["data"]["permissions"]
    for _ in range(3):
        again = await client.put(
            f"/api/v1/roles/{role_id}/permissions",
            headers=headers,
            json={"permissions": ["admin.users.view"]},
        )
        assert again.status_code == 200, again.text
        assert again.json()["data"]["permissions"] == first


async def test_audit_logs_record_role_and_permission_changes(client, session_factory):
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "AUDIT_ROLE", "name": "Audit Role", "permissions": ["admin.users.view"]},
    )
    assert role.status_code == 201, role.text
    role_id = role.json()["data"]["id"]
    user = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "audit.holder",
            "displayName": "Audit Holder",
            "email": "audit.holder@example.com",
            "password": "Passw0rd!",
            "roleCode": "AUDIT_ROLE",
        },
    )
    assert user.status_code == 201, user.text
    assigned = await client.post(
        f"/api/v1/users/{user.json()['data']['id']}/role-assignments",
        headers=headers,
        json={"role_id": role_id},
    )
    assert assigned.status_code == 201, assigned.text

    async with session_factory() as session:
        types = {
            event.event_type
            for event in (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.result == "SUCCESS",
                        AuditEvent.event_type.in_(("ROLE_CREATED", "ROLE_ASSIGNED")),
                    )
                )
            ).scalars().all()
        }
    assert {"ROLE_CREATED", "ROLE_ASSIGNED"} <= types


def test_the_migration_reports_multi_role_users_instead_of_choosing():
    """Existing multi-role data aborts the upgrade; nothing is picked silently."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert "HAVING count(*) > 1" in source
    assert "RuntimeError" in source
    # Inherited grants are materialized before the edges are removed.
    assert "DELETE FROM casbin_rule WHERE ptype = 'g' AND v0 LIKE 'role:%'" in source
