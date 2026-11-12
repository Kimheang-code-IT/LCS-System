"""Full DR backup/restore integrity checks (no PostgreSQL server needed)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import Conflict, ValidationFailed
from app.modules.backup import dr

pytestmark = pytest.mark.asyncio


class FakeRunner:
    """Stands in for pg_dump (writes to stdout) and pg_restore (no output)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd, stdout=None, stderr=None, capture_output=None, timeout=None):
        self.calls.append([str(part) for part in cmd])
        if "pg_dump" in str(cmd[0]):
            stdout.write(b"FAKE-CUSTOM-DUMP")
        return SimpleNamespace(returncode=0, stderr=b"")


@pytest.fixture()
def archive_root(tmp_path, monkeypatch):
    monkeypatch.setenv("FULL_BACKUP_DIR", str(tmp_path))
    # Runner is injected in these tests, so the binaries are never executed.
    monkeypatch.setenv("PG_DUMP_BIN", str(tmp_path / "pg_dump"))
    monkeypatch.setenv("PG_RESTORE_BIN", str(tmp_path / "pg_restore"))
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("FULL_BACKUP_ALLOW_LIVE_RESTORE", raising=False)
    return tmp_path


async def test_archive_roundtrip_and_verification(archive_root):
    runner = FakeRunner()
    manifest = await dr.build_archive(None, archive_root=archive_root, dsn="postgresql://u:p@db/x", runner=runner)
    archive = archive_root / manifest["archive"]["file"]
    assert archive.exists()
    assert manifest["encryption"]["algorithm"] == "none"

    report = dr.verify_archive(archive)
    assert report["ok"] is True, report["problems"]
    assert report["manifest"]["database"]["sha256"] == manifest["database"]["sha256"]

    # Tampering breaks verification (archive digest mismatch).
    archive.write_bytes(archive.read_bytes() + b"tampered")
    assert dr.verify_archive(archive)["ok"] is False


async def test_encrypted_archive_requires_key(archive_root, monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", key)
    runner = FakeRunner()
    manifest = await dr.build_archive(None, archive_root=archive_root, dsn="postgresql://u:p@db/x", runner=runner)
    archive = archive_root / manifest["archive"]["file"]
    assert archive.name.endswith(".fernet")
    assert manifest["encryption"]["algorithm"] == "fernet"
    assert dr.verify_archive(archive)["ok"] is True

    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY")
    with pytest.raises(ValidationFailed):
        dr.verify_archive(archive)


async def test_restore_requires_confirmation_and_isolated_target(archive_root):
    manifest = await dr.build_archive(None, archive_root=archive_root, dsn="postgresql://u:p@db/x", runner=FakeRunner())
    archive = archive_root / manifest["archive"]["file"]

    with pytest.raises(ValidationFailed):
        dr.restore_archive(archive, target_dsn="postgresql://u:p@restore-check/lcs", confirm="nope")

    # Live database target is refused unless the operator opts in.
    live = dr.libpq_dsn()
    with pytest.raises(Conflict):
        dr.restore_archive(archive, target_dsn=live, confirm="RESTORE")


async def test_restore_into_isolated_target_runs_pg_restore(archive_root):
    manifest = await dr.build_archive(None, archive_root=archive_root, dsn="postgresql://u:p@db/x", runner=FakeRunner())
    archive = archive_root / manifest["archive"]["file"]
    runner = FakeRunner()
    result = dr.restore_archive(
        archive, target_dsn="postgresql://u:p@restore-check/lcs", confirm="RESTORE", runner=runner
    )
    assert result["manifest"]["backupId"] == manifest["backupId"]
    assert any("pg_restore" in call[0] for call in runner.calls)
    assert "--single-transaction" in runner.calls[-1]


async def test_archive_path_rejects_traversal(archive_root):
    with pytest.raises(ValidationFailed):
        dr.archive_path_from_name("../../etc/passwd")
    with pytest.raises(ValidationFailed):
        dr.archive_path_from_name("lcs-full-missing.tar.gz")


def test_path_helpers_confine_user_values(tmp_path):
    # A storage key may be crafted; only its basename reaches the filesystem.
    assert dr._safe_member_name("../../etc/passwd") == "passwd"
    assert dr._safe_member_name(r"..\\..\\windows\\system32") == "system32"
    with pytest.raises(ValidationFailed):
        dr._safe_member_name("..")
    with pytest.raises(ValidationFailed):
        dr._safe_archive_name("lcs-full-ok.tar.gz/../../etc/passwd")
    # Resolution is by name from the trusted backup directory, not by joining
    # the supplied path.
    with pytest.raises(ValidationFailed):
        dr.archive_path_from_name("../../etc/passwd")
