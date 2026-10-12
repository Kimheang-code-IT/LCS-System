from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_camel(name: str) -> str:
    if "_" not in name:
        return name
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


def record(model: Any, *, camel: bool = False, data: bool = False, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Serialize a SQLAlchemy model into a plain dict.

    ``data=True`` merges a JSONB ``data`` payload over the relational columns so
    the metadata-driven frontend receives every configured field.
    """
    result: dict[str, Any] = {}
    payload = getattr(model, "data", None)
    if data and isinstance(payload, dict):
        result.update(payload)
    for column in model.__table__.columns:
        if data and column.name == "data":
            continue
        key = to_camel(column.name) if camel else column.name
        result[key] = jsonable(getattr(model, column.name, None))
    if data:
        result["id"] = str(model.id) if getattr(model, "id", None) is not None else None
    if extra:
        result.update(extra)
    return result


def records(models: list[Any], *, camel: bool = False, data: bool = False, extra_key: str | None = None) -> list[dict[str, Any]]:
    output = []
    for model in models:
        extra = None
        if extra_key and hasattr(model, extra_key):
            extra = {extra_key: jsonable(getattr(model, extra_key))}
        output.append(record(model, camel=camel, data=data, extra=extra))
    return output
