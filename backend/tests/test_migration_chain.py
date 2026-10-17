"""Static guarantees about the Alembic migration chain.

The migration itself cannot be exercised here (tests run on in-memory SQLite and
the revisions use PostgreSQL features), so these are the properties that *can* be
checked without a database: a single head, a linear chain, a real downgrade for
every revision, and an additive-only shape for the revisions that introduce the
47-table design's missing pieces.

Together they are what makes ``alembic downgrade`` a usable rollback rather than
a promise. ``docs/15_migration_and_rollback_guide.md`` documents the procedure;
this module keeps the invariants from silently regressing.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
VERSIONS = BACKEND_ROOT / "alembic" / "versions"

# Revisions that add the capabilities the 47-table reference design has and the
# 59-table design lacked, plus the later posting-rules revision. None may drop or
# narrow anything pre-existing.
ADDITIVE_REVISIONS = (
    "b3c4d5e6f7a8",  # currencies + currency_rates
    "c4d5e6f7a8b9",  # app_settings
    "d5e6f7a8b9c0",  # configuration_versions
    "e6f7a8b9c0d1",  # reporting views + integrity guards
    "f8a9b0c1d2e3",  # posting_rules priority + description + indexes
    "a9b0c1d2e3f4",  # journal_entries link to the rule that posted it
    "b0c1d2e3f4a5",  # user_credentials.must_change_password
)


def _revision_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        match = re.search(r'^revision:\s*str\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if match:
            files[match.group(1)] = path
    return files


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"alembic_rev_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _down_revisions() -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    for revision, path in _revision_files().items():
        text = path.read_text(encoding="utf-8")
        match = re.search(r'^down_revision:\s*str\s*\|\s*None\s*=\s*(\S+)', text, re.MULTILINE)
        assert match, f"{path.name} does not declare down_revision"
        raw = match.group(1).strip().strip("'\"")
        mapping[revision] = None if raw == "None" else raw
    return mapping


def test_the_chain_has_exactly_one_head_and_no_branches():
    mapping = _down_revisions()
    parents = {parent for parent in mapping.values() if parent is not None}

    heads = sorted(set(mapping) - parents)
    assert len(heads) == 1, f"expected a single head, found {heads}"

    for revision, parent in mapping.items():
        if parent is not None:
            assert parent in mapping, f"{revision} points at missing parent {parent}"

    # Every non-head revision must be referenced by exactly one child, otherwise
    # the history has a branch or an orphan.
    children: dict[str, int] = {}
    for parent in parents:
        children[parent] = children.get(parent, 0) + 1
    branched = {revision: count for revision, count in children.items() if count > 1}
    assert not branched, f"revisions with more than one child: {branched}"


def test_every_revision_defines_a_working_downgrade():
    for revision, path in _revision_files().items():
        module = _load(path)
        assert callable(getattr(module, "upgrade", None)), f"{revision} has no upgrade()"
        assert callable(getattr(module, "downgrade", None)), f"{revision} has no downgrade()"
        source = path.read_text(encoding="utf-8")
        downgrade_body = source.split("def downgrade", 1)[1]
        assert re.search(r"op\.\w+\(", downgrade_body), (
            f"{revision} defines an empty downgrade; the chain would not be reversible"
        )


def test_the_chain_reaches_the_expected_head():
    heads = sorted(set(_down_revisions()) - {p for p in _down_revisions().values() if p})
    assert heads == ["d2e3f4a5b6c8"], (
        "the head changed; update docs/15_migration_and_rollback_guide.md and the deployed "
        f"revision expectation (found {heads})"
    )


@pytest.mark.parametrize("revision", ADDITIVE_REVISIONS)
def test_new_revisions_are_additive_only(revision: str):
    """No additive revision may drop, rename or narrow an existing object.

    ``op.drop_*`` is allowed only for objects the same revision created (a
    downgrade, or a view/trigger it owns); ``op.alter_column`` is not expected at
    all because these revisions only add structures.
    """
    path = _revision_files()[revision]
    source = path.read_text(encoding="utf-8")
    upgrade_body = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0]

    assert "op.alter_column" not in upgrade_body, f"{revision} alters a column in upgrade()"

    for statement in re.findall(r"op\.drop_(\w+)\(\s*[\"']([^\"']+)", upgrade_body):
        kind, name = statement
        created_in_upgrade = f'"{name}"' in upgrade_body.split("op.drop_", 1)[0]
        assert created_in_upgrade, (
            f"{revision} drops {kind} {name!r} in upgrade() without having created it; "
            "the migration may not be additive-only"
        )


def test_new_revisions_never_drop_a_pre_existing_table():
    """The 59-table design keeps every table; nothing may be dropped on upgrade."""
    pre_existing = (
        "roles",
        "users",
        "user_credentials",
        "user_role_assignments",
        "permissions",
        "role_permissions",
        "user_sessions",
        "password_reset_tokens",
        "business_parties",
        "places",
        "container_types",
        "transport_types",
        "transport_assets",
        "fee_types",
        "trade_directions",
        "customer_customs_accounts",
        "module_records",
        "chart_of_accounts",
        "financial_accounts",
        "accounting_periods",
        "document_sequences",
        "posting_rules",
        "quotations",
        "quotation_revisions",
        "quotation_revision_lines",
        "quotation_revision_places",
        "quotation_revision_containers",
        "quotation_conversions",
        "service_orders",
        "service_order_places",
        "service_order_container_requirements",
        "service_order_containers",
        "service_order_pricing",
        "service_order_pricing_lines",
        "service_order_charges",
        "service_order_charge_lines",
        "service_order_movements",
        "service_order_milestones",
        "service_order_component_rows",
        "component_attributes",
        "component_groups",
        "component_tabs",
        "component_group_attributes",
        "component_tab_groups",
        "financial_documents",
        "financial_document_lines",
        "financial_document_allocations",
        "financial_document_sources",
        "financial_document_postings",
        "journal_entries",
        "journal_entry_lines",
        "audit_events",
        "archive_records",
        "attachments",
        "attachment_links",
        "backup_runs",
        "backup_states",
        "backup_records",
        "backup_logs",
    )
    for revision in ADDITIVE_REVISIONS:
        source = _revision_files()[revision].read_text(encoding="utf-8")
        upgrade_body = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
        for table in pre_existing:
            assert f'op.drop_table("{table}")' not in upgrade_body, (
                f"{revision} drops the pre-existing table {table!r} on upgrade"
            )
            assert f'op.drop_column("{table}"' not in upgrade_body, (
                f"{revision} drops a column of the pre-existing table {table!r} on upgrade"
            )


def test_every_model_module_is_imported_by_the_migration_environment():
    """``alembic/env.py`` must import every model module or autogenerate drifts.

    The schema generators assert the same thing implicitly, so a model module
    that is missing here would produce a revision that silently omits its tables.
    """
    env = (BACKEND_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")
    for module in (
        "app.modules.archive.models",
        "app.modules.audit.models",
        "app.modules.auth.models",
        "app.modules.backup.models",
        "app.modules.finance.models",
        "app.modules.master_data.models",
        "app.modules.operations.models",
        "app.modules.quotations.models",
        "app.modules.settings.models",
    ):
        assert f"import {module}" in env, f"alembic/env.py does not import {module}"
