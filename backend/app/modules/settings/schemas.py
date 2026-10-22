"""Request schemas for application settings and the danger-zone actions.

Settings payloads are nested documents, so the top level is checked here (an
unknown group or field is refused rather than silently written) while each
group's own semantics stay with the code that consumes it: localization has its
own validator, and backup/R2 completeness is checked by ``_validate_backup_config``.
"""

from __future__ import annotations

from app.core.validation import (
    INVALID_TYPE,
    CrossFieldRule,
    FieldSpec,
    RecordSchema,
)

APP_INFO_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("applicationName", max_length=255, aliases=("application_name",)),
        FieldSpec("shortName", max_length=100, aliases=("short_name",)),
        FieldSpec("description", max_length=2_000),
        FieldSpec("supportEmail", kind="email", max_length=255, aliases=("support_email",)),
        FieldSpec("supportPhone", kind="phone", max_length=32, aliases=("support_phone",)),
        FieldSpec("website", kind="url", max_length=500),
        FieldSpec("address", max_length=1_000),
        FieldSpec("branding", kind="json"),
        FieldSpec("footer", kind="json"),
    ),
    readonly=("updatedAt",),
    reject_unknown=True,
)


def _groups_are_objects(values: dict) -> tuple[str, str, str] | None:
    for group in (
        "general",
        "localization",
        "email",
        "telegram",
        "notifications",
        "security",
        "system",
        "backup",
    ):
        if group in values and not isinstance(values[group], dict):
            return group, INVALID_TYPE, "Provide a settings object."
    return None


APP_CONFIG_WRITE_SCHEMA = RecordSchema(
    tuple(
        FieldSpec(group, kind="json")
        for group in (
            "general",
            "localization",
            "email",
            "telegram",
            "notifications",
            "security",
            "system",
            "backup",
        )
    ),
    cross_field=(CrossFieldRule(("general", "localization"), _groups_are_objects),),
    readonly=("updatedAt",),
    reject_unknown=True,
)

RESET_DATA_SCHEMA = RecordSchema(
    (
        FieldSpec("confirm", required=True, min_length=1, max_length=16),
    ),
    reject_unknown=True,
)

SEARCH_ASK_SCHEMA = RecordSchema(
    (
        FieldSpec("q", max_length=500),
        FieldSpec("hitIds", kind="json", aliases=("hit_ids",)),
    ),
    reject_unknown=True,
)
