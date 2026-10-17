from __future__ import annotations

from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from tests.conftest import login


async def _create_user(client, headers, **overrides) -> dict:
    payload = {
        "username": "rbac.user",
        "displayName": "RBAC User",
        "email": "rbac.user@example.com",
        "password": "Passw0rd!",
        "status": "Active",
        "role": "AUDITOR",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/users", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _protected_admin(client, headers) -> dict:
    users = (await client.get("/api/v1/users", headers=headers)).json()["data"]
    return next(item for item in users if item.get("isProtectedSystemAccount") is True)


async def _roles(client, headers) -> list[dict]:
    return (await client.get("/api/v1/roles", headers=headers)).json()["data"]["items"]


async def test_user_has_exactly_one_role_and_replacement(client):
    headers = await login(client)
    user = await _create_user(
        client,
        headers,
        username="single.user",
        email="single.user@example.com",
        roles=["AUDITOR"],
    )
    assert user["roles"] == ["AUDITOR"]

    # Changing the role replaces the previous assignment (never adds a second).
    updated = await client.put(
        f"/api/v1/users/{user['id']}",
        headers=headers,
        json={"roles": ["SALES_OFFICER"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["roles"] == ["SALES_OFFICER"]

    detail = await client.get(f"/api/v1/users/{user['id']}", headers=headers)
    assert detail.json()["data"]["roles"] == ["SALES_OFFICER"]

    # A payload that tries to assign more than one role is rejected.
    multiple = await client.put(
        f"/api/v1/users/{user['id']}",
        headers=headers,
        json={"roles": ["AUDITOR", "SALES_OFFICER"]},
    )
    assert multiple.status_code == 422, multiple.text

    # Clearing every role is rejected: a user must keep exactly one role.
    cleared = await client.put(
        f"/api/v1/users/{user['id']}",
        headers=headers,
        json={"roles": []},
    )
    assert cleared.status_code == 422, cleared.text


async def test_user_create_requires_a_role(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "no.role",
            "displayName": "No Role",
            "email": "no.role@example.com",
            "password": "Passw0rd!",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_least_privilege_default_deny(client, session_factory):
    ops_headers = await login(client, "ops.pp")
    response = await client.get("/api/v1/users", headers=ops_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"
    async with session_factory() as session:
        event = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.event_type == "AUTHORIZATION_DENIED",
                    AuditEvent.action == "user.read",
                    AuditEvent.result == "REJECTED",
                )
            )
        ).scalars().first()
        assert event is not None


async def test_account_lockout_after_repeated_failures(client):
    headers = await login(client)
    await _create_user(client, headers, username="lock.user", email="lock.user@example.com")

    for _ in range(5):
        attempt = await client.post(
            "/api/v1/auth/login", json={"username": "lock.user", "password": "wrong-password"}
        )
        assert attempt.status_code == 401

    locked = await client.post(
        "/api/v1/auth/login", json={"username": "lock.user", "password": "Passw0rd!"}
    )
    assert locked.status_code == 401
    assert "locked" in locked.json()["message"].lower()


async def test_password_change_revokes_existing_tokens(client):
    headers = await login(client)
    await _create_user(client, headers, username="pw.user", email="pw.user@example.com")

    session_response = await client.post(
        "/api/v1/auth/login", json={"username": "pw.user", "password": "Passw0rd!"}
    )
    access = session_response.json()["data"]["access_token"]
    user_headers = {"Authorization": f"Bearer {access}"}
    assert (await client.get("/api/v1/auth/me", headers=user_headers)).status_code == 200

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={"current_password": "Passw0rd!", "password": "NewPassw0rd!"},
    )
    assert changed.status_code == 200, changed.text

    # The previously issued access token must be rejected after the change.
    assert (await client.get("/api/v1/auth/me", headers=user_headers)).status_code == 401


async def test_privilege_escalation_is_blocked(client):
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "code": "ROLE_MGR",
            "name": "Role Manager",
            "permissions": ["admin.roles.view", "admin.roles.create", "admin.roles.edit", "admin.roles.delete"],
        },
    )
    assert role.status_code == 201, role.text
    await _create_user(
        client,
        headers,
        username="role.mgr",
        email="role.mgr@example.com",
        roles=["ROLE_MGR"],
    )

    admin_id = next(
        item["id"] for item in (await client.get("/api/v1/users", headers=headers)).json()["data"]
        if item["username"] == "admin"
    )

    mgr_headers = await login(client, "role.mgr")
    assert mgr_headers

    # Delegated role managers cannot add capabilities they do not possess to
    # their own role or to a new role.
    broaden_own_role = await client.put(
        f"/api/v1/roles/{role.json()['data']['id']}",
        headers=mgr_headers,
        json={"permissions": ["admin.roles.edit", "admin.users.edit"]},
    )
    assert broaden_own_role.status_code == 403
    create_powerful = await client.post(
        "/api/v1/roles",
        headers=mgr_headers,
        json={"name": "Escalated Role", "permissions": ["admin.users.edit"]},
    )
    assert create_powerful.status_code == 403

    escalate = await client.post(
        f"/api/v1/users/{admin_id}/role-assignments",
        headers=mgr_headers,
        json={"role_code": "PLATFORM_ADMIN"},
    )
    assert escalate.status_code == 403

    create_super = await client.post(
        "/api/v1/roles",
        headers=mgr_headers,
        json={"code": "PLATFORM_ADMIN", "name": "Super"},
    )
    assert create_super.status_code == 403


