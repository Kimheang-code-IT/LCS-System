from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin
from app.core.types import JSONType


class AppSetting(PKMixin, TimestampMixin, Base):
    """One keyed application-configuration document.

    Settings used to live as a single JSON blob per collection inside
    ``module_records`` (``__app_info__`` / ``__app_config__``). A keyed table
    lets one group be read, validated and written without rewriting the whole
    document, and lets each row carry its own description and last writer.

    ``setting_key`` is the stable identifier the settings API addresses
    (``app_info``, ``general``, ``localization``, ``email``, ``telegram``,
    ``notifications``, ``security``, ``system``, ``backup``); ``setting_value``
    holds that group's JSON payload. Payload shape and validation remain in
    ``app/modules/settings/service.py`` — the table stores values, it does not
    define or execute behaviour.
    """

    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("setting_key", name="uq_app_settings_key"),
        Index("ix_app_settings_group", "setting_group"),
    )

    setting_key: Mapped[str] = mapped_column(String(120), nullable=False)
    setting_group: Mapped[str] = mapped_column(String(60), nullable=False)
    setting_value: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
