"""Structural comparison of two published configuration snapshots.

Identity is the stable database id recorded in the snapshot (tab id, group id,
attribute id), never array position. Position only matters for the explicit
"group ordering" result, where it is the thing being compared.

The module is framework-free so the comparison can be tested without a database
and reused by the preview screen later.
"""

from __future__ import annotations

from typing import Any

Layout = dict[str, Any]
Snapshot = dict[str, Any]

LAYOUT_KEYS = (
    "displayMode",
    "dataCardinality",
    "formColumns",
    "showGroupTitle",
    "editable",
    "collapsible",
    "defaultExpanded",
)


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _key(item: dict[str, Any], kind: str) -> str:
    stable = str(item.get("id") or "").strip()
    if stable:
        return stable
    code = str(item.get("code") or item.get("label") or "").strip()
    return f"{kind}:{code}"


def _label(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("label") or item.get("code") or item.get("id") or "—")


def _layout(item: dict[str, Any]) -> Layout:
    """Effective layout with the pre-layout defaults filled in.

    Snapshots written before per-group layouts existed only carry ``renderMode``.
    Filling the same defaults the runtime uses keeps a version upgrade from
    showing every group as "changed" in a comparison.
    """
    legacy_form = str(item.get("renderMode") or "table") == "form"
    resolved: Layout = {
        "displayMode": "form_only" if legacy_form else "table_only",
        "dataCardinality": "single" if legacy_form else "multiple",
        "formColumns": 3,
        "showGroupTitle": True,
        "editable": True,
        "collapsible": False,
        "defaultExpanded": True,
        "isVisible": True,
    }
    for key in (*LAYOUT_KEYS, "isVisible"):
        if key in item and item.get(key) is not None:
            resolved[key] = item[key]
    return resolved


