"""Test configuration and fixtures."""
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app as fastapi_app
from app.core.database import Base, get_db
import app.models  # Ensure all models are registered on Base.metadata

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
        await conn.run_sync(Base.metadata.create_all)
    
    session = async_session()
    # Seed default test user
    from app.models.user import User
    from app.core.security import get_password_hash
    test_user = User(
        email="test@quantara.com",
        hashed_password=get_password_hash("password")
    )
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
    async def override_get_db():
        yield db_session
    
    fastapi_app.dependency_overrides[get_db] = override_get_db
    
    import httpx
    async with AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac
    
    fastapi_app.dependency_overrides.clear()
