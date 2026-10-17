"""Pure helpers for building a published dynamic-configuration snapshot.

The snapshot records *what the Service Order form looked like* at the moment a
configuration version was published: which tabs existed, for which trade
direction, which groups each tab contained and which attributes each group
rendered. Saved component rows are JSON keyed by attribute ``code``, so without
the snapshot a later edit (renaming a label, hiding an attribute, moving a group)
would silently change how historical data reads.

The builder is deliberately framework-free: callers fetch rows however they
like (async ORM in the service, Core queries in an Alembic migration) and pass
plain mappings in. Keeping one implementation is what stops the snapshot written
by the very first migration from disagreeing with every snapshot published
afterwards.

Snapshot shape (keys are camelCase because the frontend consumes the same
structure as the live tab payload)::

    {
      "tabs": [
        {
          "id": "1", "code": "GENERAL", "name": "General",
          "tradeDirectionId": "3", "displayOrder": 1,
          "groups": [
            {
              "id": "5", "code": "containers", "name": "Containers",
              "renderMode": "table", "displayOrder": 1,
              "attributes": [
                {
                  "id": "9", "code": "container_no", "label": "Container No.",
                  "labelKm": None, "dataType": "text", "inputType": None,
                  "referenceType": None, "isRequired": True, "displayOrder": 1,
                  "options": [], "validationRules": {},
                }
              ],
            }
          ],
        }
      ]
    }

Nothing in the snapshot is executable: it is configuration data, and the backend
still validates every submitted value against the live rules before saving.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "on"}


def _json_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _json_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def attribute_entry(attribute: Mapping[str, Any], membership: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One attribute as rendered inside a group, honouring per-group overrides."""
    required = _bool(attribute.get("is_required"))
    if membership is not None and membership.get("is_required") is not None:
        required = _bool(membership.get("is_required"))
    display_order = membership.get("display_order") if membership else None
    return {
        "id": _text(attribute.get("id")),
        "code": _text(attribute.get("code")),
        "label": _text(attribute.get("label")),
        "labelKm": attribute.get("label_km"),
        "dataType": _text(attribute.get("data_type")),
        "inputType": attribute.get("input_type"),
        "referenceType": attribute.get("reference_type"),
        "isRequired": required,
        "defaultValue": attribute.get("default_value"),
        "placeholder": attribute.get("placeholder"),
        "options": _json_list(attribute.get("options")),
        "validationRules": _json_dict(attribute.get("validation_rules")),
        "displayOrder": int(display_order or 0),
    }


def group_entry(
    group: Mapping[str, Any],
    attributes: Iterable[dict[str, Any]],
    display_order: int | None = None,
) -> dict[str, Any]:
    order = display_order if display_order is not None else group.get("display_order")
    return {
        "id": _text(group.get("id")),
        "code": _text(group.get("code")),
        "name": _text(group.get("name")),
        "nameKm": group.get("name_km"),
        "renderMode": _text(group.get("render_mode")) or "table",
        "displayOrder": int(order or 0),
        "attributes": sorted(attributes, key=lambda item: (item["displayOrder"], item["code"] or "")),
    }


def tab_entry(
    tab: Mapping[str, Any],
    groups: Iterable[dict[str, Any]],
    display_order: int | None = None,
) -> dict[str, Any]:
    order = display_order if display_order is not None else tab.get("display_order")
    return {
        "id": _text(tab.get("id")),
        "code": _text(tab.get("code")),
        "name": _text(tab.get("name")),
        "tradeDirectionId": _text(tab.get("trade_direction_id")),
        "displayOrder": int(order or 0),
        "groups": sorted(groups, key=lambda item: (item["displayOrder"], item["code"] or "")),
    }


def build_snapshot(tabs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Wrap already-assembled tab entries in the stored snapshot envelope."""
    ordered = sorted(tabs, key=lambda item: (item["displayOrder"], item["code"] or ""))
    return {"tabs": ordered}
