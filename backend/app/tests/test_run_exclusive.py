"""run_exclusive must release its advisory lock, even when the job uses the pool heavily."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import database
from app.tests.conftest import TEST_DATABASE_URL

LOCK = 7_309_999


async def _lock_free(engine) -> bool:
    async with engine.connect() as conn:
        got = (await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK})).scalar()
        if got:
            await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK})
        return bool(got)


@pytest.mark.asyncio
async def test_lock_held_during_job_and_released_after(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=3, max_overflow=0)
    monkeypatch.setattr(database, "AsyncSessionLocal", async_sessionmaker(engine))
    seen = {}

    async def noop() -> None:
        pass

    async def job() -> None:
        seen["free_during"] = await _lock_free(engine)
        seen["second_ran"] = await database.run_exclusive(LOCK, noop)

    try:
        assert await database.run_exclusive(LOCK, job)
        assert seen == {"free_during": False, "second_ran": False}
        # Every pooled connection must be lock-free afterwards, not just the next one handed out
        for _ in range(3):
            assert await _lock_free(engine)
        assert await database.run_exclusive(LOCK, job)  # and the next pass runs
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sleep_wall_ends_when_the_wall_clock_jumps(monkeypatch):
    """A host sleep stops the monotonic clock but not the wall clock; the job must run on wake."""
    import asyncio

    from app.core import clock

    now = {"t": 1_000.0}
    naps: list[float] = []

    async def nap(seconds):
        naps.append(seconds)
        now["t"] += 3_600 if len(naps) == 1 else seconds  # the first nap spans an hour of host sleep

    monkeypatch.setattr("time.time", lambda: now["t"])
    monkeypatch.setattr(asyncio, "sleep", nap)
    await clock.sleep_wall(900)
    assert naps == [60.0]
