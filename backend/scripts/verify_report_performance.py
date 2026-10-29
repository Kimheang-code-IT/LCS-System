"""Measure the report queries on a representative PostgreSQL dataset.

This is evidence, not a gate. It builds the real schema from the models, loads a
representative ledger, then runs the *same* statements ``ReportRepository``
serves with ``EXPLAIN (ANALYZE, BUFFERS)`` and reports wall-clock timings.

Usage (from ``backend/``)::

    python scripts/verify_report_performance.py \
        --url postgresql+asyncpg://postgres:perf@localhost:55432/lcsperf \
        --journals 100000

Each journal has two lines, so ``--journals 100000`` loads 200,000 ledger lines.
The dataset is spread over 24 months and 20 accounts, which is a stress size for
a single forwarder (a busy one posts a few thousand journals a year).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from datetime import date

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.main  # noqa: F401 - registers every model module
from app.core.database import Base
from app.modules.reports.repository import ReportRepository

ACCOUNTS = [f"{1000 + index * 10}" for index in range(20)]
OPENING = "2024-01-01"


async def seed(session: AsyncSession, journals: int, months: int) -> None:
    await session.execute(text("DELETE FROM journal_entry_lines"))
    await session.execute(text("DELETE FROM journal_entries"))
    await session.execute(text("DELETE FROM chart_of_accounts"))
    await session.execute(text("DELETE FROM business_parties"))
    await session.execute(text("DELETE FROM financial_documents"))
    await session.execute(text("DELETE FROM service_orders"))
    await session.execute(text("DELETE FROM financial_accounts"))
    await session.execute(text("DELETE FROM accounting_periods"))

    rows = []
    for index in range(24):
        month = index + 1
        year = 2024 + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        start = date(year, month, 1)
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        rows.append({"y": year, "m": month, "s": start, "e": end.fromordinal(end.toordinal() - 1)})
    await session.execute(
        text(
            "INSERT INTO accounting_periods (period_year, period_month, start_date, end_date, status) "
            "VALUES (:y, :m, :s, :e, 'OPEN')"
        ),
        rows,
    )

    accounts = [{"code": code, "name": f"Perf account {code}"} for code in ACCOUNTS]
    await session.execute(
        text(
            "INSERT INTO chart_of_accounts (account_code, account_name, account_type, normal_balance, is_postable, status) "
            "VALUES (:code, :name, 'ASSET', 'DEBIT', true, 'ACTIVE')"
        ),
        accounts,
    )
    await session.execute(
        text(
            "INSERT INTO business_parties (party_code, display_name, legal_name, roles, status) "
            "SELECT 'PERF-P' || g, 'Perf party ' || g, 'Perf party ' || g, '[]'::json, 'ACTIVE' "
            "FROM generate_series(1, 200) g"
        )
    )

    await session.execute(
        text(
            "INSERT INTO journal_entries (entry_no, entry_type, entry_date, posting_date, status, "
            "debit_total, credit_total, data) "
            "SELECT 'PERF-' || g, 'MANUAL', "
            f"DATE '{OPENING}' + ((g % {months * 30})::int), DATE '{OPENING}' + ((g % {months * 30})::int), "
            "'POSTED', 100, 100, '{}'::json "
            "FROM generate_series(1, :count) g"
        ),
        {"count": journals},
    )
    # Two lines per journal, alternating accounts so several accounts carry data.
    await session.execute(
        text(
            "INSERT INTO journal_entry_lines (journal_entry_id, line_no, account_id, description, "
            "debit_amount, credit_amount, currency_code, exchange_rate, base_debit_amount, base_credit_amount) "
            "SELECT je.id, 1, a.id, 'Perf debit', 100, 0, 'USD', 1, 100, 0 "
            "FROM journal_entries je "
            "JOIN chart_of_accounts a ON a.account_code = ((1000 + 10 * (je.id % 20))::int)::text"
        )
    )
    await session.execute(
        text(
            "INSERT INTO journal_entry_lines (journal_entry_id, line_no, account_id, description, "
            "debit_amount, credit_amount, currency_code, exchange_rate, base_debit_amount, base_credit_amount) "
            "SELECT je.id, 2, a.id, 'Perf credit', 0, 100, 'USD', 1, 0, 100 "
            "FROM journal_entries je "
            "JOIN chart_of_accounts a ON a.account_code = ((1000 + 10 * ((je.id + 1) % 20))::int)::text"
        )
    )
    await session.commit()
    await session.execute(text("ANALYZE"))


async def explain(session: AsyncSession, label: str, stmt) -> dict:
    compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    sql = f"EXPLAIN (ANALYZE, BUFFERS) {compiled}"
    plan = (await session.execute(text(sql))).scalars().all()
    timings = []
    for _ in range(3):
        start = time.perf_counter()
        await session.execute(stmt)
        timings.append((time.perf_counter() - start) * 1000)
    execution = next((line for line in plan if line.strip().startswith("Execution Time")), "?")
    print(f"\n=== {label}")
    print(f"    best of 3: {min(timings):.1f} ms   median: {statistics.median(timings):.1f} ms")
    print(f"    {execution.strip()}")
    for line in plan:
        stripped = line.rstrip()
        if any(token in stripped for token in ("Scan", "Sort", "Aggregate", "WindowAgg", "Hash", "Index", "Limit")):
            print(f"    {stripped[:150]}")
    return {"label": label, "best_ms": round(min(timings), 1), "plan": plan}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="postgresql+asyncpg://postgres:perf@localhost:55432/lcsperf")
    parser.add_argument("--journals", type=int, default=100_000)
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--keep", action="store_true", help="keep the dataset after measuring")
    args = parser.parse_args()

    engine = create_async_engine(args.url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        started = time.perf_counter()
        await seed(session, args.journals, args.months)
        loaded = time.perf_counter() - started
        counts = (
            await session.execute(
                text("SELECT (SELECT count(*) FROM journal_entries), (SELECT count(*) FROM journal_entry_lines)")
            )
        ).one()
        print(f"dataset: {counts[0]:,} journals / {counts[1]:,} lines loaded in {loaded:.1f}s")

        repository = ReportRepository(session)
        period = {"from_date": date(2024, 7, 1), "to_date": date(2025, 6, 30)}

        results = []
        results.append(
            await explain(
                session,
                "trial balance, 12 months, account range",
                repository._trial_balance_statement(
                    from_date=period["from_date"],
                    to_date=period["to_date"],
                    account_from="1000",
                    account_to="1199",
                ),
            )
        )
        results.append(
            await explain(
                session,
                "trial balance, all time, every account",
                repository._trial_balance_statement(from_date=None, to_date=None),
            )
        )
        results.append(
            await explain(
                session,
                "general ledger page 1 (50 rows, one account, 12 months)",
                repository._general_ledger_statement(
                    from_date=period["from_date"],
                    to_date=period["to_date"],
                    account_code=ACCOUNTS[0],
                ).limit(50),
            )
        )
        results.append(
            await explain(
                session,
                "general ledger page 1, no account filter (all accounts, 12 months)",
                repository._general_ledger_statement(
                    from_date=period["from_date"],
                    to_date=period["to_date"],
                ).limit(50),
            )
        )
        results.append(
            await explain(
                session,
                "general ledger deep page (one account, offset 4,000)",
                repository._general_ledger_statement(
                    from_date=period["from_date"],
                    to_date=period["to_date"],
                    account_code=ACCOUNTS[0],
                ).offset(4_000).limit(50),
            )
        )
        results.append(
            await explain(
                session,
                "general ledger opening balance",
                repository._opening_balances_statement(
                    from_date=period["from_date"], account_code=ACCOUNTS[0]
                ),
            )
        )

        # The export path: every matching line, streamed, never materialised.
        for label, kwargs in (
            ("export stream, one account, 12 months", {"account_code": ACCOUNTS[0], **period}),
            ("export stream, all accounts, 12 months", dict(period)),
        ):
            start = time.perf_counter()
            streamed = 0
            async for _row in repository.general_ledger_stream(**kwargs):
                streamed += 1
            export_seconds = time.perf_counter() - start
            print(f"\n=== {label}\n    {streamed:,} rows in {export_seconds:.2f}s")
            results.append({"label": label, "rows": streamed, "seconds": round(export_seconds, 2)})

        print("\n=== summary")
        for entry in results:
            print(f"    {entry['label']}: {entry.get('best_ms', entry.get('seconds'))}")

    if not args.keep:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
