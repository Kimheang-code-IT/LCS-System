from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.pagination import PageParams, page_params
from app.modules.audit.service import write_audit
from app.modules.finance import service

router = APIRouter()


# --- Chart of accounts -------------------------------------------------------
@router.get("/chart-of-accounts")
@router.get("/chartOfAccounts")
async def list_accounts(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("journal_entry.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_accounts(session, context, page)}


@router.post("/chartOfAccounts", status_code=status.HTTP_201_CREATED)
@router.post("/chart-of-accounts", status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("chart_of_accounts.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.create_account(session, context, payload)}


@router.put("/chartOfAccounts/{account_id}")
@router.put("/chart-of-accounts/{account_id}")
async def update_account(
    account_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("chart_of_accounts.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.update_account(session, context, int(account_id), payload)}


@router.get("/chartOfAccounts/{account_id}")
@router.get("/chart-of-accounts/{account_id}")
async def get_account(
    account_id: str,
    context: RequestContext = Depends(require_permission("journal_entry.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_account(session, context, int(account_id))}


@router.delete("/chartOfAccounts")
@router.delete("/chart-of-accounts")
async def delete_accounts(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("chart_of_accounts.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    await service.delete_accounts(session, context, ids)
    return {"data": {"removed": len(ids)}}


# --- Financial accounts ------------------------------------------------------
@router.get("/financial-accounts")
@router.get("/financialAccounts")
async def list_financial_accounts(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("journal_entry.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_financial_accounts(session, context, page)}


@router.post("/financialAccounts", status_code=status.HTTP_201_CREATED)
@router.post("/financial-accounts", status_code=status.HTTP_201_CREATED)
async def create_financial_account(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("chart_of_accounts.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.create_financial_account(session, context, payload)}


@router.get("/financialAccounts/{account_id}")
@router.get("/financial-accounts/{account_id}")
async def get_financial_account(
    account_id: str,
    context: RequestContext = Depends(require_permission("journal_entry.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_financial_account(session, context, int(account_id))}


@router.put("/financialAccounts/{account_id}")
@router.put("/financial-accounts/{account_id}")
async def update_financial_account(
    account_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("chart_of_accounts.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.update_financial_account(session, context, int(account_id), payload)}


@router.delete("/financialAccounts")
@router.delete("/financial-accounts")
async def delete_financial_accounts(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("chart_of_accounts.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    await service.delete_financial_accounts(session, context, ids)
    return {"data": {"removed": len(ids)}}


# --- Accounting periods ------------------------------------------------------
@router.get("/accounting-periods")
@router.get("/accountingPeriods")
async def list_periods(
    context: RequestContext = Depends(require_permission("accounting_period.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_periods(session, context)}


@router.get("/accounting-periods/{period_id}")
@router.get("/accountingPeriods/{period_id}")
async def get_period(
    period_id: str,
    context: RequestContext = Depends(require_permission("accounting_period.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_period(session, context, int(period_id))}


@router.put("/accounting-periods/{period_id}")
@router.patch("/accounting-periods/{period_id}")
async def update_period(
    period_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("accounting_period.close")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.update_period(session, context, int(period_id), payload)}


@router.post("/accounting-periods/{period_id}/close")
async def close_period(
    period_id: str,
    payload: dict = Body(default={}),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("accounting_period.close")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    period = await service.close_period(session, context, int(period_id))
    await write_audit(
        session,
        context,
        event_type="PERIOD_CLOSED",
        entity_type="accounting_period",
        entity_id=int(period_id),
        action="close",
        reason=payload.get("reason"),
    )
    await session.commit()
    return {"data": period}


# --- Document sequences ------------------------------------------------------
@router.get("/document-sequences")
@router.get("/documentSequences")
async def list_sequences(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_sequences(session, context, page)}


@router.post("/documentSequences", status_code=status.HTTP_201_CREATED)
@router.post("/document-sequences", status_code=status.HTTP_201_CREATED)
async def upsert_sequence(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.upsert_sequence(session, context, payload)}


@router.get("/documentSequences/{sequence_id}")
@router.get("/document-sequences/{sequence_id}")
async def get_sequence(
    sequence_id: str,
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_sequence(session, context, int(sequence_id))}


# --- Posting rules -----------------------------------------------------------
@router.get("/posting-rules")
@router.get("/postingRules")
async def list_posting_rules(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_posting_rules(session, context, page)}


@router.post("/postingRules", status_code=status.HTTP_201_CREATED)
@router.post("/posting-rules", status_code=status.HTTP_201_CREATED)
async def create_posting_rule(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.create_posting_rule(session, context, payload)}


@router.get("/postingRules/{rule_id}")
@router.get("/posting-rules/{rule_id}")
async def get_posting_rule(
    rule_id: str,
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_posting_rule(session, context, int(rule_id))}


@router.put("/postingRules/{rule_id}")
@router.put("/posting-rules/{rule_id}")
async def update_posting_rule(
    rule_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.update_posting_rule(session, context, int(rule_id), payload)}


@router.delete("/postingRules")
@router.delete("/posting-rules")
async def delete_posting_rules(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    await service.delete_posting_rules(session, context, ids)
    return {"data": {"removed": len(ids)}}


# --- Financial documents -----------------------------------------------------
@router.get("/financial-documents")
async def list_financial_documents(
    page: PageParams = Depends(page_params),
    document_type: str | None = None,
    party_id: int | None = None,
    context: RequestContext = Depends(require_permission("financial_document.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_documents(session, context, page, document_type)}


@router.post("/financial-documents", status_code=status.HTTP_201_CREATED)
async def create_financial_document(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("financial_document.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_document(session, context, payload)}


@router.delete("/financial-documents")
async def delete_financial_documents(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("financial_document.update_draft")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.finance.models import FinancialDocument

    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    for document_id in ids:
        document = await session.get(FinancialDocument, document_id)
        if document is not None and document.organization_id == context.organization_id and document.status == "DRAFT":
            await session.delete(document)
    await session.commit()
    return {"data": {"removed": len(ids)}}


@router.get("/financial-documents/{document_id}")
async def get_financial_document(
    document_id: str,
    context: RequestContext = Depends(require_permission("financial_document.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_document(session, context, int(document_id))}


@router.put("/financial-documents/{document_id}")
async def update_financial_document(
    document_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("financial_document.update_draft")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_document(session, context, {**payload, "id": document_id})}


@router.post("/financial-documents/{document_id}/post")
async def post_financial_document(
    document_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("financial_document.post")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    document = await service.post_document(session, context, int(document_id))
    await write_audit(
        session,
        context,
        event_type="FINANCIAL_POSTED",
        entity_type="financial_document",
        entity_id=int(document_id),
        action="post",
        after={"documentNo": document.get("documentNo")},
    )
    await session.commit()
    return {"data": document}


@router.post("/financial-documents/{document_id}/allocate")
async def allocate_payment(
    document_id: str,
    payload: dict = Body(default={}),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("financial_document.allocate")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    allocation = await service.allocate_payment(session, context, int(document_id), payload)
    await write_audit(
        session,
        context,
        event_type="PAYMENT_ALLOCATED",
        entity_type="financial_document",
        entity_id=int(document_id),
        action="allocate",
        after=allocation,
    )
    await session.commit()
    return {"data": allocation}


@router.post("/financial-documents/{document_id}/reverse", status_code=status.HTTP_201_CREATED)
async def reverse_financial_document(
    document_id: str,
    payload: dict = Body(default={}),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("financial_document.reverse")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    reason = str(payload.get("reason") or "Reversal")
    document = await service.reverse_document(session, context, int(document_id), reason)
    await write_audit(
        session,
        context,
        event_type="FINANCIAL_REVERSED",
        entity_type="financial_document",
        entity_id=int(document_id),
        action="reverse",
        reason=reason,
    )
    await session.commit()
    return {"data": document}


# --- Journals ----------------------------------------------------------------
@router.get("/journal-entries")
@router.get("/journals")
async def list_journals(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("journal_entry.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_journals(session, context, page)}


@router.post("/journal-entries", status_code=status.HTTP_201_CREATED)
@router.post("/journals", status_code=status.HTTP_201_CREATED)
async def create_journal(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("journal_entry.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_journal(session, context, payload)}


@router.get("/journal-entries/{journal_id}")
@router.get("/journals/{journal_id}")
async def get_journal(
    journal_id: str,
    context: RequestContext = Depends(require_permission("journal_entry.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_journal(session, context, int(journal_id))}


@router.put("/journal-entries/{journal_id}")
@router.put("/journals/{journal_id}")
async def update_journal(
    journal_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("journal_entry.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_journal(session, context, {**payload, "id": journal_id})}


@router.post("/journal-entries/{journal_id}/post")
@router.post("/journals/{journal_id}/post")
async def post_journal(
    journal_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("journal_entry.post")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    entry = await service.post_journal(session, context, int(journal_id))
    await write_audit(
        session,
        context,
        event_type="JOURNAL_POSTED",
        entity_type="journal_entry",
        entity_id=int(journal_id),
        action="post",
    )
    await session.commit()
    return {"data": entry}
