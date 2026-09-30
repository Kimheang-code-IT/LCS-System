from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import ValidationFailed
from app.core.localization import DEFAULT_LOCALIZATION, normalize_localization, validate_localization_patch
from app.modules.master_data.models import BusinessParty, ModuleRecord

APP_INFO_COLLECTION = "__app_info__"
APP_CONFIG_COLLECTION = "__app_config__"
SETTINGS_RECORD_NO = "default"

DEFAULT_APP_INFO: dict[str, Any] = {
    "applicationName": "LCS Freight Forwarding",
    "shortName": "LCS Freight",
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
    "localization": deepcopy(DEFAULT_LOCALIZATION),
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
    "backup": {
        "enabled": False,
        "intervalHours": 24,
        "r2AccountId": "",
        "r2AccessKeyId": "",
        "r2SecretAccessKey": "",
        "r2BucketName": "",
        "r2Endpoint": "",
        "r2Prefix": "backups",
        "spreadsheetId": "",
        "serviceAccountEmail": "",
        "serviceAccountJson": "",
        "lastRunAt": "",
        "lastRunStatus": "idle",
        "lastRunMessage": "",
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


async def _load_record(session: AsyncSession, collection: str) -> ModuleRecord | None:
    return (
        await session.execute(
            select(ModuleRecord).where(
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


async def get_app_info(session: AsyncSession, context: RequestContext | None = None) -> dict:
    record = await _load_record(session, APP_INFO_COLLECTION)
    merged = deep_merge(DEFAULT_APP_INFO, record.data if record else {})
    return _with_timestamp(merged, record)


async def update_app_info(session: AsyncSession, context: RequestContext | None, patch: dict[str, Any]) -> dict:
    record = await _load_record(session, APP_INFO_COLLECTION)
    current = record.data if record else {}
    data = deep_merge(current, patch or {})
    if record is None:
        record = ModuleRecord(
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
    record = await _load_record(session, APP_INFO_COLLECTION)
    if record is not None:
        await session.delete(record)
        await session.commit()
    return _with_timestamp(dict(DEFAULT_APP_INFO), None)


async def get_app_config(session: AsyncSession, context: RequestContext | None = None) -> dict:
    record = await _load_record(session, APP_CONFIG_COLLECTION)
    merged = deep_merge(DEFAULT_APP_CONFIG, record.data if record else {})
    merged["localization"] = normalize_localization(merged.get("localization"))
    return _with_timestamp(merged, record)


def redact_app_config(config: dict[str, Any]) -> dict[str, Any]:
    """Never return write-only secrets (SMTP password, bot token, service JSON)."""
    payload = deepcopy(config)
    backup = payload.get("backup")
    if isinstance(backup, dict):
        backup["serviceAccountConfigured"] = bool(backup.pop("serviceAccountJson", ""))
        backup["r2SecretAccessKeyConfigured"] = bool(backup.pop("r2SecretAccessKey", ""))
    email = payload.get("email")
    if isinstance(email, dict) and "password" in email:
        email["passwordConfigured"] = bool(email.get("password"))
        email["password"] = ""
    telegram = payload.get("telegram")
    if isinstance(telegram, dict) and "botToken" in telegram:
        telegram["botTokenConfigured"] = bool(telegram.get("botToken"))
        telegram["botToken"] = ""
    return payload


def _without_blank_secrets(patch: dict[str, Any]) -> dict[str, Any]:
    """A blank secret field means 'leave the stored value unchanged'."""
    cleaned = dict(patch or {})
    backup = cleaned.get("backup")
    if isinstance(backup, dict):
        backup = dict(backup)
        for key in ("serviceAccountConfigured", "r2SecretAccessKeyConfigured"):
            backup.pop(key, None)
        for key in ("serviceAccountJson", "r2SecretAccessKey"):
            if not str(backup.get(key) or "").strip():
                backup.pop(key, None)
        cleaned["backup"] = backup
    for section, key in (("email", "password"), ("telegram", "botToken")):
        block = cleaned.get(section)
        if isinstance(block, dict) and not str(block.get(key) or "").strip():
            block = dict(block)
            block.pop(key, None)
            cleaned[section] = block
    return cleaned


def _validate_backup_config(config: dict[str, Any]) -> None:
    interval = config.get("intervalHours", 24)
    try:
        interval_hours = int(interval)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(
            "Backup interval must be a whole number of hours.",
            {"backup.intervalHours": "Enter a whole number between 1 and 720."},
        ) from exc
    if not 1 <= interval_hours <= 720:
        raise ValidationFailed(
            "Backup interval must be between 1 and 720 hours.",
            {"backup.intervalHours": "Enter a value between 1 and 720."},
        )

    r2_keys = ("r2AccountId", "r2AccessKeyId", "r2SecretAccessKey", "r2BucketName", "r2Endpoint")
    has_any_r2_value = any(str(config.get(key) or "").strip() for key in r2_keys)
    if has_any_r2_value:
        field_errors = {
            f"backup.{key}": "This field is required for Cloudflare R2 backups."
            for key in r2_keys
            if not str(config.get(key) or "").strip()
        }
        endpoint = str(config.get("r2Endpoint") or "").strip()
        parsed = urlparse(endpoint)
        if endpoint and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
            field_errors["backup.r2Endpoint"] = "Enter a valid HTTP or HTTPS S3 endpoint."
        prefix = str(config.get("r2Prefix") or "").strip()
        if prefix.startswith("/") or ".." in prefix.split("/"):
            field_errors["backup.r2Prefix"] = "Use a relative object prefix without '..' segments."
        if field_errors:
            raise ValidationFailed("Cloudflare R2 configuration is incomplete or invalid.", field_errors)

    if config.get("enabled"):
        sheets_configured = bool(config.get("spreadsheetId") and config.get("serviceAccountJson"))
        r2_configured = all(str(config.get(key) or "").strip() for key in r2_keys)
        if not sheets_configured and not r2_configured:
            raise ValidationFailed(
                "Automatic backup requires a configured destination.",
                {"backup.r2Endpoint": "Configure Cloudflare R2 before enabling automatic backup."},
            )


async def update_app_config(session: AsyncSession, context: RequestContext | None, patch: dict[str, Any]) -> dict:
    patch = dict(patch or {})
    record = await _load_record(session, APP_CONFIG_COLLECTION)
    current = record.data if record else {}
    if "localization" in patch:
        localization_patch = patch["localization"]
        if not isinstance(localization_patch, dict):
            validate_localization_patch(localization_patch)
        current_localization = normalize_localization(current.get("localization"))
        patch["localization"] = validate_localization_patch(deep_merge(current_localization, localization_patch))
    data = deep_merge(current, _without_blank_secrets(patch))
    if "backup" in patch:
        _validate_backup_config(deep_merge(DEFAULT_APP_CONFIG["backup"], data.get("backup") or {}))
    if record is None:
        record = ModuleRecord(
            collection=APP_CONFIG_COLLECTION,
            record_no=SETTINGS_RECORD_NO,
            data=data,
        )
        session.add(record)
    else:
        record.data = data
    await session.commit()
    await session.refresh(record)
    merged = deep_merge(DEFAULT_APP_CONFIG, record.data)
    merged["localization"] = normalize_localization(merged.get("localization"))
    return _with_timestamp(merged, record)


async def get_localization(session: AsyncSession) -> dict[str, Any]:
    config = await get_app_config(session)
    return config["localization"]


async def get_default_currency(session: AsyncSession) -> str:
    return str((await get_localization(session))["currency"])


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

    # Only surface entity types the caller is actually allowed to read.
    if context.has_permission("service_order.read"):
        orders = (
            await session.execute(
                select(ServiceOrder)
                .where(ServiceOrder.service_order_no.ilike(pattern))
                .limit(limit)
            )
        ).scalars().all()
        for row in orders:
            add("other", row.id, row.service_order_no, f"Service order {row.service_order_no}", f"/service-orders/{row.id}", "service_order.read", None)

    if context.has_permission("quotation.read"):
        quotations = (
            await session.execute(
                select(Quotation)
                .where(Quotation.quotation_no.ilike(pattern))
                .limit(limit)
            )
        ).scalars().all()
        for row in quotations:
            add("other", row.id, row.quotation_no, f"Quotation {row.quotation_no}", f"/quotations/{row.id}", "quotation.read", None)

    if context.has_permission("financial_document.read"):
        documents = (
            await session.execute(
                select(FinancialDocument)
                .where(
                    or_(FinancialDocument.document_no.ilike(pattern), FinancialDocument.reference_number.ilike(pattern)),
                )
                .limit(limit)
            )
        ).scalars().all()
        for row in documents:
            add("document", row.id, row.document_no, f"Financial document {row.document_no}", f"/finance/documents/{row.id}", "financial_document.read", None)

    if context.has_permission("journal_entry.read"):
        journals = (
            await session.execute(
                select(JournalEntry)
                .where(JournalEntry.entry_no.ilike(pattern))
                .limit(limit)
            )
        ).scalars().all()
        for row in journals:
            add("document", row.id, row.entry_no, f"Journal entry {row.entry_no}", f"/finance/journals/{row.id}", "journal_entry.read", None)

    if context.has_permission("master.reference.view"):
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
