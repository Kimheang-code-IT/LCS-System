from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import Base, utcnow
from app.core.exceptions import Conflict, NotFound
from app.core.pagination import PageParams, count_query, paged, parse_date
from app.core.serialization import jsonable
from app.modules.archive.models import ArchiveRecord
from app.modules.audit.service import write_audit
from app.modules.auth.models import User
from app.modules.master_data.models import ModuleRecord


@dataclass(frozen=True)
class ArchiveAdapter:
    entity_type: str
    model: type
    reference_field: str
    label: str
    collection: str | None = None


def _registry() -> dict[str, ArchiveAdapter]:
    # Local import avoids coupling model import order to the archive module.
    from app.modules.master_data.models import (
        BusinessParty,
        ContainerType,
        FeeType,
        Place,
        TradeDirection,
        TransportAsset,
        TransportType,
    )

    adapters = (
        ArchiveAdapter("businessParties", BusinessParty, "legal_name", "Business Party"),
        ArchiveAdapter("places", Place, "name", "Place"),
        ArchiveAdapter("tradeDirections", TradeDirection, "name", "Trade Direction"),
        ArchiveAdapter("containerTypes", ContainerType, "name", "Container Type"),
        ArchiveAdapter("transportTypes", TransportType, "name", "Transport Type"),
        ArchiveAdapter("transportAssets", TransportAsset, "identity", "Transport Asset"),
        ArchiveAdapter("feeTypes", FeeType, "name", "Fee Type"),
    )
    return {adapter.entity_type: adapter for adapter in adapters}


ARCHIVABLE_GENERIC_COLLECTIONS = frozenset({"companies", "shipments", "documents", "deliveries", "currencies"})


def adapter_for(entity_type: str) -> ArchiveAdapter:
    adapter = _registry().get(entity_type)
    if adapter is not None:
        return adapter
    if entity_type in ARCHIVABLE_GENERIC_COLLECTIONS:
        return ArchiveAdapter(entity_type, ModuleRecord, "record_no", _humanize(entity_type), entity_type)
    raise NotFound("This entity type is not supported by the archive.")


def _humanize(value: str) -> str:
    output = ""
    for char in value:
        output += f" {char.lower()}" if char.isupper() else char
    return output.replace("_", " ").strip().title()


async def _entity(session: AsyncSession, adapter: ArchiveAdapter, entity_id: int) -> Any | None:
    row = await session.get(adapter.model, entity_id, with_for_update=True)
    if row is not None and adapter.collection and row.collection != adapter.collection:
        return None
    return row


def _safe_snapshot(row: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for column in row.__table__.columns:
        key = column.name
        if key in {"password_hash", "encrypted_password", "password_secret_reference"}:
            continue
        value = getattr(row, key, None)
        if key == "data" and isinstance(value, dict):
            value = {
                field: ("********" if any(token in field.lower() for token in ("password", "secret", "token")) else item)
                for field, item in value.items()
            }
        snapshot[key] = jsonable(value)
    return snapshot


def _owner_id(row: Any) -> int | None:
    value = getattr(row, "created_by_user_id", None)
    if value is None and isinstance(getattr(row, "data", None), dict):
        value = row.data.get("createdByUserId") or row.data.get("created_by_user_id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def archive_record(
    session: AsyncSession,
    context: RequestContext,
    entity_type: str,
    entity_id: int,
) -> ArchiveRecord:
    adapter = adapter_for(entity_type)
    row = await _entity(session, adapter, entity_id)
    if row is None:
        raise NotFound("Record not found.")
    if getattr(row, "deleted_at", None) is not None:
        raise Conflict("ALREADY_ARCHIVED", "The record is already archived.")

    now = utcnow()
    reference = str(getattr(row, adapter.reference_field, None) or f"{adapter.label} #{entity_id}")
    snapshot = _safe_snapshot(row)
    existing = (
        await session.execute(
            select(ArchiveRecord)
            .where(ArchiveRecord.entity_type == entity_type, ArchiveRecord.entity_id == entity_id)
            .with_for_update()
        )
    ).scalars().first()
    if existing is None:
        existing = ArchiveRecord(entity_type=entity_type, entity_id=entity_id, record_reference=reference)
        session.add(existing)
    existing.record_reference = reference
    existing.status = "ARCHIVED"
    existing.deleted_by_user_id = context.user_id
    existing.original_owner_user_id = _owner_id(row)
    existing.deleted_at = now
    existing.restored_by_user_id = None
    existing.restored_at = None
    existing.hard_deleted_by_user_id = None
    existing.hard_deleted_at = None
    existing.snapshot_json = snapshot
    row.deleted_at = now
    row.deleted_by_user_id = context.user_id
    await write_audit(
        session,
        context,
        event_type="ARCHIVE",
        entity_type=entity_type,
        entity_id=entity_id,
        action="DELETE",
        before=snapshot,
        after={"deletedAt": now.isoformat(), "status": "ARCHIVED"},
        metadata={"reference": reference},
    )
    await session.commit()
    return existing


def _serialize(record: ArchiveRecord, deleted_by: str | None, owner: str | None) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "entityType": record.entity_type,
        "module": _humanize(record.entity_type),
        "entityId": str(record.entity_id),
        "reference": record.record_reference,
        "deletedById": str(record.deleted_by_user_id) if record.deleted_by_user_id else None,
        "deletedBy": deleted_by or "System",
        "deletedAt": record.deleted_at.isoformat() if record.deleted_at else None,
        "originalOwnerId": str(record.original_owner_user_id) if record.original_owner_user_id else None,
        "originalOwner": owner or "",
        "status": record.status,
    }


