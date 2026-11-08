---
description: Run backend tests selected for the current task
---

Run from backend/ with uv run --no-sync pytest -q <existing selector>.
User selector: $ARGUMENTS

With no selector, identify changed behavior and the smallest owning existing test file;
use /test-fast as a lookup. Do not default to the full backend suite. An explicit whole-suite
request or demonstrated wide shared/release impact can justify uv run --no-sync pytest -q.
Batch relevant files once; --lf only for failures relevant to this task.

SQLite fixtures do not prove PostgreSQL guards/locking. Any PostgreSQL run requires an
explicitly isolated disposable target. Do not use developer/production data, apply migrations,
reset data, install frameworks or weaken tests. Follow the DEEP policy for finance/security.
If uv/environment is unavailable, report it; do not silently deploy a Docker replacement.
Report exact command, counts, first failure and unverified properties; no verbose log dump.
