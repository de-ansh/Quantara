"""Test configuration and fixtures."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app as fastapi_app

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://quantara:quantara@localhost:5432/quantara_test"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    session = async_session()
    # Seed default test user
    from app.core.security import get_password_hash
    from app.models.user import User

    test_user = User(email="test@quantara.com", hashed_password=get_password_hash("password"))
    session.add(test_user)
    await session.commit()

    try:
        yield session
    finally:
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client."""
    from redis.asyncio import Redis

    from app.core.config import settings

    # Rate-limit counters persist in Redis across tests; start each test clean.
    redis = Redis.from_url(settings.redis_url)
    try:
        async for key in redis.scan_iter("ratelimit:*"):
            await redis.delete(key)
    except Exception:
        pass
    finally:
        await redis.close()

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    import httpx

    async with AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
