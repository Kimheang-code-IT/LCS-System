# Roles and Permissions

> Authorization engine: **PyCasbin** over PostgreSQL, synchronized through Redis.
> Authentication (JWT, Argon2id, refresh rotation, sessions, lockout, CSRF) is in
> `app/core/security.py`, `app/core/deps.py` and `docs/11_deployment_and_security.md`.

## 1. Interpretation

- **One engine.** Casbin decides every permission check. No handler, service or
  frontend computes an effective permission set of its own.
- **Default deny.** A subject without an explicit policy row is refused. An
  unknown user, an unknown role, a deactivated role, a removed policy or an
  unreadable policy table all deny.
- **Single role.** A user holds exactly one role; the effective permissions are
  that role's direct grants. Role inheritance is not supported.
- **Namespaced subjects.** `user:<id>` and `role:<code>` — a user id can never
  collide with a role code.
- **Page codes and API codes.** The Roles & Permissions matrix stores *page*
  codes (`sales.quotations.view`); route guards check *capability* codes
  (`quotation.read`). A page code is compiled into the capabilities it needs
  **once, when the role is saved**, so a request never walks an implication
  graph.
- **Backend authority.** The SPA hides menus and buttons from the permission
  snapshot it is given. That is a usability aid, not a control: every request is
  re-checked on the server.

## 2. Where authorization data lives

| Store | Holds | Decides access |
|---|---|---|
| `casbin_rule` | every grant (`p`) and every user→role assignment (`g`, one per user) | **Yes — the only source** |
| `roles` | role code, name, description, active state, system flag | No (display + lifecycle) |
| `permissions` | code, module, resource, action, name | No (display only) |
| `users`, `user_credentials`, `user_sessions` | identity, password hash, sessions | Authentication only |
| `audit_events` | every refused permission and every policy change | No |

There is no second editable role → permission mapping. Deleting `role_permissions`
and `user_role_assignments` was deliberate: two writable mappings can disagree,
and only one of them can be right.

## 3. Casbin model

`backend/app/core/authorization/model.conf`:

```ini
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && (p.obj == "*" || r.obj == p.obj) && (p.act == "*" || r.act == p.act)
```

Row shapes:

```text
p, role:SALES,       quotation,        read        # a role holds a capability
p, role:MANAGER,     sales.quotations, view        # a page code (matrix)
p, role:SUPER_ADMIN, *,                *           # protected super administrator
g, user:15,          role:SALES                    # the user's one role assignment
```

A permission code is split at its **last** dot:

```text
quotation.read          -> (quotation, read)
quotation.update_draft  -> (quotation, update_draft)
sales.quotations.view   -> (sales.quotations, view)
```

`p.obj == "*"` matches the literal string `"*"` only — it is an explicit policy
row, never a wildcard pattern. A broad grant can therefore never leak into an
unrelated capability by accident.

## 4. Permission catalog

`backend/app/core/permissions.py` defines the vocabulary. It is code, not data,
because a new endpoint ships with its guard: a code nothing checks is noise, and
a check for a code nothing defines would always deny.

| Group | Example | Checked by |
|---|---|---|
| Capability (source) codes | `quotation.read`, `financial_document.post` | `require_permission(...)` in routers |
| Matrix page codes | `sales.quotations.view`, `admin.users.update` | The Roles & Permissions matrix |
| Legacy page codes | `admin.users.edit`, `finance.reports.view` | Accepted and mapped onto the modern action; not offered as new checkboxes |
| Navigation codes | `sales.companies.view`, `settings.manage` | Menu/module visibility |

### 4.1 Page → capability compile

`PAGE_PERMISSION_GRANTS` maps a page checkbox onto the capabilities that page
needs, for example:

```text
sales.quotations.submit   -> quotation.submit, quotation.send
sales.quotations.update   -> quotation.update, quotation.accept, quotation.convert, attachment.upload
finance.service_charges.view -> service_charge.read, financial_document.read, attachment.read
```

`compile_role_permissions()` expands **one direction at a time** and never
repeats a pair of hops:

1. a submitted page (or legacy aggregate) contributes the codes it declares;
2. a declared *page* code contributes its own codes — the legacy aggregates point
   at pages, so this second forward hop is required, and it stops there;
3. a capability contributes the page code that renders it in the matrix, **but
   only when that page grants nothing that is not already granted**.

