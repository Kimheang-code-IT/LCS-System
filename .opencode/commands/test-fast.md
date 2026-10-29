---
description: Run only the backend tests affected by the current change set
---

Pick the smallest backend test set for the uncommitted diff. Run from `backend/`.

| Changed path | Run |
|---|---|
| `app/modules/quotations/**` | `uv run pytest -q tests/test_quotations.py tests/test_quotation_versions.py` |
| `app/modules/operations/**` | `uv run pytest -q tests/test_workflows.py tests/test_component_attributes.py tests/test_movements_and_milestones.py` |
| `app/modules/master_data/**` | `uv run pytest -q tests/test_config_versions.py tests/test_config_compare.py tests/test_currencies_and_fx.py tests/test_places.py` |
| `app/modules/finance/**` | `uv run pytest -q tests/test_financial_documents_module.py tests/test_posting_rules.py tests/test_finance_automation.py tests/test_multi_currency.py` |
| `app/modules/auth/**`, `app/core/permissions.py`, `app/core/authorization/**` | `uv run pytest -q tests/test_auth_rbac.py tests/test_role_permissions.py tests/test_page_api_integration.py` |
| `app/api/**`, `app/core/**` | `uv run pytest -q tests/test_api_completeness.py tests/test_frontend_api_contract.py tests/test_request_schemas.py` |
| `models.py`, `alembic/versions/**` | `uv run pytest -q tests/test_migration_chain.py tests/test_schema_integrity.py tests/test_schema_docs.py` |
| `frontend/app/utils/constants/**`, `app/utils/api/**` | `uv run pytest -q tests/test_frontend_api_contract.py` |

Rules:

- Two or more rows apply → run the union, in one `pytest` call with several paths.
- A previous run left failures → `uv run pytest -q --lf` first; it re-runs only those.
- Single test: `uv run pytest -q tests/test_quotations.py::test_name`.
- Report the pass/fail counts and the first failing traceback. Do not paste the whole run.
- Run the full suite only when the diff touches shared infrastructure or the user asks.
