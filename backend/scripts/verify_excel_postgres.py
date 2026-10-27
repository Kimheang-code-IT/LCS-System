"""PostgreSQL verification for the Excel Import & Export engine (Phase A/B).

Run against an ISOLATED PostgreSQL database (never the live stack):

    docker run -d --name excel-pg-verify -e POSTGRES_PASSWORD=verify \
        -e POSTGRES_USER=verify -e POSTGRES_DB=verify -p 5433:5432 postgres:16-alpine
    cd backend
    $env:DATABASE_URL = "postgresql+asyncpg://verify:verify@127.0.0.1:5433/verify"
    uv run alembic upgrade head
    uv run python scripts/verify_excel_postgres.py

Prints one PASS/FAIL line per check; exits non-zero on any failure.
"""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import sys
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, get_session
from app.main import app
from tests.seed import ensure_seed_data, seed_demo_data

URL = os.environ.get("VERIFY_DATABASE_URL", "postgresql+asyncpg://verify:verify@127.0.0.1:5433/verify")

_results: list[tuple[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append(("PASS" if ok else "FAIL", f"{name}{(' — ' + detail) if detail else ''}"))


def _alembic(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run alembic against the verify database (env.py runs its own event loop)."""
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True, text=True,
        env={**os.environ, "DATABASE_URL": URL},
    )


def _wb(headers: list[str], rows: list[list]) -> bytes:
    workbook = Workbook()
    instructions = workbook.active
    assert instructions is not None
    instructions.title = "Instructions"
    instructions["A1"] = "TEMPLATE_VERSION"
    instructions["B1"] = 1
    sheet = workbook.create_sheet("Data")
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def main() -> None:
    engine = create_async_engine(URL)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    reset = URL.rsplit("/", 1)[-1] == "verify" or os.environ.get("VERIFY_RESET") == "1"

    if reset:
        async with engine.begin() as conn:
            # The default target is a disposable database: reset it so reruns
            # start clean (leftover rows would turn first-run assertions into
            # failures). A custom VERIFY_DATABASE_URL is only wiped when
            # VERIFY_RESET=1 is set, so a live stack can never be truncated.
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        # The reset dropped alembic_version with the schema; re-migrate BEFORE
        # create_all so migrations own the DDL and the downgrade/upgrade checks
        # at the end have a revision to step from.
        _alembic(["upgrade", "head"])

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with maker() as session:
        await ensure_seed_data(session)
        await seed_demo_data(session)
        await session.commit()

    # --- schema facts ----------------------------------------------------
    async with maker() as session:
        tables = (await session.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))).scalars().all()
        check("import_jobs table exists on PostgreSQL", "import_jobs" in tables)
        check("import_sessions table exists on PostgreSQL", "import_sessions" in tables)
        fks = (await session.execute(text(
            "SELECT COUNT(*) FROM information_schema.table_constraints"
            " WHERE table_name='import_jobs' AND constraint_type='FOREIGN KEY'"
        ))).scalar()
        check("import_jobs foreign keys exist", int(fks or 0) >= 1)
        unique = (await session.execute(text(
            "SELECT COUNT(*) FROM pg_indexes WHERE tablename='import_sessions' AND indexname LIKE '%token%'"
        ))).scalar()
        check("import_sessions token uniqueness enforced", int(unique or 0) >= 1)

    async def override_get_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Passw0rd!"})
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

        template = await client.get("/api/v1/excel/feeTypes/template", headers=headers)
        check("template downloads over PostgreSQL", template.status_code == 200)
        headers_row = [cell.value for cell in next(load_workbook(io.BytesIO(template.content))["Data"].iter_rows(min_row=1, max_row=1))]
        fee_headers = headers_row

        async def validate(content: bytes, mode: str = "CREATE_ONLY"):
            return await client.post(
                "/api/v1/excel/feeTypes/validate",
                headers=headers,
                files={"file": ("batch.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"mode": mode},
            )

        valid = _wb(fee_headers, [["PG-FT-1", "Freight Fee", "Freight", "ACTIVE"]])
        preview = await validate(valid)
        check("valid upload validates on PostgreSQL", preview.status_code == 200, preview.text[:200])

        def preview_token(response) -> str:
            body = response.json()
            if response.status_code != 200 or "token" not in (body.get("data") or {}):
                check("validate step on PostgreSQL", False, response.text[:300])
                raise SystemExit(1)
            return body["data"]["token"]

        # Create Only commit.
        token = preview_token(preview)
        confirmed = await client.post(f"/api/v1/excel/imports/{token}/commit", headers=headers)
        check("Create Only commit persists", confirmed.status_code == 200 and confirmed.json()["data"]["create"] == 1, confirmed.text[:200])

        # Validate Only must write nothing.
        validate_only = await validate(_wb(fee_headers, [["PG-FT-VONLY", "Validate Only", None, "ACTIVE"]]), mode="VALIDATE_ONLY")
        listed = (await client.get("/api/v1/feeTypes", headers=headers)).json()["data"]["items"]
        codes = [row["code"] for row in listed]
        check("Validate Only persists nothing", validate_only.status_code == 200 and "PG-FT-VONLY" not in codes)

        # Starting a second pending import replaces the first claim.
        stale = await validate(valid)
        stale_token = preview_token(stale)
        pending = await validate(_wb(fee_headers, [["PG-FT-DURABLE", "Durable", None, "ACTIVE"]]))
        pending_token = preview_token(pending)
        stale_commit = await client.post(f"/api/v1/excel/imports/{stale_token}/commit", headers=headers)
        check("a replaced pending import cannot be committed", stale_commit.status_code == 404, f"status={stale_commit.status_code}")

        # Durable preview: readable before any later upload replaces it (one
        # pending import per user per module). A fresh DB session is the
        # backend-restart case, covered by test_excel_import_export.py.
        re_read = await client.get(f"/api/v1/excel/imports/{pending_token}", headers=headers)
        check(
            "pending preview survives (durable sessions)",
            re_read.status_code == 200
            and (re_read.json()["data"]["rows"] or [{}])[0].get("identifier") == "PG-FT-DURABLE",
            re_read.text[:200],
        )

        # Same file again → skipped, no duplicate.
        again = await validate(valid)
        again_token = preview_token(again)
        again_commit = await client.post(f"/api/v1/excel/imports/{again_token}/commit", headers=headers)
        listed = (await client.get("/api/v1/feeTypes", headers=headers)).json()["data"]["items"]
        count = len([row for row in listed if row["code"] == "PG-FT-1"])
        check("same file twice never duplicates", again_commit.status_code == 200 and count == 1 and again_commit.json()["data"]["skip"] == 1)

        # Create and Update.
        changed = await validate(_wb(fee_headers, [["PG-FT-1", "Renamed Fee", "Freight", "ACTIVE"]]), mode="CREATE_AND_UPDATE")
        update_token = changed.json()["data"]["token"]
        update_commit = await client.post(f"/api/v1/excel/imports/{update_token}/commit", headers=headers)
        listed = (await client.get("/api/v1/feeTypes", headers=headers)).json()["data"]["items"]
        row = next(item for item in listed if item["code"] == "PG-FT-1")
        check("Create and Update applies whitelisted fields", update_commit.status_code == 200 and row["name"] == "Renamed Fee")

        # Creator attribution preserved through an update.
        check("creator attribution survives update", bool(row.get("createdBy")), str(row.get("createdBy")))

        # Atomic rollback: one valid + one invalid row → nothing written.
        mixed = _wb(fee_headers, [["PG-FT-OK", "Atomic One", None, "ACTIVE"], ["PG-FT-BAD", None, None, "ACTIVE"]])
        mixed_preview = await validate(mixed)
        mixed_token = mixed_preview.json()["data"]["token"]
        mixed_commit = await client.post(f"/api/v1/excel/imports/{mixed_token}/commit", headers=headers)
        listed = (await client.get("/api/v1/feeTypes", headers=headers)).json()["data"]["items"]
        codes = [row["code"] for row in listed]
        check("atomic rollback writes nothing on failure", mixed_commit.status_code == 422 and "PG-FT-OK" not in codes and "PG-FT-BAD" not in codes, f"status={mixed_commit.status_code}")

        # Duplicate confirmation prevention (single-use claim committed first).
        duplicate = await validate(valid)
        duplicate_token = preview_token(duplicate)
        first_commit, second_commit = await asyncio.gather(
            client.post(f"/api/v1/excel/imports/{duplicate_token}/commit", headers=headers),
            client.post(f"/api/v1/excel/imports/{duplicate_token}/commit", headers=headers),
        )
        codes = (await client.get("/api/v1/feeTypes", headers=headers)).json()["data"]["items"]
        occurrences = len([row for row in codes if row["code"] == "PG-FT-1"])
        statuses = sorted((first_commit.status_code, second_commit.status_code))
        check(
            "concurrent duplicate confirmation commits once",
            statuses[0] == 200 and statuses[1] in (404, 409) and occurrences == 1,
            f"statuses={statuses} occurrences={occurrences}",
        )

        # History.
        history = (await client.get("/api/v1/excel/history", headers=headers)).json()["data"]["items"]
        statuses_seen = {job["status"] for job in history}
        check("import history records COMPLETED and FAILED", {"COMPLETED", "FAILED"} <= statuses_seen, str(statuses_seen))

        # Pending preview durable: the earlier read proves it survived the
        # claim of the stale token.

        # Error report download.
        bad = _wb(fee_headers, [["PG-FT-ERR", None, None, "ACTIVE"]])
        bad_preview = await validate(bad)
        bad_token = preview_token(bad_preview)
        report = await client.get(f"/api/v1/excel/imports/{bad_token}/error-report", headers=headers)
        check("error report downloads on PostgreSQL", report.status_code == 200)

        # Export.
        export = await client.post("/api/v1/excel/feeTypes/export", headers=headers, json={"ids": [row["id"] for row in listed[:2]]})
        check("export downloads on PostgreSQL", export.status_code == 200)

    # --- downgrade / re-upgrade of the newest migration ---
    for args in (["downgrade", "-1"], ["upgrade", "head"]):
        result = _alembic(args)
        check(
            f"alembic {args[0]} runs on PostgreSQL",
            result.returncode == 0,
            (result.stderr or result.stdout)[-300:],
        )

    await engine.dispose()

    failed = 0
    for status, name in _results:
        print(f"{status:6} {name}")
        failed += status == "FAIL"
    print(f"\n{len(_results) - failed}/{len(_results)} checks passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())

