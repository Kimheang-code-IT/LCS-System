"""Request schemas for the master-data configuration endpoints.

The component-attribute endpoints are written inline by the configuration grid,
so they need the same schema-level guarantees as the rest of the API: unknown
fields are rejected, camelCase aliases are accepted, and the limits match the
``component_attributes`` columns (``code`` 64, ``label`` 255, ``placeholder``
255). Service-level checks still own the cross-row rules (unique code, valid
data/reference type), because those need a database round-trip.
"""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.modules.master_data.component_config import (
    DATA_CARDINALITIES,
    DATA_TYPES,
    LAYOUT_DISPLAY_MODES,
    RENDER_MODES,
)

ATTRIBUTE_CODE_MAX_LENGTH = 64
ATTRIBUTE_LABEL_MAX_LENGTH = 255
ATTRIBUTE_TEXT_MAX_LENGTH = 255


def _clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    label = value.strip()
    if not label:
        raise ValueError("Label is required.")
    return label


def _validate_data_type(value: str | None) -> str | None:
    if value is None:
        return None
    data_type = value.strip().lower()
    if data_type not in DATA_TYPES:
        raise ValueError(f"Unsupported attribute type: {data_type}")
    return data_type


class ComponentAttributeBase(BaseModel):
    """Fields the configuration grid may write.

    ``extra='forbid'`` is deliberate: an inline PATCH sends one field, and a
    typo must be rejected rather than silently ignored. Unsupported fields are
    refused, not accepted and discarded.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    label: str | None = Field(
        default=None,
        max_length=ATTRIBUTE_LABEL_MAX_LENGTH,
        validation_alias=AliasChoices("label"),
    )
    code: str | None = Field(
        default=None,
        max_length=ATTRIBUTE_CODE_MAX_LENGTH,
        validation_alias=AliasChoices("code"),
    )
    labelKm: str | None = Field(
        default=None,
        max_length=ATTRIBUTE_TEXT_MAX_LENGTH,
        validation_alias=AliasChoices("labelKm", "label_km"),
    )
    dataType: str | None = Field(
        default=None,
        max_length=32,
        validation_alias=AliasChoices("dataType", "data_type"),
    )
    inputType: str | None = Field(
        default=None,
        max_length=32,
        validation_alias=AliasChoices("inputType", "input_type"),
    )
    referenceType: str | None = Field(
        default=None,
        max_length=32,
        validation_alias=AliasChoices("referenceType", "reference_type"),
    )
    isRequired: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("isRequired", "is_required"),
    )
    defaultValue: str | None = Field(
        default=None,
        max_length=ATTRIBUTE_TEXT_MAX_LENGTH,
        validation_alias=AliasChoices("defaultValue", "default_value"),
    )
    placeholder: str | None = Field(
        default=None,
        max_length=ATTRIBUTE_TEXT_MAX_LENGTH,
        validation_alias=AliasChoices("placeholder"),
    )
    width: str | None = Field(
        default=None,
        max_length=16,
        validation_alias=AliasChoices("width"),
    )
    options: list[Any] | None = Field(default=None, validation_alias=AliasChoices("options"))
    validationRules: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("validationRules", "validation_rules"),
    )
    status: str | None = Field(
        default=None,
        max_length=20,
        validation_alias=AliasChoices("status"),
    )
    displayOrder: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("displayOrder", "display_order"),
    )

    @field_validator("label")
    @classmethod
    def _normalise_label(cls, value: str | None) -> str | None:
        return _clean_label(value)

    @field_validator("dataType")
    @classmethod
    def _normalise_data_type(cls, value: str | None) -> str | None:
        return _validate_data_type(value)


class ComponentAttributeCreate(ComponentAttributeBase):
    label: str = Field(
        min_length=1,
        max_length=ATTRIBUTE_LABEL_MAX_LENGTH,
        validation_alias=AliasChoices("label"),
    )

    @field_validator("label")
    @classmethod
    def _normalise_label(cls, value: str) -> str:
        cleaned = _clean_label(value)
        if cleaned is None:
            raise ValueError("Label is required.")
        return cleaned


class ComponentAttributeUpdate(ComponentAttributeBase):
    """Every field is optional: the grid PATCHes one edited cell at a time."""


class ConfigurationPublishRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    changeNote: str | None = Field(
        default=None,
        max_length=2000,
        validation_alias=AliasChoices("changeNote", "change_note"),
    )


class ConfigurationVersionUpdate(BaseModel):
    """The only editable part of a draft: its human-readable name/note."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    changeNote: str = Field(
        min_length=1,
        max_length=2000,
        validation_alias=AliasChoices("changeNote", "change_note"),
    )

    @field_validator("changeNote")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Required")
        return text


