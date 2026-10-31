"""The Excel Import & Export engine (Phase B: Master Data).

Pins the security-relevant contract: templates are backend-driven, uploads are
validated by the same service layer the API uses, preview writes nothing,
commit is atomic and revalidated, history is recorded, and a caller may never
read, import into or export from a module it has no permission for.
"""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook, load_workbook

from tests.conftest import login

pytestmark = pytest.mark.asyncio

TEMPLATE_TTL_MINUTES = 30


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    from app.modules.excel_io import router as excel_router

    monkeypatch.setattr(
        excel_router, "_RATE_LIMITS", {key: 1_000_000 for key in excel_router._RATE_LIMITS}
    )
    yield


def _workbook_bytes(module: str, rows: list[list], headers: list[str] | None = None, version: int | None = None) -> bytes:
    """A minimal template-shaped workbook: Instructions + Data."""
    workbook = Workbook()
    instructions = workbook.active
    assert instructions is not None
    instructions.title = "Instructions"
    instructions["A1"] = "TEMPLATE_VERSION"
    instructions["B1"] = version if version is not None else 1
    sheet = workbook.create_sheet("Data")
    if headers is not None:
        sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def _headers(client, headers: dict) -> list[str]:
    response = await client.get("/api/v1/excel/feeTypes/template", headers=headers)
    assert response.status_code == 200, response.text
    workbook = load_workbook(io.BytesIO(response.content))
    return [cell.value for cell in next(workbook["Data"].iter_rows(min_row=1, max_row=1))]


async def _validate(client, headers: dict, module: str, content: bytes, mode: str = "CREATE_ONLY") -> dict:
    response = await client.post(
        f"/api/v1/excel/{module}/validate",
        headers=headers,
        files={"file": ("batch.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mode": mode},
    )
    assert response.status_code in (200, 422), response.text
    return response


def _fee_row(code: str, name: str = "Freight Fee", description: str | None = "Freight charges", status: str = "ACTIVE") -> list:
    return [code, name, description, status]


async def test_module_catalog_lists_master_data(client):
    headers = await login(client)
    response = await client.get("/api/v1/excel/modules", headers=headers)
    assert response.status_code == 200, response.text
    keys = [item["key"] for item in response.json()["data"]]
    for expected in ("businessParties", "feeTypes", "currencies", "documentTypes"):
        assert expected in keys


async def test_unsupported_import_mode_is_rejected_without_writes(client, session_factory):
    from sqlalchemy import func, select

    from app.modules.excel_io.models import ImportSession
    from app.modules.excel_io.service import get_module
    from app.modules.master_data import service as master_data

    headers = await login(client)
    model = master_data.get_spec(get_module("feeTypes").key).model
    async with session_factory() as session:
        before_records = await session.scalar(select(func.count()).select_from(model))
        before_sessions = await session.scalar(select(func.count()).select_from(ImportSession))

    response = await _validate(
        client, headers, "feeTypes", _workbook_bytes("feeTypes", []), mode="UNSUPPORTED"
    )

    assert response.status_code == 422, response.text
    assert "mode" in response.json()["field_errors"]
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(model)) == before_records
        assert await session.scalar(select(func.count()).select_from(ImportSession)) == before_sessions


async def test_template_has_instructions_examples_and_reference_sheets(client):
    headers = await login(client)
    response = await client.get("/api/v1/excel/currencies/template", headers=headers)
    workbook = load_workbook(io.BytesIO(response.content))
    assert workbook.sheetnames[:3] == ["Instructions", "Data", "Examples"]
    assert workbook["Instructions"]["B1"].value == 1
    headers = [cell.value for cell in next(workbook["Data"].iter_rows(min_row=1, max_row=1))]
    assert "code" in headers and "name" in headers


