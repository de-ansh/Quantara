"""Push notifications to Slack: DMs from the Quantara bot to linked users, else an incoming webhook (no-op when neither is set)."""

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def linked_users(raw: str) -> dict[str, int]:
    """Parse "U0123ABCD:8,U0456EFGH:9" into {Slack user ID: Quantara user ID}; malformed pairs are skipped."""
    pairs: dict[str, int] = {}
    for part in raw.split(","):
        slack_id, _, user_id = part.strip().partition(":")
        if slack_id and user_id.strip().isdigit():
            pairs[slack_id] = int(user_id)
    return pairs


def _bot_recipients(user_id: int | None = None) -> list[str]:
    if not settings.slack_bot_token:
        return []
    return [s for s, u in linked_users(settings.slack_users).items() if user_id is None or u == user_id]


def slack_configured() -> bool:
    return bool(_bot_recipients() or settings.slack_webhook_url)


async def notify_slack(text: str, user_id: int | None = None) -> bool:
    """Send `text` to Slack; returns whether it got there. Failures are logged, never raised.

    The bot is preferred: a webhook dies silently when the Slack app is reinstalled. With `user_id`, only that
    Quantara user's linked Slack accounts get it, and never the shared webhook channel.
    """
    recipients = _bot_recipients(user_id)
    if user_id is not None and not recipients:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if recipients:
                ok = True
                for slack_id in recipients:  # a user ID as the channel posts in the bot's DM with that user
                    resp = await client.post(
                        "https://slack.com/api/chat.postMessage",
                        headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                        json={"channel": slack_id, "text": text},
                    )
                    if not resp.json().get("ok"):
                        logger.warning(f"Slack DM failed: {resp.json().get('error')}")
                        ok = False
                return ok
            if not settings.slack_webhook_url:
                return False
            resp = await client.post(settings.slack_webhook_url, json={"text": text})
            if resp.status_code != 200:
                logger.warning(f"Slack webhook failed: {resp.status_code} {resp.text[:100]}")
                return False
            return True
    except Exception as e:  # type only: httpx messages include the webhook URL, which is a secret
        logger.warning(f"Slack notification failed: {type(e).__name__}")
        return False
