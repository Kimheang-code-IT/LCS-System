from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_settings_app_info_and_app_config_roundtrip(client):
    headers = await login(client)

    info = await client.get("/api/v1/settings/app-info", headers=headers)
    assert info.status_code == 200, info.text
    assert info.json()["data"]["branding"]["primaryColor"]

    updated = await client.patch(
        "/api/v1/settings/app-config",
        headers=headers,
        json={"general": {"maxUploadSizeMb": 123}, "localization": {"currency": "KHR"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["general"]["maxUploadSizeMb"] == 123

    reloaded = await client.get("/api/v1/settings/app-config", headers=headers)
    assert reloaded.status_code == 200
    data = reloaded.json()["data"]
    assert data["general"]["maxUploadSizeMb"] == 123
    assert data["localization"]["currency"] == "KHR"
    assert data["system"]["environment"] == "production"

    reset = await client.post("/api/v1/settings/app-info/reset", headers=headers)
    assert reset.status_code == 200


async def test_profile_avatar_persists(client):
    headers = await login(client)
    payload = {"avatar": "data:image/png;base64,iVBORw0KGgo="}

    saved = await client.post("/api/v1/auth/profile/avatar", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["avatar"] == payload["avatar"]

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["avatar"] == payload["avatar"]

    removed = await client.delete("/api/v1/auth/profile/avatar", headers=headers)
    assert removed.status_code == 200
    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.json()["data"]["avatar"] is None


async def test_search_finds_business_party_and_answers(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/businessParties",
        headers=headers,
        json={"partyCode": "SRCH-001", "legalName": "Mekong Search Logistics", "roles": ["Customer"]},
    )
    assert created.status_code == 201, created.text

    hits = await client.get("/api/v1/search", headers=headers, params={"q": "Mekong Search"})
    assert hits.status_code == 200, hits.text
    results = hits.json()["data"]
    assert any(hit["entityType"] == "company" for hit in results)

    ask = await client.post("/api/v1/search/ask", headers=headers, json={"q": "Mekong Search"})
    assert ask.status_code == 200, ask.text
    assert ask.json()["data"]["answer"]


async def test_admin_finance_detail_and_delete_endpoints(client):
    headers = await login(client)

    # Chart of accounts
    created_account = await client.post(
        "/api/v1/chartOfAccounts",
        headers=headers,
        json={"accountCode": "9999", "accountName": "Disposable Test Account", "accountType": "ASSET", "normalBalance": "DEBIT"},
    )
    assert created_account.status_code == 201, created_account.text
    account_id = created_account.json()["data"]["id"]
    assert (await client.get(f"/api/v1/chartOfAccounts/{account_id}", headers=headers)).status_code == 200
    deleted = await client.request("DELETE", "/api/v1/chartOfAccounts", headers=headers, json={"ids": [account_id]})
    assert deleted.status_code == 200, deleted.text
    assert (await client.get(f"/api/v1/chartOfAccounts/{account_id}", headers=headers)).status_code == 404

    # Financial accounts
    financial = (await client.get("/api/v1/financialAccounts", headers=headers)).json()["data"]["items"]
    financial_id = financial[0]["id"]
    assert (await client.get(f"/api/v1/financialAccounts/{financial_id}", headers=headers)).status_code == 200
    patched = await client.put(f"/api/v1/financialAccounts/{financial_id}", headers=headers, json={"accountName": "Renamed"})
    assert patched.status_code == 200
    assert patched.json()["data"]["accountName"] == "Renamed"

    # Accounting periods
    periods = (await client.get("/api/v1/accounting-periods", headers=headers)).json()["data"]
    period_id = periods[0]["id"]
    assert (await client.get(f"/api/v1/accounting-periods/{period_id}", headers=headers)).status_code == 200

    # Document sequences
    sequences = (await client.get("/api/v1/document-sequences", headers=headers)).json()["data"]["items"]
    sequence_id = sequences[0]["id"]
    assert (await client.get(f"/api/v1/document-sequences/{sequence_id}", headers=headers)).status_code == 200

    # Posting rules
    rules = (await client.get("/api/v1/postingRules", headers=headers)).json()["data"]["items"]
    rule_id = rules[0]["id"]
    assert (await client.get(f"/api/v1/postingRules/{rule_id}", headers=headers)).status_code == 200
    rule_update = await client.put(f"/api/v1/postingRules/{rule_id}", headers=headers, json={"status": "INACTIVE"})
    assert rule_update.status_code == 200
    assert rule_update.json()["data"]["status"] == "INACTIVE"


async def test_admin_org_role_branch_and_user_endpoints(client):
    headers = await login(client)

    organizations = (await client.get("/api/v1/organizations", headers=headers)).json()["data"]
    org_id = organizations[0]["id"]
    assert (await client.get(f"/api/v1/organizations/{org_id}", headers=headers)).status_code == 200
    org_update = await client.put(f"/api/v1/organizations/{org_id}", headers=headers, json={"display_name": "Renamed Org"})
    assert org_update.status_code == 200

    branches = (await client.get("/api/v1/branches", headers=headers)).json()["data"]
    branch_id = branches[0]["id"]
    assert (await client.get(f"/api/v1/branches/{branch_id}", headers=headers)).status_code == 200

    roles = (await client.get("/api/v1/roles", headers=headers)).json()["data"]
    role_id = roles[0]["id"]
    assert (await client.get(f"/api/v1/roles/{role_id}", headers=headers)).status_code == 200

    users = (await client.get("/api/v1/users", headers=headers)).json()["data"]
    assert users
    user_id = users[0]["id"]
    user_update = await client.put(f"/api/v1/users/{user_id}", headers=headers, json={"displayName": "Renamed User"})
    assert user_update.status_code == 200, user_update.text
