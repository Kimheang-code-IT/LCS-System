"""Google Sheets backup engine.

Design goals mapped to the requirements:

* **Separate from application transactions** — every step opens its own
  :class:`AsyncSession`; the Google API is called outside any database
  transaction and never inside a request. A Google outage cannot roll back or
  block normal CRUD.
* **Append-only history** — :class:`BackupRecord` rows and worksheet rows are
  only ever inserted, never deleted or overwritten.
* **New rows appended, updates versioned** — a SHA-256 hash per row is compared
  with :class:`BackupState`; unchanged rows are skipped, new rows are stored as
  ``insert`` and changed rows as a new ``update`` version.
* **Duplicate prevention** — a unique constraint on
  ``(table_name, record_id, row_hash)`` plus de-duplication against the hashes
  already present in the worksheet.
* **Schema changes** — worksheet headers are reconciled with the live table
  columns (new columns are appended) and restore ignores columns the database no
  longer has.
* **Failure recovery** — records are stored locally first with ``synced=False``;
  failed Google API writes are retried on the next run without losing data.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    func,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.schema import Column, Table

from app.core.crypto import is_sensitive_field
from app.core.database import SessionLocal, utcnow
from app.modules.backup.models import BackupLog, BackupRecord, BackupRun, BackupState
from app.modules.backup.sheets import (
    META_COLUMNS,
    BackupConfigurationError,
    GoogleSheetsClient,
    SheetsApiError,
    sanitize_worksheet_title,
)
from app.modules.settings import service as settings_service

logger = logging.getLogger(__name__)

BACKUP_CONFIRM = "RESTORE"
DEFAULT_BATCH_SIZE = 500
SHEET_CHUNK_SIZE = 1000
# Column names that must never be copied to an external spreadsheet.
SENSITIVE_HINTS = ("password", "secret", "token", "credential", "private")


# --- configuration -----------------------------------------------------------
async def _load_backup_config(session: AsyncSession) -> dict[str, Any]:
    config = await settings_service.get_app_config(session)
    return dict(config.get("backup") or {})


async def _store_backup_status(session: AsyncSession, *, status: str, message: str, when: str) -> None:
    await settings_service.update_app_config(
        session,
        None,
        {"backup": {"lastRunAt": when, "lastRunStatus": status, "lastRunMessage": message}},
    )


def _excluded_tables(config: dict[str, Any]) -> set[str]:
    names = {str(name) for name in (config.get("excludedTables") or [])}
    names.update({"alembic_version"})
    return names


def build_client(config: dict[str, Any]) -> GoogleSheetsClient:
    """Create a Sheets client from config, raising ``BackupConfigurationError``."""
    spreadsheet_id = str(config.get("spreadsheetId") or "").strip()
    credentials = config.get("serviceAccountJson") or ""
    if not spreadsheet_id:
        raise BackupConfigurationError("Backup is not configured: a spreadsheet ID is required.")
    if not credentials:
        raise BackupConfigurationError("Backup is not configured: service account JSON is required.")
    return GoogleSheetsClient(
        credentials,
        spreadsheet_id,
        prefix=str(config.get("worksheetPrefix") or ""),
    )


# --- schema discovery --------------------------------------------------------
def _ensure_models_loaded() -> None:
    import app.modules.audit.models  # noqa: F401
    import app.modules.auth.models  # noqa: F401
    import app.modules.finance.models  # noqa: F401
    import app.modules.master_data.models  # noqa: F401
    import app.modules.operations.models  # noqa: F401
    import app.modules.quotations.models  # noqa: F401


def discover_tables(config: dict[str, Any]) -> list[Table]:
    """All backupable tables in dependency order (parents before children)."""
    from app.core.database import Base

    _ensure_models_loaded()
    excluded = _excluded_tables(config)
    tables: list[Table] = []
    for table in Base.metadata.sorted_tables:
        if table.name in excluded or table.name.startswith("backup_") or table.name == "alembic_version":
            continue
        if not len(table.primary_key.columns):
            continue
        tables.append(table)
    return tables


def table_by_name(name: str) -> Table | None:
    for table in discover_tables({}):
        if table.name == name:
            return table
    return None


def backupable_columns(table: Table) -> list[Column]:
    from sqlalchemy import LargeBinary

    columns: list[Column] = []
    for column in table.columns:
        if isinstance(column.type, LargeBinary):
            continue
        if is_sensitive_field(column.name):
            continue
        lowered = column.name.lower()
        if any(hint in lowered for hint in SENSITIVE_HINTS):
            continue
        columns.append(column)
    return columns


# --- serialization -----------------------------------------------------------
def _normalize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _sheet_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def _row_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_row(table: Table, row: Any) -> tuple[str, dict[str, Any], str]:
    mapping = row._mapping
    data = {column.name: _normalize(mapping[column.name]) for column in backupable_columns(table)}
    pk = [mapping[column.name] for column in table.primary_key.columns]
    record_id = "|".join(str(value) for value in pk)
    return record_id, data, _row_hash(data)


# --- counters ----------------------------------------------------------------
class RunCounters:
    def __init__(self) -> None:
        self.tables_total = 0
        self.tables_processed = 0
        self.rows_scanned = 0
        self.rows_inserted = 0
        self.rows_updated = 0
        self.rows_skipped = 0
        self.rows_failed = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "tables_total": self.tables_total,
            "tables_processed": self.tables_processed,
            "rows_scanned": self.rows_scanned,
            "rows_inserted": self.rows_inserted,
            "rows_updated": self.rows_updated,
            "rows_skipped": self.rows_skipped,
            "rows_failed": self.rows_failed,
        }


# --- run lifecycle -----------------------------------------------------------
_active_run_id: int | None = None
_run_lock = asyncio.Lock()


def active_run_id() -> int | None:
    return _active_run_id


async def create_run(session: AsyncSession, *, trigger: str, user_id: int | None, spreadsheet_id: str | None) -> BackupRun:
    run = BackupRun(trigger=trigger, status="running", triggered_by_user_id=user_id, spreadsheet_id=spreadsheet_id)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _log(session: AsyncSession, run_id: int | None, level: str, message: str, *, table_name: str | None = None, detail: dict | None = None) -> None:
    session.add(BackupLog(run_id=run_id, level=level, table_name=table_name, message=message, detail=detail))


async def start_backup(session: AsyncSession, *, trigger: str, user_id: int | None = None) -> dict[str, Any]:
    """Create a run row and launch processing in the background."""
    config = await _load_backup_config(session)
    if not config.get("spreadsheetId") or not config.get("serviceAccountJson"):
        raise BackupConfigurationError("Backup is not configured. Set the spreadsheet ID and service account JSON.")
    if _active_run_id is not None:
        raise RuntimeError("A backup is already running.")

    run = await create_run(
        session,
        trigger=trigger,
        user_id=user_id,
        spreadsheet_id=str(config.get("spreadsheetId")),
    )
    await _store_backup_status(session, status="running", message="Backup started.", when=utcnow().isoformat())
    asyncio.create_task(execute_run(run.id))
    return serialize_run(run)


async def run_now(session: AsyncSession, *, trigger: str, user_id: int | None = None) -> dict[str, Any]:
    """Create and execute a run synchronously (used by the scheduler)."""
    config = await _load_backup_config(session)
    if not config.get("spreadsheetId") or not config.get("serviceAccountJson"):
        raise BackupConfigurationError("Backup is not configured. Set the spreadsheet ID and service account JSON.")
    if _active_run_id is not None:
        raise RuntimeError("A backup is already running.")
    run = await create_run(
        session, trigger=trigger, user_id=user_id, spreadsheet_id=str(config.get("spreadsheetId"))
    )
    await _store_backup_status(session, status="running", message="Backup started.", when=utcnow().isoformat())
    await execute_run(run.id)
    await session.refresh(run)
    return serialize_run(run)


async def execute_run(run_id: int) -> None:
    global _active_run_id
    async with _run_lock:
        _active_run_id = run_id
        try:
            await _execute_run(run_id)
        finally:
            _active_run_id = None


async def _execute_run(run_id: int) -> None:
    async with SessionLocal() as session:
        run = await session.get(BackupRun, run_id)
        if run is None:
            return
        counters = RunCounters()
        run.started_at = utcnow()
        run.status = "running"
        await session.commit()

        try:
            config = await _load_backup_config(session)
            client = build_client(config)
        except BackupConfigurationError as exc:
            run.status = "failed"
            run.message = str(exc)
            run.finished_at = utcnow()
            run.duration_ms = 0
            await _log(session, run.id, "error", str(exc))
            await session.commit()
            await _store_backup_status(session, status="failed", message=str(exc), when=utcnow().isoformat())
            return

        try:
            tables = discover_tables(config)
            counters.tables_total = len(tables)
            run.tables_total = counters.tables_total
            await session.commit()

            # Retry anything a previous run failed to push to Google.
            await _flush_unsynced(session, client, run, counters)

            for table in tables:
                try:
                    await _process_table(session, client, run, table, config, counters)
                except Exception as exc:  # noqa: BLE001 - never abort the whole run
                    counters.rows_failed += 1
                    await _log(session, run.id, "error", f"Table '{table.name}' failed: {exc}", table_name=table.name)
                    await session.commit()
                counters.tables_processed += 1

            run.status = "partial" if counters.rows_failed else "success"
            run.message = (
                f"Backed up {counters.rows_inserted} new and {counters.rows_updated} updated rows "
                f"across {counters.tables_processed} tables."
            )
        except Exception as exc:  # noqa: BLE001 - top-level guard
            run.status = "failed"
            run.message = str(exc)
            await _log(session, run.id, "error", f"Backup run failed: {exc}")
        finally:
            run.finished_at = utcnow()
            if run.started_at:
                run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            for field, value in counters.as_dict().items():
                setattr(run, field, value)
            await session.commit()
            await _store_backup_status(
                session,
                status=run.status,
                message=run.message or "",
                when=run.finished_at.isoformat() if run.finished_at else utcnow().isoformat(),
            )


# --- per-table processing ----------------------------------------------------
async def _process_table(
    session: AsyncSession,
    client: GoogleSheetsClient,
    run: BackupRun,
    table: Table,
    config: dict[str, Any],
    counters: RunCounters,
) -> None:
    columns = backupable_columns(table)
    if not columns:
        return
    pk_columns = list(table.primary_key.columns)
    batch_size = max(1, int(config.get("batchSize") or DEFAULT_BATCH_SIZE))

    states = {
        state.record_id: state
        for state in (
            await session.execute(select(BackupState).where(BackupState.table_name == table.name))
        ).scalars().all()
    }

    new_records: list[BackupRecord] = []
    offset = 0
    while True:
        rows = (
            await session.execute(
                select(table).order_by(*pk_columns).limit(batch_size).offset(offset)
            )
        ).all()
        if not rows:
            break
        offset += len(rows)
        now = utcnow()
        for row in rows:
            counters.rows_scanned += 1
            record_id, data, row_digest = serialize_row(table, row)
            state = states.get(record_id)
            if state is not None and state.row_hash == row_digest:
                counters.rows_skipped += 1
                continue
            version = (state.backup_version + 1) if state else 1
            kind = "update" if state else "insert"
            record = BackupRecord(
                run_id=run.id,
                table_name=table.name,
                record_id=record_id,
                backup_version=version,
                backup_at=now,
                change_kind=kind,
                row_hash=row_digest,
                data=data,
                synced=False,
            )
            session.add(record)
            new_records.append(record)
            if state is None:
                new_state = BackupState(
                    table_name=table.name,
                    record_id=record_id,
                    row_hash=row_digest,
                    backup_version=version,
                    last_backup_at=now,
                )
                session.add(new_state)
                states[record_id] = new_state
                counters.rows_inserted += 1
            else:
                state.row_hash = row_digest
                state.backup_version = version
                state.last_backup_at = now
                counters.rows_updated += 1
        await session.commit()

    if new_records:
        await _sync_records(session, client, run, new_records, counters)
    await _log(
        session,
        run.id,
        "info",
        f"Table '{table.name}' processed.",
        table_name=table.name,
        detail={"columns": len(columns)},
    )
    await session.commit()


# --- Google Sheets sync ------------------------------------------------------
def _chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


async def _sync_records(
    session: AsyncSession,
    client: GoogleSheetsClient,
    run: BackupRun,
    records: list[BackupRecord],
    counters: RunCounters,
) -> None:
    grouped: dict[str, list[BackupRecord]] = {}
    for record in records:
        grouped.setdefault(record.table_name, []).append(record)

    for table_name, table_records in grouped.items():
        table = table_by_name(table_name)
        try:
            title = await asyncio.to_thread(client.ensure_worksheet, table_name)
            columns = [column.name for column in backupable_columns(table)] if table is not None else list(META_COLUMNS)
            header = await asyncio.to_thread(client.ensure_header, title, columns)
            existing_hashes = await _existing_hashes(client, title, header)

            rows: list[list[Any]] = []
            to_mark: list[BackupRecord] = []
            for record in table_records:
                if record.row_hash in existing_hashes:
                    to_mark.append(record)
                    continue
                row_map: dict[str, Any] = {
                    "_backup_at": record.backup_at.isoformat() if record.backup_at else "",
                    "_backup_version": record.backup_version,
                    "_table": record.table_name,
                    "_record_id": record.record_id,
                    "_row_hash": record.row_hash,
                    "_change_kind": record.change_kind,
                    **(record.data or {}),
                }
                rows.append([_sheet_cell(row_map.get(column)) for column in header])
                existing_hashes.add(record.row_hash)
                to_mark.append(record)

            for chunk in _chunks(rows, SHEET_CHUNK_SIZE):
                await asyncio.to_thread(client.append_rows, title, chunk)

            record_ids = [record.id for record in to_mark if record.id is not None]
            if record_ids:
                await session.execute(
                    update(BackupRecord)
                    .where(BackupRecord.id.in_(record_ids))
                    .values(synced=True, synced_at=utcnow())
                )
                await session.commit()
        except (SheetsApiError, BackupConfigurationError) as exc:
            counters.rows_failed += len(table_records)
            await _log(
                session,
                run.id,
                "error",
                f"Google Sheets sync failed for '{table_name}': {exc}",
                table_name=table_name,
            )
            await session.commit()


async def _existing_hashes(client: GoogleSheetsClient, title: str, header: list[str]) -> set[str]:
    if "_row_hash" not in header:
        return set()
    column_index = header.index("_row_hash")
    rows = await asyncio.to_thread(client.read_rows, title)
    hashes: set[str] = set()
    for row in rows[1:]:
        if column_index < len(row):
            hashes.add(row[column_index])
    return hashes


async def _flush_unsynced(session: AsyncSession, client: GoogleSheetsClient, run: BackupRun, counters: RunCounters) -> None:
    pending = (
        await session.execute(
            select(BackupRecord).where(BackupRecord.synced.is_(False)).order_by(BackupRecord.id)
        )
    ).scalars().all()
    if not pending:
        return
    await _log(session, run.id, "info", f"Retrying {len(pending)} unsynced backup row(s).")
    await session.commit()
    await _sync_records(session, client, run, list(pending), counters)


# --- restore -----------------------------------------------------------------
def _coerce_value(column: Column, raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, str) and raw == "":
        return None
    column_type = column.type
    try:
        if isinstance(column_type, Boolean):
            return str(raw).strip().lower() in ("1", "true", "t", "yes", "y")
        if isinstance(column_type, (Integer, BigInteger)):
            return int(float(raw))
        if isinstance(column_type, Numeric):
            return Decimal(str(raw))
        if isinstance(column_type, Float):
            return float(raw)
        if isinstance(column_type, DateTime):
            return datetime.fromisoformat(str(raw))
        if isinstance(column_type, Date):
            return date.fromisoformat(str(raw)[:10])
        if isinstance(column_type, JSON):
            return raw if isinstance(raw, (dict, list)) else json.loads(raw)
        if isinstance(column_type, (String, Text)):
            return str(raw)
    except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError):
        return None
    return raw


async def restore_from_sheets(session: AsyncSession, *, confirm: str, tables: list[str] | None = None) -> dict[str, Any]:
    if str(confirm or "").strip().upper() != BACKUP_CONFIRM:
        raise ValueError(f"Typed confirmation '{BACKUP_CONFIRM}' is required.")

    config = await _load_backup_config(session)
    client = build_client(config)
    selected = set(tables or [])
    restored_rows = 0
    inserted = 0
    updated = 0
    table_summaries: list[dict[str, Any]] = []
    touched_tables: list[Table] = []

    for table in discover_tables(config):
        if selected and table.name not in selected:
            continue
        title = client.worksheet_title(table.name)
        try:
            if not await asyncio.to_thread(client.worksheet_exists, table.name):
                continue
            sheet_rows = await asyncio.to_thread(client.read_rows, title)
        except SheetsApiError:
            continue
        if len(sheet_rows) < 2:
            continue
        header = sheet_rows[0]
        index = {name: position for position, name in enumerate(header)}
        if "_record_id" not in index or "_backup_version" not in index:
            continue

        latest: dict[str, dict[str, Any]] = {}
        versions: dict[str, int] = {}
        for row in sheet_rows[1:]:
            record_id = row[index["_record_id"]] if index["_record_id"] < len(row) else ""
            if not record_id:
                continue
            try:
                version = int(float(row[index["_backup_version"]])) if index["_backup_version"] < len(row) else 0
            except (ValueError, TypeError):
                version = 0
            if record_id not in versions or version >= versions[record_id]:
                versions[record_id] = version
                latest[record_id] = {name: (row[position] if position < len(row) else "") for name, position in index.items()}

        if not latest:
            continue

        pk_columns = list(table.primary_key.columns)
        values_by_column: dict[str, Any] = {}
        table_inserted = 0
        table_updated = 0
        for record_id, cells in latest.items():
            values: dict[str, Any] = {}
            for column in backupable_columns(table):
                if column.name in cells:
                    values[column.name] = _coerce_value(column, cells[column.name])
            pk_values = record_id.split("|")
            for position, column in enumerate(pk_columns):
                if position < len(pk_values):
                    values[column.name] = _coerce_value(column, pk_values[position])
            if any(values.get(column.name) is None for column in pk_columns):
                continue
            values_by_column[record_id] = values

        for values in values_by_column.values():
            pk_filters = []
            for column in pk_columns:
                pk_filters.append(column == values[column.name])
            existing = await session.scalar(select(1).select_from(table).where(*pk_filters).limit(1))
            if existing is None:
                await session.execute(table.insert().values(**values))
                table_inserted += 1
            else:
                update_values = {
                    name: value
                    for name, value in values.items()
                    if name not in {column.name for column in pk_columns}
                }
                if update_values:
                    await session.execute(table.update().where(*pk_filters).values(**update_values))
                table_updated += 1
        await session.commit()

        inserted += table_inserted
        updated += table_updated
        restored_rows += table_inserted + table_updated
        touched_tables.append(table)
        table_summaries.append(
            {"table": table.name, "inserted": table_inserted, "updated": table_updated}
        )

    await _resync_sequences(session, touched_tables)
    return {
        "restored": restored_rows,
        "inserted": inserted,
        "updated": updated,
        "tables": table_summaries,
    }


async def _resync_sequences(session: AsyncSession, tables: Iterable[Table]) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    for table in tables:
        pk_columns = list(table.primary_key.columns)
        if len(pk_columns) != 1 or not isinstance(pk_columns[0].type, (Integer, BigInteger)):
            continue
        column = pk_columns[0]
        try:
            sequence = await session.scalar(
                text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                {"table_name": table.name, "column_name": column.name},
            )
            if not sequence:
                continue
            max_value = await session.scalar(select(func.max(column)))
            if max_value is None:
                continue
            await session.execute(text("SELECT setval(:sequence, :value)"), {"sequence": sequence, "value": int(max_value)})
        except Exception:  # noqa: BLE001 - best-effort sequence repair
            logger.warning("Could not resync sequence for table %s", table.name)
    await session.commit()


# --- serialization for API ---------------------------------------------------
def serialize_run(run: BackupRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "trigger": run.trigger,
        "status": run.status,
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
        "durationMs": run.duration_ms,
        "tablesTotal": run.tables_total,
        "tablesProcessed": run.tables_processed,
        "rowsScanned": run.rows_scanned,
        "rowsInserted": run.rows_inserted,
        "rowsUpdated": run.rows_updated,
        "rowsSkipped": run.rows_skipped,
        "rowsFailed": run.rows_failed,
        "spreadsheetId": run.spreadsheet_id,
        "message": run.message,
        "triggeredByUserId": run.triggered_by_user_id,
    }


def serialize_log(entry: BackupLog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "level": entry.level,
        "tableName": entry.table_name,
        "message": entry.message,
        "detail": entry.detail,
        "createdAt": entry.created_at.isoformat() if entry.created_at else None,
    }


async def get_run(session: AsyncSession, run_id: int) -> dict[str, Any] | None:
    run = await session.get(BackupRun, run_id)
    if run is None:
        return None
    logs = (
        await session.execute(
            select(BackupLog).where(BackupLog.run_id == run_id).order_by(BackupLog.id)
        )
    ).scalars().all()
    payload = serialize_run(run)
    payload["logs"] = [serialize_log(entry) for entry in logs]
    return payload


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    """Config safe to return to the client (service account JSON is redacted)."""
    payload = dict(config)
    credentials = str(payload.pop("serviceAccountJson", "") or "")
    payload["serviceAccountConfigured"] = bool(credentials)
    if not payload.get("serviceAccountEmail") and credentials:
        try:
            info = json.loads(credentials)
            payload["serviceAccountEmail"] = str(info.get("client_email") or "")
        except (TypeError, ValueError):
            pass
    return payload


def schedule_status(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(config.get("enabled")),
        "intervalHours": int(config.get("intervalHours") or 24),
        "configured": bool(config.get("spreadsheetId") and config.get("serviceAccountJson")),
        "lastRunAt": config.get("lastRunAt") or "",
        "lastRunStatus": config.get("lastRunStatus") or "idle",
        "lastRunMessage": config.get("lastRunMessage") or "",
        "running": _active_run_id is not None,
    }


def sanitize_title(table_name: str, config: dict[str, Any]) -> str:
    return sanitize_worksheet_title(table_name, str(config.get("worksheetPrefix") or ""))
