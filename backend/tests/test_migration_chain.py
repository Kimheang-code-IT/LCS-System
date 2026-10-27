"""Static guarantees about the Alembic migration chain.

The migration itself cannot be exercised here for PostgreSQL-specific behavior
(tests run on in-memory SQLite), so these are the properties that *can* be
checked without a database: a single head, a linear chain, a real downgrade for
every revision, and an additive/non-destructive shape for the revisions that
introduce or preserve the design's structures.

Together they are what makes ``alembic downgrade`` a usable rollback rather than
a promise. ``docs/11_deployment_and_security.md`` §8 documents the procedure;
this module keeps the invariants from silently regressing.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
VERSIONS = BACKEND_ROOT / "alembic" / "versions"

# Revisions that add the current capabilities and the preservation guard. None
# may drop or narrow anything pre-existing.
ADDITIVE_REVISIONS = (
    "35bd68fa01ce",  # verified Telegram identities and single-use challenges
    "46ce79ab12df",  # durable notification outbox and monitoring incident state
    "b3c4d5e6f7a8",  # currencies + currency_rates
    "c4d5e6f7a8b9",  # app_settings
    "d5e6f7a8b9c0",  # configuration_versions
    "e6f7a8b9c0d1",  # reporting views + integrity guards
    "f8a9b0c1d2e3",  # posting_rules priority + description + indexes
    "a9b0c1d2e3f4",  # journal_entries link to the rule that posted it
    "b0c1d2e3f4a5",  # user_credentials.must_change_password
    "e3f4a5b6c7d9",  # per-tab component group layouts
    "a7c1e2f3b4d5",  # configuration version lifecycle metadata + immutability guard
    "b8d9e0f1a2b3",  # dynamic place roles + structured route stops
    "f2c3d4e5f6a7",  # draft configuration versions: editable until published
    "a9b8c7d6e5f4",  # dynamic party roles + business-party role assignments
    "e1f2a3b4c5d6",  # transport-asset identity vocabulary + capacity columns
    "f5a6b7c8d9e0",  # capacity-unit master
    "b6d7e8f9a0b1",  # component attribute catalog display order
    "c7e8f9a0b1c2",  # quotation source service order (re-quotation trace)
    "f6a7b8c9d0e1",  # document_types soft-delete attribution column + indexes
)

PRESERVATION_REVISIONS = (
    "c3d4e5f6a7b8",  # Places text backfill; no table/column removal
    "d4e5f6a7b8c9",  # guard against the old destructive c3d4 form
)

# These revisions intentionally have nothing to undo. Their upgrade is a data
# backfill or a read-only guard, and downgrading must not drop Places either.
NOOP_DOWNGRADES = frozenset(PRESERVATION_REVISIONS)


def _revision_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        match = re.search(r'^revision:\s*str\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if match:
            assert match.group(1) not in files, f"Duplicate revision identity: {match.group(1)}"
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
        if revision in NOOP_DOWNGRADES:
            assert "pass" in downgrade_body, f"{revision} declares a no-op downgrade without pass"
            continue
        assert re.search(r"op\.\w+\(", downgrade_body), (
            f"{revision} defines an empty downgrade; the chain would not be reversible"
        )


def test_the_chain_reaches_the_expected_head():
    heads = sorted(set(_down_revisions()) - {p for p in _down_revisions().values() if p})
    assert heads == ["f6a7b8c9d0e1"], (
        "the head changed; update docs/11_deployment_and_security.md and the deployed "
        f"revision expectation (found {heads})"
    )


def test_places_revisions_keep_the_legacy_structures():
    """The Places table, mapping and legacy foreign keys must survive upgrade."""
    c3d4 = _revision_files()["c3d4e5f6a7b8"].read_text(encoding="utf-8")
    c3d4_upgrade = c3d4.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
    assert "SET free_text = p.name" in c3d4_upgrade
    assert "originPlace" in c3d4_upgrade
    assert "destinationPlace" in c3d4_upgrade

    for revision in PRESERVATION_REVISIONS:
        source = _revision_files()[revision].read_text(encoding="utf-8")
        upgrade_body = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
        assert 'op.drop_table("places")' not in upgrade_body, f"{revision} drops places"
        assert 'op.drop_table("place_role_places")' not in upgrade_body, (
            f"{revision} drops place_role_places"
        )
        assert "op.drop_column" not in upgrade_body, f"{revision} drops a legacy column"


@pytest.mark.parametrize("revision", (*ADDITIVE_REVISIONS, *PRESERVATION_REVISIONS))
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
    """The current schema keeps every pre-existing table; nothing may be dropped on upgrade."""
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
        "place_role_places",
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
    for revision in (*ADDITIVE_REVISIONS, *PRESERVATION_REVISIONS):
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


def _migrated_columns() -> dict[str, set[str]]:
    """Columns each table gains across the whole chain (create_table + add_column)."""
    columns: dict[str, set[str]] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        # Tuple assignments (for example SOFT_DELETE_TABLES) that add_column loops over.
        tuples = {
            name: set(re.findall(r'"([a-z_]+)"', body))
            for name, body in re.findall(r"^(\w+)\s*=\s*\((.*?)\)$", text, re.MULTILINE | re.DOTALL)
        }
        for match in re.finditer(r'op\.create_table\(\s*"([^"]+)"(.*?)\n    \)', text, re.DOTALL):
            table, body = match.group(1), match.group(2)
            columns.setdefault(table, set()).update(re.findall(r'sa\.Column\("([^"]+)"', body))
        for match in re.finditer(r'op\.add_column\("([^"]+)",\s*sa\.Column\("([^"]+)"', text):
            columns.setdefault(match.group(1), set()).add(match.group(2))
        for match in re.finditer(r'op\.add_column\((\w+)\s*,\s*sa\.Column\("([^"]+)"', text):
            # The table argument may be a loop variable ("for table in SOFT_DELETE_TABLES").
            loops = dict(re.findall(r"for (\w+) in (?:reversed\()?(\w+)\)?", text))
            for table in tuples.get(loops.get(match.group(1), match.group(1)), set()):
                columns.setdefault(table, set()).add(match.group(2))
    return columns


def test_every_soft_delete_column_exists_in_the_migrated_schema():
    """Regression: document_types shipped with deleted_at but not deleted_by_user_id.

    The DocumentType model carries SoftDeleteMixin, so every ORM select read the
    missing column and 500'd on a migrated database (the Audit Logs page loads
    document types and broke even though /audit-events itself answered fine).
    Tests build the schema with ``create_all`` and never see this drift, so the
    chain is checked statically here.
    """
    import app.modules.archive.models  # noqa: F401
    import app.modules.auth.models  # noqa: F401
    import app.modules.backup.models  # noqa: F401
    import app.modules.finance.models  # noqa: F401
    import app.modules.master_data.models  # noqa: F401
    import app.modules.operations.models  # noqa: F401
    import app.modules.quotations.models  # noqa: F401
    import app.modules.settings.models  # noqa: F401
    from app.core.database import Base

    migrated = _migrated_columns()
    soft_delete_tables = [
        name
        for name, table in Base.metadata.tables.items()
        if {"deleted_at", "deleted_by_user_id"} <= {column.name for column in table.columns}
    ]
    assert soft_delete_tables, "no soft-delete models found; the detection itself broke"
    for table in sorted(soft_delete_tables):
        missing = {"deleted_at", "deleted_by_user_id"} - migrated.get(table, set())
        assert not missing, (
            f"the migration chain never creates {table}.{sorted(missing)[0]}; "
            "the ORM model would fail every query against a migrated database"
        )
