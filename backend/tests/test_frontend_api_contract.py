"""Contract tests: every API path/verb the frontend calls must exist on the backend.

The frontend is a static SPA whose HTTP layer is centralised in
``app/utils/constants`` and ``app/utils/api/freight-remote.ts``. These tests
statically read those sources (plus any raw ``/api/v1/...`` literals anywhere in
``frontend/app``) and assert that the FastAPI app exposes a matching route. That
catches page/endpoint drift without booting a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.main import app

FRONTEND_APP = Path(__file__).resolve().parents[2] / "frontend" / "app"
API_V1_CONSTANTS = FRONTEND_APP / "utils" / "constants" / "api-v1-endpoints.ts"
API_CONSTANTS = FRONTEND_APP / "utils" / "constants" / "api-endpoints.ts"
FREIGHT_REMOTE = FRONTEND_APP / "utils" / "api" / "freight-remote.ts"
MODULE_CONFIGS = (
    FRONTEND_APP / "config" / "freight-modules.ts",
    FRONTEND_APP / "config" / "lcs-reference-modules.ts",
)

_CONST_ENTRY = re.compile(
    r"^\s*([A-Z][A-Z0-9_]*):\s*(?:\([^)]*\)\s*=>\s*)?([`'\"])([^`'\"]*)\2",
    re.MULTILINE,
)
_SOME_PARAM = re.compile(r"\$\{[^}]*\}|\{[^}]*\}")
_STRING_LITERAL = re.compile(r"([`'\"])(/api/v1/[^`'\"]*)\1")
_REMOTE_ENTRY = re.compile(r"\n  (\w+):\s*(.*?)(?=\n  \w+:|\n\})", re.DOTALL)

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

# Collections whose backend resource path differs from ``/api/v1/<collection>``.
# ``None`` means the collection is rendered from bespoke endpoints (reports).
_PAGE_COLLECTION_PATHS: dict[str, str | None] = {
    "quotations": "/api/v1/quotations",
    "jobs": "/api/v1/service-orders",
    "jobCharges": "/api/v1/service-charges",
    "debitNotes": "/api/v1/financial-documents",
    "customerPayments": "/api/v1/financial-documents",
    "supplierCosts": "/api/v1/financial-documents",
    "supplierPayments": "/api/v1/financial-documents",
    "journals": "/api/v1/journal-entries",
    "auditLogs": "/api/v1/audit-events",
    "receivables": "/api/v1/receivables",
    "payables": "/api/v1/payables",
    "profitability": "/api/v1/profitability",
    "documentSequences": "/api/v1/document-sequences",
    "accountingPeriods": "/api/v1/accounting-periods",
    "reports": None,
}


def _normalize(path: str) -> str:
    path = path.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return _SOME_PARAM.sub("{}", path) or "/"


def _strip_comments(text: str) -> str:
    """Drop comments so doc-blocks referencing ``/api/v1/...`` are not treated as calls."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def _backend_operations() -> set[tuple[str, str]]:
    operations: set[tuple[str, str]] = set()
    for path, item in app.openapi().get("paths", {}).items():
        for method in item:
            if method.lower() in HTTP_METHODS:
                operations.add((method.upper(), _normalize(path)))
    return operations


def _parse_constants(path: Path) -> list[str]:
    text = _strip_comments(path.read_text(encoding="utf-8"))
    return [match.group(3) for match in _CONST_ENTRY.finditer(text)]


def _raw_api_literals() -> list[str]:
    literals: list[str] = []
    for file in FRONTEND_APP.rglob("*"):
        if file.suffix not in {".ts", ".vue"}:
            continue
        text = _strip_comments(file.read_text(encoding="utf-8"))
        for match in _STRING_LITERAL.finditer(text):
            value = match.group(2)
            if "${" not in value:
                literals.append(value)
    return literals


def _page_collections() -> set[str]:
    collections: set[str] = set()
    for config in MODULE_CONFIGS:
        text = config.read_text(encoding="utf-8")
        collections.update(re.findall(r"collection:\s*'([^']+)'", text))
    return collections


def _page_collection_path(collection: str) -> str | None:
    if collection in _PAGE_COLLECTION_PATHS:
        return _PAGE_COLLECTION_PATHS[collection]
    return f"/api/v1/{collection}"


