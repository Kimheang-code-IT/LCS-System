from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, MetaData, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings
from app.core.exceptions import AccessDenied

# SQLite needs INTEGER PRIMARY KEY for autoincrement; PostgreSQL uses BIGINT.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class PKMixin:
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """Common archive markers for business rows that remain in their source table."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


_engine_options: dict = {
    "echo": False,
    "pool_pre_ping": True,
    "future": True,
}
if not settings.database_url.startswith("sqlite"):
    _engine_options.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle_seconds,
        pool_timeout=30,
    )

engine = create_async_engine(settings.database_url, **_engine_options)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One transaction per request, plus the centralized denial audit.

    Every refusal raises ``AccessDenied`` (HTTP 403) — from a route dependency, an
    inline master-data guard or a service-level check. This is the one place where
    the request's own session is still available, so the ``AUTHORIZATION_DENIED``
    event is written here, after rolling the failed transaction back and before the
    exception reaches the error handler. Audit failures never change the answer.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except AccessDenied as exc:
            await session.rollback()
            await record_denial(request, session, exc)
            raise
        except Exception:
            await session.rollback()
            raise


async def record_denial(request: Request, session: AsyncSession, exc: AccessDenied) -> None:
    """Write one ``AUTHORIZATION_DENIED`` event for a refused request.

    Shared with the test harness's session override so both exercise the same
    code path.

    Only an authenticated refusal is recorded: a 403 raised before a context exists
    (the Telegram webhook's own secret check) is a machine endpoint with its own
    monitoring, and writing one audit row per rejected public request would be an
    unbounded write path.
    """
    from app.modules.audit.service import write_audit

    context = getattr(request.state, "context", None)
    if context is None:
        return
    action = (exc.message or "").removeprefix("Missing permission: ").strip() or request.url.path
    try:
        await write_audit(
            session,
            context,
            event_type="AUTHORIZATION_DENIED",
            entity_type="permission",
            entity_id=0,
            action=action[:120],
            result="REJECTED",
            reason=exc.message or "Access denied.",
            metadata={"path": request.url.path, "method": request.method},
        )
        await session.commit()
    except Exception:  # noqa: BLE001 - a refusal must not become a server error
        await session.rollback()
