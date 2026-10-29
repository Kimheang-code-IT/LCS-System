"""Casbin authorization engine — the single source of authorization truth.

Policy storage
--------------
``casbin_rule`` holds every grant and role assignment. Roles hold their own
grants only — there is no role inheritance, so a `g` row is always
``user:<id> -> role:<code>`` and each user holds exactly one. The enforcer keeps
a compiled, in-memory copy of that table; ``can`` never reads PostgreSQL, so an
enforcement check costs nothing but a matcher evaluation.

Synchronization
---------------
Every policy mutation commits the new rows and then calls ``refresh``: it bumps
the existing ``auth`` cache version in Redis and reloads the local enforcer. A
request in another worker notices the changed version and reloads before it
decides anything. ``casbin_reload_interval_seconds`` is the backstop for a
Redis outage or ``REDIS_ENABLED=false``: policies are re-read from PostgreSQL at
least that often, so a stale in-memory copy can never outlive the interval.

Fail closed
-----------
If the policy table cannot be read, the enforcer is dropped instead of serving
the previous copy, and every check answers *deny* until a reload succeeds.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable
from pathlib import Path

import casbin
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.authorization.models import CasbinRule
from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.permissions import SUPER_ADMIN_WILDCARD

logger = logging.getLogger(__name__)

MODEL_FILE = Path(__file__).with_name("model.conf")
POLICY = "p"
GROUPING = "g"
_POLICY_TOKENS = 3
_GROUPING_TOKENS = 2
_FIELDS = ("v0", "v1", "v2", "v3", "v4", "v5")


class AuthorizationUnavailable(DomainError):
    """Raised when no policy state can be loaded. Never grants access."""

    def __init__(self, message: str = "Authorization policies are unavailable. Try again shortly.") -> None:
        super().__init__("AUTHORIZATION_UNAVAILABLE", message, status_code=503)


_state: casbin.Enforcer | None = None
_loaded_version: int | None = None
_loaded_at: float = 0.0
_lock = asyncio.Lock()


# --- Subject and code helpers -------------------------------------------------
def user_subject(user_id: int) -> str:
    return f"user:{user_id}"


def role_subject(role_code: str) -> str:
    return f"role:{role_code}"


def split_code(code: str) -> tuple[str, str]:
    """``quotation.update_draft`` -> ``("quotation", "update_draft")``.

    The super-admin wildcard is every object *and* every action. Splitting it by
    the dot rule would store ``("*", "")``, a two-token policy row the loader
    rejects — which silently removed the only grant the protected administrator
    held and denied every request.
    """
    text = str(code or "")
    if text == "*":
        return SUPER_ADMIN_WILDCARD
    obj, separator, act = text.rpartition(".")
    if not separator:
        return text, ""
    return obj, act


def join_code(obj: str, act: str) -> str:
    if obj == "*" and act in ("", "*"):
        return "*"
    return f"{obj}.{act}"


def _role_code_of(subject: str) -> str | None:
    return subject[len("role:") :] if subject.startswith("role:") else None


# --- Loading ------------------------------------------------------------------
def _model_text() -> str:
    return MODEL_FILE.read_text(encoding="utf-8")


def _build(rows: Iterable[tuple[str, list[str]]]) -> casbin.Enforcer:
    model = casbin.Model()
    model.load_model_from_text(_model_text())
    for ptype, values in rows:
        model.add_policy(ptype, ptype, values)
    enforcer = casbin.Enforcer(model)
    enforcer.build_role_links()
    return enforcer


async def _load_rows(session: AsyncSession) -> list[tuple[str, list[str]]]:
    """Read the policy table, dropping grants held by inactive or deleted roles."""
    from app.modules.auth.models import Role

    statuses = {
        code: str(status or "").upper()
        for code, status in (await session.execute(select(Role.code, Role.status))).all()
    }
    rules = (
        await session.execute(
            select(CasbinRule).where(CasbinRule.ptype.in_((POLICY, GROUPING))).order_by(CasbinRule.id)
        )
    ).scalars().all()

    def active(subject: str) -> bool:
        code = _role_code_of(subject)
        return code is None or statuses.get(code) == "ACTIVE"

    rows: list[tuple[str, list[str]]] = []
    for rule in rules:
        values = [getattr(rule, field) for field in _FIELDS]
        while values and values[-1] == "":
            values.pop()
        if rule.ptype == POLICY:
            # A wildcard row written before ``split_code`` knew about ``*`` has no
            # action token. Treat it as the full wildcard instead of dropping the
            # protected administrator's only grant.
            if len(values) == 2 and values[1] == "*":
                values.append("*")
            if len(values) != _POLICY_TOKENS or not active(values[0]):
                continue
        elif len(values) != _GROUPING_TOKENS or not active(values[0]) or not active(values[1]):
            continue
        # Roles do not inherit: a legacy ``role:X -> role:Y`` edge is ignored, and
        # only user→role assignment edges are loaded.
        if rule.ptype == GROUPING and values[0].startswith("role:"):
            continue
        rows.append((rule.ptype, values))
    return rows


async def reload(session: AsyncSession) -> casbin.Enforcer:
    """Replace the in-memory policy copy with the committed database state.

    The published version is read **before** the rows. A change committed while
    the rows are being read therefore leaves a newer version in Redis than the one
    recorded here, and the next request reloads instead of trusting a copy that
    missed it.
    """
    global _state, _loaded_version, _loaded_at
    async with _lock:
        try:
            version = await _version()
            rows = await _load_rows(session)
            enforcer = _build(rows)
        except Exception as exc:
            # Fail closed: never keep serving the previous copy.
            _state = None
            raise AuthorizationUnavailable() from exc
        _state = enforcer
        _loaded_version = version
        _loaded_at = time.monotonic()
        logger.info("Casbin policies loaded: %d rules", len(rows))
        return enforcer


async def _version() -> int | None:
    if not cache.enabled():
        return None
    return await cache.version("auth")


async def ensure_current(session: AsyncSession) -> None:
    """Reload first when another worker published a change (or the copy is old).

    Raising here is deliberate: without a verified policy copy the request is
    refused with ``503 AUTHORIZATION_UNAVAILABLE`` rather than decided.
    """
    global _loaded_at
    if _state is None:
        await reload(session)
        return
    now = time.monotonic()
    version = await _version()
    if version is not None and version != _loaded_version:
        await reload(session)
        return
    if now - _loaded_at >= max(int(settings.casbin_reload_interval_seconds), 1):
        await reload(session)


async def refresh(session: AsyncSession) -> None:
    """Publish a committed policy change and reload this worker immediately."""
    await cache.bump("auth")
    try:
        await reload(session)
    except Exception:  # noqa: BLE001 - the write already committed
        logger.exception("Casbin reload after a policy change failed; denying until it succeeds")


# --- Decisions ----------------------------------------------------------------
def is_loaded() -> bool:
    """True once a policy copy has been loaded (and not dropped after a failure)."""
    return _state is not None


def can(user_id: int, code: str) -> bool:
    """True when the user holds ``code`` through its assigned role."""
    enforcer = _state
    if enforcer is None:
        return False
    obj, act = split_code(code)
    try:
        return bool(enforcer.enforce(user_subject(user_id), obj, act))
    except Exception:  # noqa: BLE001 - a broken matcher must deny, not allow
        logger.exception("Casbin enforcement failed for %s", code)
        return False


def can_any(user_id: int, codes: Iterable[str]) -> bool:
    return any(can(user_id, code) for code in codes)


def is_super_admin(user_id: int) -> bool:
    """Holds the protected ``*, *`` grant."""
    enforcer = _state
    if enforcer is None:
        return False
    try:
        return bool(enforcer.enforce(user_subject(user_id), "*", "*"))
    except Exception:  # noqa: BLE001
        return False


def effective_codes(user_id: int) -> frozenset[str]:
    """Every code the user holds (``*`` for super admin)."""
    enforcer = _state
    if enforcer is None:
        return frozenset()
    try:
        rows = enforcer.get_implicit_permissions_for_user(user_subject(user_id))
    except Exception:  # noqa: BLE001
        logger.exception("Casbin role resolution failed for user %s", user_id)
        return frozenset()
    return frozenset(join_code(row[-2], row[-1]) for row in rows if len(row) >= 3)


# --- Policy reads (database, transaction-consistent) ---------------------------
async def user_role_codes(session: AsyncSession, user_id: int) -> list[str]:
    codes = (
        await session.execute(
            select(CasbinRule.v1).where(
                CasbinRule.ptype == GROUPING,
                CasbinRule.v0 == user_subject(user_id),
                CasbinRule.v1.like("role:%"),
            )
        )
    ).scalars().all()
    return sorted(_role_code_of(code) or code for code in codes if code)


async def users_role_codes(session: AsyncSession, user_ids: Iterable[int]) -> dict[int, list[str]]:
    ids = [int(value) for value in user_ids]
    result: dict[int, list[str]] = {user_id: [] for user_id in ids}
    if not ids:
        return result
    rows = (
        await session.execute(
            select(CasbinRule.v0, CasbinRule.v1).where(
                CasbinRule.ptype == GROUPING,
                CasbinRule.v0.in_([user_subject(user_id) for user_id in ids]),
                CasbinRule.v1.like("role:%"),
            )
        )
    ).all()
    for subject, role in rows:
        try:
            user_id = int(subject.split(":", 1)[1])
        except (IndexError, ValueError):
            continue
        code = _role_code_of(role or "")
        if code and code not in result.get(user_id, []):
            result.setdefault(user_id, []).append(code)
    for codes in result.values():
        codes.sort()
    return result


async def role_permission_codes(session: AsyncSession, role_code: str) -> list[str]:
    rows = (
        await session.execute(
            select(CasbinRule.v1, CasbinRule.v2).where(
                CasbinRule.ptype == POLICY,
                CasbinRule.v0 == role_subject(role_code),
            )
        )
    ).all()
    return sorted(join_code(obj or "", act or "") for obj, act in rows)


async def roles_permission_codes(session: AsyncSession, role_codes: Iterable[str]) -> dict[str, list[str]]:
    codes = [code for code in role_codes]
    result: dict[str, list[str]] = {code: [] for code in codes}
    if not codes:
        return result
    rows = (
        await session.execute(
            select(CasbinRule.v0, CasbinRule.v1, CasbinRule.v2).where(
                CasbinRule.ptype == POLICY,
                CasbinRule.v0.in_([role_subject(code) for code in codes]),
            )
        )
    ).all()
    for subject, obj, act in rows:
        code = _role_code_of(subject or "")
        if code in result:
            result[code].append(join_code(obj or "", act or ""))
    for values in result.values():
        values.sort()
    return result


async def user_counts_by_role(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(
            select(CasbinRule.v1).where(CasbinRule.ptype == GROUPING, CasbinRule.v0.like("user:%"))
        )
    ).scalars().all()
    counts: dict[str, int] = {}
    for value in rows:
        code = _role_code_of(value or "")
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts


async def users_with_role(session: AsyncSession, role_code: str) -> list[int]:
    subjects = (
        await session.execute(
            select(CasbinRule.v0).where(
                CasbinRule.ptype == GROUPING,
                CasbinRule.v1 == role_subject(role_code),
                CasbinRule.v0.like("user:%"),
            )
        )
    ).scalars().all()
    ids: list[int] = []
    for subject in subjects:
        try:
            ids.append(int(subject.split(":", 1)[1]))
        except (IndexError, ValueError):
            continue
    return ids


# --- Policy writes ------------------------------------------------------------
async def set_user_roles(session: AsyncSession, user_id: int, role_codes: Iterable[str]) -> None:
    """Replace every role assignment of one user with exactly ``role_codes``."""
    subject = user_subject(user_id)
    await session.execute(
        delete(CasbinRule).where(CasbinRule.ptype == GROUPING, CasbinRule.v0 == subject)
    )
    for code in dict.fromkeys(str(value).strip() for value in role_codes if str(value).strip()):
        session.add(CasbinRule(ptype=GROUPING, v0=subject, v1=role_subject(code)))
    await session.flush()


async def delete_user_policies(session: AsyncSession, user_id: int) -> None:
    subject = user_subject(user_id)
    await session.execute(
        delete(CasbinRule).where(
            CasbinRule.ptype.in_((POLICY, GROUPING)),
            CasbinRule.v0 == subject,
        )
    )


async def set_role_permissions(session: AsyncSession, role_code: str, codes: Iterable[str]) -> None:
    """Replace a role's own grants."""
    subject = role_subject(role_code)
    await session.execute(
        delete(CasbinRule).where(CasbinRule.ptype == POLICY, CasbinRule.v0 == subject)
    )
    for code in dict.fromkeys(str(value).strip() for value in codes if str(value).strip()):
        obj, act = split_code(code)
        session.add(CasbinRule(ptype=POLICY, v0=subject, v1=obj, v2=act))
    await session.flush()


async def delete_role_policies(session: AsyncSession, role_code: str) -> None:
    subject = role_subject(role_code)
    await session.execute(
        delete(CasbinRule).where(
            CasbinRule.ptype == POLICY,
            CasbinRule.v0 == subject,
        )
    )
    await session.execute(
        delete(CasbinRule).where(
            CasbinRule.ptype == GROUPING,
            (CasbinRule.v0 == subject) | (CasbinRule.v1 == subject),
        )
    )
    await session.flush()

