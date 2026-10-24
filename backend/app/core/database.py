"""Database connection and session management."""

from collections.abc import AsyncGenerator, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def run_exclusive(lock_id: int, job: Callable[[], Awaitable[None]]) -> bool:
    """Run `job` unless another worker holds Postgres advisory lock `lock_id`; returns whether it ran.

    Session-level lock on a dedicated connection, so Postgres frees it if the worker dies.
    """
    async with AsyncSessionLocal() as lock_session:
        acquired = (
            await lock_session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_id})
        ).scalar()
        # Session-level locks outlive the transaction; end it so the connection isn't
        # left "idle in transaction" for the whole job.
        await lock_session.commit()
        if not acquired:
            return False
        try:
            await job()
        finally:
            await lock_session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_id})
            await lock_session.commit()
    return True