async def test_self_lockout_guards(client):
    headers = await login(client)
    admin_id = next(
        item["id"] for item in (await client.get("/api/v1/users", headers=headers)).json()["data"]
        if item["username"] == "admin"
    )

    self_delete = await client.request(
        "DELETE", "/api/v1/users", headers=headers, json={"ids": [admin_id]}
    )
    assert self_delete.status_code == 403

    self_deactivate = await client.put(
        f"/api/v1/users/{admin_id}", headers=headers, json={"status": "Inactive"}
    )
    assert self_deactivate.status_code == 403

    remove_last_admin = await client.put(
        f"/api/v1/users/{admin_id}", headers=headers, json={"roles": []}
    )
    assert remove_last_admin.status_code == 403


async def test_platform_admin_cannot_change_own_role(client):
    headers = await login(client)
    second = await _create_user(
        client,
        headers,
        username="self.admin",
        email="self.admin@example.com",
        roles=["PLATFORM_ADMIN"],
    )
    own_headers = await login(client, "self.admin")
    changed = await client.put(
        f"/api/v1/users/{second['id']}",
        headers=own_headers,
        json={"roles": ["AUDITOR"]},
    )
    assert changed.status_code == 403, changed.text


async def test_last_platform_admin_cannot_be_deactivated_by_others(client):
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "USER_MGR", "name": "User Manager", "permissions": ["admin.users.edit"]},
    )
    assert role.status_code == 201, role.text
    await _create_user(
        client, headers, username="user.mgr", email="user.mgr@example.com", roles=["USER_MGR"]
    )
    admin_id = next(
        item["id"] for item in (await client.get("/api/v1/users", headers=headers)).json()["data"]
        if item["username"] == "admin"
    )
    mgr_headers = await login(client, "user.mgr")
    deactivate = await client.put(
        f"/api/v1/users/{admin_id}", headers=mgr_headers, json={"status": "Inactive"}
    )
    assert deactivate.status_code == 403, deactivate.text
    assert deactivate.json()["code"] == "ACCESS_DENIED"


