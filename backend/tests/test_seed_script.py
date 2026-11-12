"""The explicit seed command: demo rows fill every table and never duplicate.

Nothing seeds Master Data/Configuration automatically any more, so the demo
top-up (``python scripts/seed.py --demo``) must be both complete and
insert-missing only. The script is a file, not a package: load it the way the
CLI does, with its directory importable.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from sqlalchemy import func, select

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load_seed_script():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("lcs_seed_script", SCRIPTS / "seed.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


seed = _load_seed_script()


async def test_sequences_and_settings_seed_once(seeded, session_factory):
    """The rows `/auth/setup` no longer creates are covered by the seed command."""
    from app.core.sequences import DEFAULT_PREFIXES
    from app.modules.finance.models import DocumentSequence
    from app.modules.settings.models import AppSetting
    from app.modules.settings.service import APP_INFO_KEY

    async with session_factory() as session:
        await seed.seed_document_sequences(session)
        await session.commit()
        replay_sequences = await seed.seed_document_sequences(session)
        await session.commit()
        await seed.seed_app_settings(session)
        await session.commit()
        replay_settings = await seed.seed_app_settings(session)
        await session.commit()
        sequences = set((await session.execute(select(DocumentSequence.document_type))).scalars().all())
        info = await session.scalar(select(AppSetting.setting_key).where(AppSetting.setting_key == APP_INFO_KEY))

    assert sequences >= set(DEFAULT_PREFIXES)
    assert replay_sequences[0] == 0
    assert info == APP_INFO_KEY
    assert replay_settings[0] == 0


def test_business_parties_is_an_explicit_module():
    """Sample parties are opt-in, so `--all` stays pure reference data."""
    args = seed.parse_args(["--module", "business-parties"])
    assert args.module == "business-parties"


async def test_accounting_seed_bootstraps_complete_books(seeded, session_factory):
    """Chart, bank/cash accounts and one posting rule per document type."""
    from app.modules.finance.models import ChartOfAccount, FinancialAccount, PostingRule

    async with session_factory() as session:
        coa = await seed.seed_chart_of_accounts(session)
        await session.commit()
        financial = await seed.seed_financial_accounts(session)
        await session.commit()
        rules = await seed.seed_posting_rules(session)
        await session.commit()
        replay = await seed.seed_accounting(session)
        await session.commit()

        accounts = {
            row.account_code: row
            for row in (await session.execute(select(ChartOfAccount))).scalars().all()
        }
        rule_rows = (await session.execute(select(PostingRule))).scalars().all()
        financial_rows = (await session.execute(select(FinancialAccount))).scalars().all()

    # The test fixture already seeds a small chart, so count the planned rows
    # rather than assuming an empty database.
    assert coa[0] + coa[1] == len(seed.CHART_OF_ACCOUNTS)
    assert financial[0] + financial[1] == len(seed.FINANCIAL_ACCOUNTS)
    assert rules[0] + rules[1] == len(seed.POSTING_RULES)
    assert replay[0] == 0
    assert replay[1] == len(seed.CHART_OF_ACCOUNTS) + len(seed.FINANCIAL_ACCOUNTS) + len(seed.POSTING_RULES)

    assert {row["account_code"] for row in seed.CHART_OF_ACCOUNTS} <= set(accounts)

    # Every posting rule points at active, postable accounts.
    for rule in rule_rows:
        for account_id in (rule.debit_account_id, rule.credit_account_id, rule.tax_account_id):
            if account_id is None:
                continue
            account = next(row for row in accounts.values() if row.id == account_id)
            assert account.is_postable and account.status == "ACTIVE"

    # The chart is hierarchical and the settlement accounts link to it.
    assert accounts["1300"].parent_account_id == accounts["1000"].id
    assert accounts["1100"].is_postable and accounts["1100"].normal_balance == "DEBIT"
    assert {row.currency_code for row in financial_rows} == {"USD"}
    assert {row.account_type for row in financial_rows} == {"BANK", "CASH"}


async def test_demo_seed_fills_tables_once_per_code(seeded, session_factory):
    from app.modules.master_data.models import BusinessParty, ComponentGroup, ComponentTab

    async with session_factory() as session:
        parties_before = await session.scalar(
            select(func.count()).select_from(BusinessParty).where(BusinessParty.deleted_at.is_(None))
        )
        first_inserted, first_skipped = await seed.seed_business_parties(session)
        await session.commit()
        second = await seed.seed_business_parties(session)
        await session.commit()
        parties_after = await session.scalar(
            select(func.count()).select_from(BusinessParty).where(BusinessParty.deleted_at.is_(None))
        )

    assert first_inserted == 5
    assert first_skipped == 0
    assert second == (0, 5)
    assert parties_after == parties_before + 5

    async with session_factory() as session:
        groups_before = await session.scalar(select(func.count()).select_from(ComponentGroup))
        tabs_before = await session.scalar(select(func.count()).select_from(ComponentTab))
        inserted, _ = await seed.seed_demo_configuration(session)
        await session.commit()
        replay = await seed.seed_demo_configuration(session)
        await session.commit()
        groups_after = await session.scalar(select(func.count()).select_from(ComponentGroup))
        tabs_after = await session.scalar(select(func.count()).select_from(ComponentTab))

    # Two demo groups and four demo tabs always; links are added where the
    # attribute/group vocabulary exists (the demo run seeds it first).
    assert inserted >= 6
    assert replay[0] == 0
    assert groups_after == groups_before + 2
    assert tabs_after == tabs_before + 4
