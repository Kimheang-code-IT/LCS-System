"""Upload → validate → preview → confirm → history, plus Excel export.

Every write goes through the module's own service layer (Phase B: the
master-data reference pipeline), so an import is validated exactly like an API
write — same schema, same reference resolution, same business checks, same
audit attribution. Preview never writes; commit revalidates against the
database and is atomic per batch.
"""

from __future__ import annotations

import csv
import hashlib
import io
import secrets
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import NotFound, ValidationFailed
from app.modules.excel_io import templates
from app.modules.excel_io.models import ImportJob, ImportSession
from app.modules.excel_io.registry import (
    MAX_ARCHIVE_ENTRIES,
    MAX_FILE_BYTES,
    MAX_IMPORT_ROWS,
    MAX_UNCOMPRESSED_BYTES,
    REGISTRY,
    SESSION_TTL_SECONDS,
    ImportModule,
)

_MAX_EXPORT_ROWS = 10_000
_FORMULA_PREFIXES = ("=", "+", "-", "@")


# --- Registry access ---------------------------------------------------------


def get_module(module: str) -> ImportModule:
    if module not in REGISTRY:
        raise NotFound(f"'{module}' is not an Import/Export module.")
    return REGISTRY[module]


def module_catalog() -> list[dict[str, Any]]:
    from app.modules.master_data import service as md

    return [
        {
            "key": module.key,
            "name": module.name,
            "importEnabled": module.import_enabled,
            "exportEnabled": module.export_enabled,
            "templateVersion": module.template_version,
            "matchKey": list(module.match_key),
            "viewPermission": module.view_permission,
            "managePermission": module.manage_permission,
            "createdBySupported": hasattr(md.get_spec(module.key).model, "created_by_user_id"),
            "updatedBySupported": hasattr(md.get_spec(module.key).model, "updated_by_user_id"),
            "columns": [
                {
                    "key": column.key,
                    "kind": column.kind,
                    "required": column.required,
                    "enum": list(column.enum),
                    "updatable": column.updatable,
                }
                for column in module.columns
            ],
        }
        for module in REGISTRY.values()
    ]


# --- Workbook parsing --------------------------------------------------------