def _read_only_collections() -> set[str]:
    read_only: set[str] = set()
    for config in MODULE_CONFIGS:
        text = _strip_comments(config.read_text(encoding="utf-8"))
        parts = re.split(r"collection:\s*'([^']+)'", text)
        for index in range(1, len(parts), 2):
            name = parts[index]
            segment = parts[index + 1] if index + 1 < len(parts) else ""
            if re.search(r"readOnly:\s*true", segment):
                read_only.add(name)
    return read_only


def _remote_descriptors() -> dict[str, dict[str, object]]:
    """Parse ``REMOTE_ENDPOINTS`` into collection -> {base, item, bulk, upsert, read_only}."""
    text = _strip_comments(FREIGHT_REMOTE.read_text(encoding="utf-8"))
    body = text.split("export const REMOTE_ENDPOINTS", 1)[1]
    body = body.split("export const JOB_DERIVED_COLLECTIONS", 1)[0]

    descriptors: dict[str, dict[str, object]] = {}
    for key, chunk in _REMOTE_ENTRY.findall(body):
        reference = re.search(r"reference\(\s*'([^']+)'\s*\)", chunk)
        financial = re.search(r"financial\(\s*'([^']+)'\s*\)", chunk)
        path = re.search(r"path:\s*'([^']+)'", chunk)
        if reference:
            base = f"/api/v1/{reference.group(1)}"
        elif financial:
            base = "/api/v1/financial-documents"
        elif path:
            base = path.group(1)
        else:
            continue
        descriptors[key] = {
            "base": base,
            "item": bool(re.search(r"itemPath\s*:", chunk)),
            "bulk": bool(re.search(r"bulkDelete:\s*true", chunk)),
            "upsert": bool(re.search(r"upsertViaPost:\s*true", chunk)),
            "read_only": bool(re.search(r"readOnly:\s*true", chunk)),
        }
    return descriptors


def _frontend_paths() -> set[str]:
    paths = set(_parse_constants(API_V1_CONSTANTS))
    paths.update(_parse_constants(API_CONSTANTS))
    paths.update(_raw_api_literals())
    return {_normalize(path) for path in paths if path.startswith("/api/v1/")}


def test_every_referenced_frontend_path_exists_on_backend():
    backend_paths = {path for _, path in _backend_operations()}
    missing = sorted(path for path in _frontend_paths() if path not in backend_paths)
    assert not missing, "Frontend calls API paths the backend does not expose:\n" + "\n".join(missing)


def test_every_page_collection_has_a_list_endpoint():
    operations = _backend_operations()
    missing: list[str] = []
    for collection in sorted(_page_collections()):
        base = _page_collection_path(collection)
        if base is None:
            continue
        if ("GET", _normalize(base)) not in operations:
            missing.append(f"{collection} -> GET {base}")
    assert not missing, "Page collections without a backend list endpoint:\n" + "\n".join(missing)


def test_page_collection_write_verbs_are_exposed():
    """Mirror the freight store's generic create/save/remove logic per collection."""
    operations = _backend_operations()
    descriptors = _remote_descriptors()
    read_only = _read_only_collections()

    missing: list[str] = []
    for collection in sorted(_page_collections()):
        descriptor = descriptors.get(collection)
        if descriptor is None:
            # Bespoke collections (quotations, jobs, charges, finance) are covered
            # by the endpoint-constant contract above.
            continue
        base = _normalize(str(descriptor["base"]))
        if collection in read_only or descriptor["read_only"]:
            required = {("GET", base)}
        else:
            required = {("GET", base), ("POST", base)}
            if descriptor["item"] and not descriptor["upsert"]:
                required.add(("PUT", f"{base}/{{}}"))
            if descriptor["bulk"]:
                required.add(("DELETE", base))
            elif descriptor["item"]:
                required.add(("DELETE", f"{base}/{{}}"))
        missing.extend(
            f"{collection}: {method} {path}"
            for method, path in sorted(required)
            if (method, path) not in operations
        )
    assert not missing, "Page collections missing backend verbs:\n" + "\n".join(missing)



