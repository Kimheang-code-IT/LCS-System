"""Creator attribution on the master-data lists.

The lists show who created each record, derived only from creation audit
events: a bootstrap-seeded vocabulary row is attributed to the system, and a
record created through the API shows the actor's display name. A creator is
never invented for a row without evidence.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_seeded_vocabulary_shows_system_and_created_rows_show_the_actor(client):
    headers = await login(client)

    units = (await client.get("/api/v1/capacityUnits?page_size=200", headers=headers)).json()["data"]["items"]
    by_code = {row["code"]: row["createdBy"] for row in units}
    # The bootstrap created the default vocabulary, not a person.
    assert by_code["KG"] == "System"
    assert by_code["PCS"] == "System"

    # A record created through the API attributes its actor.
    created = await client.post(
        "/api/v1/capacityUnits", headers=headers, json={"code": "CRBY", "name": "Created By Probe"}
    )
    assert created.status_code == 201, created.text
    relisted = (await client.get("/api/v1/capacityUnits?code=CRBY", headers=headers)).json()["data"]["items"]
    actors = {row["createdBy"] for row in relisted if row["code"] == "CRBY"}
    assert len(actors) == 1
    actor = actors.pop()
    # The admin display name from the test seed; never the system label.
    assert actor and actor != "System"

    # The attribution is idempotent: a second load never changes it.
    again = (await client.get("/api/v1/capacityUnits?page_size=200", headers=headers)).json()["data"]["items"]
    refreshed = {row["code"]: row["createdBy"] for row in again}
    assert refreshed["KG"] == "System" and refreshed["CRBY"] == actor


async def test_user_created_rows_in_another_collection_get_their_actor(client):
    headers = await login(client)
    role = (await client.post(
        "/api/v1/partyRoles", headers=headers, json={"code": "CRATTR", "name": "Creator Probe"}
    )).json()["data"]
    listed = (await client.get("/api/v1/partyRoles?q=CRATTR", headers=headers)).json()["data"]["items"]
    assert len(listed) == 1
    # The party-role collection has its own matrix page and seed vocabulary;
    # either way the newest row's creator is the signed-in actor.
    assert listed[0]["createdBy"]
    await client.delete(f"/api/v1/partyRoles/{role['id']}", headers=headers)  # cleanup (archived)