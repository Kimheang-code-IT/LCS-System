---
name: dynamic-ui-configuration
description: Use when implementing or changing LCS database-driven Service Order configuration: component tabs, groups, reusable attributes, field types and labels, validation rules, options, display order, trade-direction filtering, shared tabs, and configuration versioning.
---

# Dynamic UI configuration

The Service Order form is configuration, not code. Administrators define tabs,
groups, and fields in the database; the backend decides which tabs apply to an
order based on its trade direction and validates every submitted value.

## When to use

- Adding or changing a tab, group, attribute, or their membership.
- Changing field types, labels, options, required flags, or order.
- Scoping a tab to a trade direction, or sharing one across directions.
- Publishing, previewing, or retiring a configuration version.
- Changing how dynamic values are validated or stored.

## Required inputs

1. Which trade direction(s) the change applies to.
2. Whether it is a new field or a change to an existing one — and whether existing
   Service Orders already store values for it.
3. Whether the change needs a new published configuration version.

## Project references

| Document | Use it for |
|---|---|
| `backend/app/modules/master_data/models.py` | `ComponentAttribute`, `ComponentGroup`, `ComponentGroupAttribute`, `ComponentTab`, `ComponentTabGroup`, `ConfigurationVersion` |
| `backend/app/modules/master_data/component_config.py` | Admin CRUD and the rename guard |
| `backend/app/modules/master_data/config_snapshot.py` | The snapshot builder (framework-free, shared with the migration) |
| `backend/app/modules/master_data/config_versions.py` | Preview, publish, retire, historical pinning |
| `backend/app/modules/operations/component_tabs.py` | Runtime bootstrap, value coercion, validation |
| `frontend/app/components/document/AppComponentTabs.vue`, `frontend/app/composables/freight/useComponentTabs.ts` | The renderer |
| `docs/17_repository_analysis.md` §Dynamic configuration | Current status and known gaps |

## Model

```text
trade_directions ─┐
                  ├─ component_tabs            (scoped to one direction, or NULL = all)
component_groups ─┼─ component_tab_groups      (tab ⇄ group, display_order)
                  └─ component_groups
                       └─ component_group_attributes (group ⇄ attribute, overrides)
                            └─ component_attributes (code, label, label_km, data_type, …)

service_orders ─ configuration_version_id ─┐
component_tabs ─ config_version_id ────────┼─ configuration_versions (snapshot + status)
service_order_component_rows ─ config_version_id ┘
```

- A **tab** is scoped by `trade_direction_id`; `NULL` means it appears for every
  direction (this is how a shared tab is expressed — there is no junction table).
- A **group** renders as `table` (repeatable rows) or `form` (a single row).
- An **attribute** is reusable across groups; `code` is the storage key.
- **Values** live in `service_order_component_rows.values`, a JSON object keyed by
  attribute `code`, with `UNIQUE(service_order_id, group_id, row_no)`.

## Workflow

1. **Decide whether this is configuration or schema.** A new field is a row, not a
   migration. Only a new *behaviour* (a new data type, a new reference target)
   needs code.
2. **Reuse before creating.** An attribute is defined once and attached to many
   groups; do not create `container_no` twice.
3. **Ordering is data.** `display_order` drives rendering; ties break by code. The
   admin UI keeps a `+10` spacing convention so a later insert fits between two
   rows.
4. **Validate on the server, always.** `component_tabs._validate_values` coerces
   and checks required, options, and references per the attribute's `data_type`,
   its `options`, and its `validation_rules` JSON. The frontend mirrors these rules
   for fast feedback; the mirror is a convenience, never the authority.
5. **Respect the rename guard.** `_rename_attribute` refuses to change a `code`
   that existing Service Orders already store values for
   (`Conflict("ATTRIBUTE_CODE_IN_USE")`). The label may change freely. To replace a
   field: deactivate the old one and create a new one — never rewrite stored keys.
6. **Publish a configuration version when the layout changes.** Publishing
   snapshots the live tabs/groups/fields and stamps them; new Service Orders are
   pinned to that version, existing ones keep the version they were captured under.
   Publishing an unchanged configuration is rejected
   (`Conflict("CONFIGURATION_UNCHANGED")`); only one version may be `PUBLISHED`.
7. **Snapshot via the shared builder.** `config_snapshot.py` is used by both the
   service and migration `d5e6f7a8b9c0`, so the baseline snapshot and every later
   one have the same shape. Change the builder in one place only, and keep it
   framework-free (it receives plain mappings).

## Supported field types

`text`, `textarea`, `number`, `decimal`, `money`, `currency`, `date`, `datetime`,
`select`, `multi_select`, `checkbox`, `boolean`, `reference`.

`reference` needs a `reference_type` from the code-owned `REFERENCE_TYPES` set
(`business_party`, `place`, `transport_asset`, `transport_type`, `container`,
`fee_type`, `user`) — see `component_config.REFERENCE_TYPES` and
`operations/reference_options.py`. A new reference target is a code change on both
sides.

## Security and validation requirements

- **Never execute configuration.** A snapshot is data. No stored expression, SQL
  fragment, or template is evaluated. If a requirement looks like "let admins write
  a formula", refuse it and ask.
- Do not let a configuration write bypass the backend: every value is validated
  against the live attribute rules before it is stored.
- Deactivating or archiving configuration must never delete stored values.
- A tab, group, or attribute referenced by saved rows cannot be hard-deleted; the
  admin service deactivates instead. Keep that behaviour.
- Publishing changes the form for every user, so it needs the stricter
  `service_order_config.publish` permission, not just `configuration.manage`.

## Testing

```bash
cd backend
uv run python -m pytest tests/test_config_versions.py tests/test_workflows.py -q --no-header
uv run python -m pytest -q && uv run ruff check .
cd ../frontend && pnpm vitest run tests/component-config-tables.spec.ts
```

Required coverage:

| Case | Expected |
|---|---|
| Bootstrap for a direction | only that direction's tabs (plus `NULL`-scoped shared tabs), ordered |
| Required attribute left blank | `ValidationFailed` keyed to that attribute |
| Value outside `options` | rejected |
| List value for `multi_select` | accepted; a scalar is coerced |
| Bad `reference` id | rejected |
| Unknown submitted key | ignored, not stored |
| Rename a referenced attribute code | `ATTRIBUTE_CODE_IN_USE` |
| Rename an unreferenced code | allowed |
| Publish with no active tab | rejected |
| Publish unchanged configuration | `CONFIGURATION_UNCHANGED` |
| Publish after a change | new version; previous becomes `RETIRED` |
| Existing Service Order after a publish | still pinned to its original version |

The backend's component-row `field_errors` are keyed `"<1-based row index>.<code>"`.
The frontend resolves errors against its own registered keys, so when changing that
format, update `frontend/app/utils/validation/error-paths.ts` and its consumers in
the same change or the errors degrade to page-level messages.

## Acceptance criteria

- Tabs shown for an order are determined by its trade direction, from the database.
- Shared tabs work by leaving `trade_direction_id` NULL.
- Historical Service Order values survive every configuration change.
- Backend validation is authoritative and covered by tests.
- Publishing is permission-gated and versioned; history is reproducible.
- No configuration value is ever executed as code.

## Expected outputs

- Configuration rows (via the admin API or a data migration) — not schema changes.
- Code changes only when a data type, reference target, or validation behaviour grew.
- Tests covering the affected rows above.
- An updated description of the configuration model in `docs/`.
