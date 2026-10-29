"""The protected administrator's wildcard grant.

The single most dangerous defect this feature had: ``*`` was stored as
``("role:SUPER_ADMIN", "*", "")``, a two-token policy row the loader rejected, so
the only account that can administer the installation silently held nothing and
every request was denied. These tests pin the round trip and the compatibility
path for a row written by the broken version.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, update

from app.core import authorization
from app.core.authorization.models import CasbinRule
from tests.conftest import login

pytestmark = pytest.mark.asyncio


def _wildcard_rows(rows) -> list[tuple[str, str]]:
    return [(row.v1 or "", row.v2 or "") for row in rows]


async def test_the_super_admin_wildcard_is_stored_as_object_and_action(client, session_factory):
    headers = await login(client)

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(CasbinRule).where(
                    CasbinRule.ptype == "p", CasbinRule.v0 == "role:SUPER_ADMIN"
                )
            )
        ).scalars().all()
        assert _wildcard_rows(rows) == [("*", "*")], _wildcard_rows(rows)
        # Read back the same code the role editor shows and re-saves.
        assert await authorization.role_permission_codes(session, "SUPER_ADMIN") == ["*"]

    assert authorization.split_code("*") == ("*", "*")
    from app.core.authorization import service as authorization_service

    assert authorization_service.join_code("*", "") == "*"
    assert authorization.is_super_admin(1) is True
    assert authorization.can(1, "journal_entry.create") is True

    # The account can actually administer:
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 200


async def test_a_legacy_two_token_wildcard_still_grants_access(client, session_factory):
    """A row written by the older code must not lock the administrator out."""
    await login(client)
    async with session_factory() as session:
        await session.execute(
            update(CasbinRule)
            .where(CasbinRule.ptype == "p", CasbinRule.v0 == "role:SUPER_ADMIN", CasbinRule.v1 == "*")
            .values(v2="")
        )
        await session.commit()
        await authorization.reload(session)

    assert authorization.is_super_admin(1) is True
    assert authorization.can(1, "reports.trial_balance.view") is True


async def test_an_unknown_subject_still_denies(client):
    """The wildcard grants the protected administrator, not every signed-in user."""
    headers = await login(client)
    assert headers  # signed in
    assert authorization.can(999_999, "journal_entry.create") is False
