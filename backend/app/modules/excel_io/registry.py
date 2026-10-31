"""The Import & Export module registry — an allowlist, not a table list.

Every entry is an explicit decision: a module is importable/exportable because it
is declared here, never because a table exists. Phase B supports the Master Data
reference collections; they all share one create/update pipeline
(``master_data.service``), so a workbook row goes through the same schema
validation, reference resolution, business checks and audit write as a normal
API create/update.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Boolean, Date, Numeric

#: Hard limits for one uploaded workbook (single-process backend; a Redis-backed
#: job queue would be the upgrade path if this ever needs multiple workers).
MAX_IMPORT_ROWS = 2_000
MAX_FILE_BYTES = 10 * 1024 * 1024
#: A real template stays well under 1 MB uncompressed. The caps bound what a
#: crafted archive can make openpyxl allocate on a 4 GB server.
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2_000
SESSION_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class ColumnSpec:
    """One template column. ``key`` is the stable, language-independent header."""

    key: str
    kind: str  # text | number | integer | date | boolean | enum | reference
    required: bool = False
    enum: tuple[str, ...] = ()
    updatable: bool = True
    example: str = ""


@dataclass(frozen=True)
class ImportModule:
    key: str  # the collection/API key, e.g. "businessParties"
    name: str  # English display name (frontend localizes its own labels)
    view_permission: str
    manage_permission: str
    template_version: int
    match_key: tuple[str, ...]
    columns: tuple[ColumnSpec, ...]
    import_enabled: bool = True
    export_enabled: bool = True
    #: Keys a Create-and-Update import may not change: match keys and identity
    #: columns stay out, so an import can never rename a stable business code.
    fixed_keys: tuple[str, ...] = ()

    def may_update(self, key: str) -> bool:
        return key not in self.fixed_keys and any(column.key == key and column.updatable for column in self.columns)

    def identifier(self, row: dict[str, Any]) -> str:
        return " / ".join(str(row.get(key) or "") for key in self.match_key).strip(" /")


def master_data_module(collection: str, name: str, match_key: tuple[str, ...], fixed: tuple[str, ...] = ()) -> ImportModule:
    """Derive one registry entry from the master-data Spec it reuses."""
    from app.modules.master_data import service as md

    spec = md.get_spec(collection)
    model = spec.model
    columns: list[ColumnSpec] = []
    for camel, attr in spec.fields.items():
        column = model.__table__.columns.get(attr)
        if camel in spec.refs:
            kind = "reference"
        elif camel in spec.enums:
            kind = "enum"
        elif column is None:
            kind = "text"
        elif isinstance(column.type, Boolean):
            kind = "boolean"
        elif isinstance(column.type, Date):
            kind = "date"
        elif isinstance(column.type, Numeric):
            kind = "number"
        else:
            kind = "text"
        columns.append(
            ColumnSpec(
                key=camel,
                kind=kind,
                required=camel in spec.required,
                enum=tuple(spec.enums.get(camel, ())),
                updatable=camel not in match_key + fixed,
            )
        )
    return ImportModule(
        key=collection,
        name=name,
        view_permission="master.reference.view",
        manage_permission="master.reference.manage",
        template_version=1,
        match_key=match_key,
        fixed_keys=fixed,
        columns=tuple(columns),
    )


REGISTRY: dict[str, ImportModule] = {}

#: (collection, display name, match keys, keys imports may never change).
_MASTER_ENTRIES = (
    ("businessParties", "Business Parties", ("partyCode",), ("partyCode",)),
    ("partyRoles", "Party Roles", ("code",), ()),
    ("placeRoles", "Place Roles", ("code",), ()),
    ("tradeDirections", "Trade Directions", ("code",), ()),
    ("containerTypes", "Container Types", ("code",), ()),
    ("transportTypes", "Transport Types", ("code",), ()),
    ("transportAssets", "Transport Assets", ("assetCode",), ("assetCode",)),
    ("transportAssetIdentityTypes", "Asset Identity Types", ("name",), ("name",)),
    ("capacityUnits", "Capacity Units", ("code",), ()),
    ("feeTypes", "Fee Types", ("code",), ("code",)),
    ("currencies", "Currencies", ("code",), ("code",)),
    ("documentTypes", "Document Types", ("code",), ("code", "accountingBehavior")),
)


def register_defaults() -> None:
    """Fill the registry (idempotent, so tests can reset and rebuild)."""
    for collection, name, match_key, fixed in _MASTER_ENTRIES:
        if collection not in REGISTRY:
            REGISTRY[collection] = master_data_module(collection, name, match_key, fixed)


register_defaults()
