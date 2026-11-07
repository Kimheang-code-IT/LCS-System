"""Excel Import & Export for the Configuration module.

Covers the component catalog (attributes, groups, tabs) and whole configuration
versions. Catalog imports are create-only: a row whose stable ``code`` already
exists is skipped, never silently edited, and the batch is all-or-nothing. A
version workbook (Version / Attributes / Groups / Tabs / Relationships sheets)
creates one new ``DRAFT`` ``ConfigurationVersion`` — nothing publishable, and
no existing version (draft or published) is ever touched.

Rows are validated with the same ``component_config`` rules the API applies, so
an imported attribute is rejected exactly like a rejected create request.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import NotFound, ValidationFailed
from app.modules.excel_io import templates
from app.modules.excel_io.registry import MAX_IMPORT_ROWS, ImportModule
from app.modules.excel_io.service import (
    _csv_workbook,
    _export_safe,
    _row_data,
    _safe_archive,
    preview_summary,
)

_VERSION_SHEET_HEADERS: dict[str, list[str]] = {
    "Version": ["versionNo", "changeNote", "scope"],
    "Attributes": ["label", "code", "dataType", "options"],
    "Groups": ["code", "name", "nameKm", "description", "renderMode", "displayOrder"],
    "Tabs": ["code", "name", "description", "tradeDirection", "displayOrder"],
    "Relationships": ["tabCode", "groupCode", "attributeCode", "displayOrder", "isRequired"],
}

_VERSION_LIST_HEADERS = ["versionNo", "scope", "status", "origin", "changeNote", "publishedAt"]


def attribution_supported(module: ImportModule) -> bool:
    """Configuration models do not track created/updated-by attribution."""
    del module
    return False


def _normalize(code: Any) -> str:
    return str(code or "").strip().lower().replace(" ", "-")


def _text_field(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return str(value).strip() if value not in (None, "") else ""


def _split_options(raw: str) -> list[str]:
    # A comma inside an option is folded into the semicolon rule: exports
    # always serialize with "; ", the template documents the same rule.
    return [part.strip() for part in (raw or "").replace(",", ";").split(";") if part.strip()]


# --- Catalog model builders (validated, never written here) -------------------


def _build_attribute(data: dict[str, Any]):
    from app.modules.master_data.component_config import (
        SELECT_DATA_TYPES,
        _validate_attribute_config,
        _validate_data_type,
        _validated_code,
    )
    from app.modules.master_data.models import ComponentAttribute

    label = _text_field(data, "label")
    if not label:
        raise ValidationFailed("Row validation failed.", {"label": "Required"})
    code = _validated_code(_text_field(data, "code"))
    data_type = _validate_data_type(data.get("dataType"))
    raw_options = _text_field(data, "options")
    if raw_options and data_type not in SELECT_DATA_TYPES:
        raise ValidationFailed(
            "Options only apply to select fields.", {"options": "Only for select types"},
        )
    attribute = ComponentAttribute(
        code=code,
        label=label,
        data_type=data_type,
        options=_split_options(raw_options),
        display_order=0,
        status="ACTIVE",
    )
    _validate_attribute_config(attribute)
    return attribute


def _build_group(data: dict[str, Any]):
    from app.modules.master_data.component_config import RENDER_MODES
    from app.modules.master_data.models import ComponentGroup

    code = _normalize(data.get("code") or data.get("name"))
    if not code:
        raise ValidationFailed("Row validation failed.", {"code": "Required"})
    name = _text_field(data, "name")
    if not name:
        raise ValidationFailed("Row validation failed.", {"name": "Required"})
    render_mode = str(data.get("renderMode") or "table").strip().lower()
    if render_mode not in RENDER_MODES:
        raise ValidationFailed("renderMode must be 'table' or 'form'.", {"renderMode": "Unsupported"})
    return ComponentGroup(
        code=code,
        name=name,
        name_km=_text_field(data, "nameKm") or None,
        description=_text_field(data, "description") or None,
        render_mode=render_mode,
        display_order=int(data.get("displayOrder") or 0),
        is_active=True,
    )


async def _build_tab(db: AsyncSession, data: dict[str, Any]):
    from app.modules.master_data.models import ComponentTab, TradeDirection

    code = _normalize(data.get("code") or data.get("name"))
    if not code:
        raise ValidationFailed("Row validation failed.", {"code": "Required"})
    name = _text_field(data, "name")
    if not name:
        raise ValidationFailed("Row validation failed.", {"name": "Required"})
    direction_id = None
    ref = _text_field(data, "tradeDirection")
    if ref:
        direction = (
            await db.execute(
                select(TradeDirection).where(
                    TradeDirection.deleted_at.is_(None),
                    or_(TradeDirection.name == ref, TradeDirection.code == ref),
                )
            )
        ).scalars().first()
        if direction is None:
            raise ValidationFailed(
                "Unknown trade direction.", {"tradeDirection": "No matching Trade Direction"},
            )
        direction_id = int(direction.id)
    return ComponentTab(
        code=code,
        name=name,
        description=_text_field(data, "description") or None,
        trade_direction_id=direction_id,
        display_order=int(data.get("displayOrder") or 0),
        is_active=True,
    )


async def _build_row(db: AsyncSession, module: ImportModule, data: dict[str, Any]):
    if module.key == "componentAttributes":
        return _build_attribute(data)
    if module.key == "componentGroups":
        return _build_group(data)
    return await _build_tab(db, data)


def _identity_of(module: ImportModule, data: dict[str, Any]) -> str:
    from app.modules.master_data.component_config import _derived_code

    if module.key == "componentAttributes":
        return _text_field(data, "code") or _derived_code(_text_field(data, "label"))
    return _normalize(data.get("code") or data.get("name"))


def _catalog_model(key: str):
    from app.modules.master_data.models import ComponentAttribute, ComponentGroup, ComponentTab

    return {
        "componentAttributes": ComponentAttribute,
        "componentGroups": ComponentGroup,
        "componentTabs": ComponentTab,
        # Version-workbook sheet names map to the same catalog models.
        "Attributes": ComponentAttribute,
        "Groups": ComponentGroup,
        "Tabs": ComponentTab,
    }[key]


async def _match_existing(db: AsyncSession, module: ImportModule, identity: str):
    model = _catalog_model(module.key)
    if not identity:
        return None
    return (
        await db.execute(select(model).where(model.code == identity))
    ).scalars().first()


async def validate_rows(
    db: AsyncSession,
    module: ImportModule,
    rows: list[dict[str, Any]],
    mode: str,
) -> list[dict[str, Any]]:
    """Validate every row like the module's own API write. Preview writes nothing."""
    del mode  # configuration imports are always create-only (see registry)
    preview: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for row in rows:
        item = {
            "excelRow": row["_excelRow"],
            "identifier": _identity_of(module, row) if not _text_field(row, "code") else _text_field(row, "code"),
            "action": "ERROR",
            "status": "INVALID",
            "errors": [],
            "data": {},
        }
        preview.append(item)
        try:
            data = _row_data(module, row)
            identity = _identity_of(module, data)
            if not identity:
                raise ValidationFailed("Row validation failed.", {"code": "Required"})
            duplicate_row = seen.get(identity)
            if duplicate_row:
                raise ValidationFailed(
                    f"Row {duplicate_row} in this file already uses this code.",
                    {"code": "Duplicate row within the workbook."},
                )
            seen[identity] = row["_excelRow"]
            if await _match_existing(db, module, identity) is not None:
                # Create-only: a stable code is never edited by an import.
                item["action"] = "SKIP"
                item["status"] = "VALID"
                item["identifier"] = identity
                item["errors"] = ["Duplicate — Create Only skips existing records."]
                continue
            await _build_row(db, module, data)
            item["action"] = "CREATE"
        except ValidationFailed as exc:
            item["errors"] = [exc.message, *(
                f"{key}: {text}" for key, text in (exc.field_errors or {}).items()
            )]
            continue
        item["status"] = "VALID"
        item["errors"] = []
    # _build_row only constructs in-memory models; discard that state so a
    # preview can never leak into a later write (same rule as the master-data
    # pipeline).
    await db.rollback()
    return preview


