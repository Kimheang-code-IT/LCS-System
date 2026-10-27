"""Backend-driven .xlsx templates.

Structure: ``Instructions`` (version + rules), ``Data`` (the columns an import
must match, with dropdowns for manageable reference lists) and ``Examples``
(sample rows). Headers are the stable API field keys, never localized, so the
backend's column matching cannot be confused by a translated workbook.

The Excel dropdowns are convenience only — the backend revalidates every value
against the database at import time.
"""

from __future__ import annotations

import io
from collections.abc import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.modules.excel_io.registry import ImportModule

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
REQUIRED_FONT = Font(color="FF0000", bold=True)
TITLE_FONT = Font(bold=True, size=12)

#: Reference lookups that stay small enough for an Excel dropdown.
_DROPDOWN_REF_TARGETS: dict[str, str] = {
    "party_role": "partyRoles",
    "place_role": "placeRoles",
    "trade_direction": "tradeDirections",
    "container_type": "containerTypes",
    "transport_type": "transportTypes",
    "fee_type": "feeTypes",
    "currency": "currencies",
    "document_type": "documentTypes",
}

DATE_INSTRUCTION = (
    "Dates use the format YYYY-MM-DD (for example 2026-03-01). Keep every "
    "identifier and code cell as text so leading zeros survive."
)


async def _ref_options(session, module: ImportModule) -> dict[str, tuple[str, list[str]]]:
    from sqlalchemy import select

    from app.modules.master_data import service as md
    from app.modules.master_data.models import (
        BusinessParty,
        ContainerType,
        DocumentType,
        FeeType,
        PartyRole,
        PlaceRole,
        TradeDirection,
        TransportType,
    )

    target_models = {
        "party_role": PartyRole,
        "place_role": PlaceRole,
        "trade_direction": TradeDirection,
        "container_type": ContainerType,
        "transport_type": TransportType,
        "fee_type": FeeType,
        "business_party": BusinessParty,
        "document_type": DocumentType,
    }
    options: dict[str, tuple[str, list[str]]] = {}
    for column in module.columns:
        if column.kind != "reference":
            continue
        ref = md.get_spec(module.key).refs.get(column.key)
        if ref is None or ref.target not in target_models:
            continue
        model = target_models[ref.target]
        rows = (
            (await session.execute(select(model).where(model.deleted_at.is_(None))))
            .scalars()
            .all()
        )
        names: list[str] = []
        for row in rows:
            names.append(str(getattr(row, "name", None) or getattr(row, "code", None) or ""))
        names = sorted({name for name in names if name})
        if 0 < len(names) <= 200:
            options[column.key] = (ref.target.replace("_", "-"), names)
    return options


async def build_template(session, module: ImportModule, examples: Iterable[dict[str, str]] = ()) -> bytes:
    """Return the .xlsx bytes for one module's import template."""
    ref_options = await _ref_options(session, module)
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
    instructions["B3"] = DATE_INSTRUCTION
    instructions["A4"] = "Required fields"
    instructions["B4"] = ", ".join(column.key for column in module.columns if column.required)
    instructions["A5"] = "Update rule"
    instructions["B5"] = (
        "Rows match existing records by: " + " + ".join(module.match_key) + ". "
        "Create Only never changes existing rows (duplicates are skipped); "
        "Create and Update changes only the columns an import may change; "
        "Validate Only writes nothing."
    )
    instructions["A6"] = "Formula warning"
    instructions["B6"] = (
        "Do not use formulas. A formula cell is rejected. Do not rename or reorder the"
        " header row."
    )
    for row in instructions.iter_rows():
        row[0].font = TITLE_FONT

    data = workbook.create_sheet("Data")
    headers = [column.key for column in module.columns]
    data.append(headers)
    for index, column in enumerate(module.columns, start=1):
        cell = data.cell(row=1, column=index)
        cell.font = REQUIRED_FONT if column.required else Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        data.column_dimensions[get_column_letter(index)].width = max(14, min(34, len(column.key) + 6))
    data.freeze_panes = "A2"
    data.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

    # Example rows give the operator one real-looking shape per kind.
    sample = workbook.create_sheet("Examples")
    sample.append(headers)
    for example in list(examples)[:3] or [dict.fromkeys(headers, "")]:
        sample.append([example.get(header, "") for header in headers])
    for row in sample.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(color="808080", italic=True)

    # Dropdowns for small reference lists; parties (potentially thousands) get a
    # reference sheet without a dropdown instead.
    for key, (sheet_name, values) in ref_options.items():
        index = module_column_index(module, key)
        if index is None:
            continue
        reference_sheet = workbook.create_sheet(_sheet_title(sheet_name))
        reference_sheet.append(["name"])
        for value in values:
            reference_sheet.append([value])
        if len(values) <= 200:
            letter = get_column_letter(index)
            validation = DataValidation(
                type="list",
                formula1=f"'{reference_sheet.title}'!$A$2:$A${len(values) + 1}",
                allow_blank=True,
            )
            validation.error = "Choose a value from the reference sheet."
            validation.errorTitle = "Unknown value"
            data.add_data_validation(validation)
            validation.add(f"{letter}2:{letter}5000")

    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _sheet_title(name: str) -> str:
    return name[:31].replace("_", " ").title().replace(" ", "_")


def module_column_index(module: ImportModule, key: str) -> int | None:
    for index, column in enumerate(module.columns, start=1):
        if column.key == key:
            return index
    return None
