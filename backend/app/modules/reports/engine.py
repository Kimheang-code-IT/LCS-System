"""Central registry and execution path for on-demand reports.

A report page no longer calls a raw aggregation endpoint on load. It posts its
filters here, one definition per report supplies the permission it needs and
the calculation it runs, and every result comes back in the same envelope:
``meta`` (what ran, when, over which period, how many rows) plus the report's
own payload. Report-specific accounting lives in ``ledger_reports.py``.

Deliberate limits:

* No caching. A financial report must not answer with rows generated before the
  last posting; each generation reads the ledger as it is now and stamps
  ``generatedAt`` so the SPA can say how fresh it is.
* No in-process job queue. An export streams from a server-side cursor instead;
  if a report ever outgrows one request, move ``run`` behind a task row rather
  than growing this module.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import AccessDenied, NotFound, ValidationFailed
from app.modules.reports import csv_export, ledger_reports
from app.modules.reports.schemas import ReportFilters


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    title_key: str
    permission: str
    #: ``(key, csv header)`` in export order; the request may select a subset.
    columns: tuple[tuple[str, str], ...]
    run: Callable[[AsyncSession, Any], Awaitable[dict]]
    export: Callable[[AsyncSession, Any, tuple[tuple[str, str], ...]], AsyncIterator[list[object]]]


REPORTS: dict[str, ReportDefinition] = {
    definition.key: definition
    for definition in (
        ReportDefinition(
            key="trial-balance",
            title="Trial Balance",
            title_key="freight.reportCatalog.reports.trial-balance.title",
            permission="reports.trial_balance.view",
            columns=ledger_reports.TRIAL_BALANCE_COLUMNS,
            run=ledger_reports.trial_balance,
            export=ledger_reports.export_trial_balance,
        ),
        ReportDefinition(
            key="general-ledger",
            title="General Ledger",
            title_key="freight.reportCatalog.reports.general-ledger.title",
            permission="reports.general_ledger.view",
            columns=ledger_reports.GENERAL_LEDGER_COLUMNS,
            run=ledger_reports.general_ledger,
            export=ledger_reports.export_general_ledger,
        ),
    )
}


def definition_for(key: str) -> ReportDefinition:
    definition = REPORTS.get(key)
    if definition is None:  # pragma: no cover - programming error, not user input
        raise KeyError(f"Unknown report: {key}")
    return definition


def permission_for(key: str) -> str:
    return definition_for(key).permission


def _guard(context: RequestContext, definition: ReportDefinition) -> None:
    # Defence in depth: routes already guard on the same permission, but the
    # registry is also reachable from a future background executor.
    if not (context.has_permission(definition.permission) or context.has_permission("report.read")):
        raise AccessDenied()


def _selected_columns(
    definition: ReportDefinition, requested: list[str] | None
) -> tuple[tuple[str, str], ...]:
    """The columns an export writes, in report order, restricted to the request."""
    if not requested:
        return definition.columns
    known = dict(definition.columns)
    unknown = [field for field in requested if field not in known]
    if unknown:
        raise ValidationFailed(
            "Unknown export column.",
            {"fields": f"Unknown column(s): {', '.join(sorted(unknown))}."},
        )
    wanted = set(requested)
    return tuple(column for column in definition.columns if column[0] in wanted)


async def generate(
    session: AsyncSession,
    context: RequestContext,
    key: str,
    filters: ReportFilters,
) -> dict:
    """Run one registered report and wrap its payload in the report envelope."""
    definition = REPORTS.get(key)
    if definition is None:
        raise NotFound("Unknown report.")
    _guard(context, definition)

    result = await definition.run(session, filters)
    total = int(result.pop("total", len(result.get("items", []))))
    warnings = result.pop("warnings", [])
    result["meta"] = {
        "reportKey": definition.key,
        "title": definition.title,
        "titleKey": definition.title_key,
        "generatedAt": datetime.now(UTC),
        "page": filters.page,
        "pageSize": filters.pageSize,
        "total": total,
        "filters": {
            **filters.model_dump(mode="json", exclude={"page", "pageSize"}),
            **result.pop("scope", {}),
        },
        "warnings": warnings,
    }
    return result


def export_csv(
    session: AsyncSession,
    context: RequestContext,
    key: str,
    filters: ReportFilters,
) -> AsyncIterator[str]:
    """Every matching row as CSV lines, streamed one row at a time.

    The same filters, permission and calculations as ``generate``: the footer
    totals are the totals the report itself computes, so an exported file can be
    reconciled against the screen it came from.

    Validation (permission, column selection) runs here, not inside the
    generator: once a StreamingResponse has started, a refusal can no longer
    become a ``403``/``422`` response.
    """
    definition = REPORTS.get(key)
    if definition is None:
        raise NotFound("Unknown report.")
    _guard(context, definition)
    columns = _selected_columns(definition, getattr(filters, "fields", None))
    return _encode(definition, session, filters, columns)


async def _encode(
    definition: ReportDefinition,
    session: AsyncSession,
    filters: ReportFilters,
    columns: tuple[tuple[str, str], ...],
) -> AsyncIterator[str]:
    async for row in definition.export(session, filters, columns):
        yield csv_export.row_to_csv(row)


def export_filename(key: str) -> str:
    return f"{key}-{datetime.now(UTC).date().isoformat()}.csv"
