from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.models import DocumentSequence

DEFAULT_PREFIXES: dict[str, str] = {
    "QUOTATION": "Q",
    "SERVICE_ORDER": "SO",
    "SERVICE_CHARGE": "SC",
    "CUSTOMER_INVOICE": "INV",
    "SUPPLIER_BILL": "BILL",
    "CUSTOMER_RECEIPT": "REC",
    "SUPPLIER_PAYMENT": "PAY",
    "JOURNAL": "JE",
}


async def allocate_number(
    session: AsyncSession,
    document_type: str,
    *,
    prefix: str | None = None,
    year: int | None = None,
) -> str:
    period_year = year or datetime.now(UTC).year
    sequence = (
        await session.execute(
            select(DocumentSequence)
            .where(
                DocumentSequence.document_type == document_type,
                DocumentSequence.period_year == period_year,
            )
            .with_for_update()
        )
    ).scalars().first()
    if sequence is None:
        sequence = DocumentSequence(
            document_type=document_type,
            period_year=period_year,
            prefix=prefix or DEFAULT_PREFIXES.get(document_type, document_type[:2]),
            last_value=0,
            padding_length=6,
        )
        session.add(sequence)
        await session.flush()
    sequence.last_value += 1
    number = f"{sequence.prefix}{period_year}-{str(sequence.last_value).zfill(sequence.padding_length)}"
    await session.flush()
    return number


async def preview_number(session: AsyncSession, document_type: str, year: int | None = None) -> str:
    period_year = year or datetime.now(UTC).year
    sequence = (
        await session.execute(
            select(DocumentSequence).where(
                DocumentSequence.document_type == document_type,
                DocumentSequence.period_year == period_year,
            )
        )
    ).scalars().first()
    prefix = sequence.prefix if sequence else DEFAULT_PREFIXES.get(document_type, document_type[:2])
    padding = sequence.padding_length if sequence else 6
    last = sequence.last_value if sequence else 0
    return f"{prefix}{period_year}-{str(last + 1).zfill(padding)}"