def _index_tabs(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    return {_key(tab, "tab"): tab for tab in _list(snapshot.get("tabs"))}


def _index_groups(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for tab in _list(snapshot.get("tabs")):
        for group in _list(tab.get("groups")):
            groups.setdefault(_key(group, "group"), group)
    return groups


def _index_attributes(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    attributes: dict[str, dict[str, Any]] = {}
    for group in _index_groups(snapshot).values():
        for attribute in _list(group.get("attributes")):
            attributes.setdefault(_key(attribute, "attribute"), attribute)
    return attributes


def _group_tab_names(snapshot: Snapshot) -> dict[str, str]:
    names: dict[str, str] = {}
    for tab in _list(snapshot.get("tabs")):
        for group in _list(tab.get("groups")):
            names.setdefault(_key(group, "group"), _label(tab))
    return names


def _attribute_group_names(snapshot: Snapshot) -> dict[str, str]:
    names: dict[str, str] = {}
    for group in _index_groups(snapshot).values():
        for attribute in _list(group.get("attributes")):
            names.setdefault(_key(attribute, "attribute"), _label(group))
    return names


def _brief(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "code": item.get("code"),
        "label": _label(item),
    }


def compare_snapshots(before: Snapshot, after: Snapshot) -> dict[str, Any]:
    """Return added, removed, renamed and changed objects between two snapshots."""
    before_tabs = _index_tabs(before)
    after_tabs = _index_tabs(after)
    before_groups = _index_groups(before)
    after_groups = _index_groups(after)
    before_attributes = _index_attributes(before)
    after_attributes = _index_attributes(after)
    group_tabs = _group_tab_names(after) | _group_tab_names(before)
    attribute_groups = _attribute_group_names(after) | _attribute_group_names(before)

    tabs = {
        "added": [_brief(after_tabs[key]) for key in sorted(after_tabs.keys() - before_tabs.keys())],
        "removed": [_brief(before_tabs[key]) for key in sorted(before_tabs.keys() - after_tabs.keys())],
        "renamed": [],
    }
    for key in sorted(before_tabs.keys() & after_tabs.keys()):
        old, new = before_tabs[key], after_tabs[key]
        if old.get("name") != new.get("name") or old.get("code") != new.get("code"):
            tabs["renamed"].append({
                "id": key,
                "before": {"code": old.get("code"), "name": old.get("name")},
                "after": {"code": new.get("code"), "name": new.get("name")},
            })

    groups = {
        "added": [_brief(after_groups[key]) for key in sorted(after_groups.keys() - before_groups.keys())],
        "removed": [_brief(before_groups[key]) for key in sorted(before_groups.keys() - after_groups.keys())],
        "renamed": [],
    }
    for key in sorted(before_groups.keys() & after_groups.keys()):
        old, new = before_groups[key], after_groups[key]
        if old.get("name") != new.get("name") or old.get("code") != new.get("code"):
            groups["renamed"].append({
                "id": key,
                "tab": group_tabs.get(key),
                "before": {"code": old.get("code"), "name": old.get("name")},
                "after": {"code": new.get("code"), "name": new.get("name")},
            })

    attributes = {
        "added": [_brief(after_attributes[key]) for key in sorted(after_attributes.keys() - before_attributes.keys())],
        "removed": [_brief(before_attributes[key]) for key in sorted(before_attributes.keys() - after_attributes.keys())],
        "renamed": [],
    }
    changed_types: list[dict[str, Any]] = []
    changed_required: list[dict[str, Any]] = []
    changed_display_modes: list[dict[str, Any]] = []
    changed_layouts: list[dict[str, Any]] = []

    for key in sorted(before_attributes.keys() & after_attributes.keys()):
        old, new = before_attributes[key], after_attributes[key]
        if old.get("label") != new.get("label") or old.get("code") != new.get("code"):
            attributes["renamed"].append({
                "id": key,
                "group": attribute_groups.get(key),
                "before": {"code": old.get("code"), "label": old.get("label")},
                "after": {"code": new.get("code"), "label": new.get("label")},
            })
        if old.get("dataType") != new.get("dataType"):
            changed_types.append({
                "id": key,
                "group": attribute_groups.get(key),
                "label": _label(new),
                "before": old.get("dataType"),
                "after": new.get("dataType"),
            })
        if bool(old.get("isRequired")) != bool(new.get("isRequired")):
            changed_required.append({
                "id": key,
                "group": attribute_groups.get(key),
                "label": _label(new),
                "before": bool(old.get("isRequired")),
                "after": bool(new.get("isRequired")),
            })
        old_layout, new_layout = _layout(old), _layout(new)
        for field, value in new_layout.items():
            if old_layout.get(field) != value:
                target = changed_layouts
                if field == "isVisible":
                    target = changed_layouts
                target.append({
                    "id": key,
                    "path": f"attributes.{key}.{field}",
                    "group": attribute_groups.get(key),
                    "label": _label(new),
                    "field": field,
                    "before": old_layout.get(field),
                    "after": value,
                })

    for key in sorted(before_groups.keys() & after_groups.keys()):
        old, new = before_groups[key], after_groups[key]
        old_layout, new_layout = _layout(old), _layout(new)
        if old_layout.get("displayMode") != new_layout.get("displayMode"):
            changed_display_modes.append({
                "id": key,
                "tab": group_tabs.get(key),
                "label": _label(new),
                "before": old_layout.get("displayMode"),
                "after": new_layout.get("displayMode"),
            })
        for field in LAYOUT_KEYS:
            if field == "displayMode":
                continue
            if old_layout.get(field) != new_layout.get(field):
                changed_layouts.append({
                    "id": key,
                    "path": f"groups.{key}.{field}",
                    "group": group_tabs.get(key),
                    "label": _label(new),
                    "field": field,
                    "before": old_layout.get(field),
                    "after": new_layout.get(field),
                })

    ordering: list[dict[str, Any]] = []
    for tab_key in sorted(before_tabs.keys() & after_tabs.keys()):
        old_tab, new_tab = before_tabs[tab_key], after_tabs[tab_key]
        old_ids = [_key(group, "group") for group in _list(old_tab.get("groups"))]
        new_ids = [_key(group, "group") for group in _list(new_tab.get("groups"))]
        common = set(old_ids) & set(new_ids)
        old_order = [key for key in old_ids if key in common]
        new_order = [key for key in new_ids if key in common]
        if old_order != new_order:
            ordering.append({
                "tabId": tab_key,
                "tab": _label(new_tab),
                "before": old_order,
                "after": new_order,
            })

    summary = {
        "addedTabs": len(tabs["added"]),
        "removedTabs": len(tabs["removed"]),
        "renamedTabs": len(tabs["renamed"]),
        "addedGroups": len(groups["added"]),
        "removedGroups": len(groups["removed"]),
        "renamedGroups": len(groups["renamed"]),
        "addedAttributes": len(attributes["added"]),
        "removedAttributes": len(attributes["removed"]),
        "renamedAttributes": len(attributes["renamed"]),
        "changedFieldTypes": len(changed_types),
        "changedRequiredRules": len(changed_required),
        "changedDisplayModes": len(changed_display_modes),
        "changedLayouts": len(changed_layouts),
        "changedGroupOrdering": len(ordering),
    }

    return {
        "summary": summary,
        "unchanged": not any(summary.values()),
        "tabs": tabs,
        "groups": groups,
        "attributes": {
            **attributes,
            "changedFieldTypes": changed_types,
            "changedRequiredRules": changed_required,
        },
        "layouts": {
            "changedDisplayModes": changed_display_modes,
            "changedLayouts": changed_layouts,
        },
        "ordering": ordering,
    }