async def confirm_rows(db: AsyncSession, module: ImportModule, import_session) -> dict[str, int]:
    """Revalidate against the live catalog and create the batch in one transaction."""
    preview = await validate_rows(db, module, import_session.rows, "CREATE_ONLY")
    summary = preview_summary(preview)
    if any(item["action"] == "ERROR" for item in preview):
        raise ValidationFailed(
            "The workbook no longer validates cleanly. Download the error report.",
            {"token": "Validation failed at commit time."},
        )
    for index, item in enumerate(preview):
        if item["action"] != "CREATE":
            continue
        entity = await _build_row(db, module, _row_data(module, import_session.rows[index]))
        if not int(entity.display_order or 0):
            highest = await db.scalar(select(func.max(type(entity).display_order)))
            entity.display_order = int(highest or 0) + 10
        db.add(entity)
    return summary


# --- Catalog export -----------------------------------------------------------


def _catalog_query(db: AsyncSession, module: ImportModule, filters: dict[str, Any]):
    model = _catalog_model(module.key)
    query = select(model)
    if module.key == "componentAttributes":
        query = query.where(model.status != "INACTIVE")
        status = str(filters.get("status") or "").strip().upper()
        if status and status != "ALL":
            query = query.where(model.status == status)
    else:
        query = query.where(model.is_archived.is_(False))
    needle = str(filters.get("search") or "").strip()
    if needle:
        query = query.where(or_(
            *(getattr(model, column.key).ilike(f"%{needle}%") for column in module.columns),
        ))
    for key, upper in (("date_from", False), ("date_to", True)):
        value = filters.get(key)
        if not value:
            continue
        try:
            moment = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise ValidationFailed("Invalid export date filter.", {key: "Invalid date"}) from exc
        if upper:
            moment = moment + timedelta(days=1)
        query = query.where(model.created_at >= moment if not upper else model.created_at < moment)
    return model, query


