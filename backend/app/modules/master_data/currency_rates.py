"""The configured exchange rates, and how a document finds its own.

Two directions meet here and this module is the only place that bridges them:

* a stored rate row says **"1 FROM = rate TO"** — the direction an operator reads
  and the UI shows ("1 USD = 4,000 KHR");
* a document stores the inverse, because every base amount in the ledger is
  ``base = amount * exchange_rate``.

So :func:`resolve_document_rate` answers "what rate must this KHR invoice store
when the base currency is USD?" — the direct pair if one exists, otherwise the
inverse of the (USD → KHR) row. A rate is read at save time and copied onto the
document; nothing posts from this table, which is what keeps a posted amount
explainable after the rate store changes.

Precision lives here too, because it is a property of the currency master
(``currencies.decimal_places``) and every converted amount is rounded with it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import fx
from app.core.exceptions import ValidationFailed
from app.modules.master_data.models import Currency, CurrencyRate

#: A rate is usable only once approved; PENDING is what an operator types first.
RATE_STATUSES = ("PENDING", "APPROVED", "INACTIVE")
APPROVED = "APPROVED"


def normalize_rate_input(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a rate row before it is stored.

    Runs as the master-data ``Spec.transform_input`` hook, so the operator gets
    field-level messages instead of a database constraint error. The table's own
    CHECK constraints back this up for anything that writes around the API.
    """
    from_code = str(data.get("fromCurrencyCode") or "").strip().upper()
    to_code = str(data.get("toCurrencyCode") or "").strip().upper()
    if not from_code:
        raise ValidationFailed("A currency is required.", {"fromCurrencyCode": "Choose the currency being converted."})
    if not to_code:
        raise ValidationFailed("A currency is required.", {"toCurrencyCode": "Choose the currency to convert into."})
    if from_code == to_code:
        raise ValidationFailed(
            "A rate needs two different currencies.",
            {"toCurrencyCode": "Choose a currency other than the first one."},
        )
    data["fromCurrencyCode"] = from_code
    data["toCurrencyCode"] = to_code
    if "rate" in data:
        try:
            data["rate"] = fx.normalize_rate(data.get("rate"))
        except ValidationFailed as exc:
            # `normalize_rate` is shared with document exchange rates, where the
            # field is `exchangeRate`; in this collection it is `rate`, so the
            # message has to be re-addressed or the form cannot place it.
            message = (exc.field_errors or {}).get("exchangeRate") or exc.message
            raise ValidationFailed(exc.message, {"rate": message}) from exc
    status = str(data.get("status") or APPROVED).strip().upper()
    if status not in RATE_STATUSES:
        raise ValidationFailed(
            "Unknown rate status.",
            {"status": f"Choose one of {', '.join(RATE_STATUSES)}."},
        )
    data["status"] = status
    return data


async def latest_approved(
    session: AsyncSession,
    from_currency: str,
    to_currency: str,
    on_date: date | None = None,
) -> CurrencyRate | None:
    """The newest approved row for a directed pair, effective on or before a date."""
    conditions = [
        CurrencyRate.from_currency_code == str(from_currency).strip().upper(),
        CurrencyRate.to_currency_code == str(to_currency).strip().upper(),
        CurrencyRate.status == APPROVED,
    ]
    if on_date is not None:
        conditions.append(CurrencyRate.effective_date <= on_date)
    return (
        await session.execute(
            select(CurrencyRate)
            .where(*conditions)
            .order_by(CurrencyRate.effective_date.desc(), CurrencyRate.id.desc())
            .limit(1)
        )
    ).scalars().first()


async def resolve_document_rate(
    session: AsyncSession,
    document_currency: str,
    base_currency: str,
    on_date: date | None = None,
) -> Decimal | None:
    """The rate a document stores, or ``None`` when no approved pair covers it.

    ``None`` is deliberately not 1: the caller then asks the operator for a rate
    instead of mis-stating every base amount on the document.
    """
    document_code = str(document_currency or "").strip().upper()
    base_code = str(base_currency or "").strip().upper()
    if not document_code or not base_code:
        return None
    if fx.same_currency(document_code, base_code):
        return Decimal("1")

    direct = await latest_approved(session, document_code, base_code, on_date)
    if direct is not None and direct.rate > 0:
        # "1 document = direct.rate base", which is exactly what is stored.
        return fx.normalize_rate(direct.rate)

    inverse = await latest_approved(session, base_code, document_code, on_date)
    if inverse is not None and inverse.rate > 0:
        # "1 base = inverse.rate document", so one document unit is 1 / rate base.
        return fx.normalize_rate(Decimal(1) / Decimal(inverse.rate))
    return None


async def currency_precision(session: AsyncSession, code: str | None) -> int:
    """The configured decimal places for a currency, else the default (2)."""
    value = str(code or "").strip().upper()
    if not value:
        return fx.DEFAULT_CURRENCY_PRECISION
    row = (
        await session.execute(select(Currency).where(Currency.code == value))
    ).scalars().first()
    if row is None:
        return fx.DEFAULT_CURRENCY_PRECISION
    return fx.currency_precision(row.decimal_places)


async def assert_currency_code(session: AsyncSession, code: Any, field: str = "currency") -> str:
    """Normalise a currency code, and refuse one that has been archived.

    A code with no master row is accepted: a fresh installation provisions no
    currencies, and the ledger only needs the three-letter shape. A row that
    exists and is not ACTIVE is refused, so an archived currency cannot be
    reintroduced by an API client that ignores the form.
    """
    value = str(code or "").strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise ValidationFailed(
            "A three-letter currency code is required.",
            {field: "Use an ISO 4217 code such as USD."},
        )
    row = (await session.execute(select(Currency).where(Currency.code == value))).scalars().first()
    if row is not None and str(row.status or "").upper() != "ACTIVE":
        raise ValidationFailed(
            "That currency is not active.",
            {field: "Choose an active currency."},
        )
    return value
