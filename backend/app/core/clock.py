"""Time helpers."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current UTC time as a naive datetime, matching the timezone-naive DB columns.

    Replaces `datetime.utcnow()`, which is deprecated from Python 3.12.
    """
    return datetime.now(UTC).replace(tzinfo=None)
