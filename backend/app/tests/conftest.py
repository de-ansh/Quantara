"""Test configuration and fixtures."""

import ipaddress
import socket
import zlib
from collections.abc import AsyncGenerator, Generator

import httpx
import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
import yfinance
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app as fastapi_app

_real_connect = socket.socket.connect
_network_attempts: list[str] = []


def _local_only_connect(self: socket.socket, address: object) -> None:
    """Allow Postgres/Redis on loopback or private networks; fail anything public."""
    host = address[0] if isinstance(address, tuple) else None
    if host is not None:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip is None or not (ip.is_loopback or ip.is_private):
            _network_attempts.append(str(address))
            raise RuntimeError(f"Test attempted a network call to {address}; mock it instead")
    _real_connect(self, address)


def _fake_history(ticker: str, days: int = 260) -> pd.DataFrame:
    """Deterministic per-ticker daily OHLCV ending today (a seeded random walk)."""
    rng = np.random.default_rng(zlib.crc32(ticker.encode()))
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.015, days))
    index = pd.bdate_range(end=pd.Timestamp.now('UTC').normalize().tz_localize(None), periods=days)
    return pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
         "Volume": 1_000_000.0, "Dividends": 0.0},
        index=index,
    )


class FakeYahooTicker:
    """Stands in for yfinance.Ticker: synthetic history, plausible `info`."""

    def __init__(self, ticker: str, *args: object, **kwargs: object) -> None:
        self.ticker = ticker.upper()
        last = float(_fake_history(self.ticker)["Close"].iloc[-1])
        self.info = {
            "longName": f"{self.ticker} Test Corp", "sector": "Technology", "marketCap": 1e12,
            "trailingPE": 25.0, "priceToBook": 3.5, "beta": 1.1, "currentPrice": last,
        }

    def history(self, period: str = "1y", start: object = None, end: object = None, **kwargs: object) -> pd.DataFrame:
        days = {"5d": 5, "1mo": 22, "6mo": 126, "1y": 260, "5y": 1300}.get(period, 260)
        return _fake_history(self.ticker, days if start is None else 260)


def _fake_download(tickers: str | list[str], period: str = "1y", **kwargs: object) -> pd.DataFrame:
    """yfinance.download shape: (field, ticker) MultiIndex columns."""
    names = [tickers] if isinstance(tickers, str) else list(tickers)
    frames = {t: FakeYahooTicker(t).history(period=period) for t in names}
    return pd.concat(frames, axis=1).swaplevel(axis=1).sort_index(axis=1)


async def _sec_unavailable(self: object, request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, request=request)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Tests must not depend on Yahoo, SEC or OpenAI being reachable."""
    import curl_cffi.requests

    from app.core.config import settings

    def _blocked(*args: object, **kwargs: object) -> None:
        _network_attempts.append(f"curl_cffi {args[1:3]}")
        raise RuntimeError("Test attempted a Yahoo (curl_cffi) request; mock it instead")

    monkeypatch.setattr(socket.socket, "connect", _local_only_connect)
    # Deterministic market data instead of Yahoo; SEC behaves as unavailable
    monkeypatch.setattr(yfinance, "Ticker", FakeYahooTicker)
    monkeypatch.setattr(yfinance, "download", _fake_download)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _sec_unavailable)
    # yfinance talks through curl_cffi (libcurl), which bypasses Python sockets
    monkeypatch.setattr(curl_cffi.requests.Session, "request", _blocked)
    # A real key in .env would switch embeddings and LLM calls to OpenAI
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-test")
    _network_attempts.clear()
    yield
    # Code under test often swallows the error, so fail on the attempt itself
    assert not _network_attempts, f"Test attempted network calls: {_network_attempts[:3]}"


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
        await redis.aclose()

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    import httpx

    async with AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