async def test_protected_system_admin_rejects_direct_and_bulk_mutations(client, session_factory):
    headers = await login(client)
    protected = await _protected_admin(client, headers)
    second_admin = await _create_user(
        client,
        headers,
        username="second.admin",
        email="second.admin@example.com",
        roles=["PLATFORM_ADMIN"],
    )
    actor_headers = await login(client, "second.admin")
    normal = await _create_user(
        client,
        actor_headers,
        username="normal.user",
        email="normal.user@example.com",
        roles=["AUDITOR"],
    )

    deactivate = await client.put(
        f"/api/v1/users/{protected['id']}",
        headers=actor_headers,
        json={"status": "INACTIVE"},
    )
    assert deactivate.status_code == 403, deactivate.text

    change_role = await client.put(
        f"/api/v1/users/{protected['id']}",
        headers=actor_headers,
        json={"roles": ["AUDITOR"]},
    )
    assert change_role.status_code == 403, change_role.text

    direct_assignment = await client.post(
        f"/api/v1/users/{protected['id']}/role-assignments",
        headers=actor_headers,
        json={"role_code": "AUDITOR"},
    )
    assert direct_assignment.status_code == 403, direct_assignment.text

    bulk_delete = await client.request(
        "DELETE",
        "/api/v1/users",
        headers=actor_headers,
        json={"ids": [protected["id"], normal["id"]]},
    )
    assert bulk_delete.status_code == 403, bulk_delete.text

    # The bulk operation is atomic: the ordinary user was not partially deleted.
    remaining = (await client.get("/api/v1/users", headers=actor_headers)).json()["data"]
    assert {row["id"] for row in remaining} >= {protected["id"], normal["id"], second_admin["id"]}

    async with session_factory() as session:
        rejected = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.result == "REJECTED",
                    AuditEvent.entity_type == "user",
                )
            )
        ).scalars().all()
        assert {event.event_type for event in rejected} >= {
            "USER_UPDATE_REJECTED",
            "ROLE_ASSIGNMENT_REJECTED",
            "USER_DELETE_REJECTED",
        }


async def test_protected_admin_profile_can_change_and_normal_user_can_be_deleted(client, session_factory):
    headers = await login(client)
    protected = await _protected_admin(client, headers)
    await _create_user(
        client,
        headers,
        username="profile.admin",
        email="profile.admin@example.com",
        roles=["PLATFORM_ADMIN"],
    )
    actor_headers = await login(client, "profile.admin")

    profile = await client.put(
        f"/api/v1/users/{protected['id']}",
        headers=actor_headers,
        json={
            "displayName": "Primary System Administrator",
            "email": "primary.admin@example.com",
            "role": "PLATFORM_ADMIN",
            "status": "ACTIVE",
        },
    )
    assert profile.status_code == 200, profile.text
    updated = profile.json()["data"]
    assert updated["displayName"] == "Primary System Administrator"
    assert updated["email"] == "primary.admin@example.com"
    assert updated["roles"] == ["PLATFORM_ADMIN"]
    assert updated["status"] == "ACTIVE"
    assert updated["isProtectedSystemAccount"] is True

    # Protection still follows the immutable identity after mutable profile
    # values have changed.
    renamed_delete = await client.request(
        "DELETE", "/api/v1/users", headers=actor_headers, json={"ids": [protected["id"]]}
    )
    assert renamed_delete.status_code == 403, renamed_delete.text

    normal = await _create_user(
        client,
        actor_headers,
        username="deletable.user",
        email="deletable.user@example.com",
        roles=["AUDITOR"],
    )
    deleted = await client.request(
        "DELETE", "/api/v1/users", headers=actor_headers, json={"ids": [normal["id"]]}
    )
    assert deleted.status_code == 200, deleted.text
    users = (await client.get("/api/v1/users", headers=actor_headers)).json()["data"]
    assert normal["id"] not in {row["id"] for row in users}

    async with session_factory() as session:
        successful = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.event_type == "USER_DELETED",
                    AuditEvent.result == "SUCCESS",
                )
            )
        ).scalars().all()
        assert successful


