"""CSV encoding for the report exports.

Two rules the exports must not break:

* a text cell is never interpreted as a spreadsheet formula — Excel, LibreOffice
  and Sheets all execute a cell that starts with ``=``, ``+``, ``@``, a tab or a
  carriage return, and a party name or description is user data;
* a money cell stays the exact ``NUMERIC(19,4)`` value, so a CSV can be reconciled
  against the report it came from.

Numeric cells are written straight from ``Decimal`` and are therefore never
prefixed: a leading minus is a negative amount, not a formula.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def is_number(value: object) -> bool:
    if isinstance(value, (int, float, Decimal)):
        return True
    try:
        Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return True


def text(value: object) -> str:
    """A text cell that a spreadsheet cannot turn into a formula.

    Only a leading minus is forgiven, and only when the whole cell is a number:
    a negative amount is data, while ``+1``, ``=SUM(...)`` and ``@import`` are
    formulas a spreadsheet would execute.
    """
    result = "" if value is None else str(value)
    if result.startswith(("=", "+", "@", "\t", "\r")):
        return "'" + result
    if result.startswith("-") and not is_number(result):
        return "'" + result
    return result


def money(value: object) -> str:
    """The fixed four-decimal form the ledger stores (``NUMERIC(19,4)``)."""
    return f"{Decimal(str(value if value is not None else 0)):.4f}"


def row_to_csv(cells: Iterable[object]) -> str:
    """One CRLF-terminated CSV line; ``None`` becomes an empty cell."""
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerow(["" if cell is None else cell for cell in cells])
    return buffer.getvalue()