Rule 3 is what stops a grant from widening an independent permission: adding the
quotations page for `quotation.read` would also have granted `attachment.read`, so
the page is not added. It also makes the compile **idempotent** — saving the same
selection twice produces the same policy set for every one of the 283 codes.

Nothing ever goes capability → page → capability. That loop let one read
capability inherit the write capabilities of every page that also grants it: a
read-only configuration viewer used to end up with full configuration write
access, and a settings viewer with `backup.manage`.

`resolve_role_codes()` decides what a save means:

- submitted page codes are kept and compiled;
- a capability a *submitted* page already grants is dropped and re-derived, so
  unticking that page really removes the capability — and `DELETE
  /roles/{id}/permissions` removes the page **and** the capabilities it uniquely
  supplied, then re-derives from whatever pages remain;
- a capability with no page behind it stays a deliberate grant;
- `*` is only ever accepted for `SUPER_ADMIN`.

Granting or revoking one permission never changes an independent one: `POST
/roles/{id}/permissions` with `attachment.upload` adds only that code, and
`quotation.read` cannot drag `attachment.read` in with it.

The result is stored as concrete `p` rows. Casbin never sees a page code as an
implication, only as another string it may match.

A code that no guard checks is not in the catalog at all. `excel.import`,
`excel.export`, `telegram.manage` and `telegram.view` were removed: the Excel
routes authorise per module and the Telegram routes use the settings permission.

### 4.2 Adding a permission for a new module

1. Add the capability code to `SOURCE_PERMISSIONS` in `app/core/permissions.py`.
2. Guard the route: `Depends(require_permission("<code>"))`.
3. If the screen is configurable from the matrix, add or extend its row in
   `MATRIX_PAGES` and map each page action onto capabilities in
   `PAGE_PERMISSION_GRANTS`.
4. Decide which seeded role should hold it: add the page/capability to
   `ROLE_DEFINITIONS`. Startup adds only the missing grants, so existing roles
   keep their edits.
5. Restart the backend (startup seeds the catalog and reloads the enforcer) and
   refresh the matrix — `/api/v1/permissions/catalog` reports the new row.
6. Document the change here and in `docs/10_testing_and_quality.md`.

## 5. Seeded roles

`provision` (startup, `POST /auth/setup/initialize`, and `/settings` reset) creates
the seven roles below if they are missing and adds any grant the role lacks. It
never removes an administrator's change.

| Code | Name | Scope |
|---|---|---|
| `SUPER_ADMIN` | Super Administrator | `*, *` — unrestricted. Protected (see §7). |
| `ADMIN` | Administrator | Entire permission catalog, including settings and backups. |
| `MANAGER` | Manager | Quotations, service orders, finance **read/export**, all reports, master data read, user/role read. |
| `SALES` | Sales Officer | Quotations (full), service orders read, reports read, master data read. |
| `OPERATIONS` | Operations Officer | Service orders (full), quotations read, operations reports, master data read. |
| `ACCOUNTANT` | Accountant | Finance documents, journals, periods, posting rules, finance reports; sales and operations read. |
| `VIEWER` | Viewer | Read-only dashboards, documents, journals and reports. |

The numbers behind those rows are generated by `compile_role_permissions()`
(catalog of 283 codes at the time of writing):

| Role | Compiled grants |
|---|---|
| `ADMIN` | 283 |
| `ACCOUNTANT` | 110 |
| `MANAGER` | 97 |
| `SALES` | 48 |
| `VIEWER` | 44 |
| `OPERATIONS` | 39 |
| `SUPER_ADMIN` | 1 (`*, *`) |

No role grants `*` except `SUPER_ADMIN`. Every other role is an explicit list:
broad access is a decision somebody has to make in the matrix, not a default.

## 6. No role inheritance

