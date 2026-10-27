"""The shared schema validator: types, bounds, precision and partial updates.

These are pure unit tests, so a rule failure is diagnosed without an HTTP
request. The API-level behaviour (codes and fields in the response envelope) is
covered by ``test_write_validation.py``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationFailed
from app.core.validation import (
    FieldSpec,
    RecordSchema,
    parse_decimal,
    resolve_line_tax,
)

DATETIME_SCHEMA = RecordSchema((FieldSpec("at", kind="datetime"),))


def test_datetime_accepts_zulu_and_numeric_offsets():
    """The movement/milestone form sends ISO-8601 with ``Z``."""
    assert DATETIME_SCHEMA.validate({"at": "2026-03-01T08:00:00Z"})["at"] == datetime(
        2026, 3, 1, 8, 0, tzinfo=UTC
    )
    assert DATETIME_SCHEMA.validate({"at": "2026-03-01T08:00:00+07:00"})["at"].utcoffset().total_seconds() == 7 * 3600


SCHEMA = RecordSchema(
    (
        FieldSpec("code", required=True, min_length=2, max_length=6, pattern=r"[A-Z0-9]+"),
        FieldSpec("name", required=True, max_length=10),
        FieldSpec("email", kind="email"),
        FieldSpec("quantity", kind="integer", minimum=Decimal("1"), maximum=Decimal("99")),
        FieldSpec("rate", kind="decimal", minimum=Decimal("0.00000001"), decimal_places=8),
        FieldSpec("active", kind="boolean"),
        FieldSpec("effectiveDate", kind="date"),
        FieldSpec("status", choices=("ACTIVE", "INACTIVE")),
    )
)


def _errors(payload: dict, *, partial: bool = False) -> dict[str, str]:
    with pytest.raises(ValidationFailed) as raised:
        SCHEMA.validate(payload, partial=partial)
    return raised.value.field_errors or {}


def test_required_fields_are_reported_together():
    errors = _errors({})
    assert set(errors) == {"code", "name"}


def test_a_valid_payload_is_normalised():
    value = SCHEMA.validate({
        "code": " AB12 ",
        "name": " Widget ",
        "email": " buyer@example.com ",
        "quantity": "3",
        "rate": "1.25",
        "active": "Yes",
        "effectiveDate": "2026-01-31",
        "status": "active",
    })
    assert value["code"] == "AB12"
    assert value["name"] == "Widget"
    assert value["quantity"] == 3
    assert value["rate"] == Decimal("1.25")
    assert value["active"] is True
    assert value["effectiveDate"] == date(2026, 1, 31)


def test_formats_lengths_bounds_and_precision_are_enforced():
    errors = _errors({
        "code": "a",
        "name": "a name that is far too long",
        "email": "not-an-email",
        "quantity": "2.5",
        "rate": "1.123456789",
    })
    assert errors["code"].startswith("Use at least")
    assert errors["name"].startswith("Use at most")
    assert errors["email"].startswith("Enter a valid email")
    assert errors["quantity"].startswith("Enter a whole number")
    assert errors["rate"].startswith("Use at most 8 decimal places")


def test_unknown_choice_and_status_vocabulary_are_refused():
    errors = _errors({"code": "AB12", "name": "Widget", "status": "ARCHIVED"})
    assert errors["status"].startswith("Choose one of")


def test_partial_update_does_not_require_omitted_fields_but_still_checks_supplied_ones():
    # Omitted required fields stay untouched.
    assert SCHEMA.validate({"name": "Widget"}, partial=True) == {"name": "Widget"}
    # A supplied blank value is still a field error.
    assert _errors({"name": "  "}, partial=True)["name"] == "This field is required."


def test_line_helpers_reject_malformed_and_over_precise_values():
    with pytest.raises(ValidationFailed) as raised:
        parse_decimal("abc", "lines.0.unitPrice", places=4)
    assert "lines.0.unitPrice" in (raised.value.field_errors or {})

    with pytest.raises(ValidationFailed) as raised:
        parse_decimal("10.12345", "lines.0.unitPrice", places=4)
    assert "decimal places" in (raised.value.field_errors or {})["lines.0.unitPrice"]


def test_line_tax_accepts_a_rate_or_an_amount_and_prefers_the_rate():
    rate_field, amount, rate = resolve_line_tax({"taxRate": 10}, Decimal("100"), "lines.0")
    assert (rate_field, amount, rate) == ("taxRate", Decimal("10"), Decimal("10"))

    amount_field, amount, rate = resolve_line_tax({"taxAmount": 15}, Decimal("100"), "lines.0")
    assert amount_field == "taxAmount"
    assert amount == Decimal("15")
    assert rate == Decimal("15")