async def export_count(db: AsyncSession, module: ImportModule, filters: dict[str, Any] | None = None) -> int:
    _model, query = _catalog_query(db, module, filters or {})
    return int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)


def _catalog_table(module: ImportModule, rows: list[Any]) -> tuple[list[str], list[list[Any]]]:
    headers = [column.key for column in module.columns]
    data: list[list[Any]] = []
    for row in rows:
        values: dict[str, Any] = {}
        for column in module.columns:
            if column.key == "options":
                values[column.key] = "; ".join(str(option) for option in (row.options or []))
            elif column.key == "tradeDirection":
                values[column.key] = getattr(row, "_trade_direction_label", None) or ""
            else:
                attr = {
                    "labelKm": "label_km",
                    "dataType": "data_type",
                    "renderMode": "render_mode",
                    "displayOrder": "display_order",
                }.get(column.key, column.key)
                values[column.key] = getattr(row, attr, None)
        values = {key: _display_value(value) for key, value in values.items()}
        data.append([_export_safe(values.get(header)) for header in headers])
    return headers, data


def _display_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return None
    return value


async def export_catalog_rows(
    db: AsyncSession,
    module: ImportModule,
    ids: list[int] | None,
    filters: dict[str, Any] | None = None,
    fmt: str = "xlsx",
) -> bytes:
    """Serialize the catalog's visible rows into one Data-sheet workbook."""
    if fmt not in ("xlsx", "csv"):
        raise ValidationFailed("Unsupported export format.", {"format": "Unsupported format"})
    model, query = _catalog_query(db, module, filters or {})
    if ids:
        query = query.where(model.id.in_(ids))
    rows = (
        (await db.execute(query.order_by(model.id).limit(10_000)))
        .scalars()
        .all()
    )
    if module.key == "componentTabs":
        from app.modules.master_data.models import TradeDirection

        labels: dict[int, str] = {}
        direction_ids = {row.trade_direction_id for row in rows if row.trade_direction_id}
        if direction_ids:
            found = (
                await db.execute(
                    select(TradeDirection.id, TradeDirection.name, TradeDirection.code)
                    .where(TradeDirection.id.in_(direction_ids))
                )
            ).all()
            labels = {int(row[0]): str(row[1] or row[2]) for row in found}
        for row in rows:
            row._trade_direction_label = labels.get(int(row.trade_direction_id), "") if row.trade_direction_id else ""
    headers, data = _catalog_table(module, rows)
    if fmt == "csv":
        return _csv_workbook(headers, data)
    return _sheet_workbook(module, headers, data, "Data")


def _sheet_workbook(module: ImportModule, headers: list[str], data: list[list[Any]], sheet_title: str) -> bytes:
    # The Instructions sheet makes every export re-importable (the parser reads
    # TEMPLATE_VERSION from it before any row is considered).
    workbook = Workbook()
    instructions = workbook.active
    assert instructions is not None
    instructions.title = "Instructions"
    instructions["A1"] = "TEMPLATE_VERSION"
    instructions["B1"] = module.template_version
    sheet = workbook.create_sheet(sheet_title[:31])
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = templates.HEADER_FILL
    sheet.freeze_panes = "A2"
    for values in data:
        sheet.append(list(values))
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


# --- Templates ----------------------------------------------------------------


async def build_template(db, module: ImportModule) -> bytes:
    """Configuration templates: a Data sheet (catalog) or five sheets (versions)."""
    workbook = Workbook()
    instructions = workbook.active
    assert instructions is not None
    instructions.title = "Instructions"
    instructions.column_dimensions["A"].width = 28
    instructions.column_dimensions["B"].width = 90
    instructions["A1"] = "TEMPLATE_VERSION"
    instructions["B1"] = module.template_version
    instructions["A2"] = "Module"
    instructions["B2"] = module.name
    instructions["A3"] = "Date format"
    instructions["B3"] = templates.DATE_INSTRUCTION
    instructions["A4"] = "Options"
    instructions["B4"] = "Separate select options with a semicolon ( ; )."
    instructions["A5"] = "Create only"
    instructions["B5"] = (
        "Imports never edit existing records: a code that already exists is skipped."
        if module.pipeline == "component_config"
        else "An imported configuration version always becomes a new Draft; published versions are never changed."
    )
    for row in instructions.iter_rows():
        row[0].font = templates.TITLE_FONT

    sheet_names: list[tuple[str, list[str]]]
    if module.pipeline == "config_versions":
        sheet_names = list(_VERSION_SHEET_HEADERS.items())
    else:
        sheet_names = [("Data", [column.key for column in module.columns])]
    for sheet_name, headers in sheet_names:
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(headers)
        for index, header in enumerate(headers, start=1):
            cell = sheet.cell(row=1, column=index)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = templates.HEADER_FILL
            sheet.column_dimensions[templates.get_column_letter(index)].width = max(14, min(34, len(header) + 6))
        sheet.freeze_panes = "A2"

    if module.key == "componentTabs":
        from app.modules.master_data.models import TradeDirection

        rows = (
            (await db.execute(select(TradeDirection).where(TradeDirection.deleted_at.is_(None))))
            .scalars()
            .all()
        )
        names = sorted({str(row.name) for row in rows if row.name})
        if names:
            reference = workbook.create_sheet("Trade_Directions")
            reference.append(["name"])
            for name in names:
                reference.append([name])

    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