Roles hold their own grants and nothing else — there is no
`g, role:CHILD, role:PARENT` row, no `parentRoles` payload field and no
inheritance endpoints. A role that needs another role's permissions is granted
those permissions directly. A legacy `role:` → `role:` assignment edge is
ignored by the policy loader (and removed by migration `b4c5d6e7f8a9`, which
first materializes the inherited grants as the child's own grants), so stale
rows can never re-enable inheritance.

Each user holds exactly one role: the request schemas accept only a single
`role_code`, the role-assignment endpoint **replaces** the previous role, and a
partial unique index (`uq_casbin_rule_single_user_role`) refuses a second
assignment at the database level. A user without a role holds no protected
permission at all.

## 7. Protected roles

`PROTECTED_ROLE_CODES = {SUPER_ADMIN}`.

- Only a caller that itself holds `*, *` may create, update, deactivate,
  or delete it — enforced in the service layer, not only in the UI.
- Its wildcard grant cannot be removed (`sync_role_permissions` refuses a set
  without `*`).
- The last active `SUPER_ADMIN` holder cannot be unassigned, deactivated or
  deleted (`_assert_super_admin_remains`).
- The built-in system administrator *account* (`system_identity =
  DEFAULT_SYSTEM_ADMIN`) additionally cannot be deleted or deactivated, and its
  role cannot be changed.

## 8. Enforcement

### 8.1 Dependencies

```python
from app.core.deps import require_permission, require_any_permission

@router.get("/quotations", dependencies=[Depends(require_permission("quotation.read"))])
async def list_quotations(): ...

@router.get("/settings", dependencies=[Depends(require_any_permission("settings.app_config.view", "configuration.manage"))])
async def read_settings(): ...
```

- `require_permission(*codes)` requires **every** code.
- `require_any_permission(*codes)` requires **at least one**.
- Missing or invalid credentials answer `401` (`AUTH_REQUIRED`,
  `ACCESS_TOKEN_EXPIRED`, `SESSION_REVOKED`, `SESSION_EXPIRED`). An authenticated
  caller without the permission answers `403 ACCESS_DENIED`.
- The dependency calls `context.has_permission(code)`, which asks Casbin
  directly. There is no per-request permission cache in the decision path.

Inline business guards (ownership, record scope, "only the creator may edit a
draft") stay in the service layer and run **after** the Casbin check. They
narrow access; they never widen it.

### 8.2 Denied requests are audited centrally

Every `AccessDenied` (HTTP 403) is recorded once, by
`app/core/database.py::record_denial`, from the request's own session: the failed
transaction is rolled back, the `AUTHORIZATION_DENIED` event is written (action =
the missing code, `metadata.path`, `metadata.method`) and committed, then the
refusal continues to the error handler. Route dependencies, the master-data inline
guards and service-level refusals are all covered without each call site
remembering to log, and an audit failure never turns a refusal into a 500.

`RequestContext.has_permission` is the only permission primitive in the request
path; `access_modes` (maintenance / read-only), search, reports and master data use
it too, so there is one decision point, not one per module.

### 8.3 Modules covered

Every registered router is protected: `auth` (users, roles, permissions),
`quotations`, `operations`, `finance`, `reports`, `master-data`, `settings`,
`telegram`, `backup`, `excel-io`, `audit`, `archive`. A dependency-graph inventory
of the 396 registered routes finds exactly 13 without a guard, and all 13 are
deliberate: `/health`, `/health/ready`, `/`, the login/refresh/setup/password-
recovery routes, and the Telegram webhook (authenticated by its own secret
header). Everything else reaches `get_current_context` plus a Casbin decision.

Two endpoints intentionally rely on an inline decision rather than a dependency:
the settings GETs return a redacted config to every signed-in user (the Settings
page itself needs `settings.app_config.view`), and the Excel module catalog is
filtered to the modules the caller may view or manage.

## 9. Policy synchronization

```
Admin saves a role ──► rows written to casbin_rule ──► commit
                        └─► cache.bump("auth")             (Redis version +1)
                        └─► reload()                        (this worker, immediately)
Other worker, next request ──► ensure_current() sees the new version ──► reload()
```

- The enforcer keeps a compiled in-memory copy; a decision costs a matcher
  evaluation, not a query.
- `reload()` reads the published version **before** the policy rows. A change
  committed while the rows are being read therefore leaves a newer version than
  the one recorded, and the next request reloads instead of trusting a copy that
  missed it.
- `CASBIN_RELOAD_INTERVAL_SECONDS` (default `30`) is the backstop: the copy is
  re-read from PostgreSQL at least that often, so `REDIS_ENABLED=false` or a Redis
  outage cannot freeze a stale policy set.
- **Fail closed.** If the policy table cannot be read, the in-memory copy is
  dropped and the request is refused with `503 AUTHORIZATION_UNAVAILABLE` until a
  reload succeeds. A policy update that cannot be published does not silently keep
  serving the old decision.
- Disabled roles are excluded at load time: a `p` or `g` row whose `role:<code>`
  is `INACTIVE` (or whose role row was deleted) never reaches the enforcer.
- Assignments are rows: removing one bumps the version every worker watches, so a
  revoked role cannot outlive the next request.

## 9.1 Startup seeding and an existing database

`ensure_permission_catalog` adds missing catalog rows, the seven roles and any
grant a role lacks, then publishes the new policy version. It never removes a grant
and never rewrites a role's stored codes, so an administrator's edits survive a
restart. The consequence is that a grant written by an *older* compiler keeps its
old capabilities until that role is saved again from the Roles screen — the current
build's page grants are correct, and re-saving the role recomputes them.

For a database that needs every role recomputed at once there is a development
command (it refuses to run against a production environment):

```bash
cd backend
uv run python scripts/rebuild_role_permissions.py           # dry run: per-role diff
uv run python scripts/rebuild_role_permissions.py --apply   # write + publish
```

It rebuilds each role from the page codes it holds plus any capability no page can
produce, writes only that role's `p` rows (never users, sessions, `g` rows or
business data) and is idempotent: a second run reports no changes. Because the page
selection is the authority, a capability some page could produce but that the role
holds without that page counts as stale and is removed — the dry run lists every
removal first.

Redis-unavailable behaviour, verified in isolation: a committed policy change is not
seen until the reload interval elapses, then the next request reloads and the
revocation applies; if the policy table cannot be read, the request is refused with
`503 AUTHORIZATION_UNAVAILABLE` and every permission check denies (fail closed).
See `docs/10_testing_and_quality.md` for the probe outcome.

## 10. Administration APIs

All under `/api/v1`, all returning the standard `{"data": ...}` envelope.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /users` | `user.read` | Paginated, searchable, filterable list with the assigned role (a bare list, unchanged) |
| `POST /users` | `user.manage` | Create a user with its one assigned role |
| `GET /users/{id}` | `user.read` | Detail, assigned role and effective permissions |
| `PATCH`,`PUT /users/{id}` | `user.manage` | Update fields, assigned role and status |
| `POST /users/{id}/password` | `user.manage` | Administrator password reset |
| `POST /users/{id}/revoke-sessions` | `user.manage` | Force logout |
| `DELETE /users` | `user.manage` | Bulk delete (inactive only) |
| `GET /users/{id}/role-assignments` | `role.read` | The role currently held (zero or one) |
| `POST /users/{id}/role-assignments` | `role.manage` | **Replace** the assigned role (`role_id` or `role_code`) |
| `DELETE /users/{id}/role-assignments/{roleCode}` | `role.manage` | Remove the role (the user then holds none) |
| `GET /users/{id}/effective-permissions` | `role.read` | Every code the assigned role grants |
| `GET /roles` | `role.read` | Paginated list with counts |
| `POST /roles` | `role.manage` | Create (direct grants) |
| `GET /roles/{id}` | `role.read` | Detail: grants, users |
| `PUT /roles/{id}` | `role.manage` | Rename, describe, activate/deactivate, replace grants |
| `POST /roles/{id}/duplicate` | `role.manage` | Copy a role |
| `DELETE /roles` | `role.manage` | Bulk delete (inactive, unassigned only) |
| `PUT`,`POST`,`DELETE /roles/{id}/permissions` | `role.manage` | Replace / grant / revoke codes |
| `GET /permissions` | `role.read` | Flat catalog |
| `GET /permissions/catalog` | `role.read` | Matrix metadata: pages, actions, groups, roles, modules |

Payload notes:

- The user endpoints accept a single `role_code` (aliases `roleCode` / `role`);
  the role-assignment endpoint accepts `role_id` or `role_code`. A `roles` /
  `role_ids` array is refused with `422` — a user holds exactly one role.
- `GET /users` keeps its bare-list contract (the SPA reads it directly) and each
  row carries the assigned `role`, the display label and `pagePermissions` — the
  pages that account can open. Responses still carry `roles` as a list, which now
  holds at most one code.
- `permissions` on the role endpoints is the *page/capability selection*; the
  server compiles it (see §4.1) and returns the resulting concrete codes. A
  revoke removes the codes the selection uniquely supplied, not only the literal
  code named in the request.
- Role rows and the role detail both carry `isProtected`, so the UI can disable
  editing without hardcoding the role code.

## 11. Delegation safety

- A non-super administrator cannot grant a code it does not itself hold
  (`_assert_can_grant_permissions`, checked against the compiled set).
- A non-super administrator cannot touch the `SUPER_ADMIN` role, nor change a
  `SUPER_ADMIN` holder's roles or status.
- Nobody can change their own roles or deactivate their own account.
- Unknown or disabled roles are refused with `422`/`409`, never silently ignored.
- Duplicate role codes answer `409 DUPLICATE_ROLE`; unknown permission codes
  answer `422 VALIDATION_ERROR`; a role that still has active users answers
  `409 ROLE_IN_USE` and cannot be deactivated or deleted.

## 12. Frontend

- `/auth/me` and the login/refresh payloads return `roles`, `permissions`
  (page codes), `pageAccess` (same list) and `sourcePermissions` (capability
  codes). `ALL_PAGES` marks a super administrator.
- `middleware/auth.global.ts` and `app/utils/freight/permissions.ts` read those
  codes to hide routes, menu entries and buttons. `useAuthStore` refreshes the
  snapshot after a role or permission change.
- The matrix (`AppRolePermissionMatrix.vue`) renders the **page catalog from
  `/permissions/catalog`**, falling back to the built-in list while the request
  is in flight. It sends page codes; the server compiles them.
- The users form assigns the role with a searchable single-select dropdown
  (`role` — "Assigned Role") and shows the pages the account can open
  (`pagePermissions`) read-only. A protected role renders its matrix read-only.
- The role form collects name, description and the direct permission matrix;
  there are no inheritance controls and no computed effective-permission field.
- An authorization refusal on a save lands in the form's page-level message (the
  backend message, e.g. "Missing permission: role.manage"), not in a toast.
- The frontend holds no permission implication table. It used to: an extensive
  `SOURCE_PERMISSION_PAGE_ACTIONS` graph duplicated the backend mapping and could
  disagree with it. It was removed.

## 13. Validation, audit and security rules

- Every policy change is audited: `ROLE_CREATED`, `ROLE_UPDATED`,
  `ROLE_PERMISSIONS_CHANGED`, `ROLE_PERMISSIONS_GRANTED`,
  `ROLE_PERMISSIONS_REVOKED`, `ROLE_ASSIGNED`,
  `ROLE_UNASSIGNED`, `ROLE_DELETED`, `ROLE_DUPLICATE`.
- Every refusal is audited as `AUTHORIZATION_DENIED` with the missing code and
  the request path.
- A role save and its policy rows commit together; a failure leaves neither.
- Concurrent edits: the role row is locked (`SELECT ... FOR UPDATE`) and a user's
  assignments are serialized, so two requests cannot interleave a partial grant
  set.
- Disabled users cannot authenticate; disabled roles grant nothing.

## 14. Development database

- The database ships empty. First login is `/auth/setup` →
  `POST /api/v1/auth/setup/initialize`, which creates the first account with
  `SUPER_ADMIN` and seeds document sequences, currencies, the role vocabulary and
  the permission catalog. No password is hardcoded: the operator supplies it.
- Startup (`lifespan`) calls `ensure_permission_catalog()`: missing permission
  rows, the seven roles and the missing Casbin grants are added, then the enforcer
  is reloaded and the `auth` cache version bumped.
- `reset_all_data` preserves `users`, `user_credentials`, `user_sessions`,
  `used_refresh_tokens`, `roles`, `permissions`, `casbin_rule`, `audit_events` and
  `import_jobs` — an administrative reset must never delete the administrator or
  reopen the public setup endpoint.
- Development authorization data may be dropped and recreated; nothing in the
  schema depends on it.

## 15. Known limits

- There is no tenant dimension yet. The model reserves `v3`–`v5`, so a `dom`
  column can be added without reshaping the policy table.
- **Role assignments have no expiry.** The old `user_role_assignments.expires_at`
  column went away with that table: an assignment is a `g` row and time-limited
  access is revoked by removing the role, which publishes a new policy version on
  the next request. No current workflow depended on scheduled expiry.
- There is no automated route-inventory gate. The dependency-graph audit that
  produced the 396/13 figures in §8.3 was run by hand; a new router must add its
  guard consciously, and `docs/10_testing_and_quality.md` records this gap.
- Two coarse capabilities (`configuration.manage`, `master.reference.manage`) and
  `customs_credential.retrieve` are not granted by any matrix page. The first two
  are fallbacks the guards still accept for roles created before the matrix; the
  third belongs to a feature without an endpoint yet.

