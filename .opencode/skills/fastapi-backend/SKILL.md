---
name: fastapi-backend
description: Use when implementing or changing LCS backend FastAPI routers, services, repositories, request validation, authorization, transactions, pagination, filtering, error handling, or database access.
---

# FastAPI backend

Add backend behaviour to the LCS modular monolith without breaking API contracts,
permissions, or financial correctness.

## When to use

- Adding or changing an endpoint, service function, or repository query.
- Fixing a backend bug, a validation gap, or an N+1 query.
- Adding a permission check or an audit event.

## Required inputs

1. The endpoint contract: method, path, permission, request body, response shape.
2. Whether the frontend already calls it (check before inventing a new shape).
3. Whether the change touches money, posted records, or authorization.

## Project references

| Document | Use it for |
|---|---|
| `AGENTS.md` §Backend | Layering, envelope, permission sync, ruff config |
| `docs/05_solution_architecture.md` | Module boundaries and the layering contract |
| `docs/09_roles_and_permissions.md` | Permission codes and page mapping |
| `backend/app/modules/<name>/` | The existing pattern to extend (router → service → models/repository) |
| `docs/11_deployment_and_security.md` | Security controls that must stay in place |

## Architecture

```text
router.py      HTTP shape, permission dependency, no business logic
service.py     business rules, transactions, validation, audit
repository.py  set-based queries only (when a module needs one)
models.py      SQLAlchemy 2.x typed mappings
```

- Routers live in `app/modules/<name>/router.py` and are registered in
  `app/api/v1/router.py`.
- **Response envelope:** success is `{"data": ...}`; lists are
  `{"data": {"items": [...], "meta": {page, page_size, total}}}` via
  `core/pagination.py`.
- **Errors** are `{code, message, request_id, field_errors}` raised from
  `core/exceptions.py` (`ValidationFailed`, `NotFound`, `Conflict`,
  `InvalidState`, `AccessDenied`). Never return a bare `HTTPException` with a
  custom body for a domain error — the frontend maps `field_errors` onto inputs,
  so a new error that should attach to a field must name that field.
- **Field-error keys are a contract.** The frontend resolves them against
  registered field keys (see `frontend/app/utils/validation/error-paths.ts`).
  Use bare camelCase for plain fields (`{"visibleMagnitude": "..."}`) and a
  dotted path for nested rows. When a key is prefixed by a row index, agree the
  base with the frontend rather than inventing one.
- Permissions are declared with
  `context: RequestContext = Depends(require_permission("code"))`. The catalog in
  `app/core/permissions.py` is code-owned and synced on startup; a new endpoint
  needs a code there, plus a page mapping so it is grantable from the Roles
  screen. `tests/test_role_permissions.py` fails if a source permission has no
  page key.
- `context.has_permission()` returns true for everything when the caller is a
  platform admin by design — do not "fix" that.

## Workflow

1. **Find the closest existing implementation** and follow it. Do not introduce a
   second pattern for the same problem.
2. **Write the service first**, then the router. Keep business rules out of the
   handler.
3. **Resolve references, never guess.** Use the master-data helpers
   (`resolve_reference`, `resolve_reference_id`, `resolve_or_create_container_type`)
   so a bad reference becomes a field error instead of a NULL or a dangling FK.
4. **One transaction per operation.** The service commits; the router must not
   commit a second time. Use `.with_for_update()` on the header row when
   allocating a sequence, a version number, or a posting, so two concurrent
   callers cannot collide. `no-op` downgrades of `FOR UPDATE` on SQLite are fine —
   the tests rely on that.
5. **Stamp configuration context** where the row depends on it (for example
   `config_versions.stamp_service_order` pins an order to the published dynamic
   form).
6. **Write an audit event** for anything a reviewer would want to reconstruct:
   security changes, configuration publishes, financial postings and reversals,
   archive and restore. Use `write_audit(...)` from `app/modules/audit/service.py`.
7. **Invalidate caches** after a write that a cached read depends on
   (`await cache.bump("master_data")`, `cache.bump("reports")`).
8. **Bump the frontend contract if the surface changed.** If the frontend needs a
   new path or collection, it must be registered in the frontend constants too, or
   `tests/test_frontend_api_contract.py` will fail on the frontend side.

## Security and validation requirements

- Authorization is enforced in the backend only. A frontend check is convenience.
- Validate references, enums, and numeric ranges in the service; do not rely on
  the database to raise a friendly message.
- Never return a secret. Sensitive fields are declared in `core/crypto.py`
  (`SENSITIVE_FIELD_NAMES`) and must be masked in responses and archive snapshots.
- Refuse to edit posted financial records; require a reversal instead.
- Reject an unknown status rather than silently storing it. If a status set is
  deliberately open, normalise it against a documented allow-list.
- Guard against N+1: prefer one set-based query in a repository over a query per
  row. `tests/test_repository_queries.py` and `docs/05` describe the expectation.

## Testing

```bash
cd backend
uv run python -m pytest tests/<relevant>.py -q --no-header   # focused first
uv run python -m pytest -q                                   # full suite (~12 min)
uv run ruff check .
```

Cover, per change: the happy path, each validation failure, the permission
denial, and the concurrency or idempotency property. Fixtures: `client` (seeded
`AsyncClient`), `login()` for headers, and `login(client, "sales")` for a role
that lacks a permission. Tests run on in-memory SQLite, so a PostgreSQL-only
trigger will not fire in tests — add a case to `tests/sql/integrity_guards.sql`
when you rely on one.

## Acceptance criteria

- Endpoint returns the documented envelope and error codes.
- Authorization is declared and covered by a test that proves denial.
- The operation is atomic; a failure leaves no partial write.
- Money uses `Decimal`/`NUMERIC` with no float round-trip.
- No new N+1; list endpoints paginate.
- `uv run python -m pytest -q` and `uv run ruff check .` pass.
- The frontend contract test still passes.

## Expected outputs

- Changed `router.py` / `service.py` / `models.py` / `repository.py`.
- New or updated permission codes and page mappings when the surface grew.
- Tests covering the new behaviour and the denial path.
- An updated API section in the relevant `docs/` file.
