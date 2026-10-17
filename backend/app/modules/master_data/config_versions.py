"""Publish, preview and retire dynamic Service Order configuration versions.

Editing a tab, group or attribute changes how *every* Service Order renders, so a
saved order would silently change meaning when the form moves underneath it. A
published ``ConfigurationVersion`` freezes the layout: its ``config_snapshot``
records the tabs, groups and attributes that existed at publish time, and the
rows that participated carry its ``config_version_id``.

Only one version is live at a time — publishing retires the previous one and
stamps the current tabs. Publishing is idempotent when nothing changed: the
snapshot is compared first, so re-publishing an unchanged configuration does not
create an empty revision.

Nothing in a snapshot is executed. It is configuration data, and every submitted
value is still validated against the live rules before it is stored.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.context import RequestContext
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, list_sort_orders, paged
from app.core.serialization import jsonable
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
)
from app.modules.operations.models import ServiceOrder


def serialize(version: ConfigurationVersion, *, include_snapshot: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(version.id),
        "versionNo": version.version_no,
        "status": version.status,
        "changeNote": version.change_note,
        "publishedAt": version.published_at.isoformat() if version.published_at else None,
        "publishedByUserId": str(version.published_by_user_id) if version.published_by_user_id else None,
        "tabCount": len((version.config_snapshot or {}).get("tabs") or []),
        "createdAt": version.created_at.isoformat() if version.created_at else None,
        "updatedAt": version.updated_at.isoformat() if version.updated_at else None,
    }
    if include_snapshot:
        payload["configSnapshot"] = version.config_snapshot or {}
    return payload


async def live_snapshot(session: AsyncSession) -> dict[str, Any]:
    """Build the snapshot that a publish would store, without writing anything.

    Reused by the preview endpoint so an administrator can review the exact
    configuration that would be published.
    """
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
        attributes_by_group.setdefault(membership.group_id, []).append(
            attribute_entry(
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
                {"is_required": membership.is_required, "display_order": membership.display_order},
            )
        )

    groups_by_tab: dict[int, list[dict[str, Any]]] = {}
    for link, group in tab_groups:
        groups_by_tab.setdefault(link.tab_id, []).append(
            group_entry(
                {
                    "id": group.id,
                    "code": group.code,
                    "name": group.name,
                    "name_km": group.name_km,
                    "render_mode": group.render_mode,
                },
                attributes_by_group.get(group.id, []),
                link.display_order,
            )
        )

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


async def _published_version(session: AsyncSession) -> ConfigurationVersion | None:
    return (
        await session.execute(
            select(ConfigurationVersion).where(ConfigurationVersion.status == "PUBLISHED")
        )
    ).scalars().first()


async def current_published_id(session: AsyncSession) -> int | None:
    """The live configuration version, or ``None`` when nothing is published."""
    version = await _published_version(session)
    return version.id if version is not None else None


async def list_versions(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(ConfigurationVersion)
    if page.status:
        stmt = stmt.where(ConfigurationVersion.status == str(page.status).strip().upper())
    total = await count_query(session, stmt)
    orders = list_sort_orders(ConfigurationVersion, page, ConfigurationVersion.version_no.desc())
    rows = (
        await session.execute(stmt.order_by(*orders).limit(page.page_size).offset(page.offset))
    ).scalars().all()
    return paged([serialize(row) for row in rows], page, total)


async def get_version(session: AsyncSession, context: RequestContext, version_id: int) -> dict:
    version = await session.get(ConfigurationVersion, version_id)
    if version is None:
        raise NotFound("Configuration version not found.")
    return serialize(version, include_snapshot=True)


async def preview(session: AsyncSession, context: RequestContext) -> dict:
    """Show what a publish would freeze, without changing anything."""
    snapshot = await live_snapshot(session)
    live = await _published_version(session)
    return {
        "preview": snapshot,
        "tabCount": len(snapshot.get("tabs") or []),
        "currentVersionNo": live.version_no if live is not None else None,
        "unchanged": live is not None and jsonable(live.config_snapshot or {}) == jsonable(snapshot),
    }


async def publish(session: AsyncSession, context: RequestContext, change_note: str | None = None) -> dict:
    """Freeze the live configuration as a new published version.

    The previous ``PUBLISHED`` row becomes ``RETIRED`` so the partial unique
    index keeps holding, and the current tabs are stamped with the new version.
    Historical rows are never re-stamped: a Service Order keeps the version it
    was captured under.
    """
    snapshot = await live_snapshot(session)
    if not snapshot.get("tabs"):
        raise ValidationFailed(
            "There is no active component configuration to publish.",
            {"changeNote": "Create at least one active tab before publishing."},
        )

    live = await _published_version(session)
    if live is not None and jsonable(live.config_snapshot or {}) == jsonable(snapshot):
        raise Conflict(
            "CONFIGURATION_UNCHANGED",
            "The active configuration matches the published version; nothing to publish.",
        )

    # Serialise concurrent publishes: two administrators publishing at the same
    # moment must not both allocate the same version number, and the partial
    # unique index must never see two PUBLISHED rows.
    await session.execute(
        select(ConfigurationVersion.id)
        .order_by(ConfigurationVersion.version_no.desc())
        .limit(1)
        .with_for_update()
    )

    if live is not None:
        live.status = "RETIRED"
        await session.flush()

    highest = (
        await session.execute(select(ConfigurationVersion.version_no).order_by(ConfigurationVersion.version_no.desc()))
    ).scalars().first()
    version = ConfigurationVersion(
        version_no=(highest or 0) + 1,
        status="PUBLISHED",
        change_note=change_note or None,
        config_snapshot=snapshot,
        published_at=datetime.now(UTC),
        published_by_user_id=context.user_id,
    )
    session.add(version)
    try:
        await session.flush()
    except IntegrityError as exc:
        # The lock above should prevent this; if a publish still races, report a
        # conflict instead of leaking a database error to the caller.
        await session.rollback()
        raise Conflict(
            "CONFIGURATION_PUBLISH_CONFLICT",
            "Another configuration was published at the same time; reload and try again.",
        ) from exc

    # Every tab that participates in the published layout is stamped. Archived
    # tabs are excluded because they are not part of the snapshot. Historical
    # Service Order rows are never re-stamped: they keep the version they were
    # captured under.
    await session.execute(
        ComponentTab.__table__.update()
        .where(ComponentTab.is_archived.is_(False))
        .values(config_version_id=version.id)
    )
    await session.commit()
    await cache.bump("master_data")
    return serialize(version, include_snapshot=True)


async def retire(session: AsyncSession, context: RequestContext, version_id: int) -> dict:
    version = await session.get(ConfigurationVersion, version_id)
    if version is None:
        raise NotFound("Configuration version not found.")
    if version.status == "RETIRED":
        return serialize(version)
    if version.status == "PUBLISHED":
        raise Conflict(
            "CANNOT_RETIRE_PUBLISHED",
            "Publish a replacement configuration instead of retiring the live version.",
        )
    version.status = "RETIRED"
    await session.commit()
    return serialize(version)


async def stamp_service_order(session: AsyncSession, order: ServiceOrder) -> None:
    """Pin a new Service Order to the configuration in force when it is created."""
    if order.configuration_version_id is not None:
        return
    version_id = await current_published_id(session)
    if version_id is not None:
        order.configuration_version_id = version_id


async def version_for_order(session: AsyncSession, order: ServiceOrder) -> dict | None:
    """The snapshot a specific order was captured under, for historical rendering."""
    if order.configuration_version_id is None:
        return None
    version = await session.get(ConfigurationVersion, order.configuration_version_id)
    if version is None:
        return None
    return serialize(version, include_snapshot=True)