# --- Version workbook parsing / validation ------------------------------------


def parse_version_workbook(content: bytes, module: ImportModule) -> dict[str, Any]:
    """Read the five-sheet version template into a JSON-safe structure."""
    _safe_archive(content)
    workbook = None
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        if "Instructions" not in workbook.sheetnames:
            raise ValidationFailed(
                "This file is not one of our import templates (Instructions sheet is required).",
                {"file": "Not a template"},
            )
        stored_version = workbook["Instructions"]["B1"].value
        if stored_version is None or int(stored_version) != module.template_version:
            raise ValidationFailed(
                "The template version does not match. Download a fresh template.",
                {"file": "Outdated template"},
            )
        missing = [name for name in _VERSION_SHEET_HEADERS if name not in workbook.sheetnames]
        if missing:
            raise ValidationFailed(
                f"The workbook is missing sheet(s): {', '.join(missing)}.",
                {"file": "Missing sheets"},
            )
        return {
            name: _sheet_rows(workbook[name], headers)
            for name, headers in _VERSION_SHEET_HEADERS.items()
        }
    except ValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001 - openpyxl raises many shapes here
        raise ValidationFailed("The workbook could not be read.", {"file": "Invalid workbook"}) from exc
    finally:
        if workbook is not None:
            workbook.close()


def _sheet_rows(sheet, expected_headers: list[str]) -> list[dict[str, Any]]:
    """Dicts per data row, keys bound to the exact template headers."""
    rows = sheet.iter_rows(values_only=False)
    header_row = next(rows, None)
    if header_row is None:
        raise ValidationFailed(
            f"The {sheet.title} sheet has no header row.", {"file": "Empty template"},
        )
    headers = [cell.value for cell in header_row]
    if headers != expected_headers:
        raise ValidationFailed(
            f"The {sheet.title} columns must match the template exactly, in order.",
            {"file": "Headers do not match"},
        )
    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        if all(cell.value in (None, "") for cell in row):
            continue
        if len(parsed) >= MAX_IMPORT_ROWS:
            raise ValidationFailed(
                f"A sheet may hold at most {MAX_IMPORT_ROWS} data rows.",
                {"file": "Too many rows"},
            )
        for cell in row:
            if cell.data_type == "f":
                raise ValidationFailed(
                    f"Row {index} ({sheet.title}): formulas are not allowed.",
                    {"row": index, "sheet": sheet.title},
                )
        parsed.append({"_excelRow": index, **{
            header: (ILLEGAL_CHARACTERS_RE.sub("", cell.value) if isinstance(cell.value, str) else cell.value)
            for header, cell in zip(expected_headers, row, strict=True)
        }})
    return parsed


def _duplicate_codes(rows: list[dict[str, Any]], key: str) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for row in rows:
        value = _normalize(row.get(key))
        if not value:
            continue
        if value in seen:
            dupes.add(value)
        else:
            seen.add(value)
    return dupes


def _preview_item(row: dict[str, Any], identifier: str) -> dict[str, Any]:
    return {
        "excelRow": row["_excelRow"],
        "identifier": identifier,
        "action": "ERROR",
        "status": "INVALID",
        "errors": [],
        "data": {},
    }


async def _existing_record(db: AsyncSession, sheet_name: str, code: str) -> bool:
    value = _normalize(code)
    if not value:
        return False
    return (
        await db.execute(select(_catalog_model(sheet_name)).where(_catalog_model(sheet_name).code == value))
    ).scalars().first() is not None


