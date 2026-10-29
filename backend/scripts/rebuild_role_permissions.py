"""Rebuild every role's Casbin grants from its stored page selection.

The Roles & Permissions screen stores *page* codes; the guards check *capability*
codes, and the compiler in ``app/core/permissions.py`` turns one into the other.
When that compiler is corrected, roles saved before the fix keep the codes it used
to derive. This command recomputes each role's ``p`` rows with the current rules:

    pages        the page codes the role holds (the administrator's intent)
                 + capabilities no page can produce (deliberate grants)
                 -> compiled with ``compile_role_permissions``

It writes only ``p`` rows for roles, never users, sessions, ``g`` rows or business
data, and it is idempotent: a second run reports no changes.

Because it rebuilds from the *page* selection, a capability that some page could
produce but that the role holds without that page is treated as stale and removed.
That is the point of the command; the dry run lists every removal first.

Development only — the command refuses to run against a production environment.

    uv run python scripts/rebuild_role_permissions.py            # dry run
    uv run python scripts/rebuild_role_permissions.py --apply    # write + publish
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core import authorization
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.permissions import (
    DERIVED_PERMISSION_CODES,
    PAGE_PERMISSION_CODES,
    SUPER_ADMIN_ROLE,
    compile_role_permissions,
)
from app.modules.auth.models import Role


def desired_codes(role_code: str, stored: set[str]) -> set[str]:
    """The grant set the current compiler derives from a role's stored selection."""
    if role_code == SUPER_ADMIN_ROLE:
        return {"*"}
    pages = {code for code in stored if code in PAGE_PERMISSION_CODES}
    deliberate = {
        code
        for code in stored
        if code not in PAGE_PERMISSION_CODES and code not in DERIVED_PERMISSION_CODES
    }
    return set(compile_role_permissions(pages | deliberate))


async def rebuild(apply: bool) -> int:
    if settings.environment.strip().lower() == "production":
        print("Refusing to run in production: this command rewrites authorization grants.")
        return 2

    changed = 0
    async with SessionLocal() as session:
        roles = (await session.execute(select(Role).order_by(Role.code))).scalars().all()
        if not roles:
            print("No roles in this database; nothing to rebuild.")
            return 0
        print(f"{'role':16} {'before':>6} {'after':>6}  removed / added")
        for role in roles:
            stored = set(await authorization.role_permission_codes(session, role.code))
            desired = desired_codes(role.code, stored)
            removed = sorted(stored - desired)
            added = sorted(desired - stored)
            state = "ok" if not removed and not added else "rebuild"
            print(
                f"{role.code:16} {len(stored):6} {len(desired):6}  "
                f"-{len(removed)} / +{len(added)}  {state}"
            )
            for code in removed:
                print(f"    - {code}")
            for code in added:
                print(f"    + {code}")
            if removed or added:
                changed += 1
                if apply:
                    await authorization.set_role_permissions(session, role.code, sorted(desired))

        if apply and changed:
            await session.commit()
            await authorization.refresh(session)
            print(f"\nApplied: {changed} role(s) rebuilt and published.")
        elif changed:
            print(f"\nDry run: {changed} role(s) would change. Re-run with --apply to write.")
        else:
            print("\nNo changes: every role already matches the current compiler.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the rebuilt grants (default: report the diff only)",
    )
    args = parser.parse_args()
    return asyncio.run(rebuild(args.apply))


if __name__ == "__main__":
    sys.exit(main())
