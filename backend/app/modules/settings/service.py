from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import ValidationFailed
from app.core.localization import (
    DEFAULT_LOCALIZATION,
    normalize_localization,
    normalize_message_language,
    validate_localization_patch,
)
from app.modules.master_data.models import BusinessParty, ModuleRecord
from app.modules.settings.models import AppSetting

APP_INFO_COLLECTION = "__app_info__"
APP_CONFIG_COLLECTION = "__app_config__"
SETTINGS_RECORD_NO = "default"

# Keys and groups in ``app_settings``. App info is addressed by its own key and
# grouped apart so the configuration read can load every settings group without
# picking it up.
APP_INFO_KEY = "app_info"
APP_INFO_GROUP = "app"

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
    """Legacy settings source, read only when ``app_settings`` has no row.

    Kept as a read fallback so a database that has not been provisioned yet (or
    that was rolled back to the pre-``app_settings`` revision) still returns the
    stored configuration instead of silently falling back to code defaults.
    """
    return (
        await session.execute(
            select(ModuleRecord).where(
                ModuleRecord.collection == collection,
                ModuleRecord.record_no == SETTINGS_RECORD_NO,
            )
        )
    ).scalars().first()


async def _load_settings(session: AsyncSession, keys: Iterable[str] | None = None) -> dict[str, AppSetting]:
    stmt = select(AppSetting)
    if keys is None:
        stmt = stmt.where(AppSetting.setting_group != APP_INFO_GROUP)
    else:
        stmt = stmt.where(AppSetting.setting_key.in_(tuple(keys)))
    rows = (await session.execute(stmt)).scalars().all()
    return {row.setting_key: row for row in rows}


def _latest_updated_at(records: Iterable[Any]) -> datetime | None:
    stamps = [record.updated_at for record in records if getattr(record, "updated_at", None) is not None]
    return max(stamps) if stamps else None


def _with_timestamp(data: dict[str, Any], updated_at: datetime | None) -> dict[str, Any]:
    payload = dict(data)
    payload["updatedAt"] = updated_at.isoformat() if updated_at is not None else payload.get("updatedAt") or ""
    return payload


async def _mirror_legacy_settings(session: AsyncSession, collection: str, data: dict[str, Any]) -> None:
    """Keep the pre-``app_settings`` module record in step with every write.

    ``app_settings`` is the system of record; this mirror is transitional and
    exists so rolling the application back to a build that predates this table
    still reads the configuration an administrator last saved, rather than a
    frozen pre-migration snapshot. It is safe to delete once the mirror is no
    longer needed.
    """
    record = await _load_record(session, collection)
    if record is None:
        session.add(ModuleRecord(collection=collection, record_no=SETTINGS_RECORD_NO, data=deepcopy(data)))
    else:
        record.data = deepcopy(data)


async def _upsert_setting(
    session: AsyncSession,
    key: str,
    group: str,
    value: dict[str, Any],
    context: RequestContext | None,
    description: str,
) -> AppSetting:
    row = (await session.execute(select(AppSetting).where(AppSetting.setting_key == key))).scalars().first()
    if row is None:
        row = AppSetting(setting_key=key, setting_group=group, setting_value=value, description=description)
        session.add(row)
    else:
        row.setting_group = group
        row.setting_value = value
        row.description = description
    if context is not None and context.user_id is not None:
        row.updated_by_user_id = context.user_id
    return row


async def get_app_info(session: AsyncSession, context: RequestContext | None = None) -> dict:
    row = (await session.execute(select(AppSetting).where(AppSetting.setting_key == APP_INFO_KEY))).scalars().first()
    if row is None:
        legacy = await _load_record(session, APP_INFO_COLLECTION)
        merged = deep_merge(DEFAULT_APP_INFO, legacy.data if legacy else {})
        return _with_timestamp(merged, legacy.updated_at if legacy else None)
    return _with_timestamp(deep_merge(DEFAULT_APP_INFO, row.setting_value or {}), row.updated_at)