class ConfigurationRollbackRequest(BaseModel):
    """A rollback always states why; the reason becomes the new version's note."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason: str = Field(
        min_length=1,
        max_length=2000,
        validation_alias=AliasChoices("reason", "changeNote", "change_note"),
    )

    @field_validator("reason")
    @classmethod
    def _normalise_reason(cls, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise ValueError("A rollback reason is required.")
        return reason



class ComponentTabGroupLayout(BaseModel):
    """Layout settings for one component group *within* one tab.

    Unknown keys are refused so a mistyped layout option cannot be silently
    ignored while the administrator believes it was applied. Cross-field and
    data-loss checks that need a database round-trip stay in the service.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    displayMode: str | None = Field(
        default=None, max_length=20, validation_alias=AliasChoices("displayMode", "display_mode")
    )
    dataCardinality: str | None = Field(
        default=None, max_length=20, validation_alias=AliasChoices("dataCardinality", "data_cardinality")
    )
    formColumns: int | None = Field(
        default=None, ge=1, le=4, validation_alias=AliasChoices("formColumns", "form_columns")
    )
    showGroupTitle: bool | None = Field(
        default=None, validation_alias=AliasChoices("showGroupTitle", "show_group_title")
    )
    editable: bool | None = Field(default=None, validation_alias=AliasChoices("editable"))
    collapsible: bool | None = Field(default=None, validation_alias=AliasChoices("collapsible"))
    defaultExpanded: bool | None = Field(
        default=None, validation_alias=AliasChoices("defaultExpanded", "default_expanded")
    )
    displayOrder: int | None = Field(default=None, validation_alias=AliasChoices("displayOrder", "display_order"))
    status: str | None = Field(default=None, max_length=20, validation_alias=AliasChoices("status"))

    @field_validator("displayMode")
    @classmethod
    def _validate_display_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        mode = value.strip().lower()
        if mode not in LAYOUT_DISPLAY_MODES:
            raise ValueError(f"Unsupported display mode: {mode}")
        return mode

    @field_validator("dataCardinality")
    @classmethod
    def _validate_cardinality(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cardinality = value.strip().lower()
        if cardinality not in DATA_CARDINALITIES:
            raise ValueError(f"Unsupported data cardinality: {cardinality}")
        return cardinality


class ComponentGroupCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code: str | None = Field(default=None, max_length=64, validation_alias=AliasChoices("code"))
    name: str | None = Field(default=None, max_length=255, validation_alias=AliasChoices("name"))
    nameKm: str | None = Field(default=None, max_length=255, validation_alias=AliasChoices("nameKm", "name_km"))
    description: str | None = Field(default=None, max_length=2_000)
    renderMode: str | None = Field(default=None, max_length=16, validation_alias=AliasChoices("renderMode", "render_mode"))
    displayOrder: int | None = Field(default=None, ge=0, validation_alias=AliasChoices("displayOrder", "display_order"))
    isActive: bool | None = Field(default=None, validation_alias=AliasChoices("isActive", "is_active"))

    @field_validator("renderMode")
    @classmethod
    def _validate_render_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        mode = value.strip().lower()
        if mode not in RENDER_MODES:
            raise ValueError("renderMode must be 'table' or 'form'.")
        return mode


class ComponentGroupUpdate(ComponentGroupCreate):
    isArchived: bool | None = Field(default=None, validation_alias=AliasChoices("isArchived", "is_archived"))


class ComponentGroupAttributeCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    attributeId: int | None = Field(default=None, ge=1, validation_alias=AliasChoices("attributeId", "attribute_id"))
    code: str | None = Field(default=None, max_length=64)
    isRequired: bool | None = Field(default=None, validation_alias=AliasChoices("isRequired", "is_required"))
    width: str | None = Field(default=None, max_length=16)
    displayOrder: int | None = Field(default=None, ge=0, validation_alias=AliasChoices("displayOrder", "display_order"))
    isVisible: bool | None = Field(default=None, validation_alias=AliasChoices("isVisible", "is_visible"))
    status: str | None = Field(default=None, max_length=20)


class ComponentGroupAttributeUpdate(ComponentGroupAttributeCreate):
    attributeId: int | None = Field(default=None, ge=1, validation_alias=AliasChoices("attributeId", "attribute_id"))
    code: str | None = Field(default=None, max_length=64)


class ComponentTabCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    nameKm: str | None = Field(default=None, max_length=255, validation_alias=AliasChoices("nameKm", "name_km"))
    description: str | None = Field(default=None, max_length=2_000)
    tradeDirectionId: int | None = Field(
        default=None, ge=1, validation_alias=AliasChoices("tradeDirectionId", "trade_direction_id")
    )
    tradeDirectionIds: list[int] | None = Field(
        default=None, validation_alias=AliasChoices("tradeDirectionIds", "trade_direction_ids")
    )
    displayOrder: int | None = Field(default=None, ge=0, validation_alias=AliasChoices("displayOrder", "display_order"))
    isActive: bool | None = Field(default=None, validation_alias=AliasChoices("isActive", "is_active"))


class ComponentTabUpdate(ComponentTabCreate):
    isArchived: bool | None = Field(default=None, validation_alias=AliasChoices("isArchived", "is_archived"))


class ComponentTabGroupCreate(ComponentTabGroupLayout):
    groupId: int = Field(validation_alias=AliasChoices("groupId", "group_id"))
