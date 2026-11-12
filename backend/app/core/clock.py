"""Time helpers."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current UTC time as a naive datetime, matching the timezone-naive DB columns.

    Replaces `datetime.utcnow()`, which is deprecated from Python 3.12.
    """
    return datetime.now(UTC).replace(tzinfo=None)


WAKE_CHECK_SECONDS = 60.0


async def sleep_wall(seconds: float) -> None:
    """Sleep until `seconds` of wall-clock time have passed.

    asyncio.sleep counts the monotonic clock, which stops while the host sleeps (a laptop running
    Docker), so a 15-minute wait could last hours. Short naps against the wall clock catch up on wake.
    """
    import asyncio
    import time

    deadline = time.time() + seconds
    while (left := deadline - time.time()) > 0:
        await asyncio.sleep(min(left, WAKE_CHECK_SECONDS))
