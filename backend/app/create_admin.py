"""Provision the first administrator account (CLI).

The in-browser setup page (`/setup` → `/api/v1/setup/initialize`) is the
recommended path. This command remains for automation and Docker/CI.

Usage::

    python -m app.create_admin --email admin@example.com --password 'Passw0rd!'
    python -m app.create_admin --email admin@example.com --password 'secret' \
        --role ADMINISTRATOR

Inside Docker::

    docker compose -f infrastructure/docker-compose.yml exec backend \
        python -m app.create_admin --email admin@example.com --password 'Passw0rd!'
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.bootstrap import provision_admin
from app.core.database import SessionLocal


async def create_admin(args: argparse.Namespace) -> dict:
    async with SessionLocal() as session:
        return await provision_admin(
            session,
            email=args.email,
            password=args.password,
            username=args.username,
            name=args.name,
            user_code=args.user_code,
            role_code=args.role,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or update the first administrator account.")
    parser.add_argument("--email", required=True, help="Login email address.")
    parser.add_argument("--password", required=True, help="Password for the account.")
    parser.add_argument("--username", help="Login username (defaults to the email local part).")
    parser.add_argument("--name", help="Display name (defaults to a title-cased username).")
    parser.add_argument("--user-code", help="Unique user code (defaults to the upper-case username).")
    parser.add_argument("--role", default="PLATFORM_ADMIN", help="Role code to assign (default: PLATFORM_ADMIN).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(create_admin(args))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print("Administrator ready:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