def _safe_archive(content: bytes) -> None:
    """Reject malformed workbooks and oversized zip expansion.

    The expansion limit must be read from the *uncompressed* sizes: compressed
    sizes are always smaller than the uploaded file, so checking them would
    never reject anything. A high ratio or a huge declared size is a zip bomb.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {info.filename for info in entries}
            if "[Content_Types].xml" not in names or not any(name.startswith("xl/") for name in names):
                raise ValidationFailed("Not a valid Excel workbook.", {"file": "Not a .xlsx workbook"})
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise ValidationFailed("The workbook is too large.", {"file": "Too many archive entries"})
            if sum(info.file_size for info in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ValidationFailed("The workbook is too large.", {"file": "Workbook too large"})
            if content and sum(info.file_size for info in entries) > len(content) * 100:
                raise ValidationFailed("The workbook is too large.", {"file": "Suspicious compression ratio"})
    except zipfile.BadZipFile as exc:
        raise ValidationFailed("Not a valid Excel workbook.", {"file": "Invalid file"}) from exc


def parse_workbook(content: bytes, module: ImportModule) -> list[dict[str, Any]]:
    """Read the Data sheet into dicts keyed by the template headers.

    Header matching is exact (same columns, same order). A formula cell or a
    stale template version is refused before any row is considered.
    """
    _safe_archive(content)
    workbook = None
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        return _parse_sheets(workbook, module)
    except ValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001 - openpyxl raises many shapes here
        raise ValidationFailed("The workbook could not be read.", {"file": "Invalid workbook"}) from exc
    finally:
        if workbook is not None:
            workbook.close()


def _parse_sheets(workbook, module: ImportModule) -> list[dict[str, Any]]:
    if "Data" not in workbook.sheetnames or "Instructions" not in workbook.sheetnames:
        raise ValidationFailed(
            "This file is not one of our import templates (Instructions and Data sheets are required).",
            {"file": "Not a template"},
        )
    stored_version = workbook["Instructions"]["B1"].value
    if stored_version is None or int(stored_version) != module.template_version:
        raise ValidationFailed(
            "The template version does not match. Download a fresh template.",
            {"file": "Outdated template"},
        )
    sheet = workbook["Data"]
    # Stream the rows: `list(sheet.iter_rows())` would materialize a million-row
    # sheet in memory before the row cap below could ever reject it.
    rows = sheet.iter_rows(values_only=False)
    header_row = next(rows, None)
    if header_row is None:
        raise ValidationFailed("The Data sheet has no header row.", {"file": "Empty template"})
    headers = [cell.value for cell in header_row]
    expected = [column.key for column in module.columns]
    if headers != expected:
        raise ValidationFailed(
            "Column headers must match the template exactly, in order.",
            {"file": "Headers do not match"},
        )
    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        if len(row) > len(expected):
            raise ValidationFailed(
                f"Row {index}: the sheet has more columns than the template.",
                {"row": index},
            )
        if all(cell.value in (None, "") for cell in row):
            continue
        if len(parsed) >= MAX_IMPORT_ROWS:
            raise ValidationFailed(
                f"A workbook may hold at most {MAX_IMPORT_ROWS} data rows.",
                {"file": "Too many rows"},
            )
        values: dict[str, Any] = {}
        for column, cell in zip(module.columns, row, strict=True):
            if cell.data_type == "f":
                raise ValidationFailed(
                    f"Row {index}: formulas are not allowed (column {column.key}).",
                    {"row": index, "column": column.key},
                )
            values[column.key] = _import_unescape(cell.value)
        parsed.append({"_excelRow": index, **values})
    return parsed


# --- Row validation ----------------------------------------------------------


def _coerce(column, raw: Any, errors: dict[str, str]) -> Any:
    """One cell to its typed value; a bad cell records an error on its field."""
    if raw is None or raw == "":
        return None
    text = str(raw).strip()
    if column.kind in {"text", "reference"}:
        return text
    if column.kind == "enum":
        return text.upper()
    if column.kind == "boolean":
        lowered = text.lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
        errors[column.key] = "Enter TRUE or FALSE."
        return None
    if column.kind == "integer":
        try:
            return int(text)
        except ValueError:
            errors[column.key] = "Enter a whole number."
            return None
    if column.kind == "number":
        try:
            return Decimal(text)
        except InvalidOperation:
            errors[column.key] = "Enter a number."
            return None
    return text  # date: the service pipeline parses the API date format


def _row_data(module: ImportModule, row: dict[str, Any]) -> dict[str, Any]:
    errors: dict[str, str] = {}
    data = {
        column.key: value
        for column in module.columns
        if (value := _coerce(column, row.get(column.key), errors)) is not None
    }
    if errors:
        raise ValidationFailed(
            f"Row {row['_excelRow']}: invalid value.",
            errors,
        )
    return data


async def _match_existing(db: AsyncSession, module: ImportModule, data: dict[str, Any]) -> Any:
    from app.modules.master_data import service as md

    spec = md.get_spec(module.key)
    model = spec.model
    key_values = {key: data[key] for key in module.match_key if data.get(key) not in (None, "")}
    if len(key_values) != len(module.match_key):
        return None
    column_filter = [model.__table__.columns.get(spec.fields[key]) == value for key, value in key_values.items()]
    return (
        await db.execute(select(model).where(*column_filter, model.deleted_at.is_(None)))
    ).scalars().first()


def _identifier_of(module: ImportModule, spec, record: Any) -> str:
    return module.identifier({key: getattr(record, attr, None) for key, attr in spec.fields.items()})


async def _pipeline(
    db: AsyncSession,
    module: ImportModule,
    model: Any,
    data: dict[str, Any],
    *,
    create: bool,
) -> None:
    """Run the master-data spec pipeline against a model without writing."""
    from app.modules.master_data import service as md

    spec = md.get_spec(module.key)
    if spec.transform_input is not None:
        data = spec.transform_input(dict(data))
    data = md._spec_schema(spec).validate(data, partial=not create)
    md._validate_required(spec, data, model)
    await md.apply_input(spec, model, data, db)
    if spec.validate_data is not None:
        await spec.validate_data(model, data, db)


async def validate_rows(
    db: AsyncSession,
    module: ImportModule,
    rows: list[dict[str, Any]],
    mode: str,
) -> list[dict[str, Any]]:
    """Validate every row against the module's service layer. Writes nothing."""
    from app.modules.master_data import service as md

    preview: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for row in rows:
        item = {
            "excelRow": row["_excelRow"],
            "identifier": module.identifier(row),
            "action": "ERROR",
            "status": "INVALID",
            "errors": [],
            "data": {},
        }
        preview.append(item)
        try:
            data = _row_data(module, row)

            # Duplicate rows inside one workbook share a match key.
            identity = module.identifier(data)
            duplicate_row = seen.get(identity)
            if identity and duplicate_row:
                raise ValidationFailed(
                    f"Row {duplicate_row} in this file already uses this identifier.",
                    {module.match_key[0]: "Duplicate row within the workbook."},
                )
            if identity:
                seen[identity] = row["_excelRow"]

            existing = await _match_existing(db, module, data)
            if existing is not None and mode == "CREATE_ONLY":
                item["action"] = "SKIP"
                item["status"] = "VALID"
                item["identifier"] = _identifier_of(module, md.get_spec(module.key), existing)
                item["errors"] = ["Duplicate — Create Only skips existing records."]
                continue
            item["action"] = "UPDATE" if existing is not None else "CREATE"
            if existing is not None:
                item["identifier"] = _identifier_of(module, md.get_spec(module.key), existing)
                # Only what an import may change is applied, and only what
                # actually differs is reported back to the operator.
                updates = {key: value for key, value in data.items() if module.may_update(key)}
                await _pipeline(db, module, existing, updates, create=False)
            else:
                await _pipeline(db, module, md.get_spec(module.key).model(), data, create=True)
        except ValidationFailed as exc:
            item["action"] = "ERROR"
            item["status"] = "INVALID"
            item["errors"] = [exc.message, *(
                f"{key}: {text}" for key, text in (exc.field_errors or {}).items()
            )]
            continue
        item["status"] = "VALID"
        if item["action"] != "SKIP":
            item["errors"] = []
    # The pipeline mutates fetched models in memory for cross-record validation;
    # discard that state so a preview can never leak into a later write.
    await db.rollback()
    return preview


