"""Manual seed command for Master Data and Configuration reference data.

    uv run python scripts/seed.py                    # show help
    uv run python scripts/seed.py --all              # reference data only
    uv run python scripts/seed.py --demo             # + demo rows (5 records per table)
    uv run python scripts/seed.py --master-data
    uv run python scripts/seed.py --configuration
    uv run python scripts/seed.py --module fee-types
    uv run python scripts/seed.py --module business-parties  # sample parties only
    uv run python scripts/seed.py --module accounting       # chart + bank + posting rules
    uv run python scripts/seed.py --all --dry-run    # report only, no writes

Behavior
--------
Insert-missing only. A row whose natural key (code/name) already exists is
skipped, never edited - user renames, deactivations and currency metadata
survive. Nothing is deleted and no ConfigurationVersion is created or published
(publishing stays the explicit admin workflow). Each module commits in its own
transaction; a failed module rolls back and the run reports it, so earlier
modules stay seeded.

First-run setup (`/auth/setup`) and a data reset insert nothing but the
administrator and the permission/role catalog: run this command afterwards to
create the currency master, document sequences, app settings and every other
reference row. `--demo` additionally adds sample business parties and extra
Configuration groups/tabs so every Master Data and Configuration table holds at
least five records; `--all` stays pure reference data.

Nothing here runs automatically at start-up or deploy time - this command is
the only thing that inserts master/configuration rows (see
docs/03-development/deployment-guide.md for the production invocation).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# `python scripts/seed.py` puts this directory first on sys.path; the app
# package lives one level up, so make it importable from any working directory
# (local venv, a production container, or a one-off docker compose run).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seed_data.accounting import CHART_OF_ACCOUNTS, FINANCIAL_ACCOUNTS, POSTING_RULES
from seed_data.configuration import (
    CONFIGURATION_PLANS,
    DEMO_COMPONENT_GROUPS,
    DEMO_COMPONENT_TABS,
    DEMO_GROUP_MEMBERSHIPS,
    DEMO_TAB_GROUPS,
    GROUP_MEMBERSHIPS,
    TAB_GROUPS,
    ComponentAttribute,
)
from seed_data.master_data import DEMO_BUSINESS_PARTIES, MASTER_PLANS, TRANSPORT_ASSETS
from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.master_data.models import (
    ComponentGroup,
    ComponentGroupAttribute,
    ComponentTab,
    ComponentTabGroup,
    TradeDirection,
)

MASTER_MODULE_ORDER = (
    "trade-directions",
    "party-roles",
    "place-roles",
    "container-types",
    "transport-types",
    "transport-assets",
    "asset-identity-types",
    "capacity-units",
    "fee-types",
    "currencies",
    "document-types",
)
CONFIGURATION_MODULE_ORDER = (
    "document-sequences",
    "app-settings",
    "component-attributes",
    "component-groups",
    "component-tabs",
    "configuration-links",
    # Finance bootstrap: chart of accounts, bank/cash accounts and posting rules.
    "accounting",
)


def _soft_deletes(model: type) -> bool:
    return "deleted_at" in model.__table__.columns


async def _existing_keys(session, model: type, column: str) -> set:
    stmt = select(getattr(model, column))
    if _soft_deletes(model):
        stmt = stmt.where(model.deleted_at.is_(None))
    return set((await session.execute(stmt)).scalars().all())


async def seed_plan(session, model: type, key_column: str, rows) -> tuple[int, int]:
    """Insert the plan rows missing by ``key_column``. Returns (inserted, skipped)."""
    existing = await _existing_keys(session, model, key_column)
    inserted = skipped = 0
    for row in rows:
        if row[key_column] in existing:
            skipped += 1
            continue
        session.add(model(**{k: v for k, v in row.items() if hasattr(model, k)}))
        inserted += 1
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_transport_assets(session) -> tuple[int, int]:
    """DEMO transport assets, with the transport type resolved from its code.

    Missing `transport_type` vocabularies are impossible here: the seed orders
    modules so `transport-types` runs first and its plan matches the codes the
    assets reference. An asset whose `asset_code` already exists is skipped.
    """
    from app.modules.master_data.models import TransportAsset, TransportType

    existing = await _existing_keys(session, TransportAsset, "asset_code")
    type_ids = {code: tid for code, tid in (await session.execute(select(TransportType.code, TransportType.id))).all()}
    inserted = skipped = 0
    for row in TRANSPORT_ASSETS:
        if row["asset_code"] in existing:
            skipped += 1
            continue
        type_id = type_ids.get(row["transport_type_code"])
        if type_id is None:
            raise LookupError(f"Cannot link asset '{row['asset_code']}' to transport type '{row['transport_type_code']}'.")
        fields = {k: v for k, v in row.items() if k != "transport_type_code"}
        session.add(TransportAsset(transport_type_id=type_id, **fields))
        inserted += 1
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_service_modules(session, name: str) -> tuple[int, int]:
    """Identity types & capacity units via the existing master-data services.

    The services skip existing rows themselves; the counts here predict them
    from the same defaults so the report stays accurate without a full reload.
    """
    from app.modules.master_data.models import CapacityUnit, TransportAssetIdentityType
    from app.modules.master_data.service import (
        DEFAULT_CAPACITY_UNITS,
        DEFAULT_IDENTITY_TYPES,
        seed_capacity_units,
        seed_transport_asset_identity_types,
    )

    if name == "asset-identity-types":
        existing = await _existing_keys(session, TransportAssetIdentityType, "name")
        wanted = {name_ for name_, *_ in DEFAULT_IDENTITY_TYPES}
        await seed_transport_asset_identity_types(session)
    else:
        existing = await _existing_keys(session, CapacityUnit, "code")
        wanted = {code for code, _ in DEFAULT_CAPACITY_UNITS}
        await seed_capacity_units(session)
    return len(wanted - existing), len(wanted & existing)


async def seed_configuration_tabs(session) -> tuple[int, int]:
    """Insert the tabs, resolving the trade-direction FK by code (demo convention:
    a missing direction leaves the tab unlinked = offered for every direction)."""
    model, key_column, rows = CONFIGURATION_PLANS["component-tabs"]
    existing = await _existing_keys(session, model, key_column)
    directions = {code: did for code, did in (await session.execute(select(TradeDirection.code, TradeDirection.id))).all()}
    inserted = skipped = 0
    for row in rows:
        if row[key_column] in existing:
            skipped += 1
            continue
        fields = {k: v for k, v in row.items() if hasattr(model, k) and k != "trade_direction_code"}
        fields["trade_direction_id"] = directions.get(row.get("trade_direction_code", ""))
        session.add(model(**fields))
        inserted += 1
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_members(session) -> tuple[int, int]:
    """Group↔attribute and tab↔group memberships, resolved by unique codes."""
    attribute_ids = {code: aid for code, aid in (await session.execute(select(ComponentAttribute.code, ComponentAttribute.id))).all()}
    group_ids = {code: gid for code, gid in (await session.execute(select(ComponentGroup.code, ComponentGroup.id))).all()}
    tab_ids = {code: tid for code, tid in (await session.execute(select(ComponentTab.code, ComponentTab.id))).all()}

    inserted = skipped = 0
    existing_links = set((await session.execute(select(ComponentGroupAttribute.group_id, ComponentGroupAttribute.attribute_id))).all())
    for group_code, attribute_code, order in GROUP_MEMBERSHIPS:
        gid, aid = group_ids.get(group_code), attribute_ids.get(attribute_code)
        if gid is None or aid is None:
            raise LookupError(f"Cannot link group '{group_code}' to attribute '{attribute_code}': one side is missing.")
        if (gid, aid) in existing_links:
            skipped += 1
            continue
        session.add(ComponentGroupAttribute(group_id=gid, attribute_id=aid, display_order=order, status="ACTIVE"))
        existing_links.add((gid, aid))
        inserted += 1

    existing_tab_groups = set((await session.execute(select(ComponentTabGroup.tab_id, ComponentTabGroup.group_id))).all())
    for tab_code, group_code, order in TAB_GROUPS:
        tid, gid = tab_ids.get(tab_code), group_ids.get(group_code)
        if tid is None or gid is None:
            raise LookupError(f"Cannot link tab '{tab_code}' to group '{group_code}': one side is missing.")
        if (tid, gid) in existing_tab_groups:
            skipped += 1
            continue
        session.add(ComponentTabGroup(tab_id=tid, group_id=gid, display_order=order, status="ACTIVE"))
        existing_tab_groups.add((tid, gid))
        inserted += 1

    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_document_sequences(session) -> tuple[int, int]:
    """Numbering rows for the current year (insert missing only).

    The first-run setup no longer creates these, so numbering starts working
    once this module has run. Existing counters are never touched.
    """
    from app.core.sequences import DEFAULT_PREFIXES
    from app.modules.finance.models import DocumentSequence

    year = datetime.now(UTC).year
    existing = {
        document_type
        for (document_type,) in (await session.execute(
            select(DocumentSequence.document_type).where(DocumentSequence.period_year == year)
        )).all()
    }
    inserted = skipped = 0
    for document_type, prefix in DEFAULT_PREFIXES.items():
        if document_type in existing:
            skipped += 1
            continue
        session.add(
            DocumentSequence(
                document_type=document_type,
                period_year=year,
                prefix=prefix,
                last_value=0,
                padding_length=6,
                status="ACTIVE",
            )
        )
        inserted += 1
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_app_settings(session) -> tuple[int, int]:
    """Default app info/config rows and their rollback mirror, insert missing only."""
    from copy import deepcopy

    from app.modules.master_data.models import ModuleRecord
    from app.modules.settings.models import AppSetting
    from app.modules.settings.service import (
        APP_CONFIG_COLLECTION,
        APP_INFO_COLLECTION,
        APP_INFO_GROUP,
        APP_INFO_KEY,
        DEFAULT_APP_CONFIG,
        DEFAULT_APP_INFO,
        SETTINGS_RECORD_NO,
    )

    existing = set((await session.execute(select(AppSetting.setting_key))).scalars().all())
    inserted = skipped = 0
    if APP_INFO_KEY in existing:
        skipped += 1
    else:
        session.add(
            AppSetting(
                setting_key=APP_INFO_KEY,
                setting_group=APP_INFO_GROUP,
                setting_value=deepcopy(DEFAULT_APP_INFO),
                description="Application identity, branding and support contacts.",
            )
        )
        inserted += 1
    for group, defaults in DEFAULT_APP_CONFIG.items():
        if group in existing:
            skipped += 1
            continue
        session.add(
            AppSetting(
                setting_key=group,
                setting_group=group,
                setting_value=deepcopy(defaults),
                description=f"Application settings group '{group}'.",
            )
        )
        inserted += 1
    for collection, defaults in (
        (APP_INFO_COLLECTION, DEFAULT_APP_INFO),
        (APP_CONFIG_COLLECTION, DEFAULT_APP_CONFIG),
    ):
        exists = (await session.execute(
            select(ModuleRecord.id).where(
                ModuleRecord.collection == collection,
                ModuleRecord.record_no == SETTINGS_RECORD_NO,
            )
        )).scalars().first()
        if exists is not None:
            skipped += 1
            continue
        session.add(ModuleRecord(collection=collection, record_no=SETTINGS_RECORD_NO, data=deepcopy(defaults)))
        inserted += 1
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_chart_of_accounts(session) -> tuple[int, int]:
    """Insert the standard freight-forwarding chart of accounts (parents first)."""
    from app.modules.finance.models import ChartOfAccount

    rows = (await session.execute(select(ChartOfAccount))).scalars().all()
    by_code = {row.account_code: row for row in rows}
    inserted = skipped = 0
    for plan in CHART_OF_ACCOUNTS:
        code = str(plan["account_code"])
        if code in by_code:
            skipped += 1
            continue
        parent_code = str(plan.get("parent_code") or "")
        parent = by_code.get(parent_code) if parent_code else None
        if parent_code and parent is None:
            raise LookupError(f"Cannot link account '{code}' to missing parent '{parent_code}'.")
        account = ChartOfAccount(
            account_code=code,
            account_name=str(plan["account_name"]),
            account_type=str(plan["account_type"]),
            normal_balance=str(plan["normal_balance"]),
            is_postable=bool(plan.get("postable", True)),
            status="ACTIVE",
            parent_account_id=parent.id if parent else None,
        )
        session.add(account)
        await session.flush()
        by_code[code] = account
        inserted += 1
    return inserted, skipped


async def seed_financial_accounts(session) -> tuple[int, int]:
    """Link the bank and cash settlement accounts to their ledger accounts."""
    from app.modules.finance.models import ChartOfAccount, FinancialAccount

    ledger_ids = {
        code: account_id
        for code, account_id in (
            await session.execute(select(ChartOfAccount.account_code, ChartOfAccount.id))
        ).all()
    }
    existing = set((await session.execute(select(FinancialAccount.account_id))).scalars().all())
    inserted = skipped = 0
    for plan in FINANCIAL_ACCOUNTS:
        ledger_code = str(plan["ledger_code"])
        ledger_id = ledger_ids.get(ledger_code)
        if ledger_id is None:
            raise LookupError(f"Cannot link financial account to missing ledger '{ledger_code}'.")
        if ledger_id in existing:
            skipped += 1
            continue
        session.add(
            FinancialAccount(
                account_id=ledger_id,
                account_name=str(plan["account_name"]),
                account_type=str(plan["account_type"]),
                currency_code=str(plan["currency"]),
                bank_name=plan.get("bank_name"),
                account_number_masked=plan.get("account_number_masked"),
                status="ACTIVE",
            )
        )
        existing.add(ledger_id)
        inserted += 1
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_posting_rules(session) -> tuple[int, int]:
    """One active document-default rule per financial document type.

    A document type that already has an active default rule is skipped, so an
    administrator's mapping is never replaced by the bootstrap set.
    """
    from app.modules.finance.models import ChartOfAccount, PostingRule

    account_ids = {
        code: account_id
        for code, account_id in (
            await session.execute(select(ChartOfAccount.account_code, ChartOfAccount.id))
        ).all()
    }
    existing = set(
        (
            await session.execute(
                select(PostingRule.document_type).where(
                    PostingRule.fee_type_id.is_(None),
                    PostingRule.status == "ACTIVE",
                )
            )
        ).scalars().all()
    )
    inserted = skipped = 0
    for plan in POSTING_RULES:
        document_type = str(plan["document_type"])
        if document_type in existing:
            skipped += 1
            continue
        debit_code = str(plan["debit_code"])
        credit_code = str(plan["credit_code"])
        tax_code = str(plan["tax_code"]) if plan.get("tax_code") else ""
        missing = [code for code in (debit_code, credit_code, tax_code) if code and code not in account_ids]
        if missing:
            raise LookupError(
                f"Cannot seed posting rule '{document_type}': missing account(s) {', '.join(missing)}."
            )
        session.add(
            PostingRule(
                document_type=document_type,
                fee_type_id=None,
                debit_account_id=account_ids[debit_code],
                credit_account_id=account_ids[credit_code],
                tax_account_id=account_ids[tax_code] if tax_code else None,
                status="ACTIVE",
                priority=0,
                description=str(plan["description"]),
            )
        )
        existing.add(document_type)
        inserted += 1
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_accounting(session) -> tuple[int, int]:
    """Chart of accounts + financial accounts + posting rules, in dependency order."""
    inserted = skipped = 0
    for step in (seed_chart_of_accounts, seed_financial_accounts, seed_posting_rules):
        step_inserted, step_skipped = await step(session)
        inserted += step_inserted
        skipped += step_skipped
    return inserted, skipped


async def seed_business_parties(session) -> tuple[int, int]:
    """Five domain-free sample parties, linked to seeded party roles.

    Run explicitly with ``--module business-parties`` (or as part of ``--demo``).
    They are sample master data, so ``--all`` stays pure reference data.
    """
    from app.modules.master_data.models import BusinessParty, BusinessPartyRole, PartyRole

    role_ids = {
        code: rid
        for code, rid in (await session.execute(
            select(PartyRole.code, PartyRole.id).where(PartyRole.deleted_at.is_(None))
        )).all()
    }
    role_names = {
        code: name
        for code, name in (await session.execute(
            select(PartyRole.code, PartyRole.name).where(PartyRole.deleted_at.is_(None))
        )).all()
    }
    existing = {
        code: pid
        for code, pid in (await session.execute(
            select(BusinessParty.party_code, BusinessParty.id).where(BusinessParty.deleted_at.is_(None))
        )).all()
    }
    inserted = skipped = 0
    for row in DEMO_BUSINESS_PARTIES:
        # Link the roles this database actually has; the base plan seeds the
        # whole vocabulary first, so a filtered code only happens on a database
        # an administrator deliberately trimmed.
        role_codes = tuple(code for code in row["role_codes"] if code in role_ids)
        party_id = existing.get(row["party_code"])
        if party_id is None:
            party = BusinessParty(
                party_code=row["party_code"],
                legal_name=row["legal_name"],
                display_name=row.get("display_name"),
                contact_person=row.get("contact_person"),
                phone=row.get("phone"),
                email=row.get("email"),
                roles=[role_names[code] for code in role_codes],
                status=row.get("status", "ACTIVE"),
            )
            session.add(party)
            await session.flush()
            party_id = party.id
            inserted += 1
        else:
            skipped += 1
        linked = set((await session.execute(
            select(BusinessPartyRole.business_party_id, BusinessPartyRole.party_role_id).where(
                BusinessPartyRole.business_party_id == party_id
            )
        )).all())
        for code in role_codes:
            if (party_id, role_ids[code]) in linked:
                continue
            session.add(BusinessPartyRole(business_party_id=party_id, party_role_id=role_ids[code]))
    if inserted:
        await session.flush()
    return inserted, skipped


async def seed_demo_configuration(session) -> tuple[int, int]:
    """Top up Configuration groups/tabs to five rows (``--demo``), linked like the base plan."""
    from app.modules.master_data.models import (
        ComponentAttribute,
        ComponentGroup,
        ComponentGroupAttribute,
        ComponentTab,
        ComponentTabGroup,
        TradeDirection,
    )

    direction_ids = {
        code: did for code, did in (await session.execute(select(TradeDirection.code, TradeDirection.id))).all()
    }
    inserted = skipped = 0

    existing_groups = {
        code: gid for code, gid in (await session.execute(select(ComponentGroup.code, ComponentGroup.id))).all()
    }
    for row in DEMO_COMPONENT_GROUPS:
        if row["code"] in existing_groups:
            skipped += 1
            continue
        group = ComponentGroup(**{k: v for k, v in row.items()})
        session.add(group)
        await session.flush()
        existing_groups[row["code"]] = group.id
        inserted += 1

    existing_tabs = {
        code: tid for code, tid in (await session.execute(select(ComponentTab.code, ComponentTab.id))).all()
    }
    for row in DEMO_COMPONENT_TABS:
        if row["code"] in existing_tabs:
            skipped += 1
            continue
        fields = {k: v for k, v in row.items() if k != "trade_direction_code"}
        fields["trade_direction_id"] = direction_ids.get(row.get("trade_direction_code", ""))
        tab = ComponentTab(**fields)
        session.add(tab)
        await session.flush()
        existing_tabs[row["code"]] = tab.id
        inserted += 1

    attribute_ids = {
        code: aid for code, aid in (await session.execute(select(ComponentAttribute.code, ComponentAttribute.id))).all()
    }
    existing_links = set((await session.execute(
        select(ComponentGroupAttribute.group_id, ComponentGroupAttribute.attribute_id)
    )).all())
    for group_code, attribute_code, order in DEMO_GROUP_MEMBERSHIPS:
        gid, aid = existing_groups.get(group_code), attribute_ids.get(attribute_code)
        if gid is None or aid is None:
            # A trimmed vocabulary keeps the demo groups/tabs but skips the link.
            skipped += 1
            continue
        if (gid, aid) in existing_links:
            skipped += 1
            continue
        session.add(ComponentGroupAttribute(group_id=gid, attribute_id=aid, display_order=order, status="ACTIVE"))
        existing_links.add((gid, aid))
        inserted += 1

    existing_tab_groups = set((await session.execute(
        select(ComponentTabGroup.tab_id, ComponentTabGroup.group_id)
    )).all())
    for tab_code, group_code, order in DEMO_TAB_GROUPS:
        tid, gid = existing_tabs.get(tab_code), existing_groups.get(group_code)
        if tid is None or gid is None:
            skipped += 1
            continue
        if (tid, gid) in existing_tab_groups:
            skipped += 1
            continue
        session.add(ComponentTabGroup(tab_id=tid, group_id=gid, display_order=order, status="ACTIVE"))
        existing_tab_groups.add((tid, gid))
        inserted += 1

    if inserted:
        await session.flush()
    return inserted, skipped


def _report(name: str, dry_run: bool, inserted: int, skipped: int) -> tuple[int, int]:
    if dry_run:
        print(f"[DRY-RUN] {name}: would insert {inserted}, skip {skipped}")
    else:
        print(f"[OK] {name}: inserted {inserted}, skipped {skipped}")
    return inserted, skipped


async def _run_module(session, name: str, dry_run: bool, counts: dict[str, int]) -> None:
    """Run one module in its own transaction; a failure rolls back and reports."""
    try:
        if name == "demo":
            party_counts = await seed_business_parties(session)
            config_counts = await seed_demo_configuration(session)
            inserted = party_counts[0] + config_counts[0]
            skipped = party_counts[1] + config_counts[1]
        elif name == "business-parties":
            inserted, skipped = await seed_business_parties(session)
        elif name == "accounting":
            inserted, skipped = await seed_accounting(session)
        elif name == "document-sequences":
            inserted, skipped = await seed_document_sequences(session)
        elif name == "app-settings":
            inserted, skipped = await seed_app_settings(session)
        elif name in ("asset-identity-types", "capacity-units"):
            inserted, skipped = await seed_service_modules(session, name)
        elif name == "transport-assets":
            inserted, skipped = await seed_transport_assets(session)
        elif name == "component-tabs":
            inserted, skipped = await seed_configuration_tabs(session)
        elif name == "configuration-links":
            inserted, skipped = await seed_members(session)
        elif name in ("component-attributes", "component-groups"):
            model, key_column, rows = CONFIGURATION_PLANS[name]
            inserted, skipped = await seed_plan(session, model, key_column, rows)
        else:
            model, key_column, rows = MASTER_PLANS[name]
            inserted, skipped = await seed_plan(session, model, key_column, rows)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        counts["inserted"] += inserted
        counts["skipped"] += skipped
        _report(name, dry_run, inserted, skipped)
    except Exception as exc:  # noqa: BLE001 - report the module, keep the run going
        await session.rollback()
        counts["failed"] += 1
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")


async def run(selected: list[str], dry_run: bool) -> int:
    counts = {"inserted": 0, "skipped": 0, "updated": 0, "failed": 0}
    async with SessionLocal() as session:
        for name in selected:
            await _run_module(session, name, dry_run, counts)
        # Attribute the seeded vocabulary rows so their creator shows "System"
        # (same attribution the /auth-setup baseline applies). Idempotent.
        if not dry_run and counts["inserted"]:
            from app.modules.master_data.service import ensure_vocabulary_creation_audit

            await ensure_vocabulary_creation_audit(session)
            await session.commit()

    print()
    print(f"Summary: inserted {counts['inserted']}, skipped {counts['skipped']}, "
          f"updated {counts['updated']} (insert-missing only), failed {counts['failed']}, "
          f"modules {len(selected)}")
    return 1 if counts["failed"] else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    # Sample business parties are explicit opt-in (`--module business-parties`
    # or `--demo`), so `--all` stays pure reference data.
    all_modules = (*MASTER_MODULE_ORDER, *CONFIGURATION_MODULE_ORDER, "business-parties")
    parser = argparse.ArgumentParser(
        description="Seed LCS Master Data and Configuration reference data (insert missing only). Run from backend/.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="Seed master data and configuration.")
    target.add_argument("--master-data", action="store_true", help="Seed Master Data modules only.")
    target.add_argument("--configuration", action="store_true", help="Seed Configuration modules only.")
    target.add_argument("--demo", action="store_true",
                        help="--all plus demo rows so every table has five records (business parties, component groups/tabs).")
    target.add_argument("--module", metavar="NAME", choices=all_modules,
                        help=f"Seed one module: {', '.join(all_modules)}")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
    args = parser.parse_args(argv)
    return args


def main() -> int:
    args = parse_args()
    selected: list[str] = (
        list(MASTER_MODULE_ORDER) + list(CONFIGURATION_MODULE_ORDER) + ["demo"]
        if args.demo
        else list(MASTER_MODULE_ORDER) + list(CONFIGURATION_MODULE_ORDER)
        if args.all
        else list(MASTER_MODULE_ORDER)
        if args.master_data
        else list(CONFIGURATION_MODULE_ORDER)
        if args.configuration
        else [args.module]
    )
    return asyncio.run(run(selected, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
