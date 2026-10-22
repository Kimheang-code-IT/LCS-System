"""Reusable, schema-based validation for JSON request payloads.

The API accepts plain ``dict`` bodies for most modules, so Pydantic cannot be
the only guard: a value reaches a SQLAlchemy column without a type check and an
over-long string or a malformed date fails as a database error with no field
attached. This module is the one place that turns an untrusted payload into

* normalised values (trimmed text, ``Decimal`` money, real ``date`` objects,
  real booleans) and
* a complete list of :class:`FieldSpec` violations, keyed by the camelCase API
  field the form rendered.

Rules are declarative data, so the same schema can validate a create request
(required fields enforced) and a partial update (only supplied keys checked).
Every failure carries a stable ``code`` (``REQUIRED``, ``TOO_LONG`` …) beside
its human message; the error envelope exposes both.

Keep this module free of module-specific business rules: a service composes a
``RecordSchema`` and adds cross-field rules, it does not fork the evaluator.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import Path

from app.core.exceptions import ValidationFailed

#: A numeric record id in a path. FastAPI turns a non-integer or a non-positive
#: value into the standard 422 envelope before the handler runs, instead of the
#: handler calling ``int()`` and raising an unhandled ``ValueError`` (a 500 with
#: no field attached).
EntityId = Annotated[int, Path(ge=1, description="Numeric record id")]

# Stable, machine-readable failure codes. The frontend translates the message
# and may branch on the code; adding a code is backward compatible.
REQUIRED = "REQUIRED"
INVALID_TYPE = "INVALID_TYPE"
INVALID_FORMAT = "INVALID_FORMAT"
TOO_SHORT = "TOO_SHORT"
TOO_LONG = "TOO_LONG"
OUT_OF_RANGE = "OUT_OF_RANGE"
INVALID_PRECISION = "INVALID_PRECISION"
INVALID_CHOICE = "INVALID_CHOICE"
UNKNOWN_FIELD = "UNKNOWN_FIELD"
CROSS_FIELD = "CROSS_FIELD"

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
# Mirrors `PHONE_PATTERN` in frontend/app/utils/validation/field-rules.ts: 6 to
# 15 digits with the separators a person actually types.
_PHONE_PATTERN = re.compile(r"^\+?[\d(][\d\s().-]{4,20}$")
_URL_PATTERN = re.compile(r"^https?://[^\s.]+\.[^\s]{2,}$", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$"
)

_TRUE_TEXT = {"true", "yes", "y", "1", "on", "active", "enabled"}
_FALSE_TEXT = {"false", "no", "n", "0", "off", "inactive", "disabled"}

FieldErrorItem = dict[str, str]


@dataclass(frozen=True)
class FieldSpec:
    """Validation and normalisation rules for one API field.

    ``kind`` is the storage shape (``string``, ``integer``, ``decimal``,
    ``boolean``, ``date``, ``datetime``, ``email``, ``phone``, ``url``,
    ``reference``, ``json``), not the widget type: it says what the value must
    become before it is written.
    """

    key: str
    kind: str = "string"
    required: bool = False
    min_length: int | None = None
    max_length: int | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    decimal_places: int | None = None
    pattern: str | None = None
    choices: tuple[str, ...] | None = None
    nullable: bool = True
    strip: bool = True
    label: str | None = None
    #: Legacy spellings accepted in place of ``key`` (for example ``unitAmount``
    #: for ``unitPrice``). A recognized alias is normalised onto ``key`` and is
    #: not refused as an unknown field.
    aliases: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        return self.label or self.key

    def describe_length(self) -> str:
        return f"Use at most {self.max_length} characters." if self.max_length else ""


@dataclass(frozen=True)
class CrossFieldRule:
    """A rule that needs more than one field at once.

    The check returns ``(field, code, message)`` for a failure, or ``None`` when
    the combination is valid. The returned field is the input the user has to
    change, so the message lands under it rather than in a page-level list.
    """

    fields: tuple[str, ...]
    check: Callable[[Mapping[str, Any]], tuple[str, str, str] | None]


@dataclass(frozen=True)
class RecordSchema:
    fields: tuple[FieldSpec, ...]
    cross_field: tuple[CrossFieldRule, ...] = ()
    #: Payload keys the API accepts but never writes from the client (ids,
    #: timestamps, computed mirrors). They are preserved and not validated.
    readonly: tuple[str, ...] = ()
    #: When true, a key that is neither a field nor read-only is refused.
    reject_unknown: bool = False

    def validate(self, payload: Mapping[str, Any], *, partial: bool = False) -> dict[str, Any]:
        """Return a normalised copy of ``payload`` or raise ``ValidationFailed``.

        ``partial=True`` is the update contract: a missing key keeps its stored
        value, while a supplied blank value for a required field is still an
        error. It never makes an over-long or malformed value acceptable.
        """
        specs = {spec.key: spec for spec in self.fields}
        errors: list[FieldErrorItem] = []
        normalized: dict[str, Any] = dict(payload)

        if self.reject_unknown:
            allowed = set(specs) | set(self.readonly)
            for spec in self.fields:
                allowed.update(spec.aliases)
            for key in payload:
                if key not in allowed:
                    errors.append(_error(key, UNKNOWN_FIELD, f"Unknown field: {key}."))

        for spec in self.fields:
            source_key = spec.key if spec.key in payload else next(
                (alias for alias in spec.aliases if alias in payload),
                None,
            )
            if source_key is None:
                if spec.required and not partial:
                    errors.append(_error(spec.key, REQUIRED, "This field is required."))
                continue
            try:
                normalized[spec.key] = _normalize(spec, payload[source_key])
                if source_key != spec.key:
                    # The alias was an input spelling, not a writable field: the
                    # service reads the canonical key only.
                    normalized.pop(source_key, None)
            except _Invalid as failure:
                errors.append(_error(spec.key, failure.code, failure.message))

        if not errors and self.cross_field:
            values = {**payload, **normalized}
            for rule in self.cross_field:
                outcome = rule.check(values)
                if outcome is not None:
                    field, code, message = outcome
                    errors.append(_error(field, code, message))

        if errors:
            field_errors = {item["field"]: item["message"] for item in errors}
            raise ValidationFailed(
                "Please correct the highlighted fields.",
                field_errors=field_errors,
                errors=errors,
            )
        return normalized


class _Invalid(ValueError):
    """Internal: one field failed, carrying its stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _error(field: str, code: str, message: str) -> FieldErrorItem:
    return {"field": field, "code": code, "message": message}


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _normalize(spec: FieldSpec, value: Any) -> Any:
    if is_blank(value):
        if spec.required:
            raise _Invalid(REQUIRED, "This field is required.")
        if spec.kind in {"string", "email", "phone", "url", "reference", "date", "datetime"}:
            return None
        return value if spec.kind == "json" else None

    kind = spec.kind
    if kind in {"string", "email", "phone", "url"}:
        return _string(spec, value)
    if kind == "integer":
        return _integer(spec, value)
    if kind == "decimal":
        return _decimal(spec, value)
    if kind == "boolean":
        return _boolean(spec, value)
    if kind == "date":
        return _date(spec, value)
    if kind == "datetime":
        return _datetime(spec, value)
    if kind == "reference":
        return _reference(spec, value)
    if kind == "json":
        if isinstance(value, (list, dict, str, int, float, bool)):
            return value
        raise _Invalid(INVALID_TYPE, "Enter a valid value.")
    return _string(spec, value)