# --- Import sessions (preview → confirm) -------------------------------------
#
# The session lives in PostgreSQL (import_sessions), not in process memory: a
# validated preview survives a backend restart, memory stays bounded, and the
# commit claims the row with one atomic DELETE … RETURNING, so a repeated or
# concurrent confirmation finds nothing to commit. Expired rows are purged on
# every new upload.


@dataclass
class ImportSessionState:
    token: str
    user_id: int
    module: str
    mode: str
    checksum: str
    rows: list[dict[str, Any]]
    preview: list[dict[str, Any]]
    file_name: str = ""


def preview_summary(preview: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(preview),
        "create": sum(1 for item in preview if item["action"] == "CREATE"),
        "update": sum(1 for item in preview if item["action"] == "UPDATE"),
        "skip": sum(1 for item in preview if item["action"] == "SKIP"),
        "error": sum(1 for item in preview if item["action"] == "ERROR"),
    }


async def start_import(
    db: AsyncSession,
    context: RequestContext,
    module: ImportModule,
    file_name: str,
    content: bytes,
    mode: str,
) -> dict[str, Any]:
    """Validate an uploaded workbook, store the session, return the preview."""
    if len(content) > MAX_FILE_BYTES:
        raise ValidationFailed("The file is too large.", {"file": "File too large"})
    if mode not in ("CREATE_ONLY", "CREATE_AND_UPDATE", "VALIDATE_ONLY"):
        raise ValidationFailed("Unknown import mode.", {"mode": "Unsupported mode"})
    rows = parse_workbook(content, module)
    if not rows:
        raise ValidationFailed("The workbook has no data rows.", {"file": "No data rows"})
    preview = await validate_rows(db, module, rows, mode)
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS)
    # One user, one pending import per module: the oldest pending row is
    # replaced, so memory/storage stays bounded per operator.
    await db.execute(
        delete(ImportSession).where(
            ImportSession.user_id == context.user_id,
            ImportSession.module == module.key,
        )
    )
    await db.execute(delete(ImportSession).where(ImportSession.expires_at < datetime.now(UTC)))
    db.add(
        ImportSession(
            token=token,
            user_id=context.user_id,
            module=module.key,
            mode=mode,
            file_name=file_name,
            checksum=hashlib.sha256(content).hexdigest(),
            template_version=module.template_version,
            rows_data=rows,
            preview_data=preview,
            expires_at=expires_at,
        )
    )
    await db.commit()
    return {
        "token": token,
        "module": module.key,
        "mode": mode,
        "expiresAt": expires_at.isoformat(),
        "summary": preview_summary(preview),
        "rows": preview,
    }


