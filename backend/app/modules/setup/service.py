from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bootstrap import provision_admin, requires_setup
from app.core.exceptions import Conflict, ValidationFailed


async def status(session: AsyncSession) -> dict[str, bool]:
    """Public first-run probe: true while no user account exists."""
    return {"requiresSetup": await requires_setup(session)}


async def initialize(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    if not await requires_setup(session):
        raise Conflict("SETUP_COMPLETED", "Setup has already been completed.")

    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    errors: dict[str, str] = {}
    if "@" not in email:
        errors["email"] = "A valid email address is required."
    if len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    if errors:
        raise ValidationFailed("The submitted data is invalid.", errors)

    try:
        return await provision_admin(
            session,
            email=email,
            password=password,
            username=str(payload.get("username") or "").strip() or None,
            name=str(payload.get("name") or "").strip() or None,
        )
    except ValueError as error:
        raise ValidationFailed(str(error), {"role": str(error)}) from error
