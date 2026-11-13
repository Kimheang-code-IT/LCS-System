"""Build a dedicated, seeded SQLite database for mobile integration testing.

Never touches the PostgreSQL database the deployed backend uses. Run:

    backend/.venv/Scripts/python.exe backend/scripts/seed_mobile_test_db.py <sqlite-url>

Users created (all with the default password from tests/seed.py):
    admin / ops.pp / finance / sales  @example.test
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core import authorization  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402,F401  # registers every model on Base
from tests.seed import ensure_seed_data, seed_demo_data  # noqa: E402


async def main(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await ensure_seed_data(session)
        await seed_demo_data(session)
        await session.commit()
        await authorization.refresh(session)
    await engine.dispose()
    print(f"Seeded {database_url}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: seed_mobile_test_db.py <sqlite+aiosqlite:///path.db>")
        raise SystemExit(2)
    asyncio.run(main(sys.argv[1]))
