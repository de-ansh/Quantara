"""Chat with the research assistant from Slack: DM the bot, or @mention it in a channel; it answers in a thread.

Socket Mode, so Slack needs no public URL. Only Slack users listed in SLACK_USERS get answers, each as the
Quantara account they are linked to (their risk profile, holdings and own OpenAI key, if saved).
"""

import re
from typing import Any

from fastapi import HTTPException
from redis.asyncio import Redis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.dependencies import user_dict
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)

MAX_HISTORY = 30  # the chat endpoint's own limit
MENTION = re.compile(r"<@[A-Z0-9]+>\s*")
THINKING = "Looking that up…"


def linked_users(raw: str) -> dict[str, int]:
    """Parse "U0123ABCD:8,U0456EFGH:9" into {Slack user ID: Quantara user ID}; malformed pairs are skipped."""
    pairs: dict[str, int] = {}
    for part in raw.split(","):
        slack_id, _, user_id = part.strip().partition(":")
        if slack_id and user_id.strip().isdigit():
            pairs[slack_id] = int(user_id)
    return pairs


def to_slack(text: str) -> str:
    """The assistant writes Markdown **bold**; Slack's mrkdwn bold is a single *."""
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)


async def thread_history(client: Any, event: dict) -> list[Any]:
    """The conversation so far as chat messages: the whole thread when replying in one, else just this message."""
    from app.api.v1.chat import ChatMessage

    if event.get("thread_ts"):
        resp = await client.conversations_replies(channel=event["channel"], ts=event["thread_ts"], limit=100)
        raw = resp["messages"]
    else:
        raw = [event]
    messages = []
    for m in raw:
        text = MENTION.sub("", m.get("text") or "").strip()[:4000]
        if text and text != THINKING:
            messages.append(ChatMessage(role="assistant" if m.get("bot_id") else "user", content=text))
    return messages[-MAX_HISTORY:]


async def reply(user_id: int, history: list[Any]) -> str:
    """One assistant turn for a linked Quantara user, through the same code path as the web chat."""
    from app.api.v1.chat import ChatRequest, chat

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            return "The Quantara account linked to your Slack user is missing or deactivated."
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return (await chat(ChatRequest(messages=history), user_dict(user), db, redis)).reply
        finally:
            await redis.aclose()


async def answer_event(event: dict, client: Any) -> None:
    """Answer one Slack message in its thread, or say why not."""
    channel = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]
    user_id = linked_users(settings.slack_users).get(event.get("user", ""))
    if user_id is None:
        await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=(
            f"You aren't linked to a Quantara account. To use me, add your Slack ID `{event.get('user')}` "
            "to SLACK_USERS on the Quantara server."
        ))
        return
    history = await thread_history(client, event)  # before the placeholder, so the last message is the user's
    if not history or history[-1].role != "user":
        return
    placeholder = await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=THINKING)
    try:
        text = await reply(user_id, history)
    except HTTPException as e:  # rate limit, assistant unavailable: the same messages the web chat shows
        text = str(e.detail)
    except Exception:
        logger.exception("Slack bot reply failed")
        text = "Something went wrong answering that. Try again in a minute."
    await client.chat_update(channel=channel, ts=placeholder["ts"], text=to_slack(text))


def home_view(slack_user: str) -> dict:
    """The bot's Home tab in Slack: how to use it, and whether this Slack user is linked."""
    if slack_user in linked_users(settings.slack_users):
        status = "You're linked to your Quantara account. Ask away."
    else:
        status = (f"You aren't linked yet. Add `SLACK_USERS={slack_user}:<your Quantara user ID>` to the "
                  "Quantara server's .env and restart the backend.")
    text = ("*Quantara research assistant*\n"
            "Message me here, or @mention me in a channel, with a question about a stock or your holdings, "
            "for example _is TCS a buy?_ I answer in a thread; reply in it to follow up.\n\n"
            f"Your Slack ID: `{slack_user}`\n{status}")
    return {"type": "home", "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]}


async def run_slack_bot() -> None:
    """Hold the Socket Mode connection open; Slack delivers DMs and mentions over it."""
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp

    app = AsyncApp(token=settings.slack_bot_token)

    @app.event("app_mention")
    async def on_mention(event: dict, client: Any) -> None:
        await answer_event(event, client)

    @app.event("message")
    async def on_message(event: dict, client: Any) -> None:
        # Direct messages only (channels need a mention); skip edits, joins and the bot's own posts
        if event.get("channel_type") == "im" and not event.get("subtype") and not event.get("bot_id"):
            await answer_event(event, client)

    @app.event("app_home_opened")
    async def on_home(event: dict, client: Any) -> None:
        # Without a published view Slack's Home tab spins forever
        if event.get("tab") == "home":
            await client.views_publish(user_id=event["user"], view=home_view(event["user"]))

    logger.info("Slack bot connecting (Socket Mode)")
    await AsyncSocketModeHandler(app, settings.slack_app_token).start_async()
