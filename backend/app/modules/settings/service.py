from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.modules.master_data.models import BusinessParty, ModuleRecord

APP_INFO_COLLECTION = "__app_info__"
APP_CONFIG_COLLECTION = "__app_config__"
SETTINGS_RECORD_NO = "default"

DEFAULT_APP_INFO: dict[str, Any] = {
    "applicationName": "LCS Freight Forwarding",
    "shortName": "LCS Freight",
    "organizationName": "",
    "description": "Freight forwarding, operations and finance management system.",
    "supportEmail": "",
    "supportPhone": "",
    "website": "",
    "address": "",
    "branding": {
        "primaryColor": "#e8472a",
        "secondaryColor": "#0f766e",
    },
    "footer": {"copyrightText": ""},
}

DEFAULT_APP_CONFIG: dict[str, Any] = {
    "general": {
        "defaultLandingPage": "/",
        "defaultPageSize": 25,
        "defaultRecordView": "table",
        "enableComments": True,
        "enableSharing": True,
        "enableExport": True,
        "maxUploadSizeMb": 50,
    },
    "localization": {
        "defaultLanguage": "en",
        "availableLanguages": ["en", "km"],
        "timezone": "Asia/Phnom_Penh",
        "dateFormat": "DD/MM/YYYY",
        "timeFormat": "HH:mm",
        "firstDayOfWeek": 1,
        "numberFormat": "#,##0.00",
        "currency": "USD",
        "locale": "en-US",
    },
    "email": {
        "enabled": False,
        "smtpHost": "",
        "smtpPort": 587,
        "username": "",
        "password": "",
        "encryption": "starttls",
        "fromName": "",
        "fromEmail": "",
        "replyToEmail": "",
        "timeoutSeconds": 30,
        "connectionStatus": "not_tested",
    },
    "telegram": {
        "enabled": False,
        "mode": "bot_api",
        "botToken": "",
        "webhookUrl": "",
        "connectionStatus": "not_tested",
        "destinations": [],
    },
    "notifications": {
        "inAppEnabled": True,
        "emailEnabled": False,
        "telegramEnabled": False,
        "deliveryRetries": 3,
        "quietHoursEnabled": False,
        "language": "en",
        "rules": [],
    },
    "security": {
        "sessionTimeoutMinutes": 60,
        "maxLoginAttempts": 5,
        "accountLockMinutes": 15,
        "passwordExpiryDays": 0,
        "requirePasswordChange": False,
        "allowedUploadExtensions": ["pdf", "png", "jpg", "jpeg", "webp", "docx", "xlsx", "csv"],
        "auditRetentionDays": 365,
        "frontendOnly": True,
    },
    "system": {
        "maintenanceMode": False,
        "readOnlyMode": False,
        "paginationDefault": 25,
        "configurationVersion": "1.0.0",
        "environment": "production",
        "cacheStatus": "healthy",
        "backgroundJobStatus": "idle",
    },
}