async def validate_version_rows(db, parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Previews for every sheet plus cross-sheet reference resolution."""
    from app.modules.master_data.component_config import DATA_TYPES, RENDER_MODES, SELECT_DATA_TYPES
    from app.modules.master_data.models import TradeDirection

    previews: list[dict[str, Any]] = []

    # Version sheet: exactly one row; the draft's change note is required and
    # must not collide with another *draft* (published notes are history).
    version_rows = parsed["Version"]
    for row in version_rows:
        item = _preview_item(row, "")
        errors: list[str] = []
        note = str(row.get("changeNote") or "").strip()
        if not note:
            errors.append("changeNote: Required")
        scope = str(row.get("scope") or "").strip().upper()
        if scope and scope != "GLOBAL":
            errors.append("scope: Only GLOBAL versions can be imported.")
        version_no = row.get("versionNo")
        if version_no not in (None, ""):
            try:
                int(version_no)
            except (TypeError, ValueError):
                errors.append("versionNo: Enter a whole number.")
        if note:
            from app.modules.master_data.models import ConfigurationVersion

            clash = (
                await db.execute(
                    select(ConfigurationVersion.id).where(
                        ConfigurationVersion.status == "DRAFT",
                        ConfigurationVersion.change_note == note,
                    )
                )
            ).scalars().first()
            if clash is not None:
                errors.append("changeNote: A draft with this name already exists.")
        if errors:
            item["errors"] = errors
        else:
            item["action"] = "CREATE"
            item["status"] = "VALID"
        previews.append(item)
    if not version_rows:
        previews.append({
            "excelRow": 0, "identifier": "Version", "action": "ERROR", "status": "INVALID",
            "errors": ["The Version sheet must hold exactly one row."], "data": {},
        })

    workbook_codes: dict[str, list[str]] = {}
    for sheet_name, code_key, label_key in (
        ("Attributes", "code", "label"),
        ("Groups", "code", "name"),
        ("Tabs", "code", "name"),
    ):
        rows = parsed[sheet_name]
        dupes = _duplicate_codes(rows, code_key)
        workbook_codes[sheet_name] = [_normalize(row.get(code_key)) for row in rows if _normalize(row.get(code_key))]
        for row in rows:
            code = _normalize(row.get(code_key)) or _normalize(row.get(label_key))
            item = _preview_item(row, code)
            errors: list[str] = []
            if not code:
                errors.append(f"{code_key}: Required")
            if not str(row.get(label_key) or "").strip():
                errors.append(f"{label_key}: Required")
            if code and code in dupes:
                errors.append(f"{code_key}: Duplicate row within the workbook.")
            if sheet_name == "Attributes":
                data_type = str(row.get("dataType") or "").strip().lower()
                if data_type not in DATA_TYPES:
                    errors.append("dataType: Unsupported")
                elif data_type in SELECT_DATA_TYPES and not _split_options(str(row.get("options") or "")):
                    errors.append("options: A select attribute needs at least one option.")
                elif data_type not in SELECT_DATA_TYPES and str(row.get("options") or "").strip():
                    errors.append("options: Only for select types")
                else:
                    options = _split_options(str(row.get("options") or ""))
                    if len(options) != len(set(options)):
                        errors.append("options: Duplicate option")
            elif sheet_name == "Groups":
                render_mode = str(row.get("renderMode") or "table").strip().lower()
                if render_mode not in RENDER_MODES:
                    errors.append("renderMode: Unsupported")
            else:  # Tabs
                ref = str(row.get("tradeDirection") or "").strip()
                if ref:
                    direction = (
                        await db.execute(
                            select(TradeDirection).where(
                                TradeDirection.deleted_at.is_(None),
                                or_(TradeDirection.name == ref, TradeDirection.code == ref),
                            )
                        )
                    ).scalars().first()
                    if direction is None:
                        errors.append("tradeDirection: No matching Trade Direction")
            if errors:
                item["errors"] = errors
            else:
                item["action"] = "SKIP" if await _existing_record(db, sheet_name, code) else "CREATE"
                item["status"] = "VALID"
            previews.append(item)

    # Relationships: a row with an attributeCode is a group→attribute membership,
    # otherwise it is a tab→group assignment. References may be satisfied by the
    # workbook itself (the import creates them first) or by the live catalog.
    group_codes_known = set(workbook_codes["Groups"]) | await _codes_in_db(db, "Groups")
    attribute_codes_known = set(workbook_codes["Attributes"]) | await _codes_in_db(db, "Attributes")
    membership_pairs: set[tuple[str, str]] = set()
    tab_group_pairs: set[tuple[str, str]] = set()
    tab_codes_known = set(workbook_codes["Tabs"]) | await _codes_in_db(db, "Tabs")
    for row in parsed["Relationships"]:
        tab_code = _normalize(row.get("tabCode"))
        group_code = _normalize(row.get("groupCode"))
        attribute_code = _normalize(row.get("attributeCode"))
        item = _preview_item(row, f"{tab_code} / {group_code} / {attribute_code}".strip(" /"))
        errors: list[str] = []
        if not group_code:
            errors.append("groupCode: Required")
        elif group_code not in group_codes_known:
            errors.append("groupCode: Unknown group")
        if attribute_code:
            if attribute_code not in attribute_codes_known:
                errors.append("attributeCode: Unknown attribute")
        elif tab_code not in tab_codes_known:
            errors.append("tabCode: Unknown tab")
        if not errors and attribute_code:
            if (group_code, attribute_code) in membership_pairs:
                errors.append("Duplicate relationship within the workbook.")
            membership_pairs.add((group_code, attribute_code))
        elif not errors:
            if (tab_code, group_code) in tab_group_pairs:
                errors.append("Duplicate relationship within the workbook.")
            tab_group_pairs.add((tab_code, group_code))
        if errors:
            item["errors"] = errors
        else:
            item["action"] = "CREATE"
            item["status"] = "VALID"
        previews.append(item)
    return previews


async def _codes_in_db(db, sheet_name: str) -> set[str]:
    model = _catalog_model(sheet_name)
    rows = (await db.execute(select(model.code))).scalars().all()
    return {_normalize(value) for value in rows if value}


# --- Version commit -----------------------------------------------------------


async def confirm_version(db: AsyncSession, context: RequestContext, import_session) -> dict[str, int]:
    """Create the catalog records, then a new Draft version. One transaction."""
    from sqlalchemy import text as sql_text
    from sqlalchemy.exc import IntegrityError

    from app.modules.master_data.config_snapshot import (
        attribute_entry,
        build_snapshot,
        group_entry,
        tab_entry,
    )
    from app.modules.master_data.config_versions import (
        PUBLISH_LOCK_KEY,
        _next_version_no,
        snapshot_hash,
    )
    from app.modules.master_data.models import (
        ComponentGroupAttribute,
        ComponentTabGroup,
        ConfigurationVersion,
    )

    parsed = import_session.rows[0]
    previews = await validate_version_rows(db, parsed)
    summary = preview_summary(previews)
    if any(item["action"] == "ERROR" for item in previews):
        raise ValidationFailed(
            "The workbook no longer validates cleanly. Download the error report.",
            {"token": "Validation failed at commit time."},
        )

    # Serialize version allocation with the publisher (shared advisory lock).
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        await db.execute(sql_text("SELECT pg_advisory_xact_lock(:key)"), {"key": PUBLISH_LOCK_KEY})

    next_order = {"Attributes": 0, "Groups": 0, "Tabs": 0}

    async def ensure_records(sheet_name: str, build, parsed_rows):
        """Workbook row → existing record or a new one; keyed by normalized code."""
        model = _catalog_model(sheet_name)
        result: dict[str, Any] = {}

        async def keyed(row: dict[str, Any]):
            return _normalize(row.get("code") or row.get("name") or row.get("label"))

        for row in parsed_rows:
            code = await keyed(row)
            if not code:
                continue
            existing = (
                await db.execute(select(model).where(model.code == code))
            ).scalars().first()
            if existing is None:
                entity = await build(row)
                if not int(entity.display_order or 0):
                    entity.display_order = (next_order[sheet_name]) + 1
                    next_order[sheet_name] = entity.display_order
                db.add(entity)
                await db.flush()
                result[code] = entity
            else:
                result[code] = existing
        return result

    async def _attr(row):
        return _build_attribute({
            "label": row.get("label"), "code": row.get("code"),
            "dataType": row.get("dataType"), "options": row.get("options"),
        })

    attributes = await ensure_records("Attributes", _attr, parsed["Attributes"])
    async def _group(row):
        return _build_group(row)

    groups = await ensure_records("Groups", _group, parsed["Groups"])

    async def _tab(row):
        return await _build_tab(db, row)

    tabs = await ensure_records("Tabs", _tab, parsed["Tabs"])

    # Memberships / assignments: duplicates in the catalog are reused, not copied.
    seen_group_attr: dict[tuple[int, int], int] = {}
    seen_tab_group: dict[tuple[int, int], int] = {}
    for rel in parsed["Relationships"]:
        group_code = _normalize(rel.get("groupCode"))
        attribute_code = _normalize(rel.get("attributeCode"))
        group = groups.get(group_code)
        if group is None:
            raise ValidationFailed(f"Relationship references unknown group {group_code!r}.", {"groupCode": "Unknown"})
        if attribute_code:
            attribute = attributes.get(attribute_code)
            if attribute is None:
                raise ValidationFailed(f"Relationship references unknown attribute {attribute_code!r}.", {"attributeCode": "Unknown"})
            pair = (int(group.id), int(attribute.id))
            membership = seen_group_attr.get(pair)
            if membership is None:
                existing = (
                    await db.execute(
                        select(ComponentGroupAttribute)
                        .where(
                            ComponentGroupAttribute.group_id == pair[0],
                            ComponentGroupAttribute.attribute_id == pair[1],
                        )
                    )
                ).scalars().first()
                membership = existing.id if existing is not None else None
                if membership is None:
                    order = rel.get("displayOrder")
                    link = ComponentGroupAttribute(
                        group_id=pair[0],
                        attribute_id=pair[1],
                        is_required=_rel_bool(rel.get("isRequired")),
                        display_order=int(order) if order not in (None, "") else len(seen_group_attr) * 10 + 10,
                        status="ACTIVE",
                    )
                    db.add(link)
                    await db.flush()
                    membership = int(link.id)
                seen_group_attr[pair] = membership

    memberships_by_group: dict[int, list[tuple[dict[str, Any], Any]]] = {}
    for rel in parsed["Relationships"]:
        attribute_code = _normalize(rel.get("attributeCode"))
        if attribute_code:
            group = groups.get(_normalize(rel.get("groupCode")))
            attribute = attributes.get(attribute_code)
            membership = (
                await db.execute(
                    select(ComponentGroupAttribute)
                    .where(
                        ComponentGroupAttribute.group_id == group.id,
                        ComponentGroupAttribute.attribute_id == attribute.id,
                    )
                )
            ).scalars().first()
            memberships_by_group.setdefault(int(group.id), []).append((
                {"is_required": membership.is_required if membership else _rel_bool(rel.get("isRequired")),
                 "is_visible": membership.is_visible if membership else True,
                 "display_order": membership.display_order if membership else 0},
                attribute,
            ))

    groups_by_tab: dict[int, list[dict[str, Any]]] = {}
    for rel in parsed["Relationships"]:
        attribute_code = _normalize(rel.get("attributeCode"))
        if attribute_code:
            continue
        tab = tabs.get(_normalize(rel.get("tabCode")))
        group = groups.get(_normalize(rel.get("groupCode")))
        if tab is None:
            raise ValidationFailed(f"Relationship references unknown tab {rel.get('tabCode')!r}.", {"tabCode": "Unknown"})
        pair = (int(tab.id), int(group.id))
        link = seen_tab_group.get(pair)
        if link is None:
            existing = (
                await db.execute(
                    select(ComponentTabGroup)
                    .where(ComponentTabGroup.tab_id == pair[0], ComponentTabGroup.group_id == pair[1])
                )
            ).scalars().first()
            link = existing.id if existing is not None else None
            if link is None:
                order = rel.get("displayOrder")
                assignment = ComponentTabGroup(
                    tab_id=pair[0],
                    group_id=pair[1],
                    display_order=int(order) if order not in (None, "") else len(seen_tab_group) * 10 + 10,
                    status="ACTIVE",
                )
                db.add(assignment)
                await db.flush()
                link = int(assignment.id)
            seen_tab_group[pair] = link
        attribute_entries = [
            attribute_entry(
                {
                    "id": attribute.id, "code": attribute.code, "label": attribute.label,
                    "label_km": attribute.label_km, "data_type": attribute.data_type,
                    "input_type": attribute.input_type, "reference_type": attribute.reference_type,
                    "is_required": attribute.is_required, "default_value": attribute.default_value,
                    "placeholder": attribute.placeholder, "options": attribute.options,
                    "validation_rules": attribute.validation_rules,
                },
                membership,
            )
            for membership, attribute in memberships_by_group.get(int(group.id), [])
        ]
        groups_by_tab.setdefault(int(tab.id), []).append(
            group_entry(
                {"id": group.id, "code": group.code, "name": group.name,
                 "name_km": group.name_km, "render_mode": group.render_mode},
                attribute_entries,
                rel.get("displayOrder") or group.display_order,
                None,
            )
        )

    note = str(parsed["Version"][0].get("changeNote") or "").strip()
    version_no = await _next_version_no(db)
    version = ConfigurationVersion(
        version_no=version_no,
        scope="GLOBAL",
        status="DRAFT",
        origin="IMPORT",
        change_note=note or None,
        config_snapshot={},
        snapshot_schema_version=1,
    )
    db.add(version)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationFailed(
            "The version number was just taken by another user; try again.",
            {"versionNo": "Conflict"},
        ) from exc

    # The draft snapshot records the imported shape (ids assigned above); the
    # version stays DRAFT — publishing stays an explicit, permissioned action.
    version.config_snapshot = build_snapshot([
        tab_entry(
            {"id": tab.id, "code": tab.code, "name": tab.name, "trade_direction_id": tab.trade_direction_id},
            groups_by_tab.get(int(tab.id), []),
            tab.display_order,
        )
        for tab in tabs.values()
    ])
    version.snapshot_schema_version = 1
    version.content_hash = snapshot_hash(version.config_snapshot)
    return summary


def _rel_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


# --- Version export -----------------------------------------------------------


async def export_version_workbook(db, version) -> bytes:
    """The round-trip workbook for one stored version (all five sheets)."""
    from app.modules.master_data.component_config import _option_texts
    from app.modules.master_data.config_versions import trade_direction_names

    snapshot = version.config_snapshot or {}
    directions = await trade_direction_names(db, snapshot)

    version_rows = [[
        int(version.version_no), _export_safe(version.change_note), version.scope,
    ]]
    attribute_rows: list[list[Any]] = []
    group_rows: list[list[Any]] = []
    tab_rows: list[list[Any]] = []
    relation_rows: list[list[Any]] = []
    seen_attributes: set[str] = set()
    seen_groups: set[str] = set()
    for tab in snapshot.get("tabs") or []:
        tab_rows.append([
            _export_safe(tab.get("code")),
            _export_safe(tab.get("name")),
            "",
            _export_safe(directions.get(str(tab.get("tradeDirectionId") or ""), "")),
            int(tab.get("displayOrder") or 0),
        ])
        for group in tab.get("groups") or []:
            relation_rows.append([
                tab.get("code"), group.get("code"), "", int(group.get("displayOrder") or 0), "",
            ])
            group_code = _normalize(group.get("code"))
            if group_code and group_code not in seen_groups:
                seen_groups.add(group_code)
                group_rows.append([
                    group.get("code"), group.get("name"), group.get("nameKm") or "",
                    "", group.get("renderMode") or "table", int(group.get("displayOrder") or 0),
                ])
            for attribute in group.get("attributes") or []:
                code = str(attribute.get("code") or "")
                relation_rows.append([
                    tab.get("code"), group.get("code"), code,
                    int(attribute.get("displayOrder") or 0),
                    "TRUE" if attribute.get("isRequired") else "FALSE",
                ])
                if code not in seen_attributes:
                    seen_attributes.add(code)
                    attribute_rows.append([
                        _export_safe(attribute.get("label")),
                        code,
                        attribute.get("dataType"),
                        _export_safe("; ".join(_option_texts(attribute.get("options") or []))),
                    ])
    headers_by_sheet = dict(_VERSION_SHEET_HEADERS)
    rows = {
        "Version": version_rows,
        "Attributes": attribute_rows,
        "Groups": group_rows,
        "Tabs": tab_rows,
        "Relationships": relation_rows,
    }
    workbook = Workbook()
    instructions = workbook.active
    assert instructions is not None
    instructions.title = "Instructions"
    instructions["A1"] = "TEMPLATE_VERSION"
    instructions["B1"] = 1
    for sheet_name, headers in headers_by_sheet.items():
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = templates.HEADER_FILL
        for row in rows[sheet_name]:
            sheet.append(list(row))
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def export_versions(
    db: AsyncSession,
    module: ImportModule,
    ids: list[int] | None,
    filters: dict[str, Any] | None = None,
    fmt: str = "xlsx",
) -> bytes:
    """One id: the full snapshot workbook for that version. None: the version list."""
    from app.modules.master_data.models import ConfigurationVersion

    if fmt not in ("xlsx", "csv"):
        raise ValidationFailed("Unsupported export format.", {"format": "Unsupported format"})
    if ids:
        if len(ids) != 1:
            raise ValidationFailed("Export one configuration version at a time.", {"ids": "Single version only"})
        version = await db.get(ConfigurationVersion, int(ids[0]))
        if version is None:
            raise NotFound("Configuration version not found.")
        return await export_version_workbook(db, version)
    query = select(ConfigurationVersion)
    status = str((filters or {}).get("status") or "").strip().upper()
    if status and status != "ALL":
        query = query.where(ConfigurationVersion.status == status)
    needle = str((filters or {}).get("search") or "").strip()
    if needle:
        from sqlalchemy import String, cast

        query = query.where(
            or_(
                ConfigurationVersion.change_note.ilike(f"%{needle}%"),
                cast(ConfigurationVersion.version_no, String).ilike(f"%{needle}%"),
            )
        )
    rows = (await db.execute(query.order_by(ConfigurationVersion.version_no.desc()))).scalars().all()
    data = [
        [
            int(version.version_no),
            version.scope,
            version.status,
            version.origin,
            _export_safe(version.change_note),
            version.published_at.date().isoformat() if version.published_at else None,
        ]
        for version in rows
    ]
    headers = list(_VERSION_LIST_HEADERS)
    if fmt == "csv":
        return _csv_workbook(headers, data)
    return _sheet_workbook(module, headers, data, "Data")


async def export_versions_count(db: AsyncSession, filters: dict[str, Any] | None = None) -> int:
    from app.modules.master_data.models import ConfigurationVersion

    query = select(func.count()).select_from(ConfigurationVersion)
    status = str((filters or {}).get("status") or "").strip().upper()
    if status and status != "ALL":
        query = query.where(ConfigurationVersion.status == status)
    return int((await db.execute(query)).scalar() or 0)