def _string(spec: FieldSpec, value: Any) -> str:
    if not isinstance(value, str):
        raise _Invalid(INVALID_TYPE, "Enter text.")
    text = value.strip() if spec.strip else value
    if spec.required and not text:
        raise _Invalid(REQUIRED, "This field is required.")
    if spec.min_length is not None and len(text) < spec.min_length:
        raise _Invalid(TOO_SHORT, f"Use at least {spec.min_length} characters.")
    if spec.max_length is not None and len(text) > spec.max_length:
        raise _Invalid(TOO_LONG, f"Use at most {spec.max_length} characters.")

    if spec.kind == "email" and not _EMAIL_PATTERN.match(text):
        raise _Invalid(INVALID_FORMAT, "Enter a valid email address.")
    if spec.kind == "phone":
        digits = re.sub(r"\D", "", text)
        if not _PHONE_PATTERN.match(text) or not 6 <= len(digits) <= 15:
            raise _Invalid(INVALID_FORMAT, "Enter a valid phone number.")
    if spec.kind == "url" and not _URL_PATTERN.match(text):
        raise _Invalid(INVALID_FORMAT, "Enter a valid web address.")
    if spec.choices is not None and not _matches_choice(text, spec.choices):
        raise _Invalid(INVALID_CHOICE, "Choose one of the available options.")
    if spec.pattern is not None:
        try:
            matches = re.fullmatch(spec.pattern, text) is not None
        except re.error:
            # A malformed pattern is a configuration bug, never a user error;
            # refusing every value would be worse than letting it through.
            matches = True
        if not matches:
            raise _Invalid(INVALID_FORMAT, "Enter a value in the expected format.")
    return text


