"""Thin Google Sheets client used by the backup engine.

The client is intentionally small: it creates worksheets, keeps the header row in
sync with the live database schema and appends rows. Every network call is
retried with exponential backoff on transient failures (HTTP 429 and 5xx,
timeouts and connection errors) so a flaky Google API does not abort a run.

The Google libraries are imported lazily so the rest of the application (and the
test suite) can run without them installed.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

META_COLUMNS: tuple[str, ...] = (
    "_backup_at",
    "_backup_version",
    "_table",
    "_record_id",
    "_row_hash",
    "_change_kind",
)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
# Google Sheets worksheet titles: max 100 chars, no []:*?/\
_INVALID_TITLE_CHARS = set("[]:*?/\\")


class BackupConfigurationError(RuntimeError):
    """Raised when the backup settings (credentials/spreadsheet) are unusable."""


class SheetsApiError(RuntimeError):
    """Raised after a Google Sheets request exhausts its retries."""


def sanitize_worksheet_title(table_name: str, prefix: str = "") -> str:
    raw = f"{prefix}{table_name}"
    cleaned = "".join("_" if char in _INVALID_TITLE_CHARS else char for char in raw)
    return cleaned[:100] or "backup"


class GoogleSheetsClient:
    def __init__(
        self,
        service_account: dict[str, Any] | str,
        spreadsheet_id: str,
        *,
        retries: int = 4,
        retry_base_delay: float = 1.0,
        retry_factor: float = 2.0,
        prefix: str = "",
    ) -> None:
        if not spreadsheet_id:
            raise BackupConfigurationError("A Google spreadsheet ID is required.")
        if isinstance(service_account, str):
            try:
                service_account = json.loads(service_account)
            except (TypeError, ValueError) as exc:
                raise BackupConfigurationError("Service account JSON is not valid JSON.") from exc
        if not isinstance(service_account, dict) or "client_email" not in service_account:
            raise BackupConfigurationError("Service account JSON is missing 'client_email'.")

        self._info = service_account
        self._spreadsheet_id = spreadsheet_id
        self._retries = max(0, retries)
        self._retry_base_delay = retry_base_delay
        self._retry_factor = retry_factor
        self._prefix = prefix
        self._service = None
        self._worksheet_cache: set[str] = set()

    @property
    def spreadsheet_id(self) -> str:
        return self._spreadsheet_id

    @property
    def service_account_email(self) -> str:
        return str(self._info.get("client_email") or "")

    # --- transport ---------------------------------------------------------
    def _api(self):
        if self._service is None:
            try:
                from google.oauth2 import service_account as sa
                from googleapiclient.discovery import build
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise BackupConfigurationError(
                    "Google API client libraries are not installed. "
                    "Install google-api-python-client and google-auth."
                ) from exc
            credentials = sa.Credentials.from_service_account_info(
                self._info,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        return self._service

    def _run(self, build_request: Callable[[], Any]) -> Any:
        from googleapiclient.errors import HttpError

        delay = self._retry_base_delay
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                return build_request().execute()
            except HttpError as exc:  # pragma: no cover - network path
                last_error = exc
                status = getattr(getattr(exc, "resp", None), "status", None)
                if status not in _RETRY_STATUSES or attempt == self._retries:
                    raise SheetsApiError(f"Google Sheets returned HTTP {status}: {exc}") from exc
            except (TimeoutError, ConnectionError, OSError) as exc:  # pragma: no cover
                last_error = exc
                if attempt == self._retries:
                    raise SheetsApiError(f"Google Sheets request failed: {exc}") from exc
            time.sleep(delay)
            delay *= self._retry_factor
        raise SheetsApiError("Google Sheets request failed.") from last_error

    # --- worksheets --------------------------------------------------------
    def _values(self):
        return self._api().spreadsheets().values()

    def _sheet_titles(self) -> list[str]:
        meta = self._run(lambda: self._api().spreadsheets().get(spreadsheetId=self._spreadsheet_id))
        return [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]

    def worksheet_title(self, table_name: str) -> str:
        return sanitize_worksheet_title(table_name, self._prefix)

    def ensure_worksheet(self, table_name: str) -> str:
        title = self.worksheet_title(table_name)
        if title in self._worksheet_cache:
            return title
        if title not in self._sheet_titles():
            body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
            self._run(
                lambda: self._api().spreadsheets().batchUpdate(
                    spreadsheetId=self._spreadsheet_id, body=body
                )
            )
        self._worksheet_cache.add(title)
        return title

    def get_header(self, title: str) -> list[str]:
        result = self._run(
            lambda: self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{title}!1:1")
        )
        values = result.get("values", [])
        return [str(cell) for cell in values[0]] if values else []

    def ensure_header(self, title: str, columns: list[str]) -> list[str]:
        desired = list(META_COLUMNS) + [column for column in columns if column not in META_COLUMNS]
        existing = self.get_header(title)
        # Preserve the order already in the sheet and append newly discovered
        # columns so schema changes never rewrite existing data.
        merged = list(existing) + [column for column in desired if column not in existing]
        if merged != existing:
            self._run(
                lambda: self._values().update(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"{title}!A1",
                    valueInputOption="RAW",
                    body={"values": [merged]},
                )
            )
        return merged

    def append_rows(self, title: str, rows: list[list[Any]]) -> None:
        if not rows:
            return
        self._run(
            lambda: self._values().append(
                spreadsheetId=self._spreadsheet_id,
                range=f"{title}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            )
        )

    def read_rows(self, title: str) -> list[list[str]]:
        result = self._run(
            lambda: self._values().get(spreadsheetId=self._spreadsheet_id, range=f"{title}!A1:ZZ")
        )
        return [[str(cell) for cell in row] for row in result.get("values", [])]

    def worksheet_exists(self, table_name: str) -> bool:
        return self.worksheet_title(table_name) in self._sheet_titles()

    def test_connection(self) -> dict[str, Any]:
        meta = self._run(lambda: self._api().spreadsheets().get(spreadsheetId=self._spreadsheet_id))
        return {
            "title": meta.get("properties", {}).get("title", ""),
            "sheets": [sheet["properties"]["title"] for sheet in meta.get("sheets", [])],
            "serviceAccountEmail": self.service_account_email,
        }
