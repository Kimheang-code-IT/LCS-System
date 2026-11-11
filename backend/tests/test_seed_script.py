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


async def test_demo_seed_fills_tables_once_per_code(seeded, session_factory):
    from app.modules.master_data.models import BusinessParty, ComponentGroup, ComponentTab

    async with session_factory() as session:
        parties_before = await session.scalar(
            select(func.count()).select_from(BusinessParty).where(BusinessParty.deleted_at.is_(None))
        )
        first_inserted, first_skipped = await seed.seed_demo_parties(session)
        await session.commit()
        second = await seed.seed_demo_parties(session)
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
