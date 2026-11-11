"""Full disaster-recovery backup / verify / restore CLI (run outside the app).

Examples (inside the backend container or a host venv with PG client tools):

    python scripts/full_backup.py backup                # archive + object upload
    python scripts/full_backup.py list
    python scripts/full_backup.py verify lcs-full-20261110T020000Z.tar.gz.fernet
    python scripts/full_backup.py restore lcs-full-....tar.gz.fernet \
        --target-dsn postgresql://user:pass@isolated-host:5432/restore_check --confirm RESTORE

Restore never targets the live database unless FULL_BACKUP_ALLOW_LIVE_RESTORE=1.
The archive contains a pg_dump custom dump and the uploaded attachments; the
encryption key (BACKUP_ENCRYPTION_KEY) stays outside the archive.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _print(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


async def cmd_backup(args) -> int:
    from app.core.database import SessionLocal
    from app.modules.backup import dr

    async with SessionLocal() as session:
        manifest = await dr.build_archive(session)
        archive = dr.archive_dir() / manifest["archive"]["file"]
        remote = None if args.no_upload else await dr.upload_archive(session, archive)
    _print({"archive": str(archive), "remoteKey": remote, **manifest})
    return 0


def cmd_list(_args) -> int:
    from app.modules.backup import dr

    _print({"items": dr.list_archives()})
    return 0


def cmd_verify(args) -> int:
    from app.modules.backup import dr

    report = dr.verify_archive(dr.archive_path_from_name(args.file))
    _print({"ok": report["ok"], "problems": report["problems"]})
    return 0 if report["ok"] else 2


def cmd_restore(args) -> int:
    from app.modules.backup import dr

    result = dr.restore_archive(
        dr.archive_path_from_name(args.file),
        target_dsn=args.target_dsn,
        confirm=args.confirm,
        key=os.environ.get("BACKUP_ENCRYPTION_KEY") or None,
    )
    _print(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LCS full disaster-recovery backups")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup", help="create a full backup archive")
    backup.add_argument("--no-upload", action="store_true", help="keep the archive local only")
    backup.set_defaults(func=cmd_backup)

    listing = sub.add_parser("list", help="list local full backup archives")
    listing.set_defaults(func=cmd_list)

    verify = sub.add_parser("verify", help="verify one archive's integrity")
    verify.add_argument("file")
    verify.set_defaults(func=cmd_verify)

    restore = sub.add_parser("restore", help="verified restore into an isolated database")
    restore.add_argument("file")
    restore.add_argument("--target-dsn", required=True)
    restore.add_argument("--confirm", required=True)
    restore.set_defaults(func=cmd_restore)

    args = parser.parse_args()
    result = args.func(args)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
