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
