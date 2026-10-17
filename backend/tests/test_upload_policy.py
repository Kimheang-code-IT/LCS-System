"""The stored upload allow-list narrows what the environment permits.

`app_settings('security').allowedUploadExtensions` was exposed in the settings UI
and stored, but the backend ignored it entirely and used only the
`UPLOAD_ALLOWED_EXTENSIONS` environment variable. An administrator who disabled
`csv` still saw it accepted.

The stored list can only *narrow* the environment set, never widen it: the
environment list is the operator's control, and ``_UPLOAD_TYPES`` is the set the
content-signature validator understands. Letting a database row add an extension
the validator cannot inspect would turn a validation rule into a hole.
"""

from __future__ import annotations

import pytest

from tests.conftest import login

pytestmark = pytest.mark.asyncio

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


async def _set_extensions(client, headers, extensions: list[str]) -> None:
    response = await client.patch(
        "/api/v1/settings/app-config",
        headers=headers,
        json={"security": {"allowedUploadExtensions": extensions}},
    )
    assert response.status_code == 200, response.text


async def _presign(client, headers, file_name: str):
    return await client.post(
        "/api/v1/attachments/presign", headers=headers, json={"fileName": file_name, "mimeType": ""}
    )


async def test_a_disabled_extension_is_refused(client):
    headers = await login(client)
    assert (await _presign(client, headers, "notes.csv")).status_code == 200

    await _set_extensions(client, headers, ["png", "jpg", "pdf"])
    refused = await _presign(client, headers, "notes.csv")
    assert refused.status_code == 422, refused.text
    assert "file" in refused.json()["field_errors"]

    # And the still-allowed ones keep working.
    assert (await _presign(client, headers, "photo.png")).status_code == 200


async def test_the_stored_list_cannot_widen_the_environment_list(client):
    """An extension the environment forbids must stay forbidden."""
    headers = await login(client)
    # `exe` is not in the environment list nor in the validator's known types.
    await _set_extensions(client, headers, ["png", "exe"])

    refused = await _presign(client, headers, "installer.exe")
    assert refused.status_code == 422, refused.text


async def test_an_empty_stored_list_falls_back_to_the_environment(client):
    """Clearing the field is ambiguous; refusing every upload would be worse."""
    headers = await login(client)
    await _set_extensions(client, headers, [])

    assert (await _presign(client, headers, "document.pdf")).status_code == 200


async def test_a_disabled_extension_is_refused_on_upload_not_just_presign(client):
    """Presign is advisory; the upload is the authoritative check."""
    headers = await login(client)
    await _set_extensions(client, headers, ["png"])

    refused = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        files={"file": ("payload.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert refused.status_code == 422, refused.text

    accepted = await client.post(
        "/api/v1/attachments/upload",
        headers=headers,
        files={"file": ("shot.png", _PNG, "image/png")},
    )
    assert accepted.status_code == 201, accepted.text
