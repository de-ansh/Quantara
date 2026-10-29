"""Push notifications to a Slack incoming webhook (optional; no-op when unset)."""

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def notify_slack(text: str) -> None:
    """Post `text` to SLACK_WEBHOOK_URL. Failures are logged, never raised."""
    if not settings.slack_webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.slack_webhook_url, json={"text": text})
            resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")
