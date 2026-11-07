"""Focused tests for the multi-provider storage feature."""

from __future__ import annotations

from app.core.exceptions import ValidationFailed
from app.modules.settings.service import (
    DEFAULT_APP_CONFIG,
    _validate_storage_config,
    redact_app_config,
)
from app.modules.storage.models import StorageReplica


def test_storage_defaults_exist() -> None:
    storage = DEFAULT_APP_CONFIG["storage"]
    assert storage["primaryProvider"] == ""
    assert set(storage["providers"]) == {"r2", "gdrive"}


def test_validate_storage_rejects_identical_destinations() -> None:
    base = {
        "primaryProvider": "r2",
        "backupProvider": "r2",
        "backupEnabled": True,
        "backupIntervalHours": 24,
        "backupMaxRetries": 3,
        "providers": {},
    }
    try:
        _validate_storage_config(base)
    except ValidationFailed as exc:
        assert "storage.backupProvider" in exc.field_errors
    else:  # pragma: no cover
        raise AssertionError("identical destinations must be refused")


def test_redaction_never_returns_storage_secrets() -> None:
    payload = {
        "storage": {
            "primaryProvider": "r2",
            "providers": {
                "r2": {"secretAccessKey": "supersecret", "bucketName": "bucket"},
                "gdrive": {
                    "clientSecret": "gsecret",
                    "serviceAccountJson": "{}",
                    "refreshTokenEncrypted": "enc:v1:abc",
                    "connectedEmail": "user@example.com",
                },
            },
        },
    }
    redacted = redact_app_config(payload)["storage"]
    r2 = redacted["providers"]["r2"]
    gdrive = redacted["providers"]["gdrive"]
    assert "supersecret" not in str(redacted)
    assert "gsecret" not in str(redacted)
    assert "enc:v1:abc" not in str(redacted)
    assert r2["secretAccessKeyConfigured"] is True
    assert gdrive["clientSecretConfigured"] is True
    assert gdrive["serviceAccountConfigured"] is True
    assert gdrive["connectedEmail"] == "user@example.com"


def test_replica_statuses_vocabulary() -> None:
    replica = StorageReplica(attachment_id=1, backup_provider="r2", backup_key="-", status="PENDING")
    assert replica.status == "PENDING"
