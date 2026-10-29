"""Trial balance and general ledger calculations, and their CSV exports.

``engine.py`` owns the request plumbing; this module owns the accounting
arithmetic. Both reports read the same posted-ledger projection, sum the
``base_*`` columns in ``Decimal`` and never look at drafts or cancelled entries:
``ReportRepository`` filters ``JournalEntry.status == 'POSTED'`` in one place.

Opening balances are the movement before the report period, so a report that
starts mid-history still shows a complete position instead of a period-only
total that looks like a balance.

The exports reuse the same functions as the on-screen report — the totals in the
CSV footer are the totals the report returned, not a second calculation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailed
from app.modules.finance.models import AccountingPeriod
from app.modules.reports import csv_export
from app.modules.reports.repository import ReportRepository
from app.modules.reports.schemas import GeneralLedgerFilters, ReportFilters, TrialBalanceFilters

ZERO = Decimal("0")

TRIAL_BALANCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("accountCode", "Account Code"),
    ("accountName", "Account Name"),
    ("accountType", "Account Type"),
    ("openingDebit", "Opening Debit"),
    ("openingCredit", "Opening Credit"),
    ("periodDebit", "Period Debit"),
    ("periodCredit", "Period Credit"),
    ("closingDebit", "Closing Debit"),
    ("closingCredit", "Closing Credit"),
)
TRIAL_BALANCE_NUMERIC = frozenset(
    {"openingDebit", "openingCredit", "periodDebit", "periodCredit", "closingDebit", "closingCredit"}
)

GENERAL_LEDGER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("postingDate", "Posting Date"),
    ("accountCode", "Account Code"),
    ("accountName", "Account Name"),
    ("journalNo", "Voucher No"),
    ("voucherType", "Voucher Type"),
    ("sourceDocument", "Source Document"),
    ("party", "Party"),
    ("description", "Description"),
    ("currency", "Currency"),
    ("debit", "Debit"),
    ("credit", "Credit"),
    ("runningBalance", "Running Balance"),
)
GENERAL_LEDGER_NUMERIC = frozenset({"debit", "credit", "runningBalance"})


def _dec(value: object) -> Decimal:
    return Decimal(str(value or 0))


async def resolve_range(session: AsyncSession, filters: ReportFilters) -> tuple[date | None, date | None]:
    """The date range a report runs over.

    Explicit ``fromDate``/``toDate`` narrow the range; ``fiscalYear`` resolves it
    to that year's accounting periods, so a fiscal year starts where the ledger
    says it starts rather than on an assumed 1 January.
    """
    from_date, to_date = filters.fromDate, filters.toDate
    if from_date and to_date and from_date > to_date:
        raise ValidationFailed(
            "The report date range is invalid.",
            {"toDate": "The to date must be on or after the from date."},
        )
    if filters.fiscalYear is None:
        return from_date, to_date

    first, last = (
        await session.execute(
            select(
                func.min(AccountingPeriod.start_date),
                func.max(AccountingPeriod.end_date),
            ).where(AccountingPeriod.period_year == filters.fiscalYear)
        )
    ).one()
    if first is None or last is None:
        raise ValidationFailed(
            "The requested fiscal year has no accounting periods.",
            {"fiscalYear": f"No accounting periods are defined for {filters.fiscalYear}."},
        )
    return (
        max(from_date, first) if from_date else first,
        min(to_date, last) if to_date else last,
    )


def _side(net: Decimal) -> tuple[Decimal, Decimal]:
    """A signed balance as its debit or credit presentation."""
    return (net, ZERO) if net >= ZERO else (ZERO, -net)


def _trial_balance_totals(
    items: list[dict],
) -> tuple[dict[str, Decimal], bool, Decimal, list[str]]:
    """Sum the six money columns and decide whether the control passes."""
    totals = dict.fromkeys(
        ("openingDebit", "openingCredit", "periodDebit", "periodCredit", "closingDebit", "closingCredit"),
        ZERO,
    )
    for item in items:
        for key in totals:
            totals[key] += item[key]

    # The control: both sides of the period movement and both sides of the
    # closing position must agree. A difference is reported, never hidden.
    imbalance = totals["closingDebit"] - totals["closingCredit"]
    period_imbalance = totals["periodDebit"] - totals["periodCredit"]
    balanced = imbalance == ZERO and period_imbalance == ZERO
    warnings = [] if balanced else [
        "Trial balance does not balance: period debits "
        f"{totals['periodDebit']} vs credits {totals['periodCredit']}, "
        f"closing debits {totals['closingDebit']} vs credits {totals['closingCredit']}."
    ]
    return totals, balanced, imbalance, warnings


async def _trial_balance_rows(
    session: AsyncSession, filters: TrialBalanceFilters
) -> tuple[list[dict], dict[str, Decimal], bool, Decimal, list[str], date | None, date | None]:
    from_date, to_date = await resolve_range(session, filters)
    if filters.accountFrom and filters.accountTo and filters.accountFrom > filters.accountTo:
        raise ValidationFailed(
            "The account range is invalid.",
            {"accountTo": "The to account must not sort before the from account."},
        )

    rows = await ReportRepository(session).trial_balance_balances(
        from_date=from_date,
        to_date=to_date,
        account_from=filters.accountFrom,
        account_to=filters.accountTo,
    )

    items: list[dict] = []
    for row in rows:
        opening_net = _dec(row["opening_debit"]) - _dec(row["opening_credit"])
        period_debit = _dec(row["period_debit"])
        period_credit = _dec(row["period_credit"])
        opening_debit, opening_credit = _side(opening_net)
        closing_debit, closing_credit = _side(opening_net + period_debit - period_credit)
        items.append(
            {
                "accountId": str(row["account_id"]),
                "accountCode": row["account_code"],
                "accountName": row["account_name"],
                "accountType": row["account_type"],
                "openingDebit": opening_debit,
                "openingCredit": opening_credit,
                "periodDebit": period_debit,
                "periodCredit": period_credit,
                "closingDebit": closing_debit,
                "closingCredit": closing_credit,
            }
        )

    totals, balanced, imbalance, warnings = _trial_balance_totals(items)
    return items, totals, balanced, imbalance, warnings, from_date, to_date


async def trial_balance(session: AsyncSession, filters: TrialBalanceFilters) -> dict:
    items, totals, balanced, imbalance, warnings, from_date, to_date = await _trial_balance_rows(
        session, filters
    )
    offset = (filters.page - 1) * filters.pageSize
    return {
        "items": items[offset : offset + filters.pageSize],
        "total": len(items),
        "totals": totals,
        "balanced": balanced,
        "imbalance": imbalance,
        "warnings": warnings,
        "scope": {
            "fromDate": from_date.isoformat() if from_date else None,
            "toDate": to_date.isoformat() if to_date else None,
        },
    }


def _ledger_filter_kwargs(filters: GeneralLedgerFilters) -> dict:
    return {
        "account_code": filters.accountCode,
        "party": filters.party,
        "voucher_type": filters.voucherType,
        "voucher_no": filters.voucherNo,
        "currency": filters.currency,
    }


def _ledger_item(row: dict, opening: Decimal) -> dict:
    return {
        "id": str(row["id"]),
        "postingDate": row["posting_date"],
        "journalNo": row["entry_no"],
        "journalId": str(row["journal_id"]),
        "voucherType": row["entry_type"],
        "voucherNo": row["entry_no"],
        "sourceDocument": row["source_document_no"],
        "sourceDocumentId": str(row["source_document_id"]) if row["source_document_id"] else None,
        "accountId": str(row["account_id"]),
        "accountCode": row["account_code"],
        "accountName": row["account_name"],
        "account": f"{row['account_code']} · {row['account_name']}",
        "description": row["description"] or row["journal_description"],
        "partyId": row["party_id"],
        "party": row["party_name"] or "",
        "currency": row["currency_code"],
        # The running balance is continued from the account's opening position, so
        # page two starts where page one stopped.
        "debit": _dec(row["base_debit_amount"]),
        "credit": _dec(row["base_credit_amount"]),
        "runningBalance": _dec(row["running_balance"]) + opening,
    }


async def general_ledger(session: AsyncSession, filters: GeneralLedgerFilters) -> dict:
    from_date, to_date = await resolve_range(session, filters)
    repository = ReportRepository(session)
    filter_kwargs = _ledger_filter_kwargs(filters)

    openings = await repository.ledger_opening_balances(from_date=from_date, **filter_kwargs)
    total, debit, credit = await repository.general_ledger_totals(
        from_date=from_date, to_date=to_date, **filter_kwargs
    )
    rows = await repository.general_ledger_page(
        offset=(filters.page - 1) * filters.pageSize,
        limit=filters.pageSize,
        from_date=from_date,
        to_date=to_date,
        **filter_kwargs,
    )

    items = [_ledger_item(row, openings.get(int(row["account_id"]), ZERO)) for row in rows]
    opening_balance = sum(openings.values(), ZERO)
    return {
        "items": items,
        "total": total,
        "openingBalance": opening_balance,
        "totals": {
            "debit": debit,
            "credit": credit,
            "closingBalance": opening_balance + debit - credit,
        },
        "scope": {
            "fromDate": from_date.isoformat() if from_date else None,
            "toDate": to_date.isoformat() if to_date else None,
        },
    }


# --- Exports ------------------------------------------------------------------
def _period_label(from_date: date | None, to_date: date | None) -> str:
    if from_date and to_date:
        return f"{from_date.isoformat()} to {to_date.isoformat()}"
    if from_date:
        return f"from {from_date.isoformat()}"
    if to_date:
        return f"up to {to_date.isoformat()}"
    return "all postings"


def _scope_rows(title: str, from_date: date | None, to_date: date | None, filters: dict) -> list[list[object]]:
    rows: list[list[object]] = [
        [title],
        ["Generated at", datetime.now().astimezone().isoformat(timespec="seconds")],
        ["Period", _period_label(from_date, to_date)],
    ]
    for key, value in filters.items():
        if value not in (None, ""):
            rows.append([key, csv_export.text(value)])
    return rows


def _header(fields: tuple[tuple[str, str], ...]) -> list[object]:
    return [label for _, label in fields]


def _cells(item: dict, fields: tuple[tuple[str, str], ...], numeric: frozenset[str]) -> list[object]:
    return [
        csv_export.money(item.get(key)) if key in numeric else csv_export.text(item.get(key))
        for key, _ in fields
    ]


def _totals_row(
    values: dict[str, object],
    fields: tuple[tuple[str, str], ...],
    numeric: frozenset[str],
    *,
    label: str,
) -> list[object]:
    """A totals row aligned under the exported columns."""
    cells: list[object] = []
    labelled = False
    for key, _ in fields:
        if key in values:
            cells.append(csv_export.money(values[key]) if key in numeric else csv_export.text(values[key]))
        elif not labelled:
            cells.append(label)
            labelled = True
        else:
            cells.append("")
    if not labelled:
        cells[0] = label
    return cells


async def export_trial_balance(
    session: AsyncSession,
    filters: TrialBalanceFilters,
    fields: tuple[tuple[str, str], ...],
) -> AsyncIterator[list[object]]:
    items, totals, balanced, imbalance, warnings, from_date, to_date = await _trial_balance_rows(
        session, filters
    )
    for row in _scope_rows(
        "Trial Balance",
        from_date,
        to_date,
        {
            "Account from": filters.accountFrom,
            "Account to": filters.accountTo,
            "Fiscal year": filters.fiscalYear,
            "Balanced": "yes" if balanced else "no",
            "Imbalance": csv_export.money(imbalance),
        },
    ):
        yield row
    for warning in warnings:
        yield ["Warning", csv_export.text(warning)]
    yield []
    yield _header(fields)
    for item in items:
        yield _cells(item, fields, TRIAL_BALANCE_NUMERIC)
    yield []
    yield _totals_row(totals, fields, TRIAL_BALANCE_NUMERIC, label="Totals")


async def export_general_ledger(
    session: AsyncSession,
    filters: GeneralLedgerFilters,
    fields: tuple[tuple[str, str], ...],
) -> AsyncIterator[list[object]]:
    from_date, to_date = await resolve_range(session, filters)
    repository = ReportRepository(session)
    filter_kwargs = _ledger_filter_kwargs(filters)
    openings = await repository.ledger_opening_balances(from_date=from_date, **filter_kwargs)
    total, debit, credit = await repository.general_ledger_totals(
        from_date=from_date, to_date=to_date, **filter_kwargs
    )
    opening_balance = sum(openings.values(), ZERO)

    for row in _scope_rows(
        "General Ledger",
        from_date,
        to_date,
        {
            "Account": filters.accountCode,
            "Party": filters.party,
            "Voucher type": filters.voucherType,
            "Voucher no": filters.voucherNo,
            "Currency": filters.currency,
            "Rows": total,
            "Opening balance": csv_export.money(opening_balance),
        },
    ):
        yield row
    yield []
    yield _header(fields)
    # Streamed: a large ledger is never held in memory, page or export.
    async for row in repository.general_ledger_stream(from_date=from_date, to_date=to_date, **filter_kwargs):
        item = _ledger_item(row, openings.get(int(row["account_id"]), ZERO))
        yield _cells(item, fields, GENERAL_LEDGER_NUMERIC)
    yield []
    yield _totals_row(
        {"debit": debit, "credit": credit, "runningBalance": opening_balance + debit - credit},
        fields,
        GENERAL_LEDGER_NUMERIC,
        label="Totals",
    )