async def get_session_state(db: AsyncSession, token: str, context: RequestContext) -> ImportSessionState:
    """Only the uploading user may preview, confirm, cancel or download errors."""
    row = (
        await db.execute(
            select(ImportSession).where(
                ImportSession.token == token,
                ImportSession.user_id == context.user_id,
                ImportSession.expires_at > datetime.now(UTC),
            )
        )
    ).scalars().first()
    if row is None:
        raise NotFound("The import session expired. Upload the file again.")
    return ImportSessionState(
        token=row.token,
        user_id=int(row.user_id),
        module=row.module,
        mode=row.mode,
        checksum=row.checksum,
        rows=row.rows_data or [],
        preview=row.preview_data or [],
        file_name=row.file_name,
    )


async def cancel_import(db: AsyncSession, token: str, context: RequestContext) -> None:
    await get_session_state(db, token, context)
    await db.execute(delete(ImportSession).where(ImportSession.token == token))
    await db.commit()


async def get_preview_rows(db: AsyncSession, token: str, context: RequestContext) -> dict[str, Any]:
    import_session = await get_session_state(db, token, context)
    return {
        "token": import_session.token,
        "module": import_session.module,
        "mode": import_session.mode,
        "summary": preview_summary(import_session.preview),
        "rows": import_session.preview,
        "expired": False,
    }


async def claim_session(db: AsyncSession, token: str, context: RequestContext) -> ImportSessionState:
    """Atomically claim the token: delete the row and commit immediately.

    The delete must be committed before any validation rollback can follow, so
    a token confirms at most once — including when the import itself fails.
    A concurrent second commit blocks on the row lock and then finds nothing.
    """
    result = await db.execute(
        delete(ImportSession)
        .where(
            ImportSession.token == token,
            ImportSession.user_id == context.user_id,
            ImportSession.expires_at > datetime.now(UTC),
        )
        .returning(
            ImportSession.token,
            ImportSession.user_id,
            ImportSession.module,
            ImportSession.mode,
            ImportSession.checksum,
            ImportSession.rows_data,
            ImportSession.preview_data,
            ImportSession.file_name,
        )
    )
    row = result.first()
    await db.commit()
    if row is None:
        # Either expired, never created, owned by someone else, or already
        # claimed — all resolve to the same operator action: start again.
        raise NotFound("The import session expired or was already confirmed. Upload the file again.")
    return ImportSessionState(
        token=row.token,
        user_id=int(row.user_id),
        module=row.module,
        mode=row.mode,
        checksum=row.checksum,
        rows=row.rows_data or [],
        preview=row.preview_data or [],
        file_name=row.file_name,
    )


# --- Commit ------------------------------------------------------------------


async def confirm_import(db: AsyncSession, context: RequestContext, token: str) -> dict[str, Any]:
    """Revalidate and commit the batch atomically; record the history row."""
    import_session = await claim_session(db, token, context)
    if import_session.mode == "VALIDATE_ONLY":
        raise ValidationFailed(
            "Validate Only writes nothing, so there is nothing to confirm.",
            {"mode": "Validate Only"},
        )
    module = get_module(import_session.module)

    from app.modules.master_data import service as md

    failed_summary: dict[str, int] | None = None
    failed_errors: str | None = None
    try:
        # Revalidate against the live database: rows may have changed since the
        # preview was generated.
        preview = await validate_rows(db, module, import_session.rows, import_session.mode)
        summary = preview_summary(preview)
        if any(item["action"] == "ERROR" for item in preview):
            failed_summary, failed_errors = summary, _error_text(preview)
            raise ValidationFailed(
                "The workbook no longer validates cleanly. Download the error report.",
                {"token": "Validation failed at commit time."},
            )
        for index, item in enumerate(preview):
            row = import_session.rows[index]
            data = _row_data(module, row)
            if item["action"] == "CREATE":
                await md.create_reference(db, module.key, data, context, commit=False)
            elif item["action"] == "UPDATE":
                existing = await _match_existing(db, module, data)
                if existing is None:
                    raise ValidationFailed("The record to update was removed since the preview.")
                await md.update_reference(
                    db,
                    module.key,
                    int(existing.id),
                    {key: value for key, value in data.items() if module.may_update(key)},
                    commit=False,
                )
        await md.cache.bump("master_data")
        job = _record_job(db, context, module, import_session, "COMPLETED", summary, None)
        await db.commit()
        return {"jobId": str(job.id), "status": "COMPLETED", **summary}
    except Exception as exc:
        # Atomic all-or-nothing: any failed row discards the whole batch, and the
        # failure is recorded as history on its own clean transaction. The token
        # was already claimed and stays single-use even when the import fails.
        await db.rollback()
        if failed_summary is not None or not isinstance(exc, ValidationFailed):
            _record_job(
                db,
                context,
                module,
                import_session,
                "FAILED",
                failed_summary or {"total": len(import_session.rows), "create": 0, "update": 0, "skip": 0, "error": len(import_session.rows)},
                failed_errors or str(getattr(exc, "message", exc))[:2000],
            )
            await db.commit()
        raise


