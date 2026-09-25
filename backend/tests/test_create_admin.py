from __future__ import annotations

import pytest

from app import create_admin as admin_module

pytestmark = pytest.mark.asyncio


async def test_create_admin_command_provisions_login(client, session_factory, monkeypatch):
    monkeypatch.setattr(admin_module, "SessionLocal", session_factory)
    args = admin_module.build_parser().parse_args(
        [
            "--email",
            "newadmin@example.test",
            "--password",
            "Secret123!",
            "--username",
            "newadmin",
            "--role",
            "ADMINISTRATOR",
        ]
    )

    result = await admin_module.create_admin(args)
    assert result["email"] == "newadmin@example.test"
    assert result["role"] == "ADMINISTRATOR"

    response = await client.post("/api/v1/auth/login", json={"username": "newadmin", "password": "Secret123!"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["user"]["email"] == "newadmin@example.test"


async def test_create_admin_rejects_unknown_role(client, session_factory, monkeypatch):
    monkeypatch.setattr(admin_module, "SessionLocal", session_factory)
    args = admin_module.build_parser().parse_args(
        ["--email", "x@example.test", "--password", "Secret123!", "--role", "NOPE"]
    )
    with pytest.raises(ValueError):
        await admin_module.create_admin(args)
