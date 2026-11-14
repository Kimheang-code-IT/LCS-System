"""Pre-closing validation and review for Accounting Periods (P10/S08).

One authoritative check pipeline for the Period Closing page: every check returns a
structured result (severity, message, affected count/ids, recommended action), and
`blocking_results` (run inside `close_period`'s row lock) is the exact gate the closing
action re-plays against the consistent state — the validation a user reviewed is the same
code that decides lock-time eligibility.

Severity policy (documented in P10):
- BLOCKED — the books would be broken if the period closed now (unbalanced posted
  journals, journal lines whose account no longer resolves, posting links without their
  document).
- WARNING — reviewable data (draft documents dated in the period).
- NOT_AVAILABLE — a check whose feature does not exist yet (bank reconciliation):
  never reported as PASS.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from app.core.context import RequestContext
from app.core.database import AsyncSession
from app.modules.finance.models import (
    AccountingPeriod,
    ChartOfAccount,
    FinancialDocument,
    FinancialDocumentPosting,
    JournalEntry,
    JournalEntryLine,
)


def _check(
    code: str,
    name: str,
    status: str,
    severity: str,
    message: str,
    *,
    affected: list | None = None,
    recommended: str = "",
    recommendedAction: str = "",  # both spellings accepted; recommendedAction mirrors the API field
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "status": status,          # PASS | WARNING | BLOCKED | NOT_AVAILABLE
        "severity": severity,      # BLOCKING | REVIEW
        "message": message,
        "affectedCount": len(affected or []),
        "relatedIds": [str(value) for value in (affected or [])][:20],
        "recommendedAction": recommendedAction or recommended,
    }


def blocking_results(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [check for check in checks if check["status"] == "BLOCKED"]


async def _integrity_checks(session: AsyncSession, period: AccountingPeriod) -> list[dict[str, Any]]:
    """Checks 3/8 — every posted journal in the period is complete and traceable."""
    in_period = select(JournalEntry.id).where(
        JournalEntry.accounting_period_id == period.id, JournalEntry.status == "POSTED"
    )
    checks: list[dict[str, Any]] = []

    unbalanced = (
        await session.execute(
            select(JournalEntry.id).where(
                JournalEntry.id.in_(in_period), JournalEntry.debit_total != JournalEntry.credit_total
            )
        )
    ).scalars().all()
    checks.append(_check(
        "JOURNAL_BALANCE", "Journal balance", "BLOCKED" if unbalanced else "PASS", "BLOCKING",
        "Posted journals whose debit and credit totals differ." if unbalanced else "Every posted journal is balanced.",
        affected=unbalanced,
        recommended="Reconcile or reverse the affected journals." if unbalanced else "",
    ))

    # account_id is NOT NULL on the model; an unresolvable row is an outer-join miss.
    unresolved = (
        await session.execute(
            select(JournalEntry.id)
            .join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccount, ChartOfAccount.id == JournalEntryLine.account_id, isouter=True)
            .where(JournalEntry.id.in_(in_period), ChartOfAccount.id.is_(None))
            .group_by(JournalEntry.id)
        )
    ).scalars().all()
    checks.append(_check(
        "JOURNAL_LINES", "Journal lines", "BLOCKED" if unresolved else "PASS", "BLOCKING",
        "Posted journal lines reference accounts that no longer resolve." if unresolved else "Journal lines resolve every account.",
        affected=unresolved,
        recommended="Repair or reverse the affected entries." if unresolved else "",
    ))

    # The posting link is unique per document (uq_fin_doc_postings); a link whose
    # document vanished would be an integrity break.
    missing_links = (
        await session.execute(
            select(FinancialDocumentPosting.financial_document_id)
            .select_from(FinancialDocumentPosting)
            .join(FinancialDocument, FinancialDocument.id == FinancialDocumentPosting.financial_document_id, isouter=True)
            .where(FinancialDocument.id.is_(None))
            .group_by(FinancialDocumentPosting.financial_document_id)
        )
    ).scalars().all()
    checks.append(_check(
        "POSTING_LINKS", "Posting relationships", "BLOCKED" if missing_links else "PASS", "BLOCKING",
        "Posting relationships orphaned by data changes." if missing_links else "Every posting links a live document.",
        affected=missing_links,
        recommended="Restore or archive the referenced documents." if missing_links else "",
    ))
    return checks


async def _financial_summary(session: AsyncSession, period: AccountingPeriod, base_currency: str) -> dict[str, Any]:
    """Section D figures, all read from POSTED data, valued in the base currency."""
    ledger = (
        await session.execute(
            select(
                ChartOfAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.base_debit_amount), Decimal("0")),
                func.coalesce(func.sum(JournalEntryLine.base_credit_amount), Decimal("0")),
            )
            .select_from(JournalEntryLine)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .join(ChartOfAccount, ChartOfAccount.id == JournalEntryLine.account_id)
            .where(
                JournalEntry.accounting_period_id == period.id,
                JournalEntry.status == "POSTED",
                ChartOfAccount.account_type.in_(("REVENUE", "EXPENSE")),
            )
            .group_by(ChartOfAccount.account_type)
        )
    ).all()
    revenue = expense = Decimal("0")
    for account_type, debit, credit in ledger:
        if account_type == "REVENUE":
            revenue += Decimal(str(credit)) - Decimal(str(debit))
        else:
            expense += Decimal(str(debit)) - Decimal(str(credit))

    from app.modules.reports.financial_statements import financial_statement
    ar = await financial_statement(session, "accounts-receivable", {"toDate": period.end_date})
    ap = await financial_statement(session, "accounts-payable", {"toDate": period.end_date})
    unapplied = sum((-row["baseOutstanding"] for projection in (ar, ap) for row in projection["items"]
        if row["documentType"] in {"CUSTOMER_RECEIPT", "SUPPLIER_PAYMENT"}), Decimal("0"))
    return {
        "revenue": float(revenue),
        "expenses": float(expense),
        "profit": float(revenue - expense),
        "arOutstanding": float(ar["totals"]["baseOutstanding"]),
        "apOutstanding": float(ap["totals"]["baseOutstanding"]),
        "unappliedPayments": float(unapplied),
        "currency": base_currency,
    }


async def run_closing_validation(session: AsyncSession, context: RequestContext, period_id: int) -> dict[str, Any]:
    """The full review: eight structured checks plus the financial summary."""
    from app.core.exceptions import NotFound
    from app.modules.reports import service as reports_service
    from app.modules.settings.service import get_default_currency

    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise NotFound("Accounting period not found.")
    checks: list[dict[str, Any]] = []

    # Check 1 — the period itself: only an OPEN period may close.
    if period.status == "OPEN":
        checks.append(_check(
            "PERIOD_STATE", "Period state", "PASS", "BLOCKING",
            f"{period.name or period.period_year} is open ({period.start_date} – {period.end_date}).",
        ))
    else:
        checks.append(_check(
            "PERIOD_STATE", "Period state", "BLOCKED", "BLOCKING",
            f"Only an open period can be closed; this period is {period.status}.",
            recommended="Reopen the period first (authorized action, reason required).",
        ))

    # Check 2 — financial documents dated inside the period. Drafts are review
    # warnings (never an automatic blocker per the P10 policy).
    in_range = select(FinancialDocument.id).where(
        FinancialDocument.document_date.between(period.start_date, period.end_date)
    )
    draft_rows = (
        await session.execute(
            select(FinancialDocument.document_type, func.count())
            .where(
                FinancialDocument.id.in_(in_range),
                FinancialDocument.status == "DRAFT",
                FinancialDocument.document_type.in_(
                    ("CUSTOMER_INVOICE", "SUPPLIER_BILL", "CUSTOMER_RECEIPT", "SUPPLIER_PAYMENT")
                ),
            )
            .group_by(FinancialDocument.document_type)
        )
    ).all()
    drafts_total = sum(int(count) for _type, count in draft_rows)
    drafts_check = _check(
        "DRAFT_DOCUMENTS", "Unposted documents", "WARNING" if drafts_total else "PASS", "REVIEW",
        f"{drafts_total} draft document(s) dated in the period"
        + (": " + ", ".join(f"{doc_type} × {count}" for doc_type, count in draft_rows) if draft_rows else ""),
        recommendedAction="Review and post them; drafts do not block closing.",
    )
    drafts_check["affectedCount"] = drafts_total
    checks.append(drafts_check)

    checks.extend(await _integrity_checks(session, period))

    # Check 4/5 — AR/AP layers: unpaid documents stay valid receivables/payables
    # and are never treated as errors. Informational on purpose.
    base_currency = await get_default_currency(session)
    summary = await _financial_summary(session, period, base_currency)
    checks.append(_check(
        "ACCOUNTS_RECEIVABLE", "Accounts receivable", "PASS", "REVIEW",
        f"Outstanding invoices: {summary['arOutstanding']} {base_currency} — valid receivables that carry into the next period.",
        recommendedAction="No action: unpaid invoices remain valid receivables.",
    ))
    checks.append(_check(
        "ACCOUNTS_PAYABLE", "Accounts payable", "PASS", "REVIEW",
        f"Outstanding bills: {summary['apOutstanding']} {base_currency} — valid payables that carry into the next period.",
        recommendedAction="No action: unpaid bills remain valid payables.",
    ))
    checks.append(_check(
        "ALLOCATION_CUTOFF", "Payment allocation cutoff", "PASS", "REVIEW",
        f"Allocations carry effective timestamps and settle posted documents without journals (unapplied: {summary['unappliedPayments']} {base_currency}).",
        recommendedAction="No action: settlements of older documents remain allowed in open periods.",
    ))

    # Check 7 — the trial balance control must hold before the books lock.
    trial = await reports_service.trial_balance(session, context)
    balanced = bool(trial.get("balanced"))
    checks.append(_check(
        "TRIAL_BALANCE", "Trial balance", "PASS" if balanced else "BLOCKED", "BLOCKING",
        "Debits equal credits on posted journals." if balanced else "The ledger does not balance.",
        recommendedAction="" if balanced else "Reconcile the ledger before closing.",
    ))

    # Check 6 — bank reconciliation does not exist in this build: honest
    # NOT_AVAILABLE, never a PASS.
    checks.append(_check(
        "BANK_RECONCILIATION", "Bank reconciliation", "NOT_AVAILABLE", "REVIEW",
        "No bank-reconciliation feature exists in this build; the check is not executed.",
        recommendedAction="Reconcile manually against the Financial Accounts page.",
    ))

    return {
        "period": {
            "id": str(period.id),
            "name": period.name,
            "startDate": period.start_date.isoformat(),
            "endDate": period.end_date.isoformat(),
            "status": str(period.status).capitalize(),
        },
        "checks": checks,
        "blockingCount": len(blocking_results(checks)),
        "blockingCodes": [check["code"] for check in blocking_results(checks)],
        "summary": summary,
        "baseCurrency": base_currency,
    }


async def closing_history(session: AsyncSession, context: RequestContext, period_id: int) -> dict[str, Any]:
    """The period's closing/reopening audit trail for the history dialog."""
    from app.core import exceptions
    from app.core.users import user_display_names
    from app.modules.audit.models import AuditEvent

    if await session.get(AccountingPeriod, period_id) is None:
        raise exceptions.NotFound("Accounting period not found.")
    rows = (
        await session.execute(
            select(AuditEvent)
            .where(
                # One period may own several audit rows under overlapping id
                # spaces of other entities; filter by event type so history never
                # shows unrelated records.
                AuditEvent.entity_id == period_id,
                AuditEvent.event_type.in_(
                    ("PERIOD_CREATED", "PERIOD_UPDATED", "PERIOD_CLOSED", "PERIOD_REOPENED", "PERIOD_DELETED")
                ),
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(20)
        )
    ).scalars().all()
    names = await user_display_names(session, (row.actor_user_id for row in rows))
    return {
        "periodId": str(period_id),
        "history": [
            {
                "id": str(row.id),
                "event": row.event_type,
                "action": row.action,
                "actor": names.get(row.actor_user_id) or "System",
                "at": row.occurred_at.isoformat() if row.occurred_at else None,
                "reason": row.reason,
            }
            for row in rows
        ],
    }
