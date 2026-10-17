"""Currency arithmetic: the one place rate handling and money rounding live.

Every monetary row in this system stores an amount in the document's own
currency *and* the rate that converted it, with the base-currency amount beside
it. The only conversion the ledger performs is ``base = amount * rate`` — see
``financial_documents.exchange_rate`` and ``journal_entry_lines`` — so this
module owns the rules that surround it:

* what a usable rate is (positive, finite, within a sane band) and how it is
  normalised before it is stored;
* that a document whose currency *is* the base currency always carries rate 1,
  whatever a client sends;
* how a converted amount is quantized, using the currency's configured number of
  decimal places rather than a hardcoded 2.

Nothing here touches the database or the HTTP layer: the resolver that reads the
``currency_rates`` store lives in ``app/modules/master_data/currency_rates.py``,
and it uses these helpers so the two cannot disagree.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.core.exceptions import ValidationFailed

#: ``exchange_rate`` is ``Numeric(19, 8)``; a rate is stored quantized to that.
RATE_SCALE = Decimal("0.00000001")

#: Currencies with no minor unit exist (JPY, KHR in practice) — the per-currency
#: override lives on ``currencies.decimal_places``; this is the fallback.
DEFAULT_CURRENCY_PRECISION = 2
MAX_CURRENCY_PRECISION = 6

#: A rate beyond this is a data-entry error, not a conversion. One billion units
#: of one currency per unit of another covers every real pair with room to spare.
MAX_RATE = Decimal("1000000000")

#: The field a validation failure about a rate is reported against. The document
#: form, the journal line grid and the rate store all name it this way.
RATE_FIELD = "exchangeRate"


def to_decimal(value: Any, default: Decimal | None = None) -> Decimal:
    """Coerce a JSON/DB value to Decimal without ever going through float.

    ``Decimal(str(value))`` keeps a JSON number's own spelling, so 0.1 stays 0.1
    instead of becoming the binary float 0.1000000000000000055511151231257827.
    """
    if value is None or value == "":
        return default if default is not None else Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValidationFailed(f"{value!r} is not a number.")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        if default is not None:
            return default
        raise ValidationFailed(f"{value!r} is not a valid number.") from exc


def is_valid_rate(value: Any) -> bool:
    """True when ``value`` can be used as an exchange rate."""
    try:
        rate = to_decimal(value)
    except ValidationFailed:
        return False
    return rate.is_finite() and Decimal(0) < rate <= MAX_RATE


def normalize_rate(value: Any) -> Decimal:
    """Validate a rate and quantize it to the stored scale.

    Raises ``ValidationFailed`` keyed on ``exchangeRate`` — zero, negative,
    non-finite, unparseable and absurd values are all rejected here rather than
    silently stored, because every base-currency amount is derived from it.
    """
    try:
        rate = to_decimal(value)
    except ValidationFailed as exc:
        raise ValidationFailed(
            "The exchange rate must be a number greater than zero.",
            {RATE_FIELD: "Enter a rate greater than zero."},
        ) from exc
    if not rate.is_finite() or rate <= 0:
        raise ValidationFailed(
            "The exchange rate must be greater than zero.",
            {RATE_FIELD: "Enter a rate greater than zero."},
        )
    if rate > MAX_RATE:
        raise ValidationFailed(
            "The exchange rate is not plausible.",
            {RATE_FIELD: "This rate looks like a data-entry error."},
        )
    quantized = rate.quantize(RATE_SCALE, rounding=ROUND_HALF_UP)
    if quantized <= 0:
        # A rate smaller than the stored scale would round to zero, which would
        # silently convert every amount to nothing.
        raise ValidationFailed(
            "The exchange rate is too small to store.",
            {RATE_FIELD: f"Use a rate of at least {RATE_SCALE}."},
        )
    return quantized


def same_currency(document_currency: str | None, base_currency: str | None) -> bool:
    left = str(document_currency or "").strip().upper()
    right = str(base_currency or "").strip().upper()
    return bool(left) and left == right


def document_rate(
    document_currency: str | None,
    base_currency: str | None,
    rate: Any = None,
) -> Decimal:
    """The rate a document must store for its currency against the base currency.

    A document already denominated in the base currency is always 1 — the rate
    field is not part of that document, so nothing a client sends can make it
    anything else. Otherwise the supplied rate is validated; when it is missing
    the caller is expected to have resolved one from the configured rate store
    first, so a missing rate here is an error.
    """
    if same_currency(document_currency, base_currency):
        return Decimal("1")
    if rate in (None, ""):
        raise ValidationFailed(
            "An exchange rate is required when the currency differs from the base currency.",
            {RATE_FIELD: "Enter the exchange rate for this currency."},
        )
    return normalize_rate(rate)


def currency_precision(configured: Any = None) -> int:
    """Clamp a configured decimal-places value to something storable."""
    if configured in (None, ""):
        return DEFAULT_CURRENCY_PRECISION
    try:
        precision = int(to_decimal(configured))
    except (ValidationFailed, ValueError, TypeError):
        return DEFAULT_CURRENCY_PRECISION
    return max(0, min(precision, MAX_CURRENCY_PRECISION))


def quantize_money(amount: Any, precision: int | None = None) -> Decimal:
    """Round an amount to the currency's precision, half-up.

    Half-up is what the printed documents and the manual journals already do;
    keeping one rounding rule is what stops a stored base total and the journal
    it posts from differing by a cent.
    """
    value = to_decimal(amount)
    places = currency_precision(precision)
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def convert_to_base(amount: Any, rate: Any, precision: int | None = None) -> Decimal:
    """``amount`` (document currency) expressed in the base currency."""
    return quantize_money(to_decimal(amount) * to_decimal(rate), precision)
