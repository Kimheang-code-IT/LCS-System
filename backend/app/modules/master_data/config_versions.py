"""Publish, preview, activate, roll back and compare configuration versions.

Editing a tab, group or attribute changes how *every* Service Order renders, so a
saved order would silently change meaning when the form moves underneath it. A
published ``ConfigurationVersion`` freezes the layout: its ``config_snapshot``
records the tabs, groups and attributes that existed at publish time, and the
rows that participated carry its ``config_version_id``.

Lifecycle:

* ``PUBLISH`` freezes the live configuration as a new sequential version and
  makes it active. The previous active row becomes ``RETIRED``.
* ``ACTIVATE`` makes an existing snapshot active again without creating a new
  version. The snapshot itself is never changed.
* ``ROLLBACK`` copies an older snapshot into a *new* version with
  ``source_version_id`` pointing at the original, then activates it. History is
  never overwritten.

Exactly one row may be ``PUBLISHED`` (the active version) at a time, enforced by
a partial unique index. Every publish/activate/rollback writes an audit event in
the same transaction.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.context import RequestContext
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, list_sort_orders, paged
from app.core.serialization import jsonable
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import write_audit
from app.modules.auth.models import User
from app.modules.master_data.component_config import (
    DATA_CARDINALITIES,
    DATA_TYPES,
    FORM_COLUMN_COUNTS,
    LAYOUT_DISPLAY_MODES,
    REFERENCE_TYPES,
)
from app.modules.master_data.config_compare import compare_snapshots
from app.modules.master_data.config_snapshot import (
    attribute_entry,
    build_snapshot,
    group_entry,
    tab_entry,
)
from app.modules.master_data.models import (
    ComponentAttribute,
    ComponentGroup,
    ComponentGroupAttribute,
    ComponentTab,
    ComponentTabGroup,
    ConfigurationVersion,
    TradeDirection,
)
from app.modules.operations.models import ServiceOrder, ServiceOrderComponentRow

SNAPSHOT_SCHEMA_VERSION = 2
PUBLISH_LOCK_KEY = 774_113_502

LIFECYCLE_EVENT_TYPES = (
    "configuration_version.published",
    "configuration_version.activated",
    "configuration_version.rolled_back",
    "configuration_version.retired",
    "configuration_version.updated",
    "configuration_version.deleted",
)


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    """Stable content hash: JSON key order and whitespace never affect it."""
    canonical = json.dumps(jsonable(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tab_count(version: ConfigurationVersion) -> int:
    return len((version.config_snapshot or {}).get("tabs") or [])


def _group_count(version: ConfigurationVersion) -> int:
    return sum(
        len(tab.get("groups") or [])
        for tab in (version.config_snapshot or {}).get("tabs") or []
        if isinstance(tab, dict)
    )


def _attribute_count(version: ConfigurationVersion) -> int:
    return sum(
        len(group.get("attributes") or [])
        for tab in (version.config_snapshot or {}).get("tabs") or []
        if isinstance(tab, dict)
        for group in tab.get("groups") or []
        if isinstance(group, dict)
    )


def serialize(
    version: ConfigurationVersion,
    *,
    include_snapshot: bool = False,
    published_by: str | None = None,
    activated_by: str | None = None,
    source_version_no: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(version.id),
        "versionNo": version.version_no,
        "scope": version.scope,
        "origin": version.origin,
        "status": version.status,
        "changeNote": version.change_note,
        # Versions are only created by a publish or rollback action, so the
        # acting user is also the creator; Published By keeps the publish record.
        "createdBy": published_by,
        "publishedAt": version.published_at.isoformat() if version.published_at else None,
        "publishedByUserId": str(version.published_by_user_id) if version.published_by_user_id else None,
        "publishedBy": published_by,
        "activatedAt": version.activated_at.isoformat() if version.activated_at else None,
        "activatedByUserId": str(version.activated_by_user_id) if version.activated_by_user_id else None,
        "activatedBy": activated_by,
        "sourceVersionId": str(version.source_version_id) if version.source_version_id else None,
        "sourceVersionNo": source_version_no,
        "snapshotSchemaVersion": version.snapshot_schema_version,
        "contentHash": version.content_hash,
        "tabCount": _tab_count(version),
        "groupCount": _group_count(version),
        "attributeCount": _attribute_count(version),
        "createdAt": version.created_at.isoformat() if version.created_at else None,
        "updatedAt": version.updated_at.isoformat() if version.updated_at else None,
    }
    if include_snapshot:
        payload["configSnapshot"] = version.config_snapshot or {}
    return payload


async def _user_names(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (
        await session.execute(select(User.id, User.display_name).where(User.id.in_(ids)))
    ).all()
    return {int(row[0]): str(row[1]) for row in rows}


async def _version_numbers(session: AsyncSession, ids: set[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(ConfigurationVersion.id, ConfigurationVersion.version_no).where(ConfigurationVersion.id.in_(ids))
        )
    ).all()
    return {int(row[0]): int(row[1]) for row in rows}


async def _serialize_rows(session: AsyncSession, versions: list[ConfigurationVersion]) -> list[dict[str, Any]]:
    user_ids = {
        user_id
        for version in versions
        for user_id in (version.published_by_user_id, version.activated_by_user_id)
        if user_id is not None
    }
    names = await _user_names(session, user_ids)
    source_ids = {version.source_version_id for version in versions if version.source_version_id is not None}
    numbers = await _version_numbers(session, source_ids)
    return [
        serialize(
            version,
            published_by=names.get(version.published_by_user_id or 0),
            activated_by=names.get(version.activated_by_user_id or 0),
            source_version_no=numbers.get(version.source_version_id or 0),
        )
        for version in versions
    ]


async def _serialize_one(session: AsyncSession, version: ConfigurationVersion, *, include_snapshot: bool = False) -> dict[str, Any]:
    user_ids = {
        user_id
        for user_id in (version.published_by_user_id, version.activated_by_user_id)
        if user_id is not None
    }
    names = await _user_names(session, user_ids)
    numbers = await _version_numbers(
        session, {version.source_version_id} if version.source_version_id is not None else set()
    )
    return serialize(
        version,
        include_snapshot=include_snapshot,
        published_by=names.get(version.published_by_user_id or 0),
        activated_by=names.get(version.activated_by_user_id or 0),
        source_version_no=numbers.get(version.source_version_id or 0),
    )


async def trade_direction_names(session: AsyncSession, snapshot: dict[str, Any]) -> dict[str, str]:
    ids: set[int] = set()
    for tab in snapshot.get("tabs") or []:
        if not isinstance(tab, dict):
            continue
        raw = tab.get("tradeDirectionId")
        if raw in (None, ""):
            continue
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    if not ids:
        return {}
    rows = (
        await session.execute(select(TradeDirection.id, TradeDirection.name).where(TradeDirection.id.in_(ids)))
    ).all()
    return {str(row[0]): str(row[1]) for row in rows}


async def live_snapshot(session: AsyncSession) -> dict[str, Any]:
    """Build the snapshot that a publish would store, without writing anything."""
    tabs = list(
        (
            await session.execute(
                select(ComponentTab)
                .where(ComponentTab.is_active.is_(True), ComponentTab.is_archived.is_(False))
                .order_by(ComponentTab.display_order, ComponentTab.id)
            )
        ).scalars().all()
    )
    if not tabs:
        return {"tabs": []}

    tab_groups = (
        await session.execute(
            select(ComponentTabGroup, ComponentGroup)
            .join(ComponentGroup, ComponentGroup.id == ComponentTabGroup.group_id)
            .where(
                ComponentTabGroup.tab_id.in_([tab.id for tab in tabs]),
                ComponentTabGroup.status == "ACTIVE",
                ComponentGroup.is_active.is_(True),
                ComponentGroup.is_archived.is_(False),
            )
            .order_by(ComponentTabGroup.display_order, ComponentTabGroup.id)
        )
    ).all()

    group_ids = sorted({group.id for _link, group in tab_groups})
    memberships = (
        await session.execute(
            select(ComponentGroupAttribute, ComponentAttribute)
            .join(ComponentAttribute, ComponentAttribute.id == ComponentGroupAttribute.attribute_id)
            .where(
                ComponentGroupAttribute.group_id.in_(group_ids),
                ComponentGroupAttribute.status == "ACTIVE",
                ComponentAttribute.status == "ACTIVE",
            )
            .order_by(ComponentGroupAttribute.display_order, ComponentGroupAttribute.id)
        )
    ).all() if group_ids else []

    attributes_by_group: dict[int, list[dict[str, Any]]] = {}
    for membership, attribute in memberships:
        entry = attribute_entry(
            {
                "id": attribute.id,
                "code": attribute.code,
                "label": attribute.label,
                "label_km": attribute.label_km,
                "data_type": attribute.data_type,
                "input_type": attribute.input_type,
                "reference_type": attribute.reference_type,
                "is_required": attribute.is_required,
                "default_value": attribute.default_value,
                "placeholder": attribute.placeholder,
                "options": attribute.options,
                "validation_rules": attribute.validation_rules,
            },
            {
                "is_required": membership.is_required,
                "is_visible": membership.is_visible,
                "display_order": membership.display_order,
            },
        )
        # Table-column width is rendering metadata; older snapshots simply lack it.
        entry["width"] = attribute.width
        attributes_by_group.setdefault(membership.group_id, []).append(entry)

    groups_by_tab: dict[int, list[dict[str, Any]]] = {}
    for link, group in tab_groups:
        entry = group_entry(
            {
                "id": group.id,
                "code": group.code,
                "name": group.name,
                "name_km": group.name_km,
                "render_mode": group.render_mode,
            },
            attributes_by_group.get(group.id, []),
            link.display_order,
            {
                "displayMode": link.display_mode,
                "dataCardinality": link.data_cardinality,
                "formColumns": link.form_columns,
                "showGroupTitle": link.show_group_title,
                "editable": link.editable,
                "collapsible": link.collapsible,
                "defaultExpanded": link.default_expanded,
            },
        )
        # The per-tab assignment id is what namespaced saves use; preserving it
        # keeps a historical order editable with the layout it was captured under.
        entry["tabGroupId"] = str(link.id)
        groups_by_tab.setdefault(link.tab_id, []).append(entry)

    return build_snapshot(
        [
            tab_entry(
                {
                    "id": tab.id,
                    "code": tab.code,
                    "name": tab.name,
                    "trade_direction_id": tab.trade_direction_id,
                },
                groups_by_tab.get(tab.id, []),
                tab.display_order,
            )
            for tab in tabs
        ]
    )


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, str]:
    """Return field-keyed reasons the live configuration cannot be published."""
    errors: dict[str, str] = {}
    tabs = snapshot.get("tabs") or []
    if not tabs:
        errors["tabs"] = "Create at least one active tab before publishing."
        # Kept for clients that attached the old empty-configuration refusal to
        # the publish form; the field still explains the same problem.
        errors.setdefault("changeNote", "Create at least one active tab before publishing.")
        return errors

    for tab_index, tab in enumerate(tabs):
        prefix = f"tabs.{tab_index}"
        if not str(tab.get("code") or "").strip():
            errors[f"{prefix}.code"] = "Required"
        if not str(tab.get("name") or "").strip():
            errors[f"{prefix}.name"] = "Required"
        for group_index, group in enumerate(tab.get("groups") or []):
            group_prefix = f"{prefix}.groups.{group_index}"
            if not str(group.get("code") or "").strip():
                errors[f"{group_prefix}.code"] = "Required"
            if not str(group.get("name") or "").strip():
                errors[f"{group_prefix}.name"] = "Required"
            display_mode = str(group.get("displayMode") or "").strip()
            cardinality = str(group.get("dataCardinality") or "").strip()
            if display_mode not in LAYOUT_DISPLAY_MODES:
                errors[f"{group_prefix}.displayMode"] = "Unsupported"
            if cardinality not in DATA_CARDINALITIES:
                errors[f"{group_prefix}.dataCardinality"] = "Unsupported"
            if display_mode == "form_only" and cardinality == "multiple":
                errors[f"{group_prefix}.dataCardinality"] = "A form-only group can hold one record."
            try:
                columns = int(group.get("formColumns") or 0)
            except (TypeError, ValueError):
                columns = 0
            if columns not in FORM_COLUMN_COUNTS:
                errors[f"{group_prefix}.formColumns"] = "Must be 1, 2, 3 or 4."

            seen_codes: set[str] = set()
            for attribute_index, attribute in enumerate(group.get("attributes") or []):
                attribute_prefix = f"{group_prefix}.attributes.{attribute_index}"
                code = str(attribute.get("code") or "").strip()
                if not code:
                    errors[f"{attribute_prefix}.code"] = "Required"
                elif code in seen_codes:
                    errors[f"{attribute_prefix}.code"] = "Duplicate attribute in this group."
                seen_codes.add(code)
                if not str(attribute.get("label") or "").strip():
                    errors[f"{attribute_prefix}.label"] = "Required"
                data_type = str(attribute.get("dataType") or "").strip()
                if data_type not in DATA_TYPES:
                    errors[f"{attribute_prefix}.dataType"] = "Unsupported"
                reference_type = attribute.get("referenceType")
                if data_type == "reference" and reference_type not in REFERENCE_TYPES:
                    errors[f"{attribute_prefix}.referenceType"] = "Required"
    return errors


async def _published_version(session: AsyncSession, *, for_update: bool = False) -> ConfigurationVersion | None:
    stmt = select(ConfigurationVersion).where(ConfigurationVersion.status == "PUBLISHED")
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalars().first()


async def current_published_id(session: AsyncSession) -> int | None:
    """The live configuration version, or ``None`` when nothing is published."""
    version = await _published_version(session)
    return version.id if version is not None else None


async def _lock_publish(session: AsyncSession) -> None:
    """Serialise version allocation across concurrent publish requests.

    PostgreSQL gets an advisory transaction lock, which also covers the empty
    table case where there is no row to lock. Other dialects fall back to locking
    the newest row; the unique version-number constraint remains the final guard.
    """
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": PUBLISH_LOCK_KEY})
    await session.execute(
        select(ConfigurationVersion.id)
        .order_by(ConfigurationVersion.version_no.desc())
        .limit(1)
        .with_for_update()
    )


async def _next_version_no(session: AsyncSession) -> int:
    highest = (
        await session.execute(select(func.max(ConfigurationVersion.version_no)))
    ).scalar()
    return int(highest or 0) + 1


async def list_versions(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(ConfigurationVersion)
    if page.status:
        stmt = stmt.where(ConfigurationVersion.status == str(page.status).strip().upper())
    if page.q:
        needle = f"%{page.q.strip()}%"
        stmt = stmt.where(
            or_(
                ConfigurationVersion.change_note.ilike(needle),
                cast(ConfigurationVersion.version_no, String).ilike(needle),
            )
        )
    total = await count_query(session, stmt)
    orders = list_sort_orders(
        ConfigurationVersion,
        page,
        ConfigurationVersion.version_no.desc(),
        aliases={
            "publishedBy": ConfigurationVersion.published_by_user_id,
            "sourceVersionNo": ConfigurationVersion.source_version_id,
        },
    )
    rows = (
        await session.execute(stmt.order_by(*orders).limit(page.page_size).offset(page.offset))
    ).scalars().all()
    return paged(await _serialize_rows(session, list(rows)), page, total)


async def get_version(session: AsyncSession, context: RequestContext, version_id: int) -> dict:
    version = await session.get(ConfigurationVersion, version_id)
    if version is None:
        raise NotFound("Configuration version not found.")
    payload = await _serialize_one(session, version, include_snapshot=True)
    payload["tradeDirections"] = await trade_direction_names(session, version.config_snapshot or {})
    return payload


async def active_version(session: AsyncSession, context: RequestContext) -> dict | None:
    version = await _published_version(session)
    if version is None:
        return None
    payload = await _serialize_one(session, version, include_snapshot=True)
    payload["tradeDirections"] = await trade_direction_names(session, version.config_snapshot or {})
    return payload


async def preview(session: AsyncSession, context: RequestContext) -> dict:
    """Show what a publish would freeze, without changing anything."""
    snapshot = await live_snapshot(session)
    live = await _published_version(session)
    return {
        "preview": snapshot,
        "tabCount": len(snapshot.get("tabs") or []),
        "currentVersionNo": live.version_no if live is not None else None,
        "unchanged": live is not None and jsonable(live.config_snapshot or {}) == jsonable(snapshot),
        "tradeDirections": await trade_direction_names(session, snapshot),
    }


async def preview_version(session: AsyncSession, context: RequestContext, version_id: int) -> dict:
    return await get_version(session, context, version_id)


async def publish(session: AsyncSession, context: RequestContext, change_note: str | None = None) -> dict:
    """Freeze the live configuration as a new published version."""
    snapshot = await live_snapshot(session)
    errors = validate_snapshot(snapshot)
    if errors:
        raise ValidationFailed("The live configuration cannot be published.", errors)

    live = await _published_version(session)
    if live is not None and jsonable(live.config_snapshot or {}) == jsonable(snapshot):
        raise Conflict(
            "CONFIGURATION_UNCHANGED",
            "The active configuration matches the published version; nothing to publish.",
        )

    await _lock_publish(session)
    live = await _published_version(session)
    if live is not None and jsonable(live.config_snapshot or {}) == jsonable(snapshot):
        raise Conflict(
            "CONFIGURATION_UNCHANGED",
            "The active configuration matches the published version; nothing to publish.",
        )
    if live is not None:
        live.status = "RETIRED"
        await session.flush()

    note = str(change_note).strip() if change_note else None
    version = ConfigurationVersion(
        version_no=await _next_version_no(session),
        scope="GLOBAL",
        status="PUBLISHED",
        origin="PUBLISH",
        change_note=note or None,
        config_snapshot=snapshot,
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        content_hash=snapshot_hash(snapshot),
        published_at=datetime.now(UTC),
        published_by_user_id=context.user_id,
        activated_at=datetime.now(UTC),
        activated_by_user_id=context.user_id,
    )
    session.add(version)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict(
            "CONFIGURATION_PUBLISH_CONFLICT",
            "Another configuration was published at the same time; reload and try again.",
        ) from exc

    await _stamp_live_tabs(session, version.id)
    await write_audit(
        session,
        context,
        event_type="configuration_version.published",
        entity_type="configuration_version",
        entity_id=version.id,
        action="PUBLISH",
        reason=note,
        before={"activeVersionId": str(live.id) if live is not None else None},
        after={"versionNo": version.version_no, "versionId": str(version.id)},
        metadata={"contentHash": version.content_hash},
    )
    await session.commit()
    await cache.bump("master_data")
    return await _serialize_one(session, version, include_snapshot=True)


async def _stamp_live_tabs(session: AsyncSession, version_id: int) -> None:
    """Point the live tabs at the active version. Historical rows stay untouched."""
    await session.execute(
        ComponentTab.__table__.update()
        .where(ComponentTab.is_archived.is_(False))
        .values(config_version_id=version_id)
    )


async def _get_version_for_update(session: AsyncSession, version_id: int) -> ConfigurationVersion:
    version = (
        await session.execute(
            select(ConfigurationVersion).where(ConfigurationVersion.id == version_id).with_for_update()
        )
    ).scalars().first()
    if version is None:
        raise NotFound("Configuration version not found.")
    return version


def _ensure_activatable(version: ConfigurationVersion) -> None:
    if version.status == "DRAFT":
        raise Conflict(
            "CONFIGURATION_VERSION_NOT_PUBLISHED",
            "Only a published or retired version can be activated.",
        )
    if not (version.config_snapshot or {}).get("tabs"):
        raise Conflict(
            "CONFIGURATION_VERSION_INCOMPATIBLE",
            "This version has no tab configuration and cannot be activated.",
        )


async def activate(session: AsyncSession, context: RequestContext, version_id: int) -> dict:
    """Make an existing published version active again without altering its snapshot."""
    await _lock_publish(session)
    target = await _get_version_for_update(session, version_id)
    _ensure_activatable(target)

    current = await _published_version(session, for_update=True)
    if current is not None and current.id == target.id:
        return await _serialize_one(session, target, include_snapshot=True)

    previous_status = target.status
    if current is not None and current.scope != target.scope:
        raise Conflict(
            "CONFIGURATION_VERSION_INCOMPATIBLE",
            "This version belongs to a different configuration scope and cannot be activated here.",
        )
    if current is not None:
        current.status = "RETIRED"
        await session.flush()

    target.status = "PUBLISHED"
    target.activated_at = datetime.now(UTC)
    target.activated_by_user_id = context.user_id
    await session.flush()

    await _stamp_live_tabs(session, target.id)
    await write_audit(
        session,
        context,
        event_type="configuration_version.activated",
        entity_type="configuration_version",
        entity_id=target.id,
        action="ACTIVATE",
        before={
            "activeVersionId": str(current.id) if current is not None else None,
            "targetStatus": previous_status,
        },
        after={"versionNo": target.version_no, "versionId": str(target.id)},
    )
    await session.commit()
    await cache.bump("master_data")
    return await _serialize_one(session, target, include_snapshot=True)


async def rollback(
    session: AsyncSession,
    context: RequestContext,
    version_id: int,
    reason: str,
) -> dict:
    """Publish a *new* version whose snapshot is copied from an older one."""
    note = str(reason or "").strip()
    if not note:
        raise ValidationFailed("A rollback reason is required.", {"reason": "Required"})

    await _lock_publish(session)
    target = await _get_version_for_update(session, version_id)
    _ensure_activatable(target)

    current = await _published_version(session, for_update=True)
    if current is not None and current.id == target.id:
        raise Conflict(
            "CONFIGURATION_VERSION_ALREADY_ACTIVE",
            "That version is already active; choose an older version to roll back to.",
        )

    snapshot = jsonable(target.config_snapshot or {})
    if current is not None and current.scope != target.scope:
        raise Conflict(
            "CONFIGURATION_VERSION_INCOMPATIBLE",
            "This version belongs to a different configuration scope and cannot be rolled back here.",
        )
    if current is not None:
        current.status = "RETIRED"
        await session.flush()

    version = ConfigurationVersion(
        version_no=await _next_version_no(session),
        scope=target.scope,
        status="PUBLISHED",
        origin="ROLLBACK",
        change_note=note,
        config_snapshot=snapshot,
        snapshot_schema_version=target.snapshot_schema_version or SNAPSHOT_SCHEMA_VERSION,
        content_hash=target.content_hash or snapshot_hash(snapshot),
        source_version_id=target.id,
        published_at=datetime.now(UTC),
        published_by_user_id=context.user_id,
        activated_at=datetime.now(UTC),
        activated_by_user_id=context.user_id,
    )
    session.add(version)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict(
            "CONFIGURATION_PUBLISH_CONFLICT",
            "Another configuration was published at the same time; reload and try again.",
        ) from exc

    await _stamp_live_tabs(session, version.id)
    await write_audit(
        session,
        context,
        event_type="configuration_version.rolled_back",
        entity_type="configuration_version",
        entity_id=version.id,
        action="ROLLBACK",
        reason=note,
        before={
            "activeVersionId": str(current.id) if current is not None else None,
            "sourceVersionId": str(target.id),
            "sourceVersionNo": target.version_no,
        },
        after={"versionNo": version.version_no, "versionId": str(version.id)},
    )
    await session.commit()
    await cache.bump("master_data")
    return await _serialize_one(session, version, include_snapshot=True)


async def compare(
    session: AsyncSession,
    context: RequestContext,
    version_id: int,
    other_version_id: int,
) -> dict:
    left = await session.get(ConfigurationVersion, version_id)
    right = await session.get(ConfigurationVersion, other_version_id)
    if left is None:
        raise NotFound("Configuration version not found.")
    if right is None:
        raise NotFound("Comparison configuration version not found.")
    changes = compare_snapshots(left.config_snapshot or {}, right.config_snapshot or {})
    return {
        "from": await _serialize_one(session, left),
        "to": await _serialize_one(session, right),
        "changes": changes,
        "tradeDirections": await trade_direction_names(session, right.config_snapshot or {}),
    }


async def activation_history(
    session: AsyncSession,
    context: RequestContext,
    page: PageParams,
    version_id: int | None = None,
) -> dict:
    stmt = (
        select(AuditEvent, User.display_name)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.entity_type == "configuration_version")
        .where(AuditEvent.event_type.in_(LIFECYCLE_EVENT_TYPES))
    )
    if version_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == version_id)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).all()
    items = [
        {
            "id": str(event.id),
            "occurredAt": event.occurred_at.isoformat() if event.occurred_at else None,
            "eventType": event.event_type,
            "entityId": str(event.entity_id),
            "action": event.action,
            "result": event.result,
            "reason": event.reason,
            "user": display_name or (str(event.actor_user_id) if event.actor_user_id else ""),
            "before": event.before_json,
            "after": event.after_json,
            "metadata": event.metadata_json,
        }
        for event, display_name in rows
    ]
    return paged(items, page, total)


async def retire(session: AsyncSession, context: RequestContext, version_id: int) -> dict:
    version = await session.get(ConfigurationVersion, version_id)
    if version is None:
        raise NotFound("Configuration version not found.")
    if version.status == "RETIRED":
        return await _serialize_one(session, version)
    if version.status == "PUBLISHED":
        raise Conflict(
            "CANNOT_RETIRE_PUBLISHED",
            "Activate another configuration instead of retiring the live version.",
        )
    version.status = "RETIRED"
    await write_audit(
        session,
        context,
        event_type="configuration_version.retired",
        entity_type="configuration_version",
        entity_id=version.id,
        action="RETIRE",
        before={"status": "DRAFT"},
        after={"status": "RETIRED"},
    )
    await session.commit()
    return await _serialize_one(session, version)


async def update_draft(
    session: AsyncSession,
    context: RequestContext,
    version_id: int,
    change_note: str,
) -> dict:
    """Rename a draft. Published and retired snapshots stay immutable."""
    version = await _get_version_for_update(session, version_id)
    if version.status != "DRAFT":
        raise Conflict(
            "CONFIGURATION_VERSION_IMMUTABLE",
            "Published configuration versions are immutable; roll back to create a new version instead.",
        )
    note = str(change_note or "").strip()
    if not note:
        raise ValidationFailed("A version name is required.", {"changeNote": "Required"})

    previous = version.change_note
    version.change_note = note
    await write_audit(
        session,
        context,
        event_type="configuration_version.updated",
        entity_type="configuration_version",
        entity_id=version.id,
        action="UPDATE",
        before={"changeNote": previous},
        after={"changeNote": note},
    )
    await session.commit()
    await cache.bump("master_data")
    return await _serialize_one(session, version, include_snapshot=True)


async def delete_draft(session: AsyncSession, context: RequestContext, version_id: int) -> dict:
    """Discard a draft that was never published and no record points at."""
    version = await _get_version_for_update(session, version_id)
    if version.status != "DRAFT":
        raise Conflict(
            "CONFIGURATION_VERSION_NOT_DELETABLE",
            "Only a draft version can be deleted; published and retired versions preserve their history.",
        )

    references = (
        ("a Service Order", select(func.count()).select_from(ServiceOrder).where(
            ServiceOrder.configuration_version_id == version_id
        )),
        ("a component row", select(func.count()).select_from(ServiceOrderComponentRow).where(
            ServiceOrderComponentRow.config_version_id == version_id
        )),
        ("a live tab", select(func.count()).select_from(ComponentTab).where(
            ComponentTab.config_version_id == version_id
        )),
        ("another version", select(func.count()).select_from(ConfigurationVersion).where(
            ConfigurationVersion.source_version_id == version_id
        )),
    )
    for label, stmt in references:
        count = int((await session.execute(stmt)).scalar() or 0)
        if count:
            raise Conflict(
                "CONFIGURATION_VERSION_REFERENCED",
                f"This draft is referenced by {label} and cannot be deleted.",
            )

    snapshot = {"versionNo": version.version_no, "changeNote": version.change_note}
    version_no = version.version_no
    await session.delete(version)
    await session.flush()
    await write_audit(
        session,
        context,
        event_type="configuration_version.deleted",
        entity_type="configuration_version",
        entity_id=version_id,
        action="DELETE",
        before=snapshot,
        after={"versionNo": version_no, "deleted": True},
    )
    await session.commit()
    await cache.bump("master_data")
    return {"removed": 1, "id": str(version_id)}


async def stamp_service_order(session: AsyncSession, order: ServiceOrder) -> None:
    """Pin a new Service Order to the configuration in force when it is created."""
    if order.configuration_version_id is not None:
        return
    version_id = await current_published_id(session)
    if version_id is not None:
        order.configuration_version_id = version_id


async def version_for_order(session: AsyncSession, order: ServiceOrder) -> dict | None:
    """The snapshot a specific order was captured under, for historical rendering.

    Orders created before configuration versioning have no pointer. They keep
    rendering from live configuration and are never guessed onto an old version;
    assigning one automatically could mislabel their layout.
    """
    if order.configuration_version_id is None:
        return None
    version = await session.get(ConfigurationVersion, order.configuration_version_id)
    if version is None:
        return None
    return await _serialize_one(session, version, include_snapshot=True)
