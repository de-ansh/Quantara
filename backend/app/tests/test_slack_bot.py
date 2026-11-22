"""Slack bot: only linked users get answers, threads carry the conversation, replies go through the web chat."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User
from app.services import slack_bot


class FakeSlack:
    """Records posts and updates; a thread's replies come from `thread`."""

    def __init__(self, thread=None):
        self.thread = thread or []
        self.posts: list[dict] = []
        self.updates: list[dict] = []

    async def conversations_replies(self, channel, ts, limit):
        return {"messages": self.thread}

    async def chat_postMessage(self, **kw):
        self.posts.append(kw)
        return {"ts": "999.1"}

    async def chat_update(self, **kw):
        self.updates.append(kw)


def test_linked_users_skips_malformed_pairs():
    assert slack_bot.linked_users(" U1:8, U2:x, :3, U3 ,U4:9") == {"U1": 8, "U4": 9}
    assert slack_bot.linked_users("") == {}


def test_bold_becomes_slack_bold():
    assert slack_bot.to_slack("**Hold** at **₹3,900**") == "*Hold* at *₹3,900*"


def test_home_tab_shows_the_slack_id_and_whether_it_is_linked(monkeypatch):
    monkeypatch.setattr(slack_bot.settings, "slack_users", "U1:8")
    linked = slack_bot.home_view("U1")["blocks"][0]["text"]["text"]
    unlinked = slack_bot.home_view("U2")["blocks"][0]["text"]["text"]
    assert "`U1`" in linked and "You're linked" in linked
    assert "SLACK_USERS=U2:" in unlinked


@pytest.mark.asyncio
async def test_unlinked_slack_user_is_refused_without_an_answer(monkeypatch):
    monkeypatch.setattr(slack_bot.settings, "slack_users", "U1:8")

    async def never(*a):
        raise AssertionError("must not reach the assistant")

    monkeypatch.setattr(slack_bot, "reply", never)
    client = FakeSlack()
    await slack_bot.answer_event({"channel": "D1", "ts": "1.0", "user": "U2", "text": "TCS?"}, client)
    assert "U2" in client.posts[0]["text"] and "SLACK_USERS" in client.posts[0]["text"]
    assert client.posts[0]["thread_ts"] == "1.0" and not client.updates


@pytest.mark.asyncio
async def test_thread_reply_sends_the_whole_thread_and_updates_the_placeholder(monkeypatch):
    monkeypatch.setattr(slack_bot.settings, "slack_users", "U1:8")
    seen = {}

    async def fake_reply(user_id, history):
        seen["user_id"], seen["history"] = user_id, [(m.role, m.content) for m in history]
        return "**Hold**: fairly priced."

    monkeypatch.setattr(slack_bot, "reply", fake_reply)
    client = FakeSlack(thread=[
        {"user": "U1", "text": "<@UBOT> is TCS a buy?", "ts": "1.0"},
        {"bot_id": "B1", "text": "*Hold*, for now.", "ts": "1.1"},
        {"user": "U1", "text": "and Infosys?", "ts": "1.2"},
    ])
    await slack_bot.answer_event({"channel": "C1", "ts": "1.2", "thread_ts": "1.0", "user": "U1", "text": "and Infosys?"}, client)
    assert seen == {"user_id": 8, "history": [
        ("user", "is TCS a buy?"), ("assistant", "*Hold*, for now."), ("user", "and Infosys?"),
    ]}
    assert client.posts == [{"channel": "C1", "thread_ts": "1.0", "text": slack_bot.THINKING}]
    assert client.updates == [{"channel": "C1", "ts": "999.1", "text": "*Hold*: fairly priced."}]


@pytest.mark.asyncio
async def test_rate_limit_message_reaches_slack(monkeypatch):
    monkeypatch.setattr(slack_bot.settings, "slack_users", "U1:8")

    async def limited(*a):
        raise HTTPException(429, "Too many requests, try again later")

    monkeypatch.setattr(slack_bot, "reply", limited)
    client = FakeSlack()
    await slack_bot.answer_event({"channel": "D1", "ts": "1.0", "user": "U1", "text": "TCS?"}, client)
    assert client.updates[0]["text"] == "Too many requests, try again later"


@pytest.mark.asyncio
async def test_reply_answers_as_the_linked_user_and_refuses_deactivated(db_session, monkeypatch):
    from app.api.v1 import chat as chat_api
    from app.api.v1.chat import ChatMessage

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr(slack_bot, "AsyncSessionLocal", session)
    user = (await db_session.execute(select(User))).scalars().first()
    seen = {}

    async def fake_chat(request, current_user, db, redis):
        seen["email"] = current_user["email"]
        return SimpleNamespace(reply="Hold.")

    monkeypatch.setattr(chat_api, "chat", fake_chat)
    history = [ChatMessage(role="user", content="TCS?")]
    assert await slack_bot.reply(user.id, history) == "Hold."
    assert seen["email"] == user.email

    user.is_active = False
    await db_session.commit()
    assert "deactivated" in await slack_bot.reply(user.id, history)
