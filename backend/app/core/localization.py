from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.exceptions import ValidationFailed

SUPPORTED_LANGUAGES = ("en", "km")
SUPPORTED_TIMEZONES = (
    "Asia/Phnom_Penh",
    "Asia/Bangkok",
    "Asia/Ho_Chi_Minh",
    "Asia/Singapore",
    "Asia/Jakarta",
    "Asia/Kuala_Lumpur",
    "Asia/Manila",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Europe/London",
    "Europe/Paris",
    "America/New_York",
    "America/Los_Angeles",
    "UTC",
)
SUPPORTED_DATE_FORMATS = ("YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD-MM-YYYY", "D MMM YYYY")
SUPPORTED_TIME_FORMATS = ("HH:mm", "HH:mm:ss", "h:mm A", "h:mm:ss A")
SUPPORTED_NUMBER_FORMATS = ("#,##0.00", "#.##0,00", "# ##0,00")
SUPPORTED_CURRENCIES = ("USD", "KHR", "THB", "VND", "SGD", "EUR", "GBP", "JPY", "CNY")
SUPPORTED_LOCALES = ("en-US", "en-GB", "km-KH", "th-TH", "vi-VN", "fr-FR", "ja-JP", "zh-CN")
DEFAULT_CURRENCY = "USD"

DEFAULT_LOCALIZATION: dict[str, Any] = {
    "defaultLanguage": "en",
    "availableLanguages": ["en", "km"],
    "timezone": "Asia/Phnom_Penh",
    "dateFormat": "DD/MM/YYYY",
    "timeFormat": "HH:mm",
    "firstDayOfWeek": 1,
    "numberFormat": "#,##0.00",
    "currency": DEFAULT_CURRENCY,
    "locale": "en-US",
}

_LEGACY_NUMBER_FORMATS = {
    "1,234.56": "#,##0.00",
    "1.234,56": "#.##0,00",
    "1 234,56": "# ##0,00",
}
_LANGUAGE_LOCALES = {"en": "en-US", "km": "km-KH"}


def normalize_localization(value: Any) -> dict[str, Any]:
    """Return a complete, safe display configuration for stored or missing data."""
    source = value if isinstance(value, dict) else {}
    result = dict(DEFAULT_LOCALIZATION)
    result["availableLanguages"] = list(DEFAULT_LOCALIZATION["availableLanguages"])

    language = source.get("defaultLanguage")
    if language in SUPPORTED_LANGUAGES:
        result["defaultLanguage"] = language
    languages = source.get("availableLanguages")
    if isinstance(languages, list):
        supported = [item for item in languages if item in SUPPORTED_LANGUAGES]
        if supported:
            result["availableLanguages"] = list(dict.fromkeys(supported))

    for key, supported in (
        ("timezone", SUPPORTED_TIMEZONES),
        ("dateFormat", SUPPORTED_DATE_FORMATS),
        ("timeFormat", SUPPORTED_TIME_FORMATS),
        ("currency", SUPPORTED_CURRENCIES),
    ):
        if source.get(key) in supported:
            result[key] = source[key]

    number_format = _LEGACY_NUMBER_FORMATS.get(source.get("numberFormat"), source.get("numberFormat"))
    if number_format in SUPPORTED_NUMBER_FORMATS:
        result["numberFormat"] = number_format
    if source.get("firstDayOfWeek") in (0, 1, 6):
        result["firstDayOfWeek"] = source["firstDayOfWeek"]

    # The UI language is authoritative for language-sensitive labels/month names;
    # number separators are controlled independently by ``numberFormat``.
    result["locale"] = _LANGUAGE_LOCALES[result["defaultLanguage"]]
    return result


def validate_localization_patch(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationFailed("Localization settings must be an object.", {"localization": "Expected an object."})

    errors: dict[str, str] = {}
    checks = (
        ("defaultLanguage", SUPPORTED_LANGUAGES, "language"),
        ("timezone", SUPPORTED_TIMEZONES, "timezone"),
        ("dateFormat", SUPPORTED_DATE_FORMATS, "date format"),
        ("timeFormat", SUPPORTED_TIME_FORMATS, "time format"),
        ("numberFormat", (*SUPPORTED_NUMBER_FORMATS, *_LEGACY_NUMBER_FORMATS), "number format"),
        ("currency", SUPPORTED_CURRENCIES, "currency"),
        ("locale", SUPPORTED_LOCALES, "locale"),
    )
    for key, supported, label in checks:
        if key in value and value[key] not in supported:
            errors[f"localization.{key}"] = f"Unsupported {label}."

    if "availableLanguages" in value:
        languages = value["availableLanguages"]
        if not isinstance(languages, list) or not languages or any(item not in SUPPORTED_LANGUAGES for item in languages):
            errors["localization.availableLanguages"] = "Select at least one supported application language."
    if "firstDayOfWeek" in value and value["firstDayOfWeek"] not in (0, 1, 6):
        errors["localization.firstDayOfWeek"] = "First day of week must be Sunday, Monday, or Saturday."

    timezone_name = value.get("timezone")
    if timezone_name and "localization.timezone" not in errors:
        try:
            ZoneInfo(str(timezone_name))
        except ZoneInfoNotFoundError:
            errors["localization.timezone"] = "Timezone must be a valid IANA timezone."

    if errors:
        raise ValidationFailed("Invalid localization settings.", errors)
    return normalize_localization({**DEFAULT_LOCALIZATION, **value})


def _as_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def format_date(value: date | datetime, config: dict[str, Any]) -> str:
    local = value if isinstance(value, date) and not isinstance(value, datetime) else _as_datetime(value).astimezone(ZoneInfo(config["timezone"]))
    pattern = config["dateFormat"]
    if pattern == "DD/MM/YYYY":
        return local.strftime("%d/%m/%Y")
    if pattern == "MM/DD/YYYY":
        return local.strftime("%m/%d/%Y")
    if pattern == "DD-MM-YYYY":
        return local.strftime("%d-%m-%Y")
    if pattern == "D MMM YYYY":
        return f"{local.day} {local.strftime('%b')} {local.year}"
    return local.strftime("%Y-%m-%d")


def format_time(value: datetime, config: dict[str, Any]) -> str:
    local = _as_datetime(value).astimezone(ZoneInfo(config["timezone"]))
    patterns = {"HH:mm": "%H:%M", "HH:mm:ss": "%H:%M:%S", "h:mm A": "%I:%M %p", "h:mm:ss A": "%I:%M:%S %p"}
    rendered = local.strftime(patterns[config["timeFormat"]])
    return rendered[1:] if config["timeFormat"].startswith("h") and rendered.startswith("0") else rendered


def format_number(value: Any, config: dict[str, Any]) -> str:
    try:
        number = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return str(value if value is not None else "")
    standard = f"{number:,.2f}"
    if config["numberFormat"] == "#.##0,00":
        return standard.replace(",", "_").replace(".", ",").replace("_", ".")
    if config["numberFormat"] == "# ##0,00":
        return standard.replace(",", " ").replace(".", ",")
    return standard


def format_currency(value: Any, config: dict[str, Any], currency: str | None = None) -> str:
    code = currency or config["currency"]
    return f"{code} {format_number(value, config)}"
