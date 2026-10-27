"""Administrator-set passwords, and the forced change that follows.

Creating a user already means choosing that user's password; these tests cover
the *recovery* path an administrator needs when a user cannot receive the
self-service reset email, and the state that stops the resulting temporary
password from being kept in use.

The security claims under test are:

* an administrator never sees a stored password — there is none to see, only an
  Argon2id digest;
* setting a password signs every existing session out;
* while a password is outstanding, the API refuses everything except changing it,
  and refreshing the token is not an escape;
* the flag clears when the owner chooses their own password, and only then.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import verify_password
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import UserCredential
from app.modules.auth.service import PLATFORM_ADMIN_ROLE
from tests.conftest import login

pytestmark = pytest.mark.asyncio

ADMIN_PASSWORD = "Passw0rd!"
NEW_PASSWORD = "Sup3r-Secret-9"
USER_PASSWORD = "Original-Str0ng!"


async def _make_user(client, headers, *, username: str = "recover.me", role: str = "AUDITOR") -> dict:
    response = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": username,
            "displayName": "Recover Me",
            "email": f"{username}@example.com",
            "password": USER_PASSWORD,
            "status": "Active",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _credential(session_factory, user_id: int) -> UserCredential:
    async with session_factory() as session:
        return (
            await session.execute(select(UserCredential).where(UserCredential.user_id == user_id))
        ).scalars().one()


async def test_an_administrator_can_set_a_password_and_never_sees_it_back(client, session_factory):
    headers = await login(client)
    user = await _make_user(client, headers)

    response = await client.post(
        f"/api/v1/users/{user['id']}/password",
        headers=headers,
        json={"password": NEW_PASSWORD},
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    # The payload describes the account; the password is not in it, and neither
    # is the digest.
    assert "password" not in body
    assert "passwordHash" not in body
    assert body["username"] == "recover.me"

    # The stored value is a digest, not the password.
    credential = await _credential(session_factory, int(user["id"]))
    assert credential.password_hash != NEW_PASSWORD
    assert NEW_PASSWORD not in credential.password_hash
    assert verify_password(NEW_PASSWORD, credential.password_hash)
    assert credential.must_change_password is True


async def test_the_new_password_works_and_the_old_one_does_not(client):
    headers = await login(client)
    user = await _make_user(client, headers)

    await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": NEW_PASSWORD}
    )

    old = await client.post(
        "/api/v1/auth/login", json={"username": "recover.me", "password": USER_PASSWORD}
    )
    assert old.status_code == 401

    new = await client.post(
        "/api/v1/auth/login", json={"username": "recover.me", "password": NEW_PASSWORD}
    )
    assert new.status_code == 200, new.text
    assert new.json()["data"]["user"]["mustChangePassword"] is True


async def test_setting_a_password_signs_every_existing_session_out(client):
    headers = await login(client)
    user = await _make_user(client, headers)
    victim = await login(client, "recover.me", USER_PASSWORD)
    assert (await client.get("/api/v1/auth/me", headers=victim)).status_code == 200

    await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": NEW_PASSWORD}
    )

    # A credential change that left other devices signed in would not be a reset.
    assert (await client.get("/api/v1/auth/me", headers=victim)).status_code == 401


async def test_a_temporary_password_blocks_the_api_until_it_is_changed(client):
    headers = await login(client)
    user = await _make_user(client, headers)
    await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": NEW_PASSWORD}
    )
    temporary = await login(client, "recover.me", NEW_PASSWORD)

    # Business data is refused.
    for path in ("/api/v1/quotations", "/api/v1/users", "/api/v1/posting-rules"):
        blocked = await client.get(path, headers=temporary)
        assert blocked.status_code == 403, f"{path} -> {blocked.status_code}"
        assert blocked.json()["code"] == "ACCESS_DENIED"
        assert "administrator" in blocked.json()["message"].lower()

    # Reading the profile stays open so the SPA can render the forced-change
    # screen knowing who is signed in; leaving stays open too.
    assert (await client.get("/api/v1/auth/me", headers=temporary)).status_code == 200

    # The change itself is reachable.
    allowed = await client.post(
        "/api/v1/auth/change-password",
        headers=temporary,
        json={"current_password": NEW_PASSWORD, "password": NEW_PASSWORD + "-own"},
    )
    assert allowed.status_code == 200, allowed.text


async def test_the_owner_choosing_a_password_clears_the_flag_and_restores_access(client, session_factory):
    headers = await login(client)
    user = await _make_user(client, headers)
    await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": NEW_PASSWORD}
    )
    temporary = await login(client, "recover.me", NEW_PASSWORD)

    chosen = "Chosen-By-Me-12"
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=temporary,
        json={"current_password": NEW_PASSWORD, "password": chosen},
    )
    assert changed.status_code == 200, changed.text

    # change_password revokes sessions, so the owner signs in with their own password.
    own = await login(client, "recover.me", chosen)
    assert (await client.get("/api/v1/auth/me", headers=own)).status_code == 200
    assert (await client.get("/api/v1/users", headers=own)).status_code == 200

    credential = await _credential(session_factory, int(user["id"]))
    assert credential.must_change_password is False
    # And the administrator's temporary password no longer works.
    gone = await client.post(
        "/api/v1/auth/login", json={"username": "recover.me", "password": NEW_PASSWORD}
    )
    assert gone.status_code == 401


async def test_refreshing_the_token_is_not_a_way_to_escape_the_forced_change(client):
    headers = await login(client)
    user = await _make_user(client, headers)
    await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": NEW_PASSWORD}
    )
    signed_in = await client.post(
        "/api/v1/auth/login", json={"username": "recover.me", "password": NEW_PASSWORD}
    )
    assert "refresh_token" not in signed_in.json()["data"]
    bearer = {"Authorization": f"Bearer {signed_in.json()['data']['access_token']}"}

    bearer[settings.csrf_header_name] = client.cookies.get(settings.csrf_cookie_name) or ""
    refreshed = await client.post(
        "/api/v1/auth/refresh", headers=bearer, json={}
    )

    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["user"]["mustChangePassword"] is True
    # The rotated access token still carries the restriction.
    rotated = {"Authorization": f"Bearer {refreshed.json()['data']['access_token']}"}
    assert (await client.get("/api/v1/quotations", headers=rotated)).status_code == 403


async def test_an_administrator_can_opt_out_of_the_forced_change(client):
    headers = await login(client)
    user = await _make_user(client, headers)

    response = await client.post(
        f"/api/v1/users/{user['id']}/password",
        headers=headers,
        json={"password": NEW_PASSWORD, "mustChangePassword": False},
    )
    assert response.status_code == 200, response.text

    signed_in = await login(client, "recover.me", NEW_PASSWORD)
    assert (await client.get("/api/v1/users", headers=signed_in)).status_code == 200


async def test_a_reset_also_unlocks_a_locked_out_account(client, session_factory):
    """A reset that left the account locked would be useless.

    The lockout is written directly rather than driven through repeated failed
    sign-ins: ``tests/test_lockout_policy.py`` already proves the lock is applied,
    and this test is about the reset clearing it.
    """
    headers = await login(client)
    user = await _make_user(client, headers)

    async with session_factory() as session:
        credential = (
            await session.execute(select(UserCredential).where(UserCredential.user_id == int(user["id"])))
        ).scalars().one()
        credential.locked_until = datetime.now(UTC) + timedelta(minutes=30)
        credential.failed_attempt_count = 4
        await session.commit()

    assert (await client.post(
        "/api/v1/auth/login", json={"username": "recover.me", "password": USER_PASSWORD}
    )).status_code == 401

    reset = await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": NEW_PASSWORD}
    )
    assert reset.status_code == 200, reset.text

    assert (await client.post(
        "/api/v1/auth/login", json={"username": "recover.me", "password": NEW_PASSWORD}
    )).status_code == 200
    credential = await _credential(session_factory, int(user["id"]))
    assert credential.locked_until is None
    assert credential.failed_attempt_count == 0


async def test_a_weak_password_is_refused_on_the_field_it_belongs_to(client):
    headers = await login(client)
    user = await _make_user(client, headers)

    response = await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": "short"}
    )

    assert response.status_code == 422, response.text
    assert "password" in response.json()["field_errors"]


async def test_setting_a_password_for_an_unknown_user_is_not_found(client):
    headers = await login(client)

    response = await client.post(
        "/api/v1/users/999999/password", headers=headers, json={"password": NEW_PASSWORD}
    )

    assert response.status_code == 404


async def test_setting_a_password_requires_the_user_manage_permission(client):
    headers = await login(client)
    user = await _make_user(client, headers)
    await client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "code": "NO_USER_MANAGE",
            "name": "No user management",
            "permissions": ["master.reference.view"],
        },
    )
    await _make_user(client, headers, username="outsider", role="NO_USER_MANAGE")
    outsider = await login(client, "outsider", USER_PASSWORD)

    denied = await client.post(
        f"/api/v1/users/{user['id']}/password", headers=outsider, json={"password": NEW_PASSWORD}
    )

    assert denied.status_code == 403
    assert denied.json()["code"] == "ACCESS_DENIED"
    # The target account is untouched.
    assert (await client.post(
        "/api/v1/auth/login", json={"username": "recover.me", "password": USER_PASSWORD}
    )).status_code == 200


async def test_a_non_platform_administrator_cannot_reset_the_platform_administrator(client):
    """The recovery path must not become a way to seize the super-admin account."""
    headers = await login(client)
    admins = await client.get("/api/v1/users", headers=headers)
    protected = next(item for item in admins.json()["data"] if item["isProtectedSystemAccount"] is True)

    await client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "USER_MANAGER", "name": "User manager", "permissions": ["admin.users.edit"]},
    )
    await _make_user(client, headers, username="delegated.admin", role="USER_MANAGER")
    delegated = await login(client, "delegated.admin", USER_PASSWORD)

    denied = await client.post(
        f"/api/v1/users/{protected['id']}/password",
        headers=delegated,
        json={"password": NEW_PASSWORD},
    )

    assert denied.status_code == 403, denied.text
    # The built-in administrator's own credentials still work.
    assert (await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )).status_code == 200


async def test_setting_a_password_is_audited_without_recording_the_secret(client, session_factory):
    headers = await login(client)
    user = await _make_user(client, headers)

    await client.post(
        f"/api/v1/users/{user['id']}/password", headers=headers, json={"password": NEW_PASSWORD}
    )

    async with session_factory() as session:
        events = (
            await session.execute(
                select(AuditEvent)
                .where(
                    AuditEvent.entity_type == "user",
                    AuditEvent.entity_id == int(user["id"]),
                    AuditEvent.event_type == "USER_PASSWORD_SET_BY_ADMIN",
                )
                .order_by(AuditEvent.id)
            )
        ).scalars().all()
        assert len(events) == 1
        event = events[0]
        assert event.action == "reset_password"
        assert event.after_json["username"] == "recover.me"
        # No secret may reach the audit payload.
        blob = str(event.before_json) + str(event.after_json) + str(event.metadata_json)
        assert NEW_PASSWORD not in blob
        assert "password_hash" not in blob and "passwordHash" not in blob


async def test_a_platform_administrator_can_reset_the_built_in_administrator(client):
    """The one legitimate recovery path: nobody else can help a locked-out super admin."""
    headers = await login(client)
    admins = await client.get("/api/v1/users", headers=headers)
    protected = next(item for item in admins.json()["data"] if item["isProtectedSystemAccount"] is True)

    reset = await client.post(
        f"/api/v1/users/{protected['id']}/password",
        headers=headers,
        json={"password": NEW_PASSWORD, "mustChangePassword": False},
    )
    assert reset.status_code == 200, reset.text

    # Resetting a password revokes sessions, so the token that performed the
    # reset is now dead - including when the administrator reset their own.
    stale = await client.get("/api/v1/users", headers=headers)
    assert stale.status_code == 401

    restored = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": NEW_PASSWORD}
    )
    assert restored.status_code == 200, restored.text

    # Put it back so the documented credentials hold for anything after this.
    fresh = {"Authorization": f"Bearer {restored.json()['data']['access_token']}"}
    assert (await client.post(
        f"/api/v1/users/{protected['id']}/password",
        headers=fresh,
        json={"password": ADMIN_PASSWORD, "mustChangePassword": False},
    )).status_code == 200
    assert (await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )).status_code == 200


async def test_the_platform_admin_role_constant_still_matches_the_seeded_role(client):
    """Guards the assumption the super-admin reset test relies on."""
    headers = await login(client)
    roles = await client.get("/api/v1/roles", headers=headers, params={"page_size": 200})
    codes = {item["code"] for item in roles.json()["data"]["items"]}
    assert PLATFORM_ADMIN_ROLE in codes