async def list_archived_records(
    session: AsyncSession,
    page: PageParams,
    *,
    entity_type: str | None = None,
    deleted_by_id: int | None = None,
) -> dict[str, Any]:
    deleted_user = User.__table__.alias("deleted_user")
    owner_user = User.__table__.alias("owner_user")
    stmt = (
        select(ArchiveRecord, deleted_user.c.display_name, owner_user.c.display_name)
        .outerjoin(deleted_user, deleted_user.c.id == ArchiveRecord.deleted_by_user_id)
        .outerjoin(owner_user, owner_user.c.id == ArchiveRecord.original_owner_user_id)
        .where(ArchiveRecord.status == "ARCHIVED")
    )
    if entity_type:
        stmt = stmt.where(ArchiveRecord.entity_type == entity_type)
    if deleted_by_id is not None:
        stmt = stmt.where(ArchiveRecord.deleted_by_user_id == deleted_by_id)
    if page.q:
        pattern = f"%{page.q.strip()}%"
        stmt = stmt.where(
            or_(
                ArchiveRecord.record_reference.ilike(pattern),
                ArchiveRecord.entity_type.ilike(pattern),
                cast(ArchiveRecord.entity_id, String).ilike(pattern),
            )
        )
    start = parse_date(page.from_date)
    end = parse_date(page.to_date)
    if start:
        stmt = stmt.where(ArchiveRecord.deleted_at >= datetime.combine(start, time.min, tzinfo=UTC))
    if end:
        stmt = stmt.where(ArchiveRecord.deleted_at <= datetime.combine(end, time.max, tzinfo=UTC))
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(ArchiveRecord.deleted_at.desc(), ArchiveRecord.id.desc())
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).all()
    return paged([_serialize(record, deleted_by, owner) for record, deleted_by, owner in rows], page, total)


async def archive_options(session: AsyncSession) -> dict[str, Any]:
    entity_types = (
        await session.execute(
            select(ArchiveRecord.entity_type)
            .where(ArchiveRecord.status == "ARCHIVED")
            .distinct()
            .order_by(ArchiveRecord.entity_type)
        )
    ).scalars().all()
    users = (
        await session.execute(
            select(User.id, User.display_name)
            .join(ArchiveRecord, ArchiveRecord.deleted_by_user_id == User.id)
            .where(ArchiveRecord.status == "ARCHIVED")
            .distinct()
            .order_by(User.display_name)
        )
    ).all()
    return {
        "entityTypes": [{"value": value, "label": _humanize(value)} for value in entity_types],
        "deletedByUsers": [{"value": str(user_id), "label": name} for user_id, name in users],
    }


async def _archive_entry(session: AsyncSession, entity_type: str, entity_id: int) -> ArchiveRecord:
    record = (
        await session.execute(
            select(ArchiveRecord)
            .where(ArchiveRecord.entity_type == entity_type, ArchiveRecord.entity_id == entity_id)
            .with_for_update()
        )
    ).scalars().first()
    if record is None:
        raise NotFound("Archived record not found.")
    return record


async def get_archived_record(session: AsyncSession, entity_type: str, entity_id: int) -> dict[str, Any]:
    record = await _archive_entry(session, entity_type, entity_id)
    if record.status != "ARCHIVED":
        raise Conflict("ARCHIVE_NOT_ACTIVE", f"This archive entry is already {record.status.lower().replace('_', ' ')}.")
    deleted_by = await session.get(User, record.deleted_by_user_id) if record.deleted_by_user_id else None
    owner = await session.get(User, record.original_owner_user_id) if record.original_owner_user_id else None
    return {
        **_serialize(record, deleted_by.display_name if deleted_by else None, owner.display_name if owner else None),
        "data": record.snapshot_json or {},
    }


def _model_for_table(table_name: str) -> type | None:
    for mapper in Base.registry.mappers:
        if mapper.local_table.name == table_name:
            return mapper.class_
    return None