async def update_app_info(session: AsyncSession, context: RequestContext | None, patch: dict[str, Any]) -> dict:
    row = (await session.execute(select(AppSetting).where(AppSetting.setting_key == APP_INFO_KEY))).scalars().first()
    current = row.setting_value if row is not None and isinstance(row.setting_value, dict) else None
    if current is None:
        legacy = await _load_record(session, APP_INFO_COLLECTION)
        current = legacy.data if legacy is not None and isinstance(legacy.data, dict) else {}
    row = await _upsert_setting(
        session,
        APP_INFO_KEY,
        APP_INFO_GROUP,
        deep_merge(current, patch or {}),
        context,
        "Application identity, branding and support contacts.",
    )
    await _mirror_legacy_settings(session, APP_INFO_COLLECTION, row.setting_value or {})
    await session.commit()
    await session.refresh(row)
    return _with_timestamp(deep_merge(DEFAULT_APP_INFO, row.setting_value or {}), row.updated_at)


async def reset_app_info(session: AsyncSession, context: RequestContext) -> dict:
    row = (await session.execute(select(AppSetting).where(AppSetting.setting_key == APP_INFO_KEY))).scalars().first()
    if row is not None:
        await session.delete(row)
    legacy = await _load_record(session, APP_INFO_COLLECTION)
    if legacy is not None:
        await session.delete(legacy)
    await session.commit()
    return _with_timestamp(dict(DEFAULT_APP_INFO), None)


async def _current_app_config(session: AsyncSession) -> tuple[dict[str, Any], datetime | None]:
    """Return the stored config payload plus its most recent write timestamp."""
    rows = await _load_settings(session)
    if rows:
        return {key: (row.setting_value or {}) for key, row in rows.items()}, _latest_updated_at(rows.values())
    legacy = await _load_record(session, APP_CONFIG_COLLECTION)
    if legacy is not None and isinstance(legacy.data, dict):
        return dict(legacy.data), legacy.updated_at
    return {}, None


async def get_app_config(session: AsyncSession, context: RequestContext | None = None) -> dict:
    stored, updated_at = await _current_app_config(session)
    merged = deep_merge(DEFAULT_APP_CONFIG, stored)
    merged["localization"] = normalize_localization(merged.get("localization"))
    return _with_timestamp(merged, updated_at)


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
    current, _updated_at = await _current_app_config(session)
    if "localization" in patch:
        localization_patch = patch["localization"]
        if not isinstance(localization_patch, dict):
            validate_localization_patch(localization_patch)
        current_localization = normalize_localization(current.get("localization"))
        patch["localization"] = validate_localization_patch(deep_merge(current_localization, localization_patch))
    data = deep_merge(current, _without_blank_secrets(patch))
    telegram = data.get("telegram")
    if isinstance(telegram, dict) and "messageLanguage" in telegram:
        # Rebind rather than mutate: deep_merge may hand back a reference into
        # the currently stored JSON payload.
        data["telegram"] = {**telegram, "messageLanguage": normalize_message_language(telegram["messageLanguage"])}
    if "backup" in patch:
        _validate_backup_config(deep_merge(DEFAULT_APP_CONFIG["backup"], data.get("backup") or {}))

    # One row per setting group: a write touches only the groups it changes, so
    # two administrators editing different sections cannot overwrite each other.
    rows = await _load_settings(session)
    for group in sorted(key for key, value in data.items() if isinstance(value, dict)):
        row = await _upsert_setting(
            session,
            group,
            group,
            data[group],
            context,
            f"Application settings group '{group}'.",
        )
        rows[group] = row
    await _mirror_legacy_settings(session, APP_CONFIG_COLLECTION, data)
    await session.commit()
    stored, updated_at = await _current_app_config(session)
    merged = deep_merge(DEFAULT_APP_CONFIG, stored)
    merged["localization"] = normalize_localization(merged.get("localization"))
    return _with_timestamp(merged, updated_at)


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