def _error_text(preview: list[dict[str, Any]]) -> str:
    lines = []
    for item in preview:
        if item["action"] == "ERROR":
            lines.append(f"Row {item['excelRow']}: {'; '.join(item['errors'])}")
    return "\n".join(lines)[:2000]


def _record_job(
    db: AsyncSession,
    context: RequestContext,
    module: ImportModule,
    import_session: ImportSessionState,
    status: str,
    summary: dict[str, int],
    error_summary: str | None,
) -> ImportJob:
    """One history row per confirmed/failed batch. Added on the live transaction."""
    job = ImportJob(
        module=module.key,
        file_name=import_session.file_name,
        mode=import_session.mode,
        status=status,
        template_version=module.template_version,
        total_rows=len(import_session.rows),
        created_count=summary.get("create", 0),
        updated_count=summary.get("update", 0),
        skipped_count=summary.get("skip", 0),
        failed_count=summary.get("error", 0),
        error_summary=error_summary,
        started_by_user_id=context.user_id,
        completed_at=datetime.now(UTC),
    )
    db.add(job)
    return job


# --- Error report ------------------------------------------------------------


def build_error_report(module: ImportModule, preview: list[dict[str, Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Errors"
    sheet.append(["Excel Row No.", "Identifier", "Action", "Validation Status", "Errors"])
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = templates.HEADER_FILL
    for item in preview:
        sheet.append(
            [
                item["excelRow"],
                _export_safe(item["identifier"]),
                item["action"],
                item["status"],
                "\n".join(item["errors"]),
            ]
        )
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


# --- Export ------------------------------------------------------------------


def _export_safe(value: Any) -> Any:
    """Neutralize formula injection (=+-@ prefixes) and strip XML-illegal
    control characters, so a stored value can never break the workbook.

    The prefix check ignores leading whitespace: a stored ``"\\t=cmd()"`` must be
    escaped exactly like ``"=cmd()"``.
    """
    if isinstance(value, str):
        value = ILLEGAL_CHARACTERS_RE.sub("", value)
        if value.lstrip().startswith(_FORMULA_PREFIXES):
            return "'" + value
    return value


def _import_unescape(value: Any) -> Any:
    """Undo the export quoting so an exported workbook re-imports losslessly."""
    if isinstance(value, str) and value.startswith("'") and value[1:].lstrip().startswith(_FORMULA_PREFIXES):
        return value[1:]
    return value


def _display(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value


_EXPORT_FORMATS = ("xlsx", "csv")
_BLANK = (None, "", "all")


def _parse_export_date(value: Any, key: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationFailed("Invalid export date filter.", {key: "Invalid date"}) from exc


def _parse_export_user(value: Any, key: str) -> int:
    try:
        user_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed("Invalid export user filter.", {key: "Invalid user"}) from exc
    if user_id < 1:
        raise ValidationFailed("Invalid export user filter.", {key: "Invalid user"})
    return user_id


def _export_conditions(spec: Any, module: ImportModule, filters: dict[str, Any]) -> tuple[list[Any], list[int]]:
    """Translate dialog filters into query conditions applied at the database level.

    A user filter is only legal when the module's model tracks that attribution
    (``where supported``); an unknown user id is refused instead of exporting nothing.
    Returns ``(conditions, user_ids_to_verify)``.
    """
    model = spec.model
    conditions: list[Any] = []
    user_ids: list[int] = []

    if filters.get("date_from"):
        conditions.append(model.created_at >= _parse_export_date(filters["date_from"], "date_from"))
    if filters.get("date_to"):
        # A date-only To value means "through the end of that day".
        conditions.append(model.created_at < _parse_export_date(filters["date_to"], "date_to") + timedelta(days=1))

    for key, column in (("created_by", "created_by_user_id"), ("updated_by", "updated_by_user_id")):
        value = filters.get(key)
        if value in _BLANK:
            continue
        attr = getattr(model, column, None)
        if attr is None:
            raise ValidationFailed(f"'{key}' is not supported for this module.", {key: "Not supported"})
        user_ids.append(_parse_export_user(value, key))
        conditions.append(attr == user_ids[-1])

    status = str(filters.get("status") or "").strip().upper()
    if status and status != "ALL":
        conditions.append(model.status == status)

    needle = str(filters.get("search") or "").strip()
    if needle:
        text_columns = [getattr(model, spec.fields[column.key]) for column in module.columns if column.kind == "text"]
        if text_columns:
            conditions.append(or_(*[column.ilike(f"%{needle}%") for column in text_columns]))

    return conditions, user_ids


async def _filtered_export_query(db: AsyncSession, base_query: Any, spec: Any, module: ImportModule, filters: dict[str, Any]) -> Any:
    from app.modules.auth.models import User

    conditions, user_ids = _export_conditions(spec, module, filters)
    if user_ids:
        known = set((await db.execute(select(User.id).where(User.id.in_(user_ids)))).scalars())
        if set(user_ids) - known:
            raise ValidationFailed("Unknown user in export filters.", {"user": "Unknown user"})
    for condition in conditions:
        base_query = base_query.where(condition)
    return base_query


async def export_count(db: AsyncSession, module: ImportModule, filters: dict[str, Any] | None = None) -> int:
    """Number of rows the current export filters would include."""
    from app.modules.master_data import service as md

    spec = md.get_spec(module.key)
    model = spec.model
    query = await _filtered_export_query(
        db, select(func.count()).select_from(model).where(model.deleted_at.is_(None)), spec, module, filters or {},
    )
    return int((await db.execute(query)).scalar() or 0)


def _export_table(module: ImportModule, spec: Any, rows: list[Any]) -> tuple[list[str], list[list[Any]]]:
    """Shared serialization so xlsx and csv keep the same columns and formatting."""
    headers = [column.key for column in module.columns]
    if "status" not in headers:
        headers.append("status")
    data: list[list[Any]] = []
    for row in rows:
        values = {key: getattr(row, attr, None) for key, attr in spec.fields.items()}
        values["status"] = getattr(row, spec.status_field, None)
        data.append([_export_safe(_display(values.get(header))) for header in headers])
    return headers, data


def _csv_workbook(headers: list[str], data: list[list[Any]]) -> bytes:
    # utf-8-sig so Excel opens non-ASCII values (Khmer, Chinese) correctly.
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(data)
    return stream.getvalue().encode("utf-8-sig")


async def export_rows(
    db: AsyncSession,
    module: ImportModule,
    ids: list[int] | None,
    filters: dict[str, Any] | None = None,
    fmt: str = "xlsx",
) -> bytes:
    """Serialize the module's authorized rows into one formatted workbook."""
    if fmt not in _EXPORT_FORMATS:
        raise ValidationFailed("Unsupported export format.", {"format": "Unsupported format"})
    from app.modules.master_data import service as md

    spec = md.get_spec(module.key)
    model = spec.model
    query = select(model).where(model.deleted_at.is_(None))
    if ids:
        query = query.where(model.id.in_(ids))
    query = await _filtered_export_query(db, query, spec, module, filters or {})
    rows = (
        (await db.execute(query.order_by(model.id).limit(_MAX_EXPORT_ROWS)))
        .scalars()
        .all()
    )
    headers, data = _export_table(module, spec, rows)
    if fmt == "csv":
        return _csv_workbook(headers, data)
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Data"
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = templates.HEADER_FILL
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{templates.get_column_letter(len(headers))}1"
    for index, header in enumerate(headers, start=1):
        sheet.column_dimensions[templates.get_column_letter(index)].width = max(14, min(34, len(header) + 6))
    for values in data:
        sheet.append(values)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


# --- History -----------------------------------------------------------------


async def history(db: AsyncSession, module_key: str | None, limit: int = 50) -> list[dict[str, Any]]:
    query = select(ImportJob).order_by(ImportJob.id.desc()).limit(min(limit, 200))
    if module_key:
        query = query.where(ImportJob.module == module_key)
    jobs = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(job.id),
            "module": job.module,
            "fileName": job.file_name,
            "mode": job.mode,
            "status": job.status,
            "templateVersion": job.template_version,
            "totalRows": job.total_rows,
            "created": job.created_count,
            "updated": job.updated_count,
            "skipped": job.skipped_count,
            "failed": job.failed_count,
            "errorSummary": job.error_summary,
            "startedByUserId": str(job.started_by_user_id) if job.started_by_user_id else None,
            "startedAt": job.created_at.isoformat() if job.created_at else None,
            "completedAt": job.completed_at.isoformat() if job.completed_at else None,
        }
        for job in jobs
    ]
