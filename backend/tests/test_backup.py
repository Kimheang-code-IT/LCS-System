from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.modules.backup import scheduler, service
from app.modules.backup.sheets import META_COLUMNS
from app.modules.master_data.models import TradeDirection
from app.modules.settings import service as settings_service
from tests.conftest import login


class FakeSheets:
    """In-memory stand-in for :class:`GoogleSheetsClient`."""

    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix
        self.tabs: dict[str, list[list]] = {}
        self.appended_batches = 0

    def worksheet_title(self, table_name: str) -> str:
        return f"{self.prefix}{table_name}"[:100]

    def ensure_worksheet(self, table_name: str) -> str:
        title = self.worksheet_title(table_name)
        self.tabs.setdefault(title, [])
        return title

    def ensure_header(self, title: str, columns: list[str]) -> list[str]:
        desired = list(META_COLUMNS) + [column for column in columns if column not in META_COLUMNS]
        if not self.tabs.get(title):
            self.tabs[title] = [desired]
            return desired
        existing = self.tabs[title][0]
        merged = existing + [column for column in desired if column not in existing]
        if merged != existing:
            self.tabs[title][0] = merged
        return merged

    def append_rows(self, title: str, rows: list[list]) -> None:
        self.appended_batches += 1
        self.tabs.setdefault(title, []).extend(rows)

    def read_rows(self, title: str) -> list[list]:
        return [list(row) for row in self.tabs.get(title, [])]

    def worksheet_exists(self, table_name: str) -> bool:
        return self.worksheet_title(table_name) in self.tabs

    def test_connection(self) -> dict:
        return {"title": "Fake", "sheets": list(self.tabs), "serviceAccountEmail": "sa@example.com"}


async def _configure(session_factory) -> None:
    async with session_factory() as session:
        await settings_service.update_app_config(
            session,
            None,
            {
                "backup": {
                    "enabled": True,
                    "intervalHours": 3,
                    "spreadsheetId": "fake-spreadsheet",
                    "serviceAccountJson": '{"client_email": "sa@example.com"}',
                }
            },
        )


def _install_fakes(monkeypatch, session_factory, fake: FakeSheets) -> None:
    monkeypatch.setattr(service, "build_client", lambda config: fake)
    monkeypatch.setattr(service, "SessionLocal", session_factory)


async def test_backup_detects_insert_update_and_prevents_duplicates(session_factory, monkeypatch):
    fake = FakeSheets()
    _install_fakes(monkeypatch, session_factory, fake)
    await _configure(session_factory)

    async with session_factory() as session:
        session.add(TradeDirection(code="SEA", name="Sea freight", status="ACTIVE"))
        await session.commit()

    async with session_factory() as session:
        first = await service.run_now(session, trigger="manual")
    assert first["status"] == "success"
    assert first["rowsInserted"] >= 1

    title = fake.worksheet_title("trade_directions")
    header = fake.tabs[title][0]
    name_index = header.index("name")
    assert len([row for row in fake.tabs[title][1:] if row[name_index] == "Sea freight"]) == 1

    # No changes -> the same record is not appended again (no duplicates).
    async with session_factory() as session:
        await service.run_now(session, trigger="manual")
    assert len([row for row in fake.tabs[title][1:] if row[name_index] == "Sea freight"]) == 1

    # Update the row -> a new versioned row is appended, the old one is kept.
    async with session_factory() as session:
        direction = (await session.execute(select(TradeDirection).where(TradeDirection.code == "SEA"))).scalar_one()
        direction.name = "Sea freight updated"
        await session.commit()

    async with session_factory() as session:
        third = await service.run_now(session, trigger="manual")
    assert third["rowsUpdated"] >= 1
    versions = sorted(
        int(row[header.index("_backup_version")])
        for row in fake.tabs[title][1:]
        if row[name_index] in ("Sea freight", "Sea freight updated")
    )
    assert versions == [1, 2]

    # Sensitive tables are never written to Sheets.
    assert "user_credentials" not in fake.tabs


async def test_restore_recreates_deleted_rows(session_factory, monkeypatch):
    fake = FakeSheets()
    _install_fakes(monkeypatch, session_factory, fake)
    await _configure(session_factory)

    async with session_factory() as session:
        session.add(TradeDirection(code="AIR", name="Air freight", status="ACTIVE"))
        await session.commit()
    async with session_factory() as session:
        await service.run_now(session, trigger="manual")

    async with session_factory() as session:
        await session.execute(delete(TradeDirection))
        await session.commit()
        assert (await session.execute(select(TradeDirection))).scalars().all() == []

    async with session_factory() as session:
        result = await service.restore_from_sheets(session, confirm="RESTORE")
    assert result["restored"] >= 1

    async with session_factory() as session:
        restored = (await session.execute(select(TradeDirection).where(TradeDirection.code == "AIR"))).scalar_one()
    assert restored.name == "Air freight"


async def test_restore_requires_confirmation(session_factory, monkeypatch):
    fake = FakeSheets()
    _install_fakes(monkeypatch, session_factory, fake)
    await _configure(session_factory)
    async with session_factory() as session:
        with pytest.raises(ValueError):
            await service.restore_from_sheets(session, confirm="nope")


async def test_service_account_secret_is_redacted_and_blank_keeps_value(session_factory):
    async with session_factory() as session:
        await settings_service.update_app_config(
            session,
            None,
            {"backup": {"spreadsheetId": "sheet", "serviceAccountJson": '{"client_email": "sa@example.com"}'}},
        )
    async with session_factory() as session:
        await settings_service.update_app_config(
            session, None, {"backup": {"serviceAccountJson": "", "intervalHours": 6}}
        )
        config = await settings_service.get_app_config(session)
    assert config["backup"]["serviceAccountJson"] == '{"client_email": "sa@example.com"}'
    assert config["backup"]["intervalHours"] == 6

    redacted = settings_service.redact_app_config(config)
    assert "serviceAccountJson" not in redacted["backup"]
    assert redacted["backup"]["serviceAccountConfigured"] is True


def test_scheduler_due_logic():
    now = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
    assert scheduler._is_due("", 3, now) is True
    assert scheduler._is_due((now - timedelta(hours=1)).isoformat(), 3, now) is False
    assert scheduler._is_due((now - timedelta(hours=4)).isoformat(), 3, now) is True


def test_public_config_redacts_credentials():
    payload = service.public_config(
        {"spreadsheetId": "abc", "serviceAccountJson": '{"client_email": "sa@example.com"}'}
    )
    assert "serviceAccountJson" not in payload
    assert payload["serviceAccountConfigured"] is True
    assert payload["serviceAccountEmail"] == "sa@example.com"


async def test_backup_status_endpoint(client):
    headers = await login(client)
    response = await client.get("/api/v1/backup/status", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["schedule"]["lastRunStatus"] in {"idle", "running", "success", "partial", "failed"}
    assert "serviceAccountJson" not in data["config"]


async def test_manual_backup_endpoint_starts_run(client, session_factory, monkeypatch):
    await _configure(session_factory)
    scheduled: dict[str, int] = {}

    async def fake_execute(run_id: int) -> None:
        scheduled["run_id"] = run_id

    monkeypatch.setattr(service, "execute_run", fake_execute)

    headers = await login(client)
    response = await client.post("/api/v1/backup/run", headers=headers)
    assert response.status_code == 200, response.text
    run_id = response.json()["data"]["id"]
    assert run_id

    await asyncio.sleep(0)
    assert scheduled.get("run_id") == run_id

    detail = await client.get(f"/api/v1/backup/runs/{run_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["trigger"] == "manual"