async def test_upload_with_unknown_columns_is_rejected(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-1")], headers=[*expected, "hacked"])
    response = await _validate(client, headers, "feeTypes", content)
    assert response.status_code == 422, response.text


async def test_outdated_template_version_is_rejected(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-1")], headers=expected, version=99)
    response = await _validate(client, headers, "feeTypes", content)
    assert response.status_code == 422, response.text
    assert "template" in response.text.lower()


async def test_formula_cell_is_rejected(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    row = _fee_row("=1+1", "=SUM(A1)")
    content = _workbook_bytes("feeTypes", [row], headers=expected)
    response = await _validate(client, headers, "feeTypes", content)
    assert response.status_code == 422, response.text


async def test_non_xlsx_extension_is_rejected(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/excel/feeTypes/validate",
        headers=headers,
        files={"file": ("batch.xlsm", _workbook_bytes("feeTypes", []), "application/octet-stream")},
        data={"mode": "CREATE_ONLY"},
    )
    assert response.status_code == 422, response.text
    assert "xlsx" in response.text.lower()


async def test_preview_reports_required_and_reference_errors_per_row(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    rows = [
        _fee_row("FT-A"),           # valid
        [None] * len(expected),     # empty row (skipped, not present)
        _fee_row("FT-B", name=None),  # missing required name
    ]
    content = _workbook_bytes("feeTypes", rows, headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    actions = {row["excelRow"]: row["action"] for row in data["rows"]}
    assert actions == {2: "CREATE", 4: "ERROR"}
    failed = next(row for row in data["rows"] if row["action"] == "ERROR")
    assert failed["excelRow"] == 4
    assert any("name" in error.lower() or "required" in error.lower() for error in failed["errors"])


async def test_validate_only_writes_nothing(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-VALIDATE")], headers=expected)
    data = (await _validate(client, headers, "feeTypes", content, mode="VALIDATE_ONLY")).json()["data"]
    assert data["summary"]["create"] == 1
    listed = await client.get("/api/v1/feeTypes", headers=headers)
    codes = [row["code"] for row in listed.json()["data"]["items"]]
    assert "FT-VALIDATE" not in codes


async def test_preview_generates_no_records(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-PREVIEW")], headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    assert data["summary"]["create"] == 1
    listed = await client.get("/api/v1/feeTypes", headers=headers)
    codes = [row["code"] for row in listed.json()["data"]["items"]]
    assert "FT-PREVIEW" not in codes


async def test_confirm_import_persists_and_is_single_use(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-COMMIT")], headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    confirmed = await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["create"] == 1
    # A token confirms at most once.
    again = await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=headers)
    assert again.status_code == 404, again.text


async def test_importing_the_same_file_twice_does_not_duplicate(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-ONCE")], headers=expected)

    first = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    assert (await client.post(f"/api/v1/excel/imports/{first['token']}/commit", headers=headers)).status_code == 200

    second = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    assert second["summary"]["skip"] == 1  # Create Only skips the duplicate
    commit = await client.post(f"/api/v1/excel/imports/{second['token']}/commit", headers=headers)
    assert commit.status_code == 200, commit.text
    listed = await client.get("/api/v1/feeTypes", headers=headers)
    assert len([row for row in listed.json()["data"]["items"] if row["code"] == "FT-ONCE"]) == 1


async def test_create_and_update_changes_whitelisted_fields_only(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-UP", "Original Name")], headers=expected)
    first = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    assert (await client.post(f"/api/v1/excel/imports/{first['token']}/commit", headers=headers)).status_code == 200

    changed = _fee_row("FT-UP", "Updated Name")
    content = _workbook_bytes("feeTypes", [changed], headers=expected)
    second = (await _validate(client, headers, "feeTypes", content, mode="CREATE_AND_UPDATE")).json()["data"]
    assert second["summary"]["update"] == 1
    assert (await client.post(f"/api/v1/excel/imports/{second['token']}/commit", headers=headers)).status_code == 200
    listed = await client.get("/api/v1/feeTypes", headers=headers)
    row = next(row for row in listed.json()["data"]["items"] if row["code"] == "FT-UP")
    assert row["name"] == "Updated Name"


async def test_atomic_batch_failure_writes_nothing(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    rows = [_fee_row("FT-OK1"), _fee_row("FT-OK2", name=None)]
    content = _workbook_bytes("feeTypes", rows, headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    assert data["summary"]["error"] == 1
    confirmed = await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=headers)
    assert confirmed.status_code == 422, confirmed.text
    listed = await client.get("/api/v1/feeTypes", headers=headers)
    codes = [row["code"] for row in listed.json()["data"]["items"]]
    assert "FT-OK1" not in codes and "FT-OK2" not in codes


async def test_failed_batch_is_recorded_in_history(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    rows = [_fee_row("FT-H1"), _fee_row("FT-H2", name=None)]
    content = _workbook_bytes("feeTypes", rows, headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    assert (await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=headers)).status_code == 422
    history = await client.get("/api/v1/excel/history", headers=headers)
    assert history.status_code == 200, history.text
    jobs = history.json()["data"]["items"]
    assert jobs and jobs[0]["status"] == "FAILED"
    assert jobs[0]["totalRows"] == 2


async def test_successful_import_records_completed_history(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-HIST")], headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=headers)
    history = await client.get("/api/v1/excel/history", headers=headers)
    jobs = history.json()["data"]["items"]
    completed = next(job for job in jobs if job["status"] == "COMPLETED" and job["created"] == 1)
    assert completed["module"] == "feeTypes"


async def test_error_report_download(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-E", name=None)], headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    report = await client.get(f"/api/v1/excel/imports/{data['token']}/error-report", headers=headers)
    assert report.status_code == 200, report.text
    workbook = load_workbook(io.BytesIO(report.content))
    rows = list(workbook["Errors"].iter_rows(min_row=2, values_only=True))
    assert rows and rows[0][0] == 2 and rows[0][2] == "ERROR"


async def test_export_selected_and_all(client):
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes(
        "feeTypes",
        [_fee_row("FT-EX1", "Alpha"), _fee_row("FT-EX2", "Beta")],
        headers=expected,
    )
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=headers)

    listed = await client.get("/api/v1/feeTypes", headers=headers)
    items = listed.json()["data"]["items"]
    target = next(row for row in items if row["code"] == "FT-EX1")

    selected = await client.post(
        "/api/v1/excel/feeTypes/export", headers=headers, json={"ids": [target["id"]]}
    )
    assert selected.status_code == 200, selected.text
    workbook = load_workbook(io.BytesIO(selected.content))
    codes = [row[0] for row in workbook["Data"].iter_rows(min_row=2, values_only=True)]
    assert codes == ["FT-EX1"]

    everything = await client.post("/api/v1/excel/feeTypes/export", headers=headers, json={})
    assert everything.status_code == 200, everything.text


async def test_export_neutralizes_formula_injection(client, session_factory):
    from app.modules.excel_io import service as excel
    from app.modules.master_data import service as md

    spec = md.get_spec("feeTypes")
    model = spec.model()
    setattr(model, spec.fields["code"], "=cmd()")
    setattr(model, spec.fields["name"], "=HYPERLINK('http://x')")
    setattr(model, spec.status_field, "ACTIVE")
    async with session_factory() as session:
        session.add(model)
        await session.commit()
        content = await excel.export_rows(session, excel.get_module("feeTypes"), None)
    workbook = load_workbook(io.BytesIO(content))
    codes = [row[0] for row in workbook["Data"].iter_rows(min_row=2, values_only=True)]
    assert any(str(code).startswith("'=") for code in codes)


async def test_unauthorized_import_and_export_are_denied(client):
    ops = await login(client, "ops.pp")
    blocked = await client.post(
        "/api/v1/excel/feeTypes/validate",
        headers=ops,
        files={"file": ("batch.xlsx", _workbook_bytes("feeTypes", [], headers=["code"]), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mode": "CREATE_ONLY"},
    )
    assert blocked.status_code == 403, blocked.text

    admin = await login(client)
    unlisted = await client.get("/api/v1/excel/unknownModule/template", headers=admin)
    assert unlisted.status_code == 404, unlisted.text


async def test_import_session_is_private_to_its_owner(client):
    admin = await login(client)
    expected = await _headers(client, admin)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-PRIVATE")], headers=expected)
    data = (await _validate(client, admin, "feeTypes", content)).json()["data"]
    ops = await login(client, "ops.pp")
    stolen = await client.get(f"/api/v1/excel/imports/{data['token']}", headers=ops)
    assert stolen.status_code == 404, stolen.text


async def test_import_session_survives_a_new_database_session(client, session_factory, seeded):
    """The preview is durable: a fresh session (a restarted backend) sees it."""
    admin = await login(client)
    expected = await _headers(client, admin)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-DURABLE")], headers=expected)
    data = (await _validate(client, admin, "feeTypes", content)).json()["data"]

    # A brand-new session, as after a process restart.
    from app.core.context import RequestContext
    from app.modules.excel_io import service as excel

    async with session_factory() as new_db:
        context = RequestContext(
            user_id=1, username="admin", email="a@b.c", display_name="Admin",
            permissions=set(), is_platform_admin=True, request_id="r",
        )
        preview = await excel.get_preview_rows(new_db, data["token"], context)
        assert preview["summary"]["create"] == 1
        assert preview["rows"][0]["identifier"] == "FT-DURABLE"


async def test_second_pending_import_replaces_the_first(client):
    admin = await login(client)
    expected = await _headers(client, admin)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-OLD")], headers=expected)
    first = (await _validate(client, admin, "feeTypes", content)).json()["data"]
    content = _workbook_bytes("feeTypes", [_fee_row("FT-NEW")], headers=expected)
    second = (await _validate(client, admin, "feeTypes", content)).json()["data"]

    gone = await client.post(f"/api/v1/excel/imports/{first['token']}/commit", headers=admin)
    assert gone.status_code == 404, gone.text
    kept = await client.get(f"/api/v1/excel/imports/{second['token']}", headers=admin)
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["rows"][0]["identifier"] == "FT-NEW"


async def test_cancelled_session_cannot_be_confirmed(client):
    admin = await login(client)
    expected = await _headers(client, admin)
    content = _workbook_bytes("feeTypes", [_fee_row("FT-CANCEL")], headers=expected)
    data = (await _validate(client, admin, "feeTypes", content)).json()["data"]
    cancelled = await client.post(f"/api/v1/excel/imports/{data['token']}/cancel", headers=admin)
    assert cancelled.status_code == 200, cancelled.text
    confirmed = await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=admin)
    assert confirmed.status_code == 404, confirmed.text
    listed = await client.get("/api/v1/feeTypes", headers=admin)
    codes = [row["code"] for row in listed.json()["data"]["items"]]
    assert "FT-CANCEL" not in codes


async def test_concurrent_confirmation_commits_once(client):
    import asyncio

    admin = await login(client)
    expected = await _headers(client, admin)
    content = _workbook_bytes(
        "feeTypes",
        [_fee_row("FT-RACE"), _fee_row("FT-RACE2")],
        headers=expected,
    )
    data = (await _validate(client, admin, "feeTypes", content)).json()["data"]

    async def attempt():
        return await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=admin)

    first, second = await asyncio.gather(attempt(), attempt())
    statuses = sorted((first.status_code, second.status_code))
    assert statuses[0] == 200, (first.text, second.text)
    assert statuses[1] in (404, 409), (first.text, second.text)
    listed = await client.get("/api/v1/feeTypes", headers=admin)
    codes = [row["code"] for row in listed.json()["data"]["items"]]
    assert codes.count("FT-RACE") == 1 and codes.count("FT-RACE2") == 1


async def test_oversized_upload_is_rejected(client):
    headers = await login(client)
    response = await client.post(
        "/api/v1/excel/feeTypes/validate",
        headers=headers,
        files={"file": ("big.xlsx", b"\x00" * (11 * 1024 * 1024), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mode": "CREATE_ONLY"},
    )
    assert response.status_code == 422, response.text


async def test_rate_limit_trip_on_validate(client):
    """The validate window is the tight one: the 11th upload in a minute fails."""
    from app.modules.excel_io import router as excel_router

    excel_router._RATE_LIMITS["validate"] = 2
    excel_router._RATE_BUCKETS.clear()
    try:
        admin = await login(client)
        expected = await _headers(client, admin)
        content = _workbook_bytes("feeTypes", [], headers=expected)
        for _ in range(2):
            response = await client.post(
                "/api/v1/excel/feeTypes/validate",
                headers=admin,
                files={"file": ("batch.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"mode": "CREATE_ONLY"},
            )
            assert response.status_code in (200, 422), response.text
        third = await client.post(
            "/api/v1/excel/feeTypes/validate",
            headers=admin,
            files={"file": ("batch.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"mode": "CREATE_ONLY"},
        )
        assert third.status_code == 403, third.text
    finally:
        del excel_router._RATE_LIMITS["validate"]


async def test_export_strips_illegal_control_characters(client, session_factory):
    from app.modules.excel_io import service as excel
    from app.modules.master_data import service as md

    spec = md.get_spec("feeTypes")
    model = spec.model()
    setattr(model, spec.fields["code"], "FT-CTRL")
    setattr(model, spec.fields["name"], "Bad\x00\x08Name")
    setattr(model, spec.status_field, "ACTIVE")
    async with session_factory() as session:
        session.add(model)
        await session.commit()
        content = await excel.export_rows(session, excel.get_module("feeTypes"), None)
    workbook = load_workbook(io.BytesIO(content))
    names = [row[1] for row in workbook["Data"].iter_rows(min_row=2, values_only=True)]
    assert any(name == "BadName" for name in names)


async def test_zip_expansion_limit_uses_uncompressed_size(monkeypatch):
    """A small archive that expands hugely must be refused (zip bomb)."""
    import zipfile

    from app.core.exceptions import ValidationFailed
    from app.modules.excel_io import service as excel

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("xl/worksheets/sheet1.xml", b"\0" * (5 * 1024 * 1024))
    content = stream.getvalue()
    # Compressed size is tiny, so a compress_size check would let this through.
    assert len(content) < 200 * 1024
    monkeypatch.setattr(excel, "MAX_UNCOMPRESSED_BYTES", 1024 * 1024)
    with pytest.raises(ValidationFailed):
        excel.parse_workbook(content, excel.get_module("feeTypes"))


async def test_row_cap_is_enforced(monkeypatch):
    """The row cap still fires now that the Data sheet is streamed, not listed."""
    from app.core.exceptions import ValidationFailed
    from app.modules.excel_io import service as excel

    monkeypatch.setattr(excel, "MAX_IMPORT_ROWS", 3)
    headers = [column.key for column in excel.get_module("feeTypes").columns]
    content = _workbook_bytes("feeTypes", [_fee_row(f"FT-ROW-{index}") for index in range(4)], headers=headers)
    with pytest.raises(ValidationFailed):
        excel.parse_workbook(content, excel.get_module("feeTypes"))


async def test_export_escapes_a_formula_prefix_hidden_behind_whitespace():
    from app.modules.excel_io import service as excel

    assert excel._export_safe("\t=cmd()").startswith("'")
    assert excel._export_safe("  =1+1").startswith("'")
    assert excel._export_safe("plain text") == "plain text"


async def test_no_registered_module_exports_a_sensitive_field():
    from app.core.crypto import is_sensitive_field
    from app.modules.excel_io.registry import REGISTRY

    for module in REGISTRY.values():
        for column in module.columns:
            assert not is_sensitive_field(column.key), f"{module.key}.{column.key}"


async def test_unscoped_history_requires_master_data_read():
    """Unscoped history spans every module, so it needs the module read right."""
    from app.core.context import RequestContext
    from app.core.exceptions import AccessDenied
    from app.modules.excel_io import router as excel_router

    context = RequestContext(
        user_id=99,
        username="nobody",
        email="nobody@example.test",
        display_name="Nobody",
        permissions={"report.read"},
        is_platform_admin=False,
        request_id="test",
    )
    with pytest.raises(AccessDenied):
        await excel_router.import_history(request=None, module=None, context=context, session=None)


async def test_document_types_import_rejects_invented_behaviour(client):
    headers = await login(client)
    response = await client.get("/api/v1/excel/documentTypes/template", headers=headers)
    workbook = load_workbook(io.BytesIO(response.content))
    expected = [cell.value for cell in next(workbook["Data"].iter_rows(min_row=1, max_row=1))]
    row = ["DT_ONE", "Custom Type", "FINANCE", None, "INVENTED", None, "financial_documents", "ACTIVE"]
    content = _workbook_bytes("documentTypes", [row], headers=expected)
    data = (await _validate(client, headers, "documentTypes", content)).json()["data"]
    assert data["summary"]["error"] == 1, data
    failed = next(item for item in data["rows"] if item["action"] == "ERROR")
    assert any("accountingBehavior" in error for error in failed["errors"]), failed["errors"]


def test_export_quote_is_removed_on_import():
    from app.modules.excel_io.service import _import_unescape

    assert _import_unescape("'+855 12 345 678") == "+855 12 345 678"
    assert _import_unescape("'  =cmd()") == "  =cmd()"
    assert _import_unescape("'hello") == "'hello"
    assert _import_unescape("plain") == "plain"


async def test_export_headers_match_the_template_so_a_file_can_be_reimported(client):
    headers = await login(client)
    template = await client.get("/api/v1/excel/businessParties/template", headers=headers)
    assert template.status_code == 200, template.text
    expected = [cell.value for cell in next(load_workbook(io.BytesIO(template.content))["Data"].iter_rows(min_row=1, max_row=1))]
    exported = await client.post("/api/v1/excel/businessParties/export", headers=headers, json={})
    assert exported.status_code == 200, exported.text
    workbook = load_workbook(io.BytesIO(exported.content))
    exported_headers = [cell.value for cell in next(workbook["Data"].iter_rows(min_row=1, max_row=1))]
    assert exported_headers == expected, exported_headers
    assert len(exported_headers) == len(set(exported_headers)), exported_headers


# --- Export dialog filters ----------------------------------------------------


async def _seed_fee(client, code: str, name: str, status: str = "ACTIVE") -> None:
    headers = await login(client)
    expected = await _headers(client, headers)
    content = _workbook_bytes("feeTypes", [_fee_row(code, name, status=status)], headers=expected)
    data = (await _validate(client, headers, "feeTypes", content)).json()["data"]
    commit = await client.post(f"/api/v1/excel/imports/{data['token']}/commit", headers=headers)
    assert commit.status_code == 200, commit.text


async def _exported_codes(response) -> list[str]:
    assert response.status_code == 200, response.text
    if response.headers["content-type"].startswith("text/csv"):
        import csv as csv_module

        rows = list(csv_module.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        return [row[0] for row in rows[1:]]
    workbook = load_workbook(io.BytesIO(response.content))
    return [row[0] for row in workbook["Data"].iter_rows(min_row=2, values_only=True)]


async def test_export_filter_by_status(client):
    headers = await login(client)
    await _seed_fee(client, "FT-ST-A", "Status Active")
    await _seed_fee(client, "FT-ST-I", "Status Inactive", status="INACTIVE")
    response = await client.post(
        "/api/v1/excel/feeTypes/export", headers=headers, json={"filters": {"status": "ACTIVE"}}
    )
    codes = await _exported_codes(response)
    assert "FT-ST-A" in codes and "FT-ST-I" not in codes


async def test_export_filter_by_search_only(client):
    headers = await login(client)
    await _seed_fee(client, "FT-ONLY-1", "Alpha Freight")
    await _seed_fee(client, "FT-ONLY-2", "Beta Handling")
    response = await client.post(
        "/api/v1/excel/feeTypes/export", headers=headers, json={"filters": {"search": "  Alpha  "}}
    )
    assert await _exported_codes(response) == ["FT-ONLY-1"]


async def test_export_filter_by_search_and_combined_filters(client):
    headers = await login(client)
    await _seed_fee(client, "FT-SR-1", "Alpha Freight")
    await _seed_fee(client, "FT-SR-2", "Beta Handling")
    response = await client.post(
        "/api/v1/excel/feeTypes/export",
        headers=headers,
        json={"filters": {"search": "alpha", "status": "ACTIVE", "date_from": "2020-01-01"}},
    )
    codes = await _exported_codes(response)
    assert "FT-SR-1" in codes and "FT-SR-2" not in codes


async def test_export_filter_by_date_range_excludes_future_rows(client):
    headers = await login(client)
    await _seed_fee(client, "FT-DT-1", "Dated Row")
    response = await client.post(
        "/api/v1/excel/feeTypes/export", headers=headers, json={"filters": {"date_from": "2999-01-01"}}
    )
    assert await _exported_codes(response) == []
    response = await client.post(
        "/api/v1/excel/feeTypes/export",
        headers=headers,
        json={"filters": {"date_from": "2000-01-01", "date_to": "2999-01-01"}},
    )
    assert "FT-DT-1" in await _exported_codes(response)


async def test_export_csv_format_keeps_the_same_columns(client):
    headers = await login(client)
    await _seed_fee(client, "FT-CS-1", "Csv Row")
    response = await client.post(
        "/api/v1/excel/feeTypes/export", headers=headers, json={"format": "csv", "filters": {"search": "Csv Row"}}
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    import csv as csv_module

    rows = list(csv_module.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][0] == "code" and rows[0][-1] == "status"
    assert ["FT-CS-1", "Csv Row", "Freight charges", "ACTIVE"] == rows[1]


async def test_export_count_matches_filters(client):
    headers = await login(client)
    await _seed_fee(client, "FT-CN-1", "Count One")
    count = await client.get("/api/v1/excel/feeTypes/export-count", headers=headers, params={"search": "Count One"})
    assert count.status_code == 200, count.text
    assert count.json()["data"]["count"] >= 1
    empty = await client.get(
        "/api/v1/excel/feeTypes/export-count", headers=headers, params={"search": "no-such-row"}
    )
    assert empty.json()["data"]["count"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"filters": {"date_from": "not-a-date"}},
        {"filters": {"created_by": "nope"}},
        {"filters": {"created_by": "999999"}},
        {"filters": {"updated_by": "1"}},  # feeTypes does not track updated_by
        {"format": "pdf"},
    ],
)
async def test_export_rejects_invalid_filters(client, payload):
    headers = await login(client)
    await _seed_fee(client, "FT-BAD-1", "Bad Filter")
    response = await client.post("/api/v1/excel/feeTypes/export", headers=headers, json=payload)
    assert response.status_code == 422, response.text


async def test_export_by_created_user_on_supported_module(client, session_factory):
    """documentTypes tracks created_by; only its rows created by user 1 match."""
    from app.modules.master_data import service as md

    async with session_factory() as session:
        spec = md.get_spec("documentTypes")
        model = spec.model()
        setattr(model, spec.fields["code"], "DT_EXP_USER")
        setattr(model, spec.fields["name"], "Export User Type")
        model.accounting_behavior = "financial_documents"
        setattr(model, spec.status_field, "ACTIVE")
        model.created_by_user_id = 1
        session.add(model)
        await session.commit()

    headers = await login(client)
    response = await client.post(
        "/api/v1/excel/documentTypes/export", headers=headers, json={"filters": {"created_by": "1"}}
    )
    assert "DT_EXP_USER" in await _exported_codes(response)
    count = await client.get(
        "/api/v1/excel/documentTypes/export-count", headers=headers, params={"created_by": "1"}
    )
    assert count.json()["data"]["count"] >= 1
    catalog = await client.get("/api/v1/excel/modules", headers=headers)
    modules = {item["key"]: item for item in catalog.json()["data"]}
    assert modules["documentTypes"]["createdBySupported"] is True
    assert modules["feeTypes"]["updatedBySupported"] is False

