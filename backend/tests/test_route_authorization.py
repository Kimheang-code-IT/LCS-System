"""Every registered route must authenticate, and all but the public list authorize.

This is the gate that was missing: a new router without a guard used to be reachable
by any signed-in user and no check failed. It is deliberately shallow — it walks the
FastAPI dependency graph and looks for ``get_current_context`` (or the optional
variant) — because *which* permission a route needs is decided per endpoint and
covered by the RBAC tests.

A route that legitimately needs no authentication must be added to
``PUBLIC_ROUTES`` in the same change, which keeps this list a reviewed decision
instead of an accident.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.core import deps
from app.main import app

GUARD_NAMES = frozenset(
    {
        deps.get_current_context.__name__,
        deps.get_optional_context.__name__,
    }
)

#: Unauthenticated by design. Each entry needs a reason; a public endpoint that
#: touches data must authenticate some other way (the Telegram webhook checks its
#: own secret header).
PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/health/ready"),
        ("GET", "/"),
        ("GET", "/api/v1/health"),
        # First-run bootstrap; the handler refuses once a user exists.
        ("GET", "/api/v1/auth/setup/status"),
        ("POST", "/api/v1/auth/setup/initialize"),
        # Login/refresh carry the credential in the request itself.
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/refresh"),
        # Self-service recovery, rate limited and code based.
        ("POST", "/api/v1/auth/forgot-password"),
        ("POST", "/api/v1/auth/forgot-password/verify"),
        ("POST", "/api/v1/auth/forgot-password/resend"),
        ("POST", "/api/v1/auth/forgot-password/reset"),
        # Authenticated by Telegram's secret token header, not by a session.
        ("POST", "/api/v1/integrations/telegram/webhook"),
    }
)


def _walk(router, prefix: str = "", seen: set[int] | None = None):
    """Yield ``(absolute_path, APIRoute)`` for every route, however it is included.

    This FastAPI version keeps an included router as a wrapper instead of flattening
    it, so the mount prefix is read from the wrapper's include context and carried
    down. Nested routers inherit the prefix they were mounted under.
    """
    seen = seen if seen is not None else set()
    for route in getattr(router, "routes", []):
        if id(route) in seen:
            continue
        seen.add(id(route))
        if isinstance(route, APIRoute):
            yield f"{prefix}{route.path}", route
            continue
        context = getattr(route, "include_context", None)
        mount = getattr(context, "prefix", "") or ""
        inner = getattr(route, "original_router", None) or getattr(route, "router", None)
        if inner is not None:
            yield from _walk(inner, f"{prefix}{mount}", seen)
        elif hasattr(route, "routes"):
            yield from _walk(route, prefix, seen)


def _reaches_guard(dependant, seen: set[int] | None = None) -> bool:
    seen = seen if seen is not None else set()
    if id(dependant) in seen:
        return False
    seen.add(id(dependant))
    if getattr(dependant.call, "__name__", "") in GUARD_NAMES:
        return True
    return any(_reaches_guard(child, seen) for child in dependant.dependencies)


def _route_table() -> dict[tuple[str, str], bool]:
    table: dict[tuple[str, str], bool] = {}
    for path, route in _walk(app.router):
        guarded = _reaches_guard(route.dependant)
        for method in sorted(route.methods or ()):
            table[(method, path)] = guarded
    return table


def test_route_inventory_is_not_empty():
    """Guard against a refactor making the walker silently see nothing."""
    table = _route_table()
    assert len(table) > 300, f"only found {len(table)} routes; the walker is broken"


def test_every_route_authenticates_unless_it_is_on_the_public_list():
    unguarded = {key for key, guarded in _route_table().items() if not guarded}
    assert unguarded == set(PUBLIC_ROUTES), (
        "a route requires no authentication and is not on PUBLIC_ROUTES: "
        f"{sorted(unguarded - PUBLIC_ROUTES)}; "
        "stale entries (route gone or now guarded): "
        f"{sorted(PUBLIC_ROUTES - unguarded)}"
    )