def _matches_choice(text: str, choices: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return any(folded == choice.casefold() for choice in choices)


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise _Invalid(INVALID_TYPE, "Enter a number.")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise _Invalid(INVALID_TYPE, "Enter a number.") from None
    if not number.is_finite():
        raise _Invalid(INVALID_TYPE, "Enter a number.")
    return number


def _enforce_range(spec: FieldSpec, number: Decimal) -> None:
    if spec.minimum is not None and number < spec.minimum:
        raise _Invalid(OUT_OF_RANGE, f"Enter a value greater than or equal to {spec.minimum}.")
    if spec.maximum is not None and number > spec.maximum:
        raise _Invalid(OUT_OF_RANGE, f"Enter a value less than or equal to {spec.maximum}.")


def _integer(spec: FieldSpec, value: Any) -> int:
    number = _to_decimal(value)
    if number != number.to_integral_value():
        raise _Invalid(INVALID_TYPE, "Enter a whole number.")
    _enforce_range(spec, number)
    return int(number)


def _decimal(spec: FieldSpec, value: Any) -> Decimal:
    number = _to_decimal(value)
    _enforce_range(spec, number)
    if spec.decimal_places is not None:
        normalized = number.normalize()
        places = max(0, -normalized.as_tuple().exponent)
        if places > spec.decimal_places:
            raise _Invalid(INVALID_PRECISION, f"Use at most {spec.decimal_places} decimal places.")
    return number


def _boolean(spec: FieldSpec, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().casefold()
        if text in _TRUE_TEXT:
            return True
        if text in _FALSE_TEXT:
            return False
    raise _Invalid(INVALID_TYPE, "Choose Yes or No.")


def _date(spec: FieldSpec, value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not _DATE_PATTERN.match(text):
        raise _Invalid(INVALID_FORMAT, "Enter a valid date.")
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        raise _Invalid(INVALID_FORMAT, "Enter a valid date.") from None


def _datetime(spec: FieldSpec, value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    text = str(value).strip()
    if not _DATETIME_PATTERN.match(text):
        raise _Invalid(INVALID_FORMAT, "Enter a valid date and time.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise _Invalid(INVALID_FORMAT, "Enter a valid date and time.") from None
    return parsed


def _reference(spec: FieldSpec, value: Any) -> Any:
    """A foreign key or a code/name the service later resolves.

    Both a numeric id and a code are legitimate inputs; existence is checked by
    the service against its repository, not here, because only the caller knows
    which table the reference points at.
    """
    if isinstance(value, bool):
        raise _Invalid(INVALID_TYPE, "Choose a valid record.")
    if isinstance(value, int):
        if value <= 0:
            raise _Invalid(INVALID_TYPE, "Choose a valid record.")
        return value
    if isinstance(value, float):
        if not value.is_integer() or value <= 0:
            raise _Invalid(INVALID_TYPE, "Choose a valid record.")
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if spec.max_length is not None and len(text) > spec.max_length:
            raise _Invalid(TOO_LONG, f"Use at most {spec.max_length} characters.")
        return text
    raise _Invalid(INVALID_TYPE, "Choose a valid record.")


def validate_payload(schema: RecordSchema, payload: Mapping[str, Any], *, partial: bool = False) -> dict[str, Any]:
    """Module-level convenience wrapper around :meth:`RecordSchema.validate`."""
    return schema.validate(payload, partial=partial)


def validate_id_list(payload: Mapping[str, Any], *, field: str = "ids") -> list[int]:
    """Read a bulk-action id list, refusing a malformed member by its index.

    Every bulk delete endpoint used to build its list with a comprehension that
    silently dropped a non-numeric member (``"abc"`` in a delete request removed
    nothing and reported success). Rejecting the request instead keeps the
    caller's intent and the server's action in agreement.
    """
    raw = payload.get(field)
    if raw in (None, "", []):
        return []
    if not isinstance(raw, list):
        raise ValidationFailed(
            "Please correct the selected records.",
            {field: "Provide a list of record ids."},
        )
    ids: list[int] = []
    errors: list[FieldErrorItem] = []
    for index, value in enumerate(raw):
        if isinstance(value, bool):
            number = None
        elif isinstance(value, int):
            number = value
        elif isinstance(value, str) and value.strip().isdigit():
            number = int(value.strip())
        else:
            number = None
        if number is None or number <= 0:
            errors.append(
                _error(f"{field}.{index}", INVALID_TYPE, "Choose a valid record id.")
            )
            continue
        ids.append(number)
    if errors:
        raise ValidationFailed(
            "Please correct the selected records.",
            field_errors={item["field"]: item["message"] for item in errors},
            errors=errors,
        )
    return ids


def validate_line_items(
    value: Any,
    schema: RecordSchema,
    *,
    field: str = "lines",
) -> list[dict[str, Any]]:
    """Validate a repeated child collection and address errors by ``field.row.key``.

    A line table is one form control per row, so an error in row 1 must not be
    reported as a page-level message. The prefix is the same shape the frontend
    already uses for repeatable rows (``lines.0.unitPrice``).
    """
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValidationFailed(
            "Please correct the document lines.",
            {field: "Provide a list of rows."},
        )
    items: list[dict[str, Any]] = []
    field_errors: dict[str, str] = {}
    errors: list[FieldErrorItem] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            path = f"{field}.{index}"
            field_errors[path] = "Enter a valid row."
            errors.append(_error(path, INVALID_TYPE, "Enter a valid row."))
            continue
        try:
            items.append(schema.validate(item))
        except ValidationFailed as failure:
            for item_error in failure.errors or [
                {"field": key, "code": INVALID_FORMAT, "message": message}
                for key, message in (failure.field_errors or {}).items()
            ]:
                path = f"{field}.{index}.{item_error.get('field', '')}".rstrip(".")
                message = str(item_error.get("message", "Invalid value."))
                code = str(item_error.get("code") or INVALID_FORMAT)
                field_errors.setdefault(path, message)
                errors.append(_error(path, code, message))
    if errors:
        raise ValidationFailed(
            "Please correct the document lines.",
            field_errors=field_errors,
            errors=errors,
        )
    return items


# --- Line-item helpers -------------------------------------------------------
# Money lines are nested, repeated and partly computed. These two helpers keep
# the create paths for service charges and financial documents reading a line
# the same way, so a value cannot be valid for one and silently zero for the
# other.

def parse_decimal(
    value: Any,
    field: str,
    default: Decimal = Decimal("0"),
    places: int | None = None,
) -> Decimal:
    """Parse a money-bearing line value, refusing a malformed one on its cell.

    ``places`` mirrors the column scale, so a client cannot submit more
    precision than the document can store and have it silently rounded.
    """
    if value in (None, ""):
        return default
    try:
        number = Decimal(str(value).strip())
    except Exception:  # noqa: BLE001 - any parse failure is a field error
        raise ValidationFailed("Please correct the document lines.", {field: "Enter a number."}) from None
    if not number.is_finite():
        raise ValidationFailed("Please correct the document lines.", {field: "Enter a number."})
    if places is not None:
        normalized = number.normalize()
        used = max(0, -normalized.as_tuple().exponent)
        if used > places:
            raise ValidationFailed(
                "Please correct the document lines.",
                {field: f"Use at most {places} decimal places."},
            )
    return number


def resolve_line_tax(
    line: Mapping[str, Any],
    taxable: Decimal,
    prefix: str = "",
) -> tuple[str, Decimal, Decimal]:
    """Resolve a line's tax as ``(field, amount, rate)``.

    Document-style forms expose a tax *amount*; service-charge forms and API
    clients expose a tax *rate*. Both are accepted, and an explicit rate wins
    because it is the figure a caller can reason about without knowing the
    subtotal. The returned field name is the one the caller must highlight.
    """
    field_prefix = f"{prefix}." if prefix else ""
    if line.get("taxRate") not in (None, ""):
        rate = parse_decimal(line.get("taxRate"), f"{field_prefix}taxRate", places=4)
        return "taxRate", taxable * rate / Decimal("100"), rate
    if line.get("taxAmount") not in (None, ""):
        amount = parse_decimal(line.get("taxAmount"), f"{field_prefix}taxAmount", places=4)
        rate = (amount / taxable * Decimal("100")) if taxable > 0 else Decimal("0")
        return "taxAmount", amount, rate
    if line.get("tax") not in (None, ""):
        rate = parse_decimal(line.get("tax"), f"{field_prefix}tax", places=4)
        return "tax", taxable * rate / Decimal("100"), rate
    return "taxRate", Decimal("0"), Decimal("0")


# --- SQLAlchemy helpers ------------------------------------------------------

def _column_kind(column: Any) -> str:
    """Map a SQLAlchemy column type onto a :class:`FieldSpec` kind."""
    from sqlalchemy import JSON
    from sqlalchemy import Boolean as SABoolean
    from sqlalchemy import Date as SADate
    from sqlalchemy import DateTime as SADateTime
    from sqlalchemy import Integer as SAInteger
    from sqlalchemy import Numeric as SANumeric
    from sqlalchemy import String as SAString
    from sqlalchemy import Text as SAText

    column_type = column.type
    if isinstance(column_type, SABoolean):
        return "boolean"
    if isinstance(column_type, (SADate,)):
        return "date"
    if isinstance(column_type, SADateTime):
        return "datetime"
    if isinstance(column_type, SAInteger):
        return "integer"
    if isinstance(column_type, SANumeric):
        return "decimal"
    if isinstance(column_type, JSON):
        return "json"
    if isinstance(column_type, (SAString, SAText)):
        return "string"
    return "string"


def field_from_column(
    key: str,
    column: Any,
    *,
    required: bool | None = None,
    choices: tuple[str, ...] | None = None,
    kind: str | None = None,
    **overrides: Any,
) -> FieldSpec:
    """Derive a field rule from the column that will store it.

    Lengths, decimal scale and nullability come from the schema itself, so a
    model change cannot silently leave the API accepting a value the database
    will reject. Business requirements (which optional column is actually
    required) stay explicit through ``required``.
    """
    resolved_kind = kind or _column_kind(column)
    nullable = bool(getattr(column, "nullable", True))
    values: dict[str, Any] = {
        "kind": resolved_kind,
        "required": (not nullable) if required is None else required,
        "max_length": getattr(column.type, "length", None) if resolved_kind == "string" else None,
        "decimal_places": getattr(column.type, "scale", None) if resolved_kind == "decimal" else None,
        "choices": choices,
        "nullable": nullable,
    }
    # Explicit business rules win over the column-derived default (a currency
    # code is exactly three characters even though the column is wider).
    values.update(overrides)
    return FieldSpec(key=key, **values)
