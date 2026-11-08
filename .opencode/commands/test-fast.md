---
description: Find the smallest relevant existing backend regression selector
---

Select by changed behavior and existing tests, then run the union once from backend/.
This table is a starting lookup, not a mandate to run every file in a row.

| Area | Existing candidates (tests/) |
|---|---|
| Quotations/SO conversion | test_quotation_reuse.py, test_quotations.py, test_quotation_versions.py, test_workflows.py |
| Operations | test_movements_and_milestones.py, test_workflows.py, test_component_attributes.py |
| Finance | test_financial_documents_module.py, test_posting_rules.py, test_multi_currency.py, test_accounting_periods.py |
| Invoice/container print | test_financial_printing.py |
| Master/config | test_config_versions.py, test_currencies_and_fx.py, test_place_roles.py |
| Auth/permissions | test_auth_rbac.py, test_role_permissions.py, test_route_authorization.py |
| API/client contracts | test_frontend_api_contract.py, test_request_schemas.py |
| Schema | test_migration_chain.py, test_schema_integrity.py, test_schema_docs.py |

Verify files and relevant cases exist. Command: uv run --no-sync pytest -q tests/<selected>.py.
New meaningful regressions are allowed for actual gaps. DEEP adds required denial/rollback/
idempotency/race checks and independent review; never substitute only a smoke test. SQLite
cannot validate PostgreSQL triggers/locks. Do not rerun unchanged passing suites or run the
whole repository merely because two areas are touched. Report exact command/results/limits.