def deep_merge(base: Any, override: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    merged = dict(base)
    for key, value in override.items():
        if key in merged:
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


async def _load_record(session: AsyncSession, organization_id: int, collection: str) -> ModuleRecord | None:
    return (
        await session.execute(
            select(ModuleRecord).where(
                ModuleRecord.organization_id == organization_id,
                ModuleRecord.collection == collection,
                ModuleRecord.record_no == SETTINGS_RECORD_NO,
            )
        )
    ).scalars().first()


def _with_timestamp(data: dict[str, Any], record: ModuleRecord | None) -> dict[str, Any]:
    payload = dict(data)
    payload["updatedAt"] = (
        record.updated_at.isoformat() if record is not None and record.updated_at else payload.get("updatedAt") or ""
    )
    return payload


async def get_app_info(session: AsyncSession, context: RequestContext) -> dict:
    record = await _load_record(session, context.organization_id, APP_INFO_COLLECTION)
    merged = deep_merge(DEFAULT_APP_INFO, record.data if record else {})
    return _with_timestamp(merged, record)


async def update_app_info(session: AsyncSession, context: RequestContext, patch: dict[str, Any]) -> dict:
    record = await _load_record(session, context.organization_id, APP_INFO_COLLECTION)
    current = record.data if record else {}
    data = deep_merge(current, patch or {})
    if record is None:
        record = ModuleRecord(
            organization_id=context.organization_id,
            collection=APP_INFO_COLLECTION,
            record_no=SETTINGS_RECORD_NO,
            data=data,
        )
        session.add(record)
    else:
        record.data = data
    await session.commit()
    await session.refresh(record)
    return _with_timestamp(deep_merge(DEFAULT_APP_INFO, record.data), record)


async def reset_app_info(session: AsyncSession, context: RequestContext) -> dict:
    record = await _load_record(session, context.organization_id, APP_INFO_COLLECTION)
    if record is not None:
        await session.delete(record)
        await session.commit()
    return _with_timestamp(dict(DEFAULT_APP_INFO), None)


async def get_app_config(session: AsyncSession, context: RequestContext) -> dict:
    record = await _load_record(session, context.organization_id, APP_CONFIG_COLLECTION)
    merged = deep_merge(DEFAULT_APP_CONFIG, record.data if record else {})
    return _with_timestamp(merged, record)


async def update_app_config(session: AsyncSession, context: RequestContext, patch: dict[str, Any]) -> dict:
    record = await _load_record(session, context.organization_id, APP_CONFIG_COLLECTION)
    current = record.data if record else {}
    data = deep_merge(current, patch or {})
    if record is None:
        record = ModuleRecord(
            organization_id=context.organization_id,
            collection=APP_CONFIG_COLLECTION,
            record_no=SETTINGS_RECORD_NO,
            data=data,
        )
        session.add(record)
    else:
        record.data = data
    await session.commit()
    await session.refresh(record)
    return _with_timestamp(deep_merge(DEFAULT_APP_CONFIG, record.data), record)


def connection_result(enabled: bool, label: str) -> dict[str, str]:
    if not enabled:
        return {"status": "disabled", "message": f"{label} is disabled in App Config."}
    return {"status": "connected", "message": f"{label} configuration saved. Delivery is sent by the backend worker."}


# --- Global search -----------------------------------------------------------
def _snippet(text: str, query: str, size: int = 120) -> str:
    lowered = text.lower()
    index = lowered.find(query.lower())
    if index < 0:
        return text[:size]
    start = max(0, index - 40)
    return text[start:start + size]


async def search(session: AsyncSession, context: RequestContext, query: str, limit: int = 20) -> list[dict[str, Any]]:
    from app.modules.finance.models import FinancialDocument, JournalEntry
    from app.modules.operations.models import ServiceOrder
    from app.modules.quotations.models import Quotation

    q = (query or "").strip()
    if not q:
        return []
    pattern = f"%{q}%"
    hits: list[dict[str, Any]] = []

    def add(entity_type: str, entity_id: int, title: str, text: str, url: str, permission: str, updated_at: Any) -> None:
        stamp = updated_at.isoformat() if updated_at is not None else ""
        hits.append(
            {
                "id": f"{entity_type}-{entity_id}",
                "entityType": entity_type,
                "entityId": str(entity_id),
                "title": title,
                "text": text,
                "url": url,
                "permission": permission,
                "updatedAt": stamp,
                "score": 100 - len(hits),
                "snippet": _snippet(text, q),
                "sourceLabel": entity_type,
            }
        )

    orders = (
        await session.execute(
            select(ServiceOrder)
            .where(ServiceOrder.organization_id == context.organization_id, ServiceOrder.service_order_no.ilike(pattern))
            .limit(limit)
        )
    ).scalars().all()
    for row in orders:
        add("other", row.id, row.service_order_no, f"Service order {row.service_order_no}", f"/service-orders/{row.id}", "service_order.read", None)

    quotations = (
        await session.execute(
            select(Quotation)
            .where(Quotation.organization_id == context.organization_id, Quotation.quotation_no.ilike(pattern))
            .limit(limit)
        )
    ).scalars().all()
    for row in quotations:
        add("other", row.id, row.quotation_no, f"Quotation {row.quotation_no}", f"/quotations/{row.id}", "quotation.read", None)

    documents = (
        await session.execute(
            select(FinancialDocument)
            .where(
                FinancialDocument.organization_id == context.organization_id,
                or_(FinancialDocument.document_no.ilike(pattern), FinancialDocument.reference_number.ilike(pattern)),
            )
            .limit(limit)
        )
    ).scalars().all()
    for row in documents:
        add("document", row.id, row.document_no, f"Financial document {row.document_no}", f"/finance/documents/{row.id}", "financial_document.read", None)

    journals = (
        await session.execute(
            select(JournalEntry)
            .where(JournalEntry.organization_id == context.organization_id, JournalEntry.entry_no.ilike(pattern))
            .limit(limit)
        )
    ).scalars().all()
    for row in journals:
        add("document", row.id, row.entry_no, f"Journal entry {row.entry_no}", f"/finance/journals/{row.id}", "journal_entry.read", None)

    parties = (
        await session.execute(
            select(BusinessParty)
            .where(
                or_(
                    BusinessParty.legal_name.ilike(pattern),
                    BusinessParty.party_code.ilike(pattern),
                    BusinessParty.display_name.ilike(pattern),
                )
            )
            .limit(limit)
        )
    ).scalars().all()
    for row in parties:
        add("company", row.id, row.legal_name, f"Business party {row.party_code} - {row.legal_name}", f"/master-data/business-parties/{row.id}", "master.reference.view", None)

    return hits[:limit]


async def answer(session: AsyncSession, context: RequestContext, query: str, hit_ids: list[str] | None = None) -> dict:
    hits = await search(session, context, query, limit=5)
    if hit_ids:
        hits = [hit for hit in hits if hit["id"] in hit_ids] or hits
    if not hits:
        return {"answer": f'No permitted records matched "{query.strip()}".', "citations": []}
    lines = [f"{index + 1}. {hit['title']} -> {hit['url']}" for index, hit in enumerate(hits)]
    return {
        "answer": "\n".join(
            [
                f'Top matches for "{query.strip()}":',
                "",
                *lines,
            ]
        ),
        "citations": hits,
    }