async def test_builtin_admin_role_cannot_lose_permissions_or_be_deleted(client, session_factory):
    headers = await login(client)
    roles = await _roles(client, headers)
    protected_role = next(role for role in roles if role.get("isSystemRole") is True)

    stripped = await client.put(
        f"/api/v1/roles/{protected_role['id']}",
        headers=headers,
        json={"permissions": []},
    )
    assert stripped.status_code == 403, stripped.text

    deactivated = await client.put(
        f"/api/v1/roles/{protected_role['id']}",
        headers=headers,
        json={"status": "INACTIVE"},
    )
    assert deactivated.status_code == 403, deactivated.text

    deleted = await client.request(
        "DELETE", "/api/v1/roles", headers=headers, json={"ids": [protected_role["id"]]}
    )
    assert deleted.status_code == 403, deleted.text

    detail = await client.get(f"/api/v1/roles/{protected_role['id']}", headers=headers)
    assert detail.status_code == 200
    assert set(detail.json()["data"]["permissions"]) == set(protected_role["permissions"])
    assert detail.json()["data"]["status"] == "ACTIVE"

    async with session_factory() as session:
        rejected = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.result == "REJECTED",
                    AuditEvent.entity_type == "role",
                )
            )
        ).scalars().all()
        assert {event.event_type for event in rejected} >= {
            "ROLE_UPDATE_REJECTED",
            "ROLE_DELETE_REJECTED",
        }


async def test_assigned_role_cannot_be_deleted(client):
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "ASSIGNED_ROLE", "name": "Assigned Role", "permissions": []},
    )
    assert role.status_code == 201, role.text
    user = await _create_user(
        client,
        headers,
        username="assigned.user",
        email="assigned.user@example.com",
        roles=["ASSIGNED_ROLE"],
    )

    rejected = await client.request(
        "DELETE",
        "/api/v1/roles",
        headers=headers,
        json={"ids": [role.json()["data"]["id"]]},
    )
    assert rejected.status_code == 409, rejected.text
    detail = await client.get(f"/api/v1/users/{user['id']}", headers=headers)
    assert detail.json()["data"]["roles"] == ["ASSIGNED_ROLE"]

    deactivated = await client.put(
        f"/api/v1/roles/{role.json()['data']['id']}",
        headers=headers,
        json={"status": "INACTIVE"},
    )
    assert deactivated.status_code == 409, deactivated.text


async def test_permission_and_role_changes_take_effect_without_relogin(client):
    headers = await login(client)

    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "RBAC_VIEWER", "name": "RBAC Viewer", "permissions": ["admin.users.view"]},
    )
    assert role.status_code == 201, role.text
    role_id = role.json()["data"]["id"]

    user = await _create_user(
        client,
        headers,
        username="rbac.viewer",
        email="rbac.viewer@example.com",
        roles=["RBAC_VIEWER"],
    )
    viewer_headers = await login(client, "rbac.viewer")
    assert (await client.get("/api/v1/users", headers=viewer_headers)).status_code == 200

    # A permission update on the role applies to the live session immediately.
    updated = await client.put(
        f"/api/v1/roles/{role_id}", headers=headers, json={"permissions": []}
    )
    assert updated.status_code == 200, updated.text
    assert (await client.get("/api/v1/users", headers=viewer_headers)).status_code == 403

    # Replacing the user's role is a revocation to the old role's permissions.
    no_access = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "RBAC_NONE", "name": "RBAC None", "permissions": []},
    )
    assert no_access.status_code == 201, no_access.text
    replaced = await client.put(
        f"/api/v1/users/{user['id']}", headers=headers, json={"roles": ["RBAC_NONE"]}
    )
    assert replaced.status_code == 200, replaced.text
    assert (await client.get("/api/v1/users", headers=viewer_headers)).status_code == 403
    assert replaced.json()["data"]["roles"] == ["RBAC_NONE"]