async def _restore_conflict(session: AsyncSession, row: Any) -> str | None:
    table = row.__table__
    for constraint in table.constraints:
        columns = list(getattr(constraint, "columns", []))
        if constraint.__class__.__name__ != "UniqueConstraint" or not columns:
            continue
        predicates = [getattr(row.__class__, column.name) == getattr(row, column.name) for column in columns]
        predicates.append(row.__class__.id != row.id)
        if hasattr(row.__class__, "deleted_at"):
            predicates.append(row.__class__.deleted_at.is_(None))
        if await session.scalar(select(func.count()).select_from(row.__class__).where(and_(*predicates))):
            return "An active record already uses the same unique value."
    for foreign_key in table.foreign_keys:
        if foreign_key.parent.name == "deleted_by_user_id":
            continue
        value = getattr(row, foreign_key.parent.name, None)
        if value is None:
            continue
        parent_model = _model_for_table(foreign_key.column.table.name)
        if parent_model is None or not hasattr(parent_model, "deleted_at"):
            continue
        parent = await session.get(parent_model, value)
        if parent is None:
            return f"Required dependency {foreign_key.column.table.name} no longer exists."
        if parent.deleted_at is not None:
            return f"Required dependency {foreign_key.column.table.name} is still archived."
    return None


async def restore_record(
    session: AsyncSession, context: RequestContext, entity_type: str, entity_id: int
) -> dict[str, Any]:
    record = await _archive_entry(session, entity_type, entity_id)
    if record.status != "ARCHIVED":
        raise Conflict("ARCHIVE_NOT_ACTIVE", "The record is no longer archived.")
    adapter = adapter_for(entity_type)
    row = await _entity(session, adapter, entity_id)
    if row is None:
        raise Conflict("RESTORE_IMPOSSIBLE", "The source record was permanently deleted and cannot be restored.")
    if row.deleted_at is None:
        raise Conflict("ALREADY_RESTORED", "The record has already been restored.")
    conflict = await _restore_conflict(session, row)
    if conflict:
        await write_audit(
            session, context, event_type="ARCHIVE", entity_type=entity_type, entity_id=entity_id,
            action="RESTORE", result="FAILED", reason=conflict, metadata={"reference": record.record_reference},
        )
        await session.commit()
        raise Conflict("RESTORE_CONFLICT", conflict)
    before = {"deletedAt": row.deleted_at.isoformat(), "status": "ARCHIVED"}
    row.deleted_at = None
    row.deleted_by_user_id = None
    record.status = "RESTORED"
    record.restored_by_user_id = context.user_id
    record.restored_at = utcnow()
    await write_audit(
        session, context, event_type="ARCHIVE", entity_type=entity_type, entity_id=entity_id,
        action="RESTORE", before=before, after=_safe_snapshot(row), metadata={"reference": record.record_reference},
    )
    await session.commit()
    return {"entityType": entity_type, "entityId": str(entity_id), "status": "RESTORED"}


async def _dependency_names(session: AsyncSession, row: Any) -> list[str]:
    found: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name in {"archive_records", "audit_events"}:
            continue
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table.name != row.__table__.name or foreign_key.column.name != "id":
                continue
            count = await session.scalar(select(func.count()).select_from(table).where(foreign_key.parent == row.id))
            if count:
                found.append(f"{table.name} ({count})")
    return sorted(set(found))


async def hard_delete_record(
    session: AsyncSession, context: RequestContext, entity_type: str, entity_id: int
) -> dict[str, Any]:
    record = await _archive_entry(session, entity_type, entity_id)
    if record.status != "ARCHIVED":
        raise Conflict("ARCHIVE_NOT_ACTIVE", "The record is no longer archived.")
    adapter = adapter_for(entity_type)
    row = await _entity(session, adapter, entity_id)
    if row is None:
        raise Conflict("ALREADY_HARD_DELETED", "The source record has already been permanently deleted.")
    dependencies = await _dependency_names(session, row)
    if dependencies:
        reason = f"Permanent deletion is blocked by related data: {', '.join(dependencies)}."
        await write_audit(
            session, context, event_type="ARCHIVE", entity_type=entity_type, entity_id=entity_id,
            action="HARD_DELETE", result="FAILED", reason=reason, metadata={"reference": record.record_reference},
        )
        await session.commit()
        raise Conflict("HARD_DELETE_BLOCKED", reason)
    await write_audit(
        session, context, event_type="ARCHIVE", entity_type=entity_type, entity_id=entity_id,
        action="HARD_DELETE", before=record.snapshot_json, after={"status": "HARD_DELETED"},
        metadata={"reference": record.record_reference},
    )
    record.status = "HARD_DELETED"
    record.hard_deleted_by_user_id = context.user_id
    record.hard_deleted_at = utcnow()
    await session.delete(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        await write_audit(
            session, context, event_type="ARCHIVE", entity_type=entity_type, entity_id=entity_id,
            action="HARD_DELETE", result="FAILED", reason="A database relationship still references this record.",
            metadata={"reference": record.record_reference},
        )
        await session.commit()
        raise Conflict("HARD_DELETE_BLOCKED", "A database relationship still references this record.") from exc
    return {"entityType": entity_type, "entityId": str(entity_id), "status": "HARD_DELETED"}